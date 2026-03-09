# Phase 7: Hardening + v0.1.0 Release - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Security audit (secrets scan, tool allowlist enforcement, cross-cluster DB isolation), error resilience
(heartbeat AWOL detection, crash recovery), and shipping the package as a public v0.1.0 release
(PyPI publish via GitHub Actions, CHANGELOG.md, GitHub release with wheel + sdist). No new cluster
features, no web UI, no messaging integrations.

</domain>

<decisions>
## Implementation Decisions

### Package Release Format

- Publish to PyPI — `pip install agent-factory` works out of the box for end users
- Triggered by GitHub Actions on `git tag v0.1.0` push (OIDC trusted publishing — no stored API token)
- Full system: both `runtime` and `factory` packages included (matches existing pyproject.toml declaration)
- TestPyPI gate before real PyPI: CI uploads to TestPyPI first; success gates the real PyPI upload

### Heartbeat Monitoring (AWOL Detection)

- Detection mechanism: compare `agent_status.last_heartbeat` timestamp — if `now - last_heartbeat > 3 * interval_seconds`, agent is AWOL
- Alert channel: `notifier.notify_escalation()` (stdout in v0.1.0) + `activity_log` entry (same pattern as existing model-tier escalation)
- Boss action: observe only — no auto-reassignment or restart attempt; user decides what to do

### Crash Recovery

- On startup, `BaseAgent._load_state()` (already called at `start()`) reads local state file
- If state file contains a previous in-progress task ID, and that task is still `in-progress` in the DB, the agent claims it back and resumes
- No change to task state machine — task was already claimed by this agent

### Security Audit

- **Secrets scan**: truffleHog runs as a CI gate (separate `security.yml` workflow or step in existing `smoke-test.yml`) on every push to `main` and every PR
- **Tool allowlist enforcement**: automated test in `tests/test_security.py` — mock LLM response returns a tool call for a tool not in the agent's allowlist; assert WorkerAgent raises an error or ignores it (does NOT forward the call)
- **Cross-cluster DB isolation**: automated test — create two independent DatabaseManager instances pointing to two different `tmp_path` DBs; seed cluster A; assert cluster B's DB has no data from A (proves structural path-based isolation)

### Release Documentation

- `CHANGELOG.md`: single v0.1.0 section, human-written high-level summary of capabilities shipped (factory cluster, boss/worker heartbeats, peer review gate, demo cluster, PyPI release). Readable for users discovering the project — not a raw commit dump.
- GitHub release: `v0.1.0` tag; wheel (`.whl`) + sdist (`.tar.gz`) attached as assets via GitHub Actions
- `CONTRIBUTING.md`: deferred — not for v0.1.0

### Claude's Discretion

- Exact threshold comparison formula (e.g., whether to use `>` or `>=` when counting missed heartbeats)
- Whether truffleHog runs as its own job or as a step inside `smoke-test.yml`
- Exact error type raised when disallowed tool call is detected (custom exception vs. assertion vs. log + skip)
- CHANGELOG wording and section structure

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `pyproject.toml`: already declares `version = "0.1.0"`, hatchling build backend, `runtime` + `factory` packages, and `agent-factory`/`cluster` CLI entry points — publish workflow needs no structural changes
- `.github/workflows/smoke-test.yml`: existing CI template using `actions/checkout@v4` and `docker compose` (v2); new `publish.yml` follows the same job structure
- `runtime/heartbeat.py — BaseAgent._load_state()`: already called at `start()` entry; extend this method to also check for a resumed in-progress task
- `runtime/heartbeat.py — BossAgent`: already has stuck-task detection logic; AWOL detection follows the same pattern (iterate `agent_status` rows, compare timestamps)
- `runtime/worker.py — WorkerAgent._execute_task()`: tool allowlist in `AgentConfig.tool_allowlist`; security test targets this method with a mocked LLM response
- `runtime/notifier.py — StdoutNotifier.notify_escalation()`: existing method; boss calls this for AWOL alerts (same as model-tier escalation)
- `runtime/database.py — DatabaseManager`: path-based construction; cross-cluster isolation test verifies two managers targeting different paths cannot read each other's data

### Established Patterns

- `activity_log` entries for all boss escalation actions (established in Phase 3): AWOL alerts follow the same write pattern
- `pytest.importorskip` inside test body for new modules (established across Phases 3-6): `tests/test_security.py` may need this if `runtime.worker` import is guarded
- `asyncio.run()` once per CLI command (established in Phase 1): publish workflow does not add CLI commands, no change needed

### Integration Points

- `.github/workflows/publish.yml` — new file; triggered by `v*` tag push; `permissions: id-token: write` for OIDC; TestPyPI step gates PyPI step; attaches `.whl` + `.tar.gz` to GitHub release
- `runtime/heartbeat.py` — `BossAgent` heartbeat loop: add `_check_awol_agents()` method called each boss tick
- `runtime/heartbeat.py` — `BaseAgent._load_state()`: extend to return the prior in-progress task ID if found; `start()` passes this to the first tick
- `tests/test_security.py` — new file: tool allowlist enforcement test + cross-cluster DB isolation test
- `CHANGELOG.md` — new file at project root
- `.github/workflows/` — add truffleHog step (to security.yml or smoke-test.yml)

</code_context>

<specifics>
## Specific Ideas

- The TestPyPI → PyPI gate is the key safety check before first public release — any build or metadata error surfaces there, not in front of real users
- AWOL detection reuses the `last_heartbeat` column already in `agent_status` — no schema migration needed
- Crash recovery is mostly a `_load_state()` extension — the heavy lifting (task claiming, resume-first claiming) was already built in Phase 4 (`WorkerAgent` resume-first logic in `do_own_tasks`)
- The security tests should live in a dedicated `tests/test_security.py` to make it easy to audit what was verified

</specifics>

<deferred>
## Deferred Ideas

- `agent-factory logs` streaming (real-time `tail -f`) — flagged in Phase 6 context; still deferred
- CONTRIBUTING.md — explicitly deferred from v0.1.0
- Docker image published to GitHub Container Registry (ghcr.io) — raised as a release option, deferred to v0.2+
- Nightly CI job running `agent-factory create` with real LLM calls — flagged in Phase 6 context; still deferred
- Agent status `stalled` flag in `cluster agents status` output — would pair well with AWOL detection; deferred since observe-only was chosen for v0.1.0

</deferred>

---

*Phase: 07-hardening-v0-1-0-release*
*Context gathered: 2026-03-09*
