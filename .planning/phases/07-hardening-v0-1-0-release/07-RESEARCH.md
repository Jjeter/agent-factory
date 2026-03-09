# Phase 7: Hardening + v0.1.0 Release - Research

**Researched:** 2026-03-09
**Domain:** Security hardening, CI/CD release automation, PyPI trusted publishing, AWOL detection, crash recovery, CHANGELOG
**Confidence:** HIGH

## Summary

Phase 7 closes out the Agent Factory v0.1.0 milestone. All six prior phases are complete with 128 tests GREEN and 85.78% coverage. The work in this phase is entirely additive: no existing behavior changes, only security gates, observability enhancements to the heartbeat machinery, and the publication pipeline. The implementation surface is narrow — four new files (`.github/workflows/publish.yml`, `tests/test_security.py`, `CHANGELOG.md`, and a truffleHog step) plus targeted extensions to two existing modules (`runtime/heartbeat.py` and `runtime/boss.py`).

The `pyproject.toml` already declares `version = "0.1.0"`, the hatchling build backend, and both `runtime` and `factory` packages — the publish workflow needs zero structural changes to the package itself. The TestPyPI → PyPI gating pattern with OIDC trusted publishing eliminates stored API tokens from the repository entirely. The AWOL detection and crash recovery work is a direct extension of patterns already proven in Phases 2–3 (stuck-task detection, `_load_state()`). The two security tests are narrow mock-based tests with no external dependencies.

**Primary recommendation:** Build the publish workflow first (it gates the release), then the security tests (they block the merge gate), then AWOL detection and crash recovery extensions, and finally CHANGELOG + GitHub release.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Package Release Format**
- Publish to PyPI — `pip install agent-factory` works out of the box for end users
- Triggered by GitHub Actions on `git tag v0.1.0` push (OIDC trusted publishing — no stored API token)
- Full system: both `runtime` and `factory` packages included (matches existing pyproject.toml declaration)
- TestPyPI gate before real PyPI: CI uploads to TestPyPI first; success gates the real PyPI upload

**Heartbeat Monitoring (AWOL Detection)**
- Detection mechanism: compare `agent_status.last_heartbeat` timestamp — if `now - last_heartbeat > 3 * interval_seconds`, agent is AWOL
- Alert channel: `notifier.notify_escalation()` (stdout in v0.1.0) + `activity_log` entry (same pattern as existing model-tier escalation)
- Boss action: observe only — no auto-reassignment or restart attempt; user decides what to do

**Crash Recovery**
- On startup, `BaseAgent._load_state()` (already called at `start()`) reads local state file
- If state file contains a previous in-progress task ID, and that task is still `in-progress` in the DB, the agent claims it back and resumes
- No change to task state machine — task was already claimed by this agent

**Security Audit**
- **Secrets scan**: truffleHog runs as a CI gate (separate `security.yml` workflow or step in existing `smoke-test.yml`) on every push to `main` and every PR
- **Tool allowlist enforcement**: automated test in `tests/test_security.py` — mock LLM response returns a tool call for a tool not in the agent's allowlist; assert WorkerAgent raises an error or ignores it (does NOT forward the call)
- **Cross-cluster DB isolation**: automated test — create two independent DatabaseManager instances pointing to two different `tmp_path` DBs; seed cluster A; assert cluster B's DB has no data from A (proves structural path-based isolation)

**Release Documentation**
- `CHANGELOG.md`: single v0.1.0 section, human-written high-level summary of capabilities shipped
- GitHub release: `v0.1.0` tag; wheel (`.whl`) + sdist (`.tar.gz`) attached as assets via GitHub Actions
- `CONTRIBUTING.md`: deferred — not for v0.1.0

### Claude's Discretion
- Exact threshold comparison formula (e.g., whether to use `>` or `>=` when counting missed heartbeats)
- Whether truffleHog runs as its own job or as a step inside `smoke-test.yml`
- Exact error type raised when disallowed tool call is detected (custom exception vs. assertion vs. log + skip)
- CHANGELOG wording and section structure

### Deferred Ideas (OUT OF SCOPE)
- `agent-factory logs` streaming (real-time `tail -f`)
- CONTRIBUTING.md
- Docker image published to GitHub Container Registry (ghcr.io)
- Nightly CI job running `agent-factory create` with real LLM calls
- Agent status `stalled` flag in `cluster agents status` output
</user_constraints>

---

## Standard Stack

### Core (already in pyproject.toml)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| hatchling | latest | Build backend — produces .whl + .tar.gz | Already declared |
| pytest | >=8.0.0 | Test runner | Already in dev deps |
| pytest-cov | >=5.0.0 | Coverage with `--cov-fail-under=80` in addopts | Already in dev deps |
| pytest-asyncio | >=0.24.0 | Async test support | Already in dev deps |

### CI/CD Actions
| Action | Version | Purpose | Why This |
|--------|---------|---------|----------|
| `pypa/gh-action-pypi-publish` | `release/v1` | Upload dists to TestPyPI / PyPI | Official PyPA action; OIDC trusted publishing built in |
| `softprops/action-gh-release` | `v2` | Create GitHub release + attach .whl + .tar.gz | Standard community action; `contents: write` permission |
| `trufflesecurity/trufflehog` | `main` | Secrets scan on every push + PR | Official Truffle Security action; `fetch-depth: 0` required |
| `actions/upload-artifact` | `v4` | Share dist/ between jobs | Needed for multi-job publish workflow |
| `actions/download-artifact` | `v4` | Retrieve dist/ in publish jobs | Pair with upload-artifact |

**Installation:** No new runtime dependencies. Build dependency only:
```bash
pip install build
python -m build
```

---

## Architecture Patterns

### Recommended File Structure (new files only)

```
.github/workflows/
├── smoke-test.yml          # Existing — add truffleHog step or leave separate
├── security.yml            # NEW (optional) — truffleHog standalone job
└── publish.yml             # NEW — tag-triggered TestPyPI → PyPI → GitHub Release

tests/
└── test_security.py        # NEW — tool allowlist enforcement + cross-cluster DB isolation

CHANGELOG.md                # NEW — project root, single v0.1.0 section
```

### Pattern 1: PyPI Trusted Publishing Workflow (publish.yml)

**What:** Three-job workflow: build → test-publish (TestPyPI) → publish (PyPI) → release (GitHub)
**When to use:** Triggered by `v*` tag push only
**Key points:**
- `id-token: write` permission required per job (NOT at workflow level — job-level is safer)
- `contents: write` permission required for the GitHub release job
- Each job has its own `environment:` declaration for audit trail (testpypi / pypi)
- TestPyPI job gates PyPI job via `needs: [build, test-publish]`
- GitHub release job runs after PyPI job via `needs: [build, publish]`

```yaml
# Source: https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/
name: Publish

on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build && python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: python-package-distributions
          path: dist/

  test-publish:
    needs: [build]
    runs-on: ubuntu-latest
    environment:
      name: testpypi
      url: https://test.pypi.org/p/agent-factory
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/

  publish:
    needs: [build, test-publish]
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/agent-factory
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1

  github-release:
    needs: [build, publish]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: dist/
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/*.whl\ndist/*.tar.gz
```

### Pattern 2: TruffleHog Secrets Scan (security.yml or step in smoke-test.yml)

**What:** Git history scan for live secrets; runs on push to main and every PR
**Key points:**
- `fetch-depth: 0` is required — truffleHog scans full git history
- `--results=verified,unknown` catches both confirmed and unverified detections
- Recommendation: a separate `security.yml` workflow is cleaner for auditing; adding a step to `smoke-test.yml` is acceptable if the job is lightweight

```yaml
# Source: https://github.com/marketplace/actions/trufflehog-oss
name: Secret Scanning

on:
  push:
    branches: [main]
  pull_request:

jobs:
  trufflehog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: TruffleHog OSS
        uses: trufflesecurity/trufflehog@main
        with:
          extra_args: --results=verified,unknown
```

### Pattern 3: AWOL Detection in BossAgent

**What:** `_check_awol_agents()` method called each boss tick; mirrors `_detect_stuck_tasks()` structure
**When to use:** Called from `do_own_tasks()` alongside stuck detection

```python
# Pattern: follows existing _detect_stuck_tasks() structure in runtime/boss.py
async def _check_awol_agents(self) -> None:
    """Detect agents that missed 3+ consecutive heartbeats."""
    now = datetime.now(timezone.utc)
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT agent_id, agent_role, last_heartbeat FROM agent_status"
        ) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()

    for row in rows:
        if row["last_heartbeat"] is None:
            continue  # Never heartbeated yet — not AWOL
        last = datetime.fromisoformat(row["last_heartbeat"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        threshold = self._config.interval_seconds * 3
        if (now - last).total_seconds() > threshold:
            await self._alert_awol_agent(row["agent_id"], row["agent_role"])

async def _alert_awol_agent(self, agent_id: str, agent_role: str) -> None:
    """Emit notifier alert + activity_log entry for an AWOL agent."""
    reason = f"Agent {agent_id} ({agent_role}) missed 3+ heartbeats"
    await self._notifier.notify_escalation(agent_id, reason)
    now = _now_iso()
    db = await self._db.open_write()
    try:
        await db.execute(
            "INSERT INTO activity_log (id, agent_id, action, details, created_at) "
            "VALUES (?, ?, 'agent_awol', ?, ?)",
            (_uuid(), self._config.agent_id, json.dumps({
                "awol_agent_id": agent_id, "agent_role": agent_role
            }), now),
        )
        await db.commit()
    finally:
        await db.close()
```

**Integration point:** Call `await self._check_awol_agents()` from `do_own_tasks()` in `BossAgent`.

**Threshold comparison:** Use `>` (strictly greater than) to match the existing stuck-task pattern (`now - baseline < STUCK_THRESHOLD` → continue). An agent that hits exactly 3× interval at the moment of check is not yet AWOL; the first detection fires on the next tick after the threshold is crossed.

### Pattern 4: Crash Recovery via `_load_state()` Extension

**What:** Extend `BaseAgent._load_state()` to return `current_task_id` and pass it to the first tick
**When to use:** On agent startup when a prior state file exists

```python
# Extension to runtime/heartbeat.py BaseAgent._load_state()
# Returns the state dict; start() reads it and passes task_id to first tick

def _load_state(self) -> dict:
    """Load local state file. Returns fresh dict on missing or corrupt file."""
    try:
        state = json.loads(self._state_path.read_text(encoding="utf-8"))
        return state  # includes current_task_id if set
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(
            "State file missing or corrupt for agent %s — treating as fresh start",
            self._config.agent_id,
        )
        return {"last_heartbeat": None, "current_task_id": None}

# In start(): pass resumed task id to first tick
async def start(self) -> None:
    prior_state = self._load_state()
    self._resumed_task_id = prior_state.get("current_task_id")
    # ... rest of start() unchanged
```

**WorkerAgent integration:** In `do_own_tasks()`, check `self._resumed_task_id` before calling `_fetch_in_progress_task()`. If the task is still `in-progress` in the DB and assigned to this agent, resume it directly. Clear `_resumed_task_id` after the first tick so normal flow resumes.

**Key constraint:** The task state machine does not change. The task was already `in-progress` when the crash occurred; the agent re-claims it by reading the existing DB state, not by re-setting any status.

### Pattern 5: Security Tests (tests/test_security.py)

**What:** Two pytest tests; no LLM calls; uses `unittest.mock.patch` and `pytest.mark.asyncio`

**Test A — Tool allowlist enforcement:**
```python
# Source: CONTEXT.md — mock LLM response returns disallowed tool call
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_tool_allowlist_blocks_disallowed_call(tmp_path):
    worker = importorskip_worker(tmp_path)
    # Patch _llm.messages.create to return a response that includes a disallowed tool call
    # AgentConfig.tool_allowlist = ["allowed_tool"]
    # Assert WorkerAgent raises DisallowedToolError or logs + skips (does NOT forward)
    ...
```

**Test B — Cross-cluster DB isolation:**
```python
@pytest.mark.asyncio
async def test_cross_cluster_db_isolation(tmp_path):
    db_a_path = tmp_path / "cluster_a" / "cluster.db"
    db_b_path = tmp_path / "cluster_b" / "cluster.db"
    db_a_path.parent.mkdir()
    db_b_path.parent.mkdir()

    manager_a = DatabaseManager(db_a_path)
    manager_b = DatabaseManager(db_b_path)

    conn_a = await manager_a.open_write()
    await manager_a.init_schema(conn_a)
    # Seed cluster A data
    await conn_a.execute("INSERT INTO goals (id, title, description) VALUES ('g1', 'T', 'D')")
    await conn_a.commit()
    await conn_a.close()

    conn_b = await manager_b.open_write()
    await manager_b.init_schema(conn_b)
    async with conn_b.execute("SELECT COUNT(*) FROM goals") as cur:
        row = await cur.fetchone()
    count = row[0]
    await conn_b.close()

    assert count == 0  # Cluster B sees no data from Cluster A
```

### Anti-Patterns to Avoid

- **Storing the API token in repository secrets:** Trusted publishing eliminates this — never add `PYPI_API_TOKEN` to repo secrets.
- **Using `master` branch pin for truffleHog action:** The `trufflesecurity/trufflehog@main` pin is standard; do not pin to a stale SHA without verification.
- **Tool allowlist test that patches at class level:** Patch `boss._llm.messages.create` (instance-level) directly, consistent with existing `test_boss.py` pattern (`patch.object(boss._llm.messages, 'parse')`).
- **Checking `fetch-depth` default:** The default `actions/checkout@v4` only fetches the latest commit. truffleHog requires `fetch-depth: 0` for full history scan — omitting this produces a shallow scan that misses historical secrets.
- **Re-raising `CancelledError` in crash recovery path:** Crash recovery reads state in `start()` before the loop. Any await there must not suppress `CancelledError`. The existing `start()` structure already handles this correctly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PyPI upload with token | Custom `twine` step with stored secret | `pypa/gh-action-pypi-publish@release/v1` OIDC | Eliminates stored tokens; attestations auto-generated |
| GitHub release asset upload | `curl` to GitHub API | `softprops/action-gh-release@v2` | Handles release creation + asset upload atomically |
| Secret scanning | Custom `grep` for patterns | `trufflesecurity/trufflehog@main` | 700+ verified credential detectors; active API verification |
| Build isolation across jobs | Rebuilding in each job | `actions/upload-artifact@v4` + `download-artifact@v4` | Guarantees the same artifacts are tested and published |

---

## Common Pitfalls

### Pitfall 1: Missing `fetch-depth: 0` for truffleHog
**What goes wrong:** Default checkout fetches 1 commit; truffleHog only scans that commit, missing secrets introduced in earlier history.
**Why it happens:** `actions/checkout@v4` default `fetch-depth: 1` is optimized for build speed.
**How to avoid:** Always add `with: fetch-depth: 0` to the checkout step in the truffleHog job.
**Warning signs:** Scan completes in < 1 second with 0 findings on a repo with history.

### Pitfall 2: `id-token: write` at workflow level instead of job level
**What goes wrong:** OIDC token is exposed to all jobs including untrusted PR jobs — security risk.
**Why it happens:** Convenience of setting it once at the top.
**How to avoid:** Set `permissions: id-token: write` only on the specific publish jobs. Keep the build job with default (read-only) permissions.
**Warning signs:** Workflow-level `permissions:` block includes `id-token: write`.

### Pitfall 3: TestPyPI package name collision on re-runs
**What goes wrong:** TestPyPI rejects re-upload of the same version (HTTP 400) on subsequent CI runs before the tag is cut.
**Why it happens:** TestPyPI enforces unique filenames per version like real PyPI.
**How to avoid:** The publish workflow is gated on `tags: ["v*"]` so it only runs on explicit tag pushes, not every commit. Do not run the TestPyPI step on non-tag pushes in this project.
**Warning signs:** Workflow runs on every push to main and fails with "File already exists."

### Pitfall 4: AWOL detection double-alerts on every boss tick
**What goes wrong:** Boss alerts every tick for the same AWOL agent indefinitely, flooding `activity_log`.
**Why it happens:** No "already alerted" guard in `_alert_awol_agent()`.
**How to avoid:** Track alerted agent IDs in a set on the `BossAgent` instance (e.g., `self._alerted_awol: set[str]`). Only alert once per agent per session; clear on agent recovery (detected when `last_heartbeat` is recent again).
**Warning signs:** `activity_log` shows hundreds of `agent_awol` entries for the same agent.

### Pitfall 5: Crash recovery claims a task already re-assigned during downtime
**What goes wrong:** Agent restarts, reads stale state file showing task T as in-progress, but boss already re-assigned T to a different agent during the downtime.
**Why it happens:** State file is stale; DB is the source of truth.
**How to avoid:** After reading `current_task_id` from state, always re-query the DB: `SELECT assigned_to, status FROM tasks WHERE id = ?`. Only resume if `assigned_to = this agent_id AND status = 'in-progress'`. Do not resume if the assignment changed.
**Warning signs:** Two agents claiming the same task simultaneously.

### Pitfall 6: PyPI environment name must match the Trusted Publisher configuration
**What goes wrong:** Publish fails with "invalid OIDC token" despite correct workflow structure.
**Why it happens:** The environment name in the workflow (e.g., `name: pypi`) must exactly match what is registered on PyPI under the project's Trusted Publisher settings.
**How to avoid:** Register the Trusted Publisher on PyPI before pushing the tag. Use `pypi` as the environment name (no spaces, lowercase).
**Warning signs:** "Token request failed" or "invalid claims" in the publish step output.

### Pitfall 7: `_write_state_file()` does not persist `current_task_id`
**What goes wrong:** Crash recovery reads state file but `current_task_id` is always `None`.
**Why it happens:** Current `_write_state_file()` always writes `"current_task_id": None` (hardcoded).
**How to avoid:** Update `_write_state_file()` to accept the current task ID as a parameter, or read it from `self._current_task_id` instance variable. The WorkerAgent must set this when a task is claimed and clear it when submitted.
**Warning signs:** State file on disk always has `"current_task_id": null`.

---

## Code Examples

Verified patterns from existing codebase and official sources:

### Existing `_write_state_file()` — needs extension
```python
# Source: runtime/heartbeat.py line 113-119
async def _write_state_file(self) -> None:
    """Write {last_heartbeat, current_task_id} atomically via tmp + Path.replace()."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {"last_heartbeat": _now_iso(), "current_task_id": None}  # ← extend this
    tmp = self._state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(self._state_path)
```

### Existing stuck detection pattern (AWOL mirrors this)
```python
# Source: runtime/boss.py _detect_stuck_tasks()
baseline = datetime.fromisoformat(baseline_str)
if baseline.tzinfo is None:
    baseline = baseline.replace(tzinfo=timezone.utc)  # Fix naive timestamp from SQLite
if now - baseline < STUCK_THRESHOLD:
    continue  # Not stuck yet
```

### Existing `notify_escalation()` call site pattern
```python
# Source: runtime/boss.py _promote_to_review() + runtime/notifier.py
await self._notifier.notify_escalation(task_id, reason)
```

### Existing `activity_log` insert pattern
```python
# Source: runtime/boss.py _escalate_task()
await db.execute(
    "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
    "VALUES (?, ?, ?, 'task_escalated', ?, ?)",
    (_uuid(), self._config.agent_id, task_id, json.dumps({...}), now),
)
```

### pytest-cov current configuration
```toml
# Source: pyproject.toml (already configured)
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=runtime --cov=factory --cov-report=term-missing --cov-fail-under=80"
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| PyPI API token in repo secrets | OIDC trusted publishing (`id-token: write`) | No stored long-lived credentials; token per-workflow-run |
| `twine upload` with `TWINE_PASSWORD` | `pypa/gh-action-pypi-publish@release/v1` | Attestations auto-generated (PEP 740); tokenless |
| `docker-compose` (hyphen, v1) | `docker compose` (space, v2) | Already correct in `smoke-test.yml` |
| Manual secret scanning | `trufflesecurity/trufflehog@main` | 700+ credential detectors with API verification |

**Deprecated/outdated:**
- `actions/checkout@v3` — use `@v4` (already established in project)
- `trufflesecurity/trufflehog@master` — use `@main` (master branch sunset)
- `pypa/gh-action-pypi-publish@master` — use `@release/v1`

---

## Open Questions

1. **Tool allowlist enforcement — current implementation gap**
   - What we know: `AgentConfig.tool_allowlist` exists as `list[str]` field. `WorkerAgent._execute_task()` makes LLM calls but does not currently validate tool calls against the allowlist.
   - What's unclear: Whether the test should test that an error is raised (strict enforcement) or that the call is logged-and-skipped (lenient). Both are valid v0.1.0 behaviors.
   - Recommendation: Log + skip is safer for v0.1.0 (no agent crash from a disallowed call); raise a custom `DisallowedToolCallError` as the strict option. The test should be written for whichever behavior is implemented — the test must match the implementation choice. The planner should pick one and implement consistently.

2. **AWOL alert deduplication**
   - What we know: Boss tick interval is 10 minutes; without deduplication, an AWOL agent triggers a new alert every 10 minutes.
   - What's unclear: Whether a per-session in-memory set (cleared on restart) is sufficient, or whether a DB flag is needed for persistence across boss restarts.
   - Recommendation: In-memory `self._alerted_awol: set[str]` is sufficient for v0.1.0. The user is expected to respond quickly once notified. No DB schema change needed.

3. **TestPyPI project name registration**
   - What we know: The workflow must be written before the tag is pushed. TestPyPI trusted publisher registration is a one-time manual step on TestPyPI.org.
   - What's unclear: Whether the project name `agent-factory` is available on TestPyPI.
   - Recommendation: The planner should include a manual pre-task: register Trusted Publisher on both TestPyPI and PyPI before the publish workflow is merged and the tag is cut.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x + pytest-cov 5.x |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_security.py -x` |
| Full suite command | `pytest` (all 128+ tests with `--cov-fail-under=80`) |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| SEC-01 | Tool allowlist blocks disallowed call | unit | `pytest tests/test_security.py::test_tool_allowlist_blocks_disallowed_call -x` | ❌ Wave 0 |
| SEC-02 | Cross-cluster DB isolation (path-based) | unit | `pytest tests/test_security.py::test_cross_cluster_db_isolation -x` | ❌ Wave 0 |
| AWOL-01 | Boss detects agent missed 3+ heartbeats | unit | `pytest tests/test_boss.py -k awol -x` | ❌ Wave 0 (new test in test_boss.py) |
| AWOL-02 | Boss calls notifier.notify_escalation for AWOL | unit | `pytest tests/test_boss.py -k awol -x` | ❌ Wave 0 |
| CRASH-01 | Agent resumes in-progress task on restart | unit | `pytest tests/test_heartbeat.py -k resume -x` | ❌ Wave 0 |
| CRASH-02 | Agent skips resume if task re-assigned | unit | `pytest tests/test_heartbeat.py -k resume -x` | ❌ Wave 0 |
| SECRETS-01 | No hardcoded secrets in codebase | CI gate | truffleHog in `.github/workflows/security.yml` | ❌ Wave 0 |
| COV-01 | 80%+ test coverage maintained | CI gate | `pytest --cov-fail-under=80` | ✅ Already enforced |
| PKG-01 | `pip install agent-factory` installs runtime+factory | smoke | manual TestPyPI install check | N/A (manual) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_security.py -x` (new tests) or `pytest tests/test_boss.py -k awol -x` (AWOL tests)
- **Per wave merge:** `pytest` (full suite, must stay GREEN with 80%+ coverage)
- **Phase gate:** Full suite green + truffleHog green + TestPyPI upload successful before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_security.py` — covers SEC-01, SEC-02
- [ ] AWOL test stubs in `tests/test_boss.py` — covers AWOL-01, AWOL-02
- [ ] Crash recovery test stubs in `tests/test_heartbeat.py` — covers CRASH-01, CRASH-02
- [ ] `.github/workflows/security.yml` (or truffleHog step in `smoke-test.yml`) — covers SECRETS-01
- [ ] `.github/workflows/publish.yml` — covers PKG-01 pipeline
- [ ] `CHANGELOG.md` at project root — covers release docs

---

## Sources

### Primary (HIGH confidence)
- PyPI official docs — https://docs.pypi.org/trusted-publishers/using-a-publisher/ — OIDC workflow structure, `id-token: write` requirement
- Python Packaging Guide — https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/ — full multi-job workflow with artifact sharing
- `pypa/gh-action-pypi-publish` GitHub — https://github.com/marketplace/actions/pypi-publish — TestPyPI `repository-url` parameter, `release/v1` pin
- `trufflesecurity/trufflehog` GitHub — https://github.com/marketplace/actions/trufflehog-oss — `fetch-depth: 0` requirement, `extra_args` pattern
- Project source: `runtime/heartbeat.py`, `runtime/boss.py`, `runtime/worker.py`, `runtime/config.py`, `runtime/notifier.py`, `pyproject.toml`, `.github/workflows/smoke-test.yml` — existing patterns

### Secondary (MEDIUM confidence)
- `softprops/action-gh-release@v2` — https://github.com/softprops/action-gh-release — `contents: write` permission, `files` glob pattern
- Keep a Changelog — https://keepachangelog.com/en/1.0.0/ — CHANGELOG.md structural conventions

### Tertiary (LOW confidence)
- None — all critical claims verified against official sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pyproject.toml already correct; CI action versions verified against official sources
- Architecture: HIGH — all patterns mirror existing codebase conventions (Phase 3/4 patterns)
- Pitfalls: HIGH — verified against official docs (fetch-depth, id-token scope) + established project patterns

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (30 days; PyPI/GH Actions APIs are stable)
