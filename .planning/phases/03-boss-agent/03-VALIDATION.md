---
phase: 3
slug: boss-agent
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-02
completed: 2026-03-03
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-asyncio 0.24+ |
| **Config file** | pyproject.toml — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| **Quick run command** | `pytest tests/test_boss.py tests/test_boss_cli.py -x --no-cov` |
| **Full suite command** | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_boss.py tests/test_boss_cli.py -x --no-cov`
- **After every plan wave:** Run `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task | Plan | Wave | Behavior | Test Type | Command | Status |
|------|------|------|----------|-----------|---------|--------|
| Schema + tabulate | 03-00 | 0 | reviewer_roles column in schema | unit | `python -c "import sqlite3..."` | green |
| Boss test stubs | 03-00 | 0 | 25 stubs collected | collect | `pytest --collect-only` | green |
| BossAgent structure | 03-01 | 1 | is BaseAgent, has _llm, counter=0 | unit | `pytest tests/test_boss.py -k structure` | green |
| Peer review promotion | 03-01 | 1 | peer_review -> review when all approved | unit | `pytest tests/test_boss.py -k promote` | green |
| Rejection handling | 03-01 | 1 | any rejection -> in-progress, reset reviews | unit | `pytest tests/test_boss.py -k rejection` | green |
| Goal decomposition | 03-01 | 1 | LLM -> 3-5 tasks inserted | unit (mocked) | `pytest tests/test_boss.py -k decompose` | green |
| Reviewer roles | 03-01 | 1 | reviewer_roles stored as JSON | unit | `pytest tests/test_boss.py -k reviewer_roles` | green |
| Re-review upsert | 03-01 | 1 | INSERT OR REPLACE on rejection | unit | `pytest tests/test_boss.py -k re_review` | green |
| Stuck detection haiku->sonnet | 03-02 | 2 | model_tier escalates | unit | `pytest tests/test_boss.py -k haiku_to_sonnet` | green |
| Stuck detection sonnet->opus | 03-02 | 2 | model_tier escalates | unit | `pytest tests/test_boss.py -k sonnet_to_opus` | green |
| stuck_since set | 03-02 | 2 | NULL -> timestamp on first escalation | unit | `pytest tests/test_boss.py -k stuck_since` | green |
| Second intervention | 03-02 | 2 | LLM hint posted as task_comment | unit (mocked) | `pytest tests/test_boss.py -k second_intervention` | green |
| Escalation activity log | 03-02 | 2 | action=task_escalated with JSON details | unit | `pytest tests/test_boss.py -k activity_log` | green |
| Gap-fill every 3 heartbeats | 03-02 | 2 | called on 3,6,9 not 1,2 | unit | `pytest tests/test_boss.py -k gap_fill` | green |
| Goal completion | 03-02 | 2 | LLM True -> goal.status=completed | unit (mocked) | `pytest tests/test_boss.py -k goal_completion` | green |
| CLI goal set | 03-03 | 3 | inserts goal, triggers decompose | integration | `pytest tests/test_boss_cli.py -k goal_set` | green |
| CLI tasks list table | 03-03 | 3 | tabulate table with correct columns | integration | `pytest tests/test_boss_cli.py -k table_output` | green |
| CLI tasks list filter | 03-03 | 3 | --status filters correctly | integration | `pytest tests/test_boss_cli.py -k status_filter` | green |
| CLI tasks list JSON | 03-03 | 3 | --json outputs valid JSON array | integration | `pytest tests/test_boss_cli.py -k json_output` | green |
| CLI agents status | 03-03 | 3 | table with agent rows | integration | `pytest tests/test_boss_cli.py -k agents_status` | green |
| CLI approve review | 03-03 | 3 | exit 0, status=approved in DB | integration | `pytest tests/test_boss_cli.py -k approve_review` | green |
| CLI approve wrong state | 03-03 | 3 | exit 1 with error message | integration | `pytest tests/test_boss_cli.py -k wrong_state` | green |

---

## Wave 0 Requirements

All Wave 0 gaps were addressed in plan 03-00:
- [x] `tests/test_boss.py` — 19 stubs created (plan said 18; template authoritative)
- [x] `tests/test_boss_cli.py` — 7 stubs created
- [x] `runtime/schema.sql` — reviewer_roles TEXT column added
- [x] `pyproject.toml` — tabulate>=0.9.0 added

---

## Manual-Only Verifications

| Behavior | Why Manual | Test Instructions |
|----------|------------|-------------------|
| Live LLM decomposition quality | Requires ANTHROPIC_API_KEY and real API call | `cluster goal set "Write a Python utility library"` with real key; verify 3-5 meaningful tasks created |
| Live stuck detection timing | Requires 30+ min wait | Run cluster with short interval, inject old timestamp, verify escalation fires within one heartbeat |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete 2026-03-03
