---
phase: 1
slug: core-runtime-database-state-machine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-02-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio (asyncio_mode = "auto") |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | schema.sql | unit | `pytest tests/test_database.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | DatabaseManager | unit | `pytest tests/test_database.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | WAL + pragmas | unit | `pytest tests/test_database.py::test_wal_mode -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | Pydantic models | unit | `pytest tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | TaskStatus enum | unit | `pytest tests/test_models.py::test_task_status -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | State machine transitions | unit | `pytest tests/test_state_machine.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 2 | Invalid transitions | unit | `pytest tests/test_state_machine.py::test_invalid_transitions -x -q` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 2 | Migration runner db up | integration | `pytest tests/test_migrations.py -x -q` | ❌ W0 | ⬜ pending |
| 1-04-02 | 04 | 2 | Migration runner db reset | integration | `pytest tests/test_migrations.py::test_db_reset -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_database.py` — stubs for DatabaseManager, WAL, pragma tests
- [ ] `tests/test_models.py` — stubs for all 7 Pydantic model tests
- [ ] `tests/test_state_machine.py` — stubs for all valid/invalid transition tests
- [ ] `tests/test_migrations.py` — stubs for `db up` / `db reset` tests
- [ ] `tests/conftest.py` — shared async fixtures (tmp db path, db manager instance)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| WAL mode persists after reconnect | PRAGMA journal_mode=WAL | Requires re-opening connection | `PRAGMA journal_mode` after close/reopen returns 'wal' |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
