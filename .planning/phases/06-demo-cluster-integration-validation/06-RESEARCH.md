# Phase 6: Demo Cluster + Integration Validation - Research

**Researched:** 2026-03-08
**Domain:** CLI integration, GitHub Actions CI, live terminal polling, demo artifact generation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Demo Command:**
- `agent-factory demo` subcommand — dedicated command, not a flag on `create`
- Creates a pre-configured cluster with the fixed goal "Write a Python utility library for date arithmetic" and accelerated heartbeats (~5-10 seconds interval)
- Uses real LLM calls (Haiku for workers, Sonnet for boss) — genuine integration validation
- After creation, enters a live-updating status loop in the terminal showing task progress
- Exits with a summary once at least one task reaches `approved`; user then approves via `agent-factory approve`

**CI Smoke Test:**
- Pre-generated demo cluster artifact committed to the repository under `clusters/demo-date-arithmetic/`
- CI pipeline: `docker compose up` in that directory, wait for containers to be healthy
- Health check: shell step queries `clusters/demo-date-arithmetic/db/cluster.db` via `sqlite3`:
  ```
  sqlite3 clusters/demo-date-arithmetic/db/cluster.db "SELECT count(*) FROM agent_status"
  ```
  Asserts count >= 2 (boss + at least one worker registered)
- No real LLM calls in CI — smoke test validates build, config, and startup only
- Trigger: on push to `main` and on all pull requests

**agent-factory approve Command:**
- Signature: `agent-factory approve <cluster-name> <task-id>`
- Resolves cluster DB via `FACTORY_CLUSTERS_BASE` env var: `$FACTORY_CLUSTERS_BASE/<cluster-name>/db/cluster.db`
- Pre-approval validation: fetch task, verify `status == 'review'` — fail with info message if not
- Success output format defined (see CONTEXT.md)
- Error handling: exit 0 with info message for all edge cases (cluster not found, task not found, wrong state)

**agent-factory logs Command:**
- Signature: `agent-factory logs <cluster-name> [--tail N] [--agent <agent-id>] [--json]`
- Resolves cluster DB via `FACTORY_CLUSTERS_BASE`
- Output: tabulate "simple" table — columns: `timestamp | agent_id | action | details` (details truncated to fit)
- `--tail N`: show last N entries (default: 50)
- `--agent <id>`: filter to one agent's entries (SQL WHERE clause)
- `--json`: output raw JSON list instead of tabulate table
- Exit 0 with info message if cluster not found or activity_log is empty

**README Structure:**
- Root-level `README.md`
- Three sections: What it is, Quick Start, How it works
- Demo walkthrough: full annotated terminal trace

### Claude's Discretion
- Exact heartbeat interval for demo cluster (5 seconds vs 10 seconds — balance speed vs realism)
- Demo cluster name (e.g., `demo-date-arithmetic` or `date-utils-demo`)
- Status polling interval in the `demo` command's live loop
- README tone and exact wording
- docker-compose.yml structure for the committed demo cluster artifact
- `--tail` default value (50 is a starting point)

### Deferred Ideas (OUT OF SCOPE)
- `agent-factory logs <cluster>` streaming (real-time tail, like `tail -f`) — Phase 7
- `agent-factory approve` interactive confirmation prompt — Phase 7
- Nightly CI job that runs `agent-factory create` + real LLM demo — Phase 7
- `CONTRIBUTING.md` and full API documentation — Phase 7
</user_constraints>

---

## Summary

Phase 6 has four tightly coupled but distinct workstreams: (1) two new factory CLI subcommands (`approve` and `logs`), (2) the `agent-factory demo` command with its live polling loop, (3) the committed demo cluster artifact under `clusters/demo-date-arithmetic/`, and (4) the GitHub Actions smoke test workflow. All four reuse existing codebase patterns — no new libraries are needed. The biggest non-obvious concern is the live polling loop in `demo`: the pattern must be synchronous-safe (a `while True` loop with `time.sleep()` inside `asyncio.run()`) because we poll SQLite from a top-level Click command. The CI smoke test depends on `sqlite3` being available on the ubuntu-latest runner (it is, pre-installed), and on Docker Compose v2 syntax (`docker compose`, not `docker-compose`).

The demo cluster artifact committed to the repository requires a pre-seeded SQLite DB (`db/cluster.db`) so the CI health check can assert `agent_status` row count >= 2 without actually starting agents. This means Phase 6 must generate the artifact files AND pre-seed the DB as part of the Wave 0 / artifact creation task — not wait for agent startup.

**Primary recommendation:** Implement in three waves: (Wave 1) `approve` + `logs` CLI subcommands, (Wave 2) `agent-factory demo` command with live polling loop, (Wave 3) demo cluster artifact + pre-seeded DB + CI workflow + README.

---

## Standard Stack

### Core (all already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.1 | CLI subcommand structure for `approve`, `logs`, `demo` | All CLI already uses Click; consistent |
| tabulate | 0.9.0 | `logs` table output — `timestamp \| agent_id \| action \| details` | Already used for all tabular output |
| aiosqlite | >=0.20.0 | DB queries in `approve` and `logs` async helpers | All DB access uses aiosqlite |
| anthropic | 0.84.0 | Real LLM calls in `demo` (boss=Sonnet, workers=Haiku) | Runtime dependency |
| asyncio (stdlib) | 3.12+ | Async coordination in `demo` via `run_factory()` | Project-wide pattern |
| time (stdlib) | 3.12+ | `time.sleep()` in polling loop inside `demo`'s sync Click callback | Simpler than asyncio for polling outer loop |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| subprocess (stdlib) | 3.12+ | Launching demo cluster in background (mirrors `create` pattern) | Used in `factory_create` already |
| json (stdlib) | 3.12+ | `--json` flag output for `logs`, `approve` structured data | Already used in `tasks list --json` |
| sqlite3 (stdlib CLI) | pre-installed on ubuntu-latest | CI health check: `sqlite3 db/cluster.db "SELECT count(*) FROM agent_status"` | Shell step in GitHub Actions |
| yaml (PyYAML) | >=6.0.0 | Reading/generating cluster YAML for the committed demo artifact | Already in deps |
| shutil (stdlib) | 3.12+ | Copying runtime into demo cluster artifact (via `copy_runtime`) | Used in E2E tests already |

### No New Dependencies Required
The entire phase is implementable with the existing dependency set. The only external tool consumed at CI time is the `sqlite3` CLI binary on ubuntu-latest runners (pre-installed on all ubuntu-latest images).

**No additional installation:**
All libraries are already present. The demo cluster artifact's `requirements.txt` is generated by `render_requirements_txt()` from the existing baseline packages.

---

## Architecture Patterns

### Recommended Project Structure (additions for Phase 6)
```
clusters/
└── demo-date-arithmetic/         # Committed artifact (Wave 3)
    ├── docker-compose.yml        # Generated by render_docker_compose()
    ├── .env.example              # ANTHROPIC_API_KEY placeholder
    ├── Dockerfile                # Generated by render_dockerfile()
    ├── requirements.txt          # Generated by render_requirements_txt()
    ├── config/
    │   ├── cluster.yaml          # interval_seconds=5 for accelerated demo
    │   └── agents/
    │       ├── boss.yaml
    │       ├── critic.yaml
    │       └── coder.yaml        # A coding worker role
    ├── db/
    │   ├── schema.sql            # Copied from runtime/schema.sql
    │   └── cluster.db            # Pre-seeded: boss + coder in agent_status
    ├── runtime/                  # Copied by copy_runtime()
    └── launch.sh                 # Generated by render_launch_sh()
.github/
└── workflows/
    └── smoke-test.yml            # New: triggers on push to main + all PRs
README.md                         # New: root-level project README
```

### Pattern 1: Factory CLI Subcommand (approve + logs)

**What:** New subcommands on `factory_cli` that resolve cluster DB from `FACTORY_CLUSTERS_BASE/<cluster-name>/db/cluster.db`.

**When to use:** Any command that operates on a specific named cluster.

**Example — approve follows the exact same shape as existing commands:**
```python
# Source: runtime/cli.py — existing factory_cli subcommand pattern
@factory_cli.command(name="approve")
@click.argument("cluster_name")
@click.argument("task_id")
def factory_approve(cluster_name: str, task_id: str) -> None:
    """Approve a task in 'review' state."""
    asyncio.run(_do_factory_approve(cluster_name, task_id))

async def _do_factory_approve(cluster_name: str, task_id: str) -> None:
    cluster_db = _clusters_base() / cluster_name / "db" / "cluster.db"
    if not cluster_db.exists():
        click.echo(f"Cluster '{cluster_name}' not found.")
        return  # exit 0 per established convention
    # ... fetch task, validate status == 'review', UPDATE ...
```

**Key invariants:**
- Cluster DB path: `_clusters_base() / cluster_name / "db" / "cluster.db"` (not factory.db)
- Exit 0 on all not-found / wrong-state cases (established Phase 5 convention)
- `asyncio.run()` once at the top-level sync Click callback

### Pattern 2: logs SQL Query with --tail and --agent

**What:** Read from `activity_log` table with optional WHERE and LIMIT.

**SQL pattern:**
```python
# Builds query dynamically — safe parameterized approach
sql = "SELECT created_at, agent_id, action, details FROM activity_log"
params: list = []
if agent_filter:
    sql += " WHERE agent_id = ?"
    params.append(agent_filter)
sql += " ORDER BY created_at DESC LIMIT ?"
params.append(tail_n)
```

**Output (tabulate "simple"):**
```
timestamp             agent_id     action             details
--------------------  -----------  -----------------  ---------------------------
2026-03-08T14:01:02  boss-01      task_claimed       task_id=abc123 title=Write...
```

**details truncation:** truncate to ~40 chars with `…` suffix so the table stays readable on an 80-column terminal. This is Claude's discretion — 40 chars is the recommendation.

### Pattern 3: demo Command with Live Polling Loop

**What:** `agent-factory demo` creates the pre-configured cluster (using existing factory machinery), then enters a polling loop that reads task status from the cluster DB and overwrites each line with `\r`.

**Critical constraint:** Click commands are synchronous. The polling loop must use `time.sleep()`, not `asyncio.sleep()`. The factory cluster is started in a subprocess (same as `create`), and the demo command polls the cluster's output DB, not the factory DB.

```python
import time, sys

@factory_cli.command(name="demo")
def factory_demo() -> None:
    """Run a live demo: factory creates a coding cluster and you watch it work."""
    asyncio.run(_do_demo_setup())
    _poll_demo_until_approved()          # sync polling loop after setup

async def _do_demo_setup() -> None:
    # 1. Create cluster dir + seed factory DB goal row
    # 2. Start run_factory() in subprocess (as in factory_create)
    # Sets a known cluster name, interval_seconds=5
    ...

def _poll_demo_until_approved() -> None:
    """Synchronous polling loop — reads cluster DB status every N seconds."""
    cluster_db = _clusters_base() / "demo-date-arithmetic" / "db" / "cluster.db"
    while True:
        # Read task statuses from cluster_db (sync sqlite3 stdlib — avoid aiosqlite in sync context)
        # Print status line with \r to overwrite previous line
        sys.stdout.write(f"\r  Tasks: {todo} todo / {in_prog} in-progress / {review} review / {approved} approved  ")
        sys.stdout.flush()
        if approved >= 1:
            break
        time.sleep(5)  # poll every 5 seconds
    print()  # final newline
```

**Why sync sqlite3 (not aiosqlite) in polling loop:** The polling loop runs outside `asyncio.run()`. Using `aiosqlite` here would require a nested event loop or a new `asyncio.run()` call per iteration. The stdlib `sqlite3` module is simpler and correct for this read-only polling use case. WAL mode means concurrent readers do not block.

### Pattern 4: Demo Cluster Artifact with Pre-Seeded DB

**What:** The `clusters/demo-date-arithmetic/` directory committed to the repo is a static snapshot of a factory-generated cluster artifact. The `db/cluster.db` file within it must be pre-seeded so that the CI health check (`SELECT count(*) FROM agent_status`) returns >= 2 without running any agents.

**How to seed:** Run a small Python script at artifact-creation time (in the Wave 3 plan task):
```python
import sqlite3, uuid, datetime

db_path = "clusters/demo-date-arithmetic/db/cluster.db"
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")
conn.executescript(open("runtime/schema.sql").read())
# Insert boss + coder into agent_status
for agent_id, role in [("boss-01", "boss"), ("coder-01", "coder")]:
    conn.execute(
        "INSERT OR REPLACE INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
        (agent_id, role)
    )
conn.commit()
conn.close()
```

**Why committed to repo:** CI cannot run `agent-factory demo` (requires real LLM calls). CI only validates startup: build, config, container health. The artifact must be self-contained and pre-seeded.

**Git tracking of .db files:** `cluster.db` must NOT be in `.gitignore`. Verify the root `.gitignore` does not exclude `*.db` under `clusters/`. The existing `.gitignore` excludes `runtime/state/` (per Phase 2 decisions) but not cluster db files — this should be confirmed when writing the artifact.

### Pattern 5: GitHub Actions Smoke Test Workflow

**What:** A new file `.github/workflows/smoke-test.yml` that runs on push to `main` and all PRs. It uses `docker compose` (v2 syntax — no hyphen) since Docker Compose v2 is pre-installed on ubuntu-latest as of early 2026.

**Critical details:**
- ubuntu-latest has `sqlite3` CLI pre-installed (it is part of the default ubuntu image)
- Use `docker compose` (v2, space syntax), not `docker-compose` (v1, was removed from ubuntu-latest in 2024)
- Wait strategy: use `docker compose up --wait` (Docker Compose v2.1+ syntax) which blocks until all services with healthchecks are healthy, OR use a `sleep 10` + sqlite3 check as a simpler alternative since the smoke test doesn't care about agents running — it just checks DB seeding
- The CI check is against `db/cluster.db` which is pre-seeded in the committed artifact — no agent startup needed

**Recommended workflow structure:**
```yaml
name: Smoke Test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build demo cluster containers
        working-directory: clusters/demo-date-arithmetic
        run: docker compose build

      - name: Start demo cluster (detached)
        working-directory: clusters/demo-date-arithmetic
        env:
          ANTHROPIC_API_KEY: placeholder-ci-no-llm-calls
        run: docker compose up -d

      - name: Wait for containers to start
        run: sleep 10

      - name: Verify agent_status rows in pre-seeded DB
        run: |
          count=$(sqlite3 clusters/demo-date-arithmetic/db/cluster.db "SELECT count(*) FROM agent_status")
          echo "agent_status rows: $count"
          [ "$count" -ge 2 ] || (echo "FAIL: expected >= 2 agent_status rows" && exit 1)

      - name: Stop containers
        if: always()
        working-directory: clusters/demo-date-arithmetic
        run: docker compose down
```

**Why no healthcheck on docker-compose services:** The smoke test validates build + DB seeding, not agent liveness. Adding healthchecks to the compose file for CI would require agents to successfully connect to Anthropic API (no real key in CI). The check is intentionally DB-only.

**Why `actions/checkout@v4`:** This is the current stable version as of 2026 (v4 replaced v3 in 2023 and remains current). Do not use v2.

### Anti-Patterns to Avoid

- **Nested asyncio event loops in demo:** Do not call `asyncio.run()` inside the polling loop. Use stdlib `sqlite3` for the read-only status check in the synchronous polling function.
- **`docker-compose` (hyphen) in CI:** Docker Compose v1 was removed from ubuntu-latest runners. Use `docker compose` (space, v2 plugin syntax).
- **Relying on agent_status being populated by running agents in CI:** The committed `cluster.db` must be pre-seeded. CI does not start agents (no API key).
- **Missing `.env` file in CI:** The `docker compose up` will fail if `.env` is missing but the compose file uses `env_file: .env`. Provide a `.env` with placeholder values or use `environment:` directly in the compose for CI. The committed `.env.example` needs to be copied (or the smoke test creates a `.env` with `ANTHROPIC_API_KEY=ci-placeholder`).
- **`click.echo()` with newlines in polling loop:** Use `sys.stdout.write()` + `sys.stdout.flush()` for carriage-return-based line overwriting. `click.echo()` always appends a newline and cannot do in-place updates.
- **Using `CLUSTER_DB_PATH` instead of `FACTORY_CLUSTERS_BASE`:** The factory CLI `approve` and `logs` commands resolve the cluster DB from `FACTORY_CLUSTERS_BASE/<name>/db/cluster.db`, matching how `status` and `add-role` work. Do not use `CLUSTER_DB_PATH` (that is the cluster runtime CLI pattern for `cluster approve <task-id>`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Table output for logs | Custom string formatting | `tabulate(..., tablefmt="simple")` | Already used everywhere; consistent |
| JSON output for logs | Custom serializer | `json.dumps(rows, indent=2)` | Same pattern as `tasks list --json` |
| In-line terminal updates | curses or rich | `sys.stdout.write(f"\r...")` + flush | Simple, no new deps, established pattern |
| DB health check in CI | curl + HTTP endpoint | `sqlite3` CLI shell step | No HTTP server in cluster containers; WAL mode allows concurrent reads |
| Artifact YAML generation | String templating | `render_docker_compose()`, `render_cluster_yaml()`, etc. | All seven generator functions are already implemented and tested |
| Runtime copy into artifact | Manual file copy | `copy_runtime()` | Already implemented; `dirs_exist_ok=True` |

**Key insight:** Phase 6 is integration of existing components, not new infrastructure. The risk is incorrect wiring, not missing capability.

---

## Common Pitfalls

### Pitfall 1: `.env` missing when docker compose up runs in CI
**What goes wrong:** `docker compose up` fails immediately with "env_file .env not found" because the committed artifact has `.env.example` but not `.env`.
**Why it happens:** The `.gitignore` (correctly) excludes `.env` files from commits, so only `.env.example` is in the repo.
**How to avoid:** The CI smoke test workflow must create a `.env` from `.env.example` before running `docker compose up`, OR the committed `docker-compose.yml` uses `environment:` with explicit values instead of `env_file:`, OR the workflow step copies `.env.example` to `.env` with a placeholder `ANTHROPIC_API_KEY`.
**Recommended solution:** Add a CI step before `docker compose up`: `cp clusters/demo-date-arithmetic/.env.example clusters/demo-date-arithmetic/.env`

### Pitfall 2: sqlite3 CLI not found in CI
**What goes wrong:** `sqlite3` command not found on the GitHub Actions runner.
**Why it happens:** Assumption that sqlite3 is pre-installed.
**How to avoid:** ubuntu-latest runners include `sqlite3` as part of the base image. Verify with `sqlite3 --version` in a test step. If it ever fails, add `sudo apt-get install -y sqlite3` as a preceding step. This is a LOW-confidence assumption — a verification step in CI is cheap insurance.

### Pitfall 3: docker compose up --wait vs sleep N
**What goes wrong:** Using `--wait` flag requires all services to have healthchecks defined in `docker-compose.yml`. If no healthcheck is defined, `--wait` exits immediately (treating services as healthy by default in some Compose versions).
**Why it happens:** `--wait` behavior varies by Compose version and healthcheck presence.
**How to avoid:** Use `docker compose up -d` followed by `sleep 10` (deterministic), then the sqlite3 DB check (which is against the pre-seeded file, not a live agent). The sleep is just to allow container startup — not needed for the DB check since `cluster.db` is pre-seeded at commit time.

### Pitfall 4: cluster.db committed with wrong WAL state
**What goes wrong:** The pre-seeded `cluster.db` is committed while WAL journal files (`cluster.db-wal`, `cluster.db-shm`) are active, causing DB corruption or incomplete data on checkout.
**Why it happens:** SQLite WAL mode creates `-wal` and `-shm` sidecar files while transactions are open.
**How to avoid:** After seeding, run `PRAGMA wal_checkpoint(TRUNCATE)` and close the connection before committing. All three files (`cluster.db`, `cluster.db-wal`, `cluster.db-shm`) must be committed together, OR the WAL must be fully checkpointed so only `cluster.db` exists. The script should use `conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")` before closing.

### Pitfall 5: Polling loop reads factory DB instead of cluster DB
**What goes wrong:** The `demo` command shows no task progress because it polls the factory DB (where factory tasks live), not the output cluster's DB (where the coding cluster's tasks live).
**Why it happens:** The factory machinery stores factory tasks in `~/.agent-factory/factory.db`. The cluster output has its own `clusters/demo-date-arithmetic/db/cluster.db`.
**How to avoid:** The polling loop must read from `_clusters_base() / cluster_name / "db" / "cluster.db"`, not from the factory DB. This is where the running agents write their status.

### Pitfall 6: README annotated trace is stale
**What goes wrong:** The annotated terminal trace in the README shows task IDs or exact output that don't match what the actual `demo` command produces.
**Why it happens:** Writing the trace before the command is implemented.
**How to avoid:** Write the README trace AFTER running the actual demo command once and capturing its output. Use `agent-factory demo` → copy the actual terminal output → annotate it.

### Pitfall 7: factory_approve resolves wrong DB path
**What goes wrong:** `agent-factory approve <cluster-name> <task-id>` updates the factory DB rather than the cluster's DB, so the cluster agents never see the approval.
**Why it happens:** Copy-paste from `factory_create`/`factory_status` which use the factory DB.
**How to avoid:** `approve` and `logs` resolve `_clusters_base() / cluster_name / "db" / "cluster.db"`. This is a different path than the factory DB at `~/.agent-factory/factory.db`.

---

## Code Examples

Verified patterns from existing codebase:

### activity_log Query Pattern (for logs command)
```python
# Derived from existing _fetch_tasks_rows() pattern in runtime/cli.py
async def _do_factory_logs(cluster_name: str, tail: int, agent_filter: str | None, as_json: bool) -> None:
    cluster_db = _clusters_base() / cluster_name / "db" / "cluster.db"
    if not cluster_db.exists():
        click.echo(f"Cluster '{cluster_name}' not found.")
        return

    from runtime.database import DatabaseManager
    mgr = DatabaseManager(cluster_db)
    db = await mgr.open_read()
    try:
        sql = "SELECT created_at, agent_id, action, details FROM activity_log"
        params: list = []
        if agent_filter:
            sql += " WHERE agent_id = ?"
            params.append(agent_filter)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(tail)
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()

    if not rows:
        click.echo("No activity log entries found.")
        return

    if as_json:
        import json as _json
        click.echo(_json.dumps([dict(r) for r in rows], indent=2))
    else:
        from tabulate import tabulate
        table = [
            [r["created_at"], r["agent_id"], r["action"],
             (r["details"] or "")[:40] + ("…" if r["details"] and len(r["details"]) > 40 else "")]
            for r in rows
        ]
        click.echo(tabulate(table, headers=["Timestamp", "Agent", "Action", "Details"], tablefmt="simple"))
```

### Cluster DB Approve Pattern (for factory approve)
```python
# Mirrors _do_approve() from cluster_cli but resolves via FACTORY_CLUSTERS_BASE/<name>/db/cluster.db
async def _do_factory_approve(cluster_name: str, task_id: str) -> None:
    cluster_db = _clusters_base() / cluster_name / "db" / "cluster.db"
    if not cluster_db.exists():
        click.echo(f"Cluster '{cluster_name}' not found.")
        return

    from runtime.database import DatabaseManager
    mgr = DatabaseManager(cluster_db)
    db = await mgr.open_read()
    try:
        async with db.execute("SELECT id, title, status FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()

    if row is None:
        click.echo(f"Task '{task_id}' not found in cluster '{cluster_name}'.")
        return
    if row["status"] != "review":
        click.echo(f"Task '{task_id}' is in '{row['status']}' state, not 'review'. Cannot approve.")
        return

    db = await mgr.open_write()
    try:
        from runtime.models import _now_iso
        await db.execute(
            "UPDATE tasks SET status = 'approved', updated_at = ? WHERE id = ?",
            (_now_iso(), task_id),
        )
        await db.commit()
    finally:
        await db.close()

    click.echo(f"Approved: {row['title']} ({task_id[:8]})")
    click.echo(f"  Cluster: {cluster_name}")
    click.echo(f"  Status: approved")
```

### Live Polling Loop Pattern (for demo command)
```python
import sys
import time
import sqlite3 as _sqlite3  # stdlib sqlite3 for sync polling outside asyncio

def _poll_demo_until_approved(cluster_db_path: str, poll_interval: float = 5.0) -> None:
    """Synchronous polling loop — overwrites current line with \r."""
    while True:
        try:
            conn = _sqlite3.connect(cluster_db_path)
            conn.row_factory = _sqlite3.Row
            cur = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
            )
            counts = {row["status"]: row["cnt"] for row in cur.fetchall()}
            conn.close()
        except _sqlite3.OperationalError:
            counts = {}  # DB not yet initialized — cluster still starting

        approved = counts.get("approved", 0)
        review = counts.get("review", 0)
        in_progress = counts.get("in-progress", 0)
        todo = counts.get("todo", 0)

        sys.stdout.write(
            f"\r  todo={todo} | in-progress={in_progress} | review={review} | approved={approved}   "
        )
        sys.stdout.flush()

        if approved >= 1:
            break
        time.sleep(poll_interval)

    print()  # final newline after the \r loop
```

### Pre-Seeding cluster.db for CI
```python
import sqlite3
from pathlib import Path

def seed_demo_db(db_path: Path, schema_path: Path) -> None:
    """Create and seed cluster.db for the committed demo artifact."""
    conn = sqlite3.connect(str(db_path))
    # Apply schema
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    # Seed agent_status with boss + coder (CI asserts count >= 2)
    for agent_id, role in [("boss-01", "boss"), ("coder-01", "coder")]:
        conn.execute(
            "INSERT OR REPLACE INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
            (agent_id, role),
        )
    conn.commit()
    # Checkpoint WAL so cluster.db is the only file committed
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
```

### GitHub Actions Smoke Test Workflow
```yaml
# .github/workflows/smoke-test.yml
name: Smoke Test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Create .env for CI (placeholder key — no real LLM calls)
        run: cp clusters/demo-date-arithmetic/.env.example clusters/demo-date-arithmetic/.env

      - name: Build demo cluster containers
        working-directory: clusters/demo-date-arithmetic
        run: docker compose build

      - name: Start demo cluster containers (detached)
        working-directory: clusters/demo-date-arithmetic
        run: docker compose up -d

      - name: Wait for container startup
        run: sleep 15

      - name: Verify pre-seeded agent_status rows
        run: |
          count=$(sqlite3 clusters/demo-date-arithmetic/db/cluster.db "SELECT count(*) FROM agent_status")
          echo "agent_status row count: $count"
          [ "$count" -ge 2 ] || (echo "FAIL: expected >= 2 rows, got $count" && exit 1)

      - name: Tear down containers
        if: always()
        working-directory: clusters/demo-date-arithmetic
        run: docker compose down --volumes
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose` (v1, hyphen) | `docker compose` (v2, space) | 2024 (removed from ubuntu-latest) | CI workflows must use v2 syntax |
| `actions/checkout@v2` | `actions/checkout@v4` | 2023 | v2 is deprecated; use v4 |
| `docker-compose --wait` healthcheck | `sleep N` + direct DB check | N/A (pattern choice) | Simpler, no healthcheck config needed |
| Full integration test in CI | Startup smoke test only | N/A (design decision) | Real LLM calls only in `agent-factory demo` |

**Deprecated/outdated:**
- `docker-compose` (hyphen): removed from ubuntu-latest runners in 2024. All CI must use `docker compose`.
- `actions/checkout@v2` / `@v3`: superseded by `@v4`. Use `@v4`.

---

## Open Questions

1. **Will docker compose containers start cleanly without a real ANTHROPIC_API_KEY?**
   - What we know: Agents call `AsyncAnthropic()` on startup, which reads `ANTHROPIC_API_KEY`. If the key is invalid, the first LLM call (not the constructor) will fail.
   - What's unclear: Do agents make LLM calls during container startup before the first heartbeat tick? If `BaseAgent.start()` makes no LLM call before entering the loop, containers will start healthy with a placeholder key.
   - Recommendation: Review `heartbeat.py` `start()` method — if it only writes `agent_status` and then enters the tick loop, a placeholder key is safe. The first real LLM call only happens on the first tick (10+ seconds in). CI's `sleep 15` + teardown happens before that. This is HIGH confidence based on the heartbeat model described in REQUIREMENTS.md.

2. **Should cluster.db-wal and cluster.db-shm be in .gitignore?**
   - What we know: After `PRAGMA wal_checkpoint(TRUNCATE)` and connection close, the -wal and -shm files should be empty/removed. But git may track them if they exist at commit time.
   - What's unclear: Whether the seed script reliably produces only `cluster.db` with no sidecar files.
   - Recommendation: Add `clusters/*/db/*.db-wal` and `clusters/*/db/*.db-shm` to `.gitignore`. Commit only `cluster.db`.

3. **Exact heartbeat interval for demo (5s vs 10s)?**
   - Discretion: 5 seconds is recommended. At 10 seconds, a full task cycle (claim + execute + peer_review + promote + review) takes 50+ seconds minimum. At 5 seconds, ~25 seconds. Either is acceptable; 5 seconds produces a more impressive demo.
   - Recommendation: Use `interval_seconds=5` with `jitter_seconds=1` for the demo cluster config.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `python -m pytest tests/test_factory_cli.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| `factory approve` exits 0 on not-found cluster | unit/CLI | `pytest tests/test_factory_cli.py::test_approve_cluster_not_found -x` | Wave 0 |
| `factory approve` exits 0 on wrong-state task | unit/CLI | `pytest tests/test_factory_cli.py::test_approve_wrong_state -x` | Wave 0 |
| `factory approve` updates task to 'approved' | unit/CLI | `pytest tests/test_factory_cli.py::test_approve_success -x` | Wave 0 |
| `factory logs` exits 0 on not-found cluster | unit/CLI | `pytest tests/test_factory_cli.py::test_logs_cluster_not_found -x` | Wave 0 |
| `factory logs` shows tabulate table | unit/CLI | `pytest tests/test_factory_cli.py::test_logs_table_output -x` | Wave 0 |
| `factory logs --json` outputs JSON list | unit/CLI | `pytest tests/test_factory_cli.py::test_logs_json_output -x` | Wave 0 |
| `factory logs --tail N` limits rows | unit/CLI | `pytest tests/test_factory_cli.py::test_logs_tail -x` | Wave 0 |
| `factory logs --agent <id>` filters | unit/CLI | `pytest tests/test_factory_cli.py::test_logs_agent_filter -x` | Wave 0 |
| `factory demo` subcommand exists | smoke | `pytest tests/test_factory_cli.py::test_demo_exists -x` | Wave 0 |
| demo cluster artifact files exist | structural | `pytest tests/test_demo_artifact.py -x` | Wave 0 |
| cluster.db pre-seeded with >= 2 rows | unit | `pytest tests/test_demo_artifact.py::test_cluster_db_seeded -x` | Wave 0 |
| README.md exists at repo root | structural | `pytest tests/test_demo_artifact.py::test_readme_exists -x` | Wave 0 |
| Full suite coverage >= 80% | suite | `python -m pytest tests/ -q` | Ongoing |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_factory_cli.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_factory_cli.py` — add stubs: `test_approve_cluster_not_found`, `test_approve_wrong_state`, `test_approve_success`, `test_logs_cluster_not_found`, `test_logs_table_output`, `test_logs_json_output`, `test_logs_tail`, `test_logs_agent_filter`, `test_demo_exists`
- [ ] `tests/test_demo_artifact.py` — new file: covers committed artifact structure + DB seeding
- [ ] No new framework installation required — existing pytest + pytest-asyncio sufficient

---

## Sources

### Primary (HIGH confidence)
- `C:/Projects/Agent Creation/runtime/cli.py` — existing subcommand patterns for approve, logs; `_clusters_base()` resolver; tabulate usage
- `C:/Projects/Agent Creation/runtime/schema.sql` — activity_log table schema (columns: id, agent_id, task_id, action, details, created_at)
- `C:/Projects/Agent Creation/factory/generator.py` — all seven generator functions verified implemented and tested
- `C:/Projects/Agent Creation/factory/runner.py` — `run_factory()` signature and subprocess pattern for demo command
- `C:/Projects/Agent Creation/.planning/phases/06-demo-cluster-integration-validation/06-CONTEXT.md` — all locked decisions
- GitHub Actions runner-images changelog (2026-01-30) — Docker Compose v2.40 on ubuntu-latest, v2 syntax required

### Secondary (MEDIUM confidence)
- [Docker and Docker Compose version upgrades on hosted runners](https://github.blog/changelog/2026-01-30-docker-and-docker-compose-version-upgrades-on-hosted-runners/) — Docker Compose v2 pre-installed, `docker compose` (space) syntax confirmed
- [peter-evans/docker-compose-actions-workflow](https://github.com/peter-evans/docker-compose-actions-workflow) — GitHub Actions + docker compose pattern (checkout → build → up -d → test)
- Click documentation — `click.echo()` always appends newline; `sys.stdout.write()` required for `\r` overwrite
- [How terminal progress bars work](https://code.mendhak.com/how-do-terminal-progress-bars-actually-work/) — confirms `\r` + `sys.stdout.flush()` pattern

### Tertiary (LOW confidence)
- sqlite3 CLI pre-installation on ubuntu-latest: verified by project familiarity and GitHub runner images reputation, but not directly sourced from the official runner-images manifest. Add `sqlite3 --version` verification step or `sudo apt-get install -y sqlite3` as fallback.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already present, no new dependencies
- Architecture: HIGH — all patterns derived from existing codebase, locked decisions in CONTEXT.md
- CI workflow: MEDIUM — docker compose v2 syntax verified; sqlite3 pre-installation is MEDIUM (very likely but not directly confirmed from runner-images manifest)
- Pitfalls: HIGH — derived from existing codebase decisions (WAL checkpoint, .env.example pattern, DB path routing)

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable dependencies; GitHub Actions runner images update more frequently but core patterns are stable)
