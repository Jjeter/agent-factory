---
phase: 2
slug: agent-heartbeat-framework
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-01
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-asyncio 0.24+ |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/test_heartbeat.py tests/test_config.py tests/test_notifier.py -x` |
| **Full suite command** | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_config.py tests/test_notifier.py tests/test_heartbeat.py -x`
- **After every plan wave:** Run `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| Wave 0 | stub | 0 | HB-01..HB-13 | unit/integration | `pytest tests/test_config.py tests/test_notifier.py tests/test_heartbeat.py -x` | ❌ W0 | ⬜ pending |
| config | 01 | 1 | HB-01, HB-02 | unit | `pytest tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| notifier | 01 | 1 | HB-03 | unit | `pytest tests/test_notifier.py -x` | ❌ W0 | ⬜ pending |
| heartbeat | 02 | 2 | HB-04..HB-13 | unit+integration | `pytest tests/test_heartbeat.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — stubs for HB-01, HB-02
- [ ] `tests/test_notifier.py` — stubs for HB-03
- [ ] `tests/test_heartbeat.py` — stubs for HB-04 through HB-13
- [ ] `runtime/state/` added to `.gitignore`

*Framework already installed — no install step needed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
