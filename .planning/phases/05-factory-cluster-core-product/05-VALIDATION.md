---
phase: 5
slug: factory-cluster-core-product
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/test_factory_generator.py tests/test_factory_pipeline.py tests/test_factory_cli.py -x` |
| **Full suite command** | `pytest --cov=runtime --cov=factory --cov-fail-under=80` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_factory_generator.py tests/test_factory_pipeline.py tests/test_factory_cli.py -x`
- **After every plan wave:** Run `pytest --cov=runtime --cov=factory --cov-fail-under=80`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-GEN-01 | generator | 0 | GEN-01 | unit | `pytest tests/test_factory_generator.py::test_render_agent_yaml -x` | ❌ W0 | ⬜ pending |
| 5-GEN-02 | generator | 0 | GEN-02 | unit | `pytest tests/test_factory_generator.py::test_render_docker_compose -x` | ❌ W0 | ⬜ pending |
| 5-GEN-03 | generator | 0 | GEN-03 | unit | `pytest tests/test_factory_generator.py::test_render_cluster_yaml -x` | ❌ W0 | ⬜ pending |
| 5-GEN-04 | generator | 0 | GEN-04 | unit | `pytest tests/test_factory_generator.py::test_launch_sh_fails_without_key -x` | ❌ W0 | ⬜ pending |
| 5-GEN-05 | generator | 0 | GEN-05 | unit | `pytest tests/test_factory_generator.py::test_copy_runtime -x` | ❌ W0 | ⬜ pending |
| 5-PIPELINE-01 | pipeline | 1 | PIPELINE-01 | unit (mock LLM) | `pytest tests/test_factory_pipeline.py::test_pipeline_produces_roles -x` | ❌ W0 | ⬜ pending |
| 5-PIPELINE-02 | pipeline | 1 | PIPELINE-02 | unit (mock LLM) | `pytest tests/test_factory_pipeline.py::test_fit_check_retry -x` | ❌ W0 | ⬜ pending |
| 5-PIPELINE-03 | pipeline | 1 | PIPELINE-03 | unit | `pytest tests/test_factory_pipeline.py::test_structural_roles_present -x` | ❌ W0 | ⬜ pending |
| 5-CLI-01 | cli | 2 | CLI-01 | unit (mock subprocess) | `pytest tests/test_factory_cli.py::test_create_returns_immediately -x` | ❌ W0 | ⬜ pending |
| 5-CLI-02 | cli | 2 | CLI-02 | unit (mock DB) | `pytest tests/test_factory_cli.py::test_status_in_progress -x` | ❌ W0 | ⬜ pending |
| 5-CLI-03 | cli | 2 | CLI-03 | unit (mock DB) | `pytest tests/test_factory_cli.py::test_status_complete -x` | ❌ W0 | ⬜ pending |
| 5-CLI-04 | cli | 2 | CLI-04 | unit (mock DB) | `pytest tests/test_factory_cli.py::test_list_clusters -x` | ❌ W0 | ⬜ pending |
| 5-CLI-05 | cli | 2 | CLI-05 | unit (mock pipeline) | `pytest tests/test_factory_cli.py::test_add_role -x` | ❌ W0 | ⬜ pending |
| 5-CLI-06 | cli | 2 | CLI-06 | unit | `pytest tests/test_factory_cli.py::test_name_flag_and_autoslug -x` | ❌ W0 | ⬜ pending |
| 5-CLI-07 | cli | 2 | CLI-07 | unit | `pytest tests/test_factory_cli.py::test_collision_policy -x` | ❌ W0 | ⬜ pending |
| 5-E2E-01 | e2e | 3 | E2E-01 | e2e (mock LLM) | `pytest tests/test_factory_e2e.py::test_full_artifact_created -x` | ❌ W0 | ⬜ pending |
| 5-E2E-02 | e2e | 3 | E2E-02 | e2e (real SQLite) | `pytest tests/test_factory_e2e.py::test_db_seeded_correctly -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Note on GEN-02:** The automated command runs `test_render_docker_compose` in `tests/test_factory_generator.py` (unit test for the render function). Docker Compose validation (`docker compose config`) is a manual-only verification listed below — it requires Docker installed and is skipped in CI.

---

## Wave 0 Requirements

- [ ] `tests/test_factory_generator.py` — stubs for GEN-01 through GEN-05
- [ ] `tests/test_factory_pipeline.py` — stubs for PIPELINE-01 through PIPELINE-03
- [ ] `tests/test_factory_cli.py` — stubs for CLI-01 through CLI-07
- [ ] `tests/test_factory_e2e.py` — stubs for E2E-01, E2E-02
- [ ] `factory/__init__.py` — empty package marker
- [ ] `factory/models.py` — RoleSpec, RolesResult, FitCheckResult stubs
- [ ] `factory/generator.py` — function stubs including render_dockerfile, render_requirements_txt
- [ ] `factory/pipeline.py` — pipeline function stubs
- [ ] `factory/boss.py` — FactoryBossAgent stub
- [ ] `factory/workers.py` — FactoryResearcherAgent, FactorySecurityCheckerAgent, FactoryExecutorAgent stubs
- [ ] `factory/runner.py` — subprocess entry point stub
- [ ] Update `pyproject.toml`: add `"factory"` to wheel packages, add `--cov=factory` to addopts

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose config` validates generated docker-compose.yml | GEN-02 | Requires Docker to be installed; skipped in CI if absent | Run `cd clusters/<name> && docker compose config`; confirm no errors |
| `./launch.sh` fails with clear error when ANTHROPIC_API_KEY unset | GEN-04 | Shell script behavior; automated test covers exit code, manual confirms message | `unset ANTHROPIC_API_KEY && ./launch.sh`; confirm error message matches spec |
| Fire-and-forget: `agent-factory create` returns to shell immediately | CLI-01 | Subprocess detachment behavior | `time agent-factory create "test goal"`; confirm returns in <1s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
