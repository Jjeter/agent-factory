---
phase: 6
slug: demo-cluster-integration-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24+ |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `python -m pytest tests/test_factory_cli.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_factory_cli.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | Wave 0 stubs | unit | `python -m pytest tests/test_factory_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 6-01-02 | 01 | 0 | Wave 0 stubs | unit | `python -m pytest tests/test_demo_artifact.py -x -q` | ❌ W0 | ⬜ pending |
| 6-02-01 | 02 | 1 | factory approve | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_approve_success -x` | ❌ W0 | ⬜ pending |
| 6-02-02 | 02 | 1 | factory approve not-found | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_approve_cluster_not_found -x` | ❌ W0 | ⬜ pending |
| 6-02-03 | 02 | 1 | factory approve wrong-state | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_approve_wrong_state -x` | ❌ W0 | ⬜ pending |
| 6-02-04 | 02 | 1 | factory logs table | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_logs_table_output -x` | ❌ W0 | ⬜ pending |
| 6-02-05 | 02 | 1 | factory logs --json | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_logs_json_output -x` | ❌ W0 | ⬜ pending |
| 6-02-06 | 02 | 1 | factory logs --tail | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_logs_tail -x` | ❌ W0 | ⬜ pending |
| 6-02-07 | 02 | 1 | factory logs --agent | unit/CLI | `python -m pytest tests/test_factory_cli.py::test_logs_agent_filter -x` | ❌ W0 | ⬜ pending |
| 6-03-01 | 03 | 2 | factory demo exists | smoke | `python -m pytest tests/test_factory_cli.py::test_demo_exists -x` | ❌ W0 | ⬜ pending |
| 6-03-02 | 03 | 2 | demo cluster artifact files | structural | `python -m pytest tests/test_demo_artifact.py -x` | ❌ W0 | ⬜ pending |
| 6-03-03 | 03 | 2 | cluster.db pre-seeded | unit | `python -m pytest tests/test_demo_artifact.py::test_cluster_db_seeded -x` | ❌ W0 | ⬜ pending |
| 6-04-01 | 04 | 3 | README.md exists | structural | `python -m pytest tests/test_demo_artifact.py::test_readme_exists -x` | ❌ W0 | ⬜ pending |
| 6-04-02 | 04 | 3 | CI smoke test | manual | Review `.github/workflows/smoke-test.yml` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_factory_cli.py` — add stubs: `test_approve_cluster_not_found`, `test_approve_wrong_state`, `test_approve_success`, `test_logs_cluster_not_found`, `test_logs_table_output`, `test_logs_json_output`, `test_logs_tail`, `test_logs_agent_filter`, `test_demo_exists`
- [ ] `tests/test_demo_artifact.py` — new file: covers committed artifact structure + DB seeding (`test_cluster_db_seeded`, `test_readme_exists`, artifact file existence checks)
- [ ] No new framework installation required — existing pytest + pytest-asyncio sufficient

*All stubs must xfail (not skip) so the suite remains runnable before implementation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `agent-factory demo` live polling loop displays progress | Demo UX | Requires real subprocess + LLM calls; cannot mock convincingly | Run `agent-factory demo` in a terminal; confirm `\r` line overwrites show task counts changing |
| README annotated trace matches actual output | Documentation accuracy | Requires running demo first | Run `agent-factory demo`, capture output, compare to README trace |
| CI GitHub Actions smoke test passes | CI integrity | Requires push to GitHub | Merge to main; check Actions tab for green smoke-test job |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
