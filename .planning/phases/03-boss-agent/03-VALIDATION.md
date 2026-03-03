---
phase: 3
slug: boss-agent
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-02
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

| Task | Plan | Wave | Behavior | Test Type | Command | File Exists | Status |
|------|------|------|----------|-----------|---------|-------------|--------|
| Schema + tabulate | 03-00 | 0 | reviewer_roles in tasks table | structural | `python -c "import sqlite3..."` | ❌ W0 | ⬜ pending |
| Boss test stubs | 03-00 | 0 | 25 stubs collected | collect | `pytest --collect-only -q` | ❌ W0 | ⬜ pending |
| BossAgent structure | 03-01 | 1 | is BaseAgent, has _llm, counter=0 | unit | `pytest tests/test_boss.py -k "is_base_agent or has_llm or has_heartbeat"` | ❌ W0 | ⬜ pending |
| Peer review promotion | 03-01 | 1 | peer_review → review when all approved | unit | `pytest tests/test_boss.py -k promote` | ❌ W0 | ⬜ pending |
| Rejection handling | 03-01 | 1 | any rejection → in-progress | unit | `pytest tests/test_boss.py -k rejection` | ❌ W0 | ⬜ pending |
| Goal decomposition | 03-01 | 1 | LLM → 3-5 tasks inserted | unit (mocked) | `pytest tests/test_boss.py -k decompose` | ❌ W0 | ⬜ pending |
| Reviewer roles JSON | 03-01 | 1 | reviewer_roles stored as JSON | unit | `pytest tests/test_boss.py -k reviewer_roles` | ❌ W0 | ⬜ pending |
| Re-review upsert | 03-01 | 1 | INSERT OR REPLACE on rejection | unit | `pytest tests/test_boss.py -k re_review` | ❌ W0 | ⬜ pending |
| Stuck haiku→sonnet | 03-02 | 2 | model_tier escalates | unit | `pytest tests/test_boss.py -k haiku_to_sonnet` | ❌ W0 | ⬜ pending |
| Stuck sonnet→opus | 03-02 | 2 | model_tier escalates | unit | `pytest tests/test_boss.py -k sonnet_to_opus` | ❌ W0 | ⬜ pending |
| stuck_since set | 03-02 | 2 | NULL → timestamp on first escalation | unit | `pytest tests/test_boss.py -k stuck_since` | ❌ W0 | ⬜ pending |
| Second intervention | 03-02 | 2 | LLM hint posted as task_comment | unit (mocked) | `pytest tests/test_boss.py -k second_intervention` | ❌ W0 | ⬜ pending |
| Escalation activity log | 03-02 | 2 | action=task_escalated with JSON details | unit | `pytest tests/test_boss.py -k activity_log` | ❌ W0 | ⬜ pending |
| Gap-fill every 3 HBs | 03-02 | 2 | called on HB 3,6,9 not 1,2 | unit | `pytest tests/test_boss.py -k gap_fill` | ❌ W0 | ⬜ pending |
| Goal completion | 03-02 | 2 | LLM True → goal.status=completed | unit (mocked) | `pytest tests/test_boss.py -k goal_completion` | ❌ W0 | ⬜ pending |
| CLI goal set | 03-03 | 3 | inserts goal, triggers decompose | integration | `pytest tests/test_boss_cli.py -k goal_set` | ❌ W0 | ⬜ pending |
| CLI tasks list table | 03-03 | 3 | tabulate table with correct columns | integration | `pytest tests/test_boss_cli.py -k table_output` | ❌ W0 | ⬜ pending |
| CLI tasks filter | 03-03 | 3 | --status filters correctly | integration | `pytest tests/test_boss_cli.py -k status_filter` | ❌ W0 | ⬜ pending |
| CLI tasks JSON | 03-03 | 3 | --json outputs valid JSON array | integration | `pytest tests/test_boss_cli.py -k json_output` | ❌ W0 | ⬜ pending |
| CLI agents status | 03-03 | 3 | table with agent rows | integration | `pytest tests/test_boss_cli.py -k agents_status` | ❌ W0 | ⬜ pending |
| CLI approve review | 03-03 | 3 | exit 0, status=approved in DB | integration | `pytest tests/test_boss_cli.py -k approve_review` | ❌ W0 | ⬜ pending |
| CLI approve wrong | 03-03 | 3 | exit 1 with error message | integration | `pytest tests/test_boss_cli.py -k wrong_state` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_boss.py` — 18 unit test stubs (BossAgent behaviors)
- [ ] `tests/test_boss_cli.py` — 7 CLI integration test stubs
- [ ] `runtime/schema.sql` — reviewer_roles TEXT column added to tasks table
- [ ] `pyproject.toml` — tabulate>=0.9.0 added to dependencies

*(Existing pytest-asyncio infrastructure from Phase 2 covers all execution requirements — no new framework install needed.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live LLM decomposition quality | Boss Agent — goal decomposition | Requires ANTHROPIC_API_KEY + real API call | `cluster goal set "Write a Python utility library"` with live key; verify 3-5 meaningful tasks created |
| Live stuck detection timing | Boss Agent — stuck detection | Requires 30+ min real wait or manual timestamp injection | Run cluster with short interval; inject old `updated_at` timestamp; verify escalation fires within one heartbeat |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — set by 03-04-PLAN.md execution
