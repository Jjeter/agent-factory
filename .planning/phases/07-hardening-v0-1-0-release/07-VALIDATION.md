---
phase: 7
slug: hardening-v0-1-0-release
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x + pytest-cov 5.x |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_security.py -x` |
| **Full suite command** | `pytest` (all tests with `--cov-fail-under=80`) |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_security.py -x` (new security tests) or `pytest tests/test_boss.py -k awol -x` / `pytest tests/test_heartbeat.py -k resume -x` (for AWOL/crash tasks)
- **After every plan wave:** Run `pytest` (full suite, must stay GREEN with 80%+ coverage)
- **Before `/gsd:verify-work`:** Full suite green + truffleHog green + TestPyPI upload successful
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | SEC-01 | unit | `pytest tests/test_security.py::test_tool_allowlist_blocks_disallowed_call -x` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 0 | SEC-02 | unit | `pytest tests/test_security.py::test_cross_cluster_db_isolation -x` | ❌ W0 | ⬜ pending |
| 7-01-03 | 01 | 0 | AWOL-01/02 | unit | `pytest tests/test_boss.py -k awol -x` | ❌ W0 | ⬜ pending |
| 7-01-04 | 01 | 0 | CRASH-01/02 | unit | `pytest tests/test_heartbeat.py -k resume -x` | ❌ W0 | ⬜ pending |
| 7-01-05 | 01 | 0 | SECRETS-01 | CI gate | `.github/workflows/security.yml` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | SEC-01 | unit | `pytest tests/test_security.py::test_tool_allowlist_blocks_disallowed_call -x` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | SEC-02 | unit | `pytest tests/test_security.py::test_cross_cluster_db_isolation -x` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 1 | AWOL-01 | unit | `pytest tests/test_boss.py -k awol -x` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 1 | AWOL-02 | unit | `pytest tests/test_boss.py -k awol -x` | ❌ W0 | ⬜ pending |
| 7-04-01 | 04 | 1 | CRASH-01 | unit | `pytest tests/test_heartbeat.py -k resume -x` | ❌ W0 | ⬜ pending |
| 7-04-02 | 04 | 1 | CRASH-02 | unit | `pytest tests/test_heartbeat.py -k resume -x` | ❌ W0 | ⬜ pending |
| 7-05-01 | 05 | 2 | PKG-01 | smoke | Manual TestPyPI install check | N/A | ⬜ pending |
| 7-05-02 | 05 | 2 | COV-01 | CI gate | `pytest --cov-fail-under=80` | ✅ | ⬜ pending |
| 7-06-01 | 06 | 2 | DOCS-01 | manual | Review CHANGELOG.md content | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_security.py` — stubs for SEC-01 (tool allowlist), SEC-02 (cross-cluster DB isolation)
- [ ] AWOL test stubs in `tests/test_boss.py` — covers AWOL-01, AWOL-02
- [ ] Crash recovery test stubs in `tests/test_heartbeat.py` — covers CRASH-01, CRASH-02
- [ ] `.github/workflows/security.yml` — truffleHog CI gate covering SECRETS-01
- [ ] `.github/workflows/publish.yml` — TestPyPI → PyPI pipeline covering PKG-01

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pip install agent-factory` installs correctly | PKG-01 | Requires live TestPyPI/PyPI registry | After publish workflow succeeds: `pip install --index-url https://test.pypi.org/simple/ agent-factory && agent-factory --help` |
| CHANGELOG.md content quality | DOCS-01 | Human judgment on wording | Read CHANGELOG.md, verify v0.1.0 section summarizes all 6 phases accurately |
| GitHub release assets attached | PKG-01 | Requires live GitHub release | Verify `.whl` + `.tar.gz` attached to v0.1.0 release on GitHub |
| TruffleHog `security.yml` CI gate passes | SECRETS-01 | Requires repo push | Open PR, verify `Secret Scanning` check shows green in GitHub Actions |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
