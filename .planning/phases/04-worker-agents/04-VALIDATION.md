---
phase: 4
slug: worker-agents
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| **Quick run command** | `pytest tests/test_worker.py -x` |
| **Full suite command** | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_worker.py -x`
- **After every plan wave:** Run `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-W0-01 | 01 | 0 | W-01..W-18 stubs | unit | `pytest tests/test_worker.py -x` | ❌ W0 | ⬜ pending |
| 4-W0-02 | 01 | 0 | W-02 | unit | `pytest tests/test_config.py -x` | ✅ extend | ⬜ pending |
| 4-01-01 | 01 | 1 | W-02 | unit | `pytest tests/test_config.py -x` | ✅ | ⬜ pending |
| 4-01-02 | 01 | 1 | W-03 | unit | `pytest tests/test_worker.py::test_load_agent_config_merge -x` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | W-04 | unit | `pytest tests/test_worker.py::test_schema_migration_idempotent -x` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | W-01 | unit | `pytest tests/test_worker.py::test_worker_inherits_base_agent -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 2 | W-05 | unit | `pytest tests/test_worker.py::test_resume_first -x` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 2 | W-06 | unit | `pytest tests/test_worker.py::test_claim_by_role -x` | ❌ W0 | ⬜ pending |
| 4-02-04 | 02 | 2 | W-07 | unit | `pytest tests/test_worker.py::test_atomic_claim_guard -x` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 2 | W-08 | unit | `pytest tests/test_worker.py::test_first_execution_prompt -x` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 2 | W-09 | unit | `pytest tests/test_worker.py::test_reexecution_prompt -x` | ❌ W0 | ⬜ pending |
| 4-03-03 | 03 | 2 | W-10 | unit | `pytest tests/test_worker.py::test_execute_task_full_cycle -x` | ❌ W0 | ⬜ pending |
| 4-03-04 | 03 | 2 | W-11 | unit | `pytest tests/test_worker.py::test_document_version_increment -x` | ❌ W0 | ⬜ pending |
| 4-03-05 | 03 | 2 | W-18 | unit | `pytest tests/test_worker.py::test_no_tasks_noop -x` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 3 | W-12 | unit | `pytest tests/test_worker.py::test_fetch_pending_reviews -x` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 3 | W-13 | unit | `pytest tests/test_worker.py::test_review_uses_sonnet -x` | ❌ W0 | ⬜ pending |
| 4-04-03 | 04 | 3 | W-14 | unit | `pytest tests/test_worker.py::test_review_decision_parsed -x` | ❌ W0 | ⬜ pending |
| 4-04-04 | 04 | 3 | W-15 | unit | `pytest tests/test_worker.py::test_review_posts_comment_and_updates_status -x` | ❌ W0 | ⬜ pending |
| 4-04-05 | 04 | 3 | W-16 | unit | `pytest tests/test_worker.py::test_review_independent -x` | ❌ W0 | ⬜ pending |
| 4-04-06 | 04 | 3 | W-17 | unit | `pytest tests/test_worker.py::test_review_skips_no_document -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_worker.py` — 18 stubs (W-01..W-18), all RED initially
- [ ] `tests/test_config.py` — extend with `system_prompt` + `tool_allowlist` field coverage (W-02)
- [ ] No framework install needed — pytest + pytest-asyncio already configured in `pyproject.toml`

*Existing infrastructure covers all phase requirements — no new test tooling needed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
