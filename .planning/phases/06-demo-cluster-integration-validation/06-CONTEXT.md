# Phase 6: Demo Cluster + Integration Validation - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Run a real end-to-end scenario: the factory creates a coding cluster ("Write a Python utility library for date arithmetic"), the cluster runs autonomously with real LLM calls and completes at least one full task cycle (todo → approved). Phase 6 also delivers the `agent-factory approve` and `agent-factory logs` commands (deferred from Phase 5), a CI smoke test via GitHub Actions, and the project README. Phase 7 hardening/release work (security audit, PyPI publish, CHANGELOG) is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Demo Command

- `agent-factory demo` subcommand — dedicated command, not a flag on `create`
- Creates a pre-configured cluster with the fixed goal "Write a Python utility library for date arithmetic" and accelerated heartbeats (~5-10 seconds interval)
- Uses real LLM calls (Haiku for workers, Sonnet for boss) — genuine integration validation
- After creation, enters a live-updating status loop in the terminal showing task progress
- Exits with a summary once at least one task reaches `approved`; user then approves via `agent-factory approve`

### CI Smoke Test

- Pre-generated demo cluster artifact committed to the repository under `clusters/demo-date-arithmetic/`
- CI pipeline: `docker compose up` in that directory, wait for containers to be healthy
- Health check: shell step queries `clusters/demo-date-arithmetic/db/cluster.db` via `sqlite3`:
  ```
  sqlite3 clusters/demo-date-arithmetic/db/cluster.db "SELECT count(*) FROM agent_status"
  ```
  Asserts count ≥ 2 (boss + at least one worker registered)
- No real LLM calls in CI — smoke test validates build, config, and startup only
- Trigger: on push to `main` and on all pull requests

### agent-factory approve Command

- Signature: `agent-factory approve <cluster-name> <task-id>`
- Resolves cluster DB via `FACTORY_CLUSTERS_BASE` env var: `$FACTORY_CLUSTERS_BASE/<cluster-name>/db/cluster.db`
  (same pattern as `status`, `logs` — consistent across all factory CLI)
- Pre-approval validation: fetch task, verify `status == 'review'` — fail with info message if not
- Success output:
  ```
  Approved: <task-title> (<task-id>)
    Cluster: <cluster-name>
    Status: approved
  ```
- Error handling: exit 0 with info message for all edge cases (cluster not found, task not found, wrong state) — consistent with Phase 5 exit-0 convention for not-found / informational errors

### agent-factory logs Command

- Signature: `agent-factory logs <cluster-name> [--tail N] [--agent <agent-id>] [--json]`
- Resolves cluster DB via `FACTORY_CLUSTERS_BASE` (same as approve)
- Output: tabulate "simple" table — columns: `timestamp | agent_id | action | details` (details truncated to fit)
- `--tail N`: show last N entries (default: 50)
- `--agent <id>`: filter to one agent's entries (SQL WHERE clause)
- `--json`: output raw JSON list instead of tabulate table (for scripting)
- Exit 0 with info message if cluster not found or activity_log is empty

### README Structure

- Root-level `README.md`
- Three-section structure:
  1. **What it is** — 2-3 sentences: the core value proposition (factory cluster → self-contained coding cluster)
  2. **Quick Start** — install + `agent-factory demo` + `agent-factory approve`
  3. **How it works** — brief ASCII diagram (factory → artifact → running cluster) + prose explaining boss/worker/heartbeat/factory layers
- Demo walkthrough: full annotated terminal trace showing exact commands + expected output for the full happy path (pip install → demo → status watching → approve → cluster tasks list --status approved)

### Claude's Discretion

- Exact heartbeat interval for demo cluster (5 seconds vs 10 seconds — balance speed vs realism)
- Demo cluster name (e.g., `demo-date-arithmetic` or `date-utils-demo`)
- Status polling interval in the `demo` command's live loop
- README tone and exact wording
- docker-compose.yml structure for the committed demo cluster artifact
- `--tail` default value (50 is a starting point)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `runtime/cli.py` — `factory_cli` group: `create`, `list`, `status`, `add-role` subcommands already implemented in Phase 5. `approve` and `logs` follow the same click command pattern. `cluster_cli` group also lives here — `cluster approve <task-id>` may already exist from Phase 3.
- `runtime/cli.py` — `FACTORY_CLUSTERS_BASE` env var resolution pattern: already used in `status` and `add-role` for cluster DB lookup. `approve` and `logs` reuse the same resolver.
- `factory/runner.py` — `run_factory()`: starts factory boss + workers with configurable `interval_seconds`. Demo command sets this to a small value (5-10s) rather than the production 600s.
- `runtime/models.py` — `_uuid()`, `_now_iso()`: reused in demo cluster DB seeding.
- `factory/generator.py` — all seven artifact generator functions: `render_docker_compose`, `render_dockerfile`, `render_requirements_txt`, `render_agent_yaml`, `render_schema_sql`, `render_launch_sh`, `render_cluster_yaml`. Demo cluster artifact is generated by these.
- `tabulate` (already in dependencies): used for `logs` table output, consistent with `cluster tasks list` format.

### Established Patterns

- Exit 0 with info message on not-found (established in Phase 5): all factory CLI commands follow this. `approve` and `logs` do the same.
- `FACTORY_CLUSTERS_BASE` env var (established in Phase 5): factory CLI cluster resolution uses this. Default: `Path.cwd() / "clusters"`.
- tabulate "simple" tablefmt: consistent across all CLI commands since Phase 3.
- `asyncio.run()` once per CLI command: no nested event loops. `approve` and `logs` follow this.
- `pytest.importorskip` inside test body (not module level): Phase 6 tests that depend on new CLI subcommands follow this where modules are absent during TDD RED phase.

### Integration Points

- `runtime/cli.py:factory_cli` — add `approve` and `logs` subcommands here (alongside existing `create`, `list`, `status`, `add-role`)
- `factory/runner.py:run_factory` — demo command calls this with `interval_seconds=5` (or similar) and the fixed goal
- `.github/workflows/` — new file: `smoke-test.yml` (GitHub Actions workflow for CI)
- `clusters/demo-date-arithmetic/` — new directory committed to repo containing the pre-generated demo cluster artifact

</code_context>

<specifics>
## Specific Ideas

- The demo cluster uses real LLM calls — this is the genuine integration test that validates the entire stack (factory pipeline, generator, heartbeat, boss, worker, peer review, state machine, CLI) in a single run
- The committed `clusters/demo-date-arithmetic/` artifact is what CI spins up — factory creation is validated by `agent-factory demo`, not by CI. These are two separate concerns.
- `agent-factory demo` streams live status updates so the user can watch the task lifecycle in real time — this is part of the product experience, not just a test
- Logs command needs `--json` and `--agent` from the start because the demo debugging experience depends on being able to filter a specific agent's activity

</specifics>

<deferred>
## Deferred Ideas

- `agent-factory logs <cluster>` streaming (real-time tail, like `tail -f`) — Phase 7 observability work; Phase 6 ships the read-only snapshot version
- `agent-factory approve` interactive confirmation prompt (show task details + y/N) — would break scripting; deferred unless user requests
- Nightly CI job that runs `agent-factory create` + real LLM demo — possible Phase 7 enhancement; Phase 6 smoke test is startup-only
- `CONTRIBUTING.md` and full API documentation — Phase 7 release prep

</deferred>

---

*Phase: 06-demo-cluster-integration-validation*
*Context gathered: 2026-03-08*
