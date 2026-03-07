---
phase: 05-factory-cluster-core-product
plan: "01"
subsystem: factory
tags: [pydantic, yaml, docker, shutil, generator, models]

# Dependency graph
requires:
  - phase: 05-00
    provides: factory package scaffold, 17 xfail test stubs (GEN-01 to GEN-05), factory/models.py and factory/generator.py stubs

provides:
  - RoleSpec, RolesResult, FitCheckResult Pydantic models (fully implemented in factory/models.py)
  - Seven pure-function artifact generators in factory/generator.py (render_agent_yaml, render_docker_compose, render_cluster_yaml, render_launch_sh, render_dockerfile, render_requirements_txt, copy_runtime)
  - GEN-01 through GEN-05 all GREEN (5 tests passing, xfail markers removed)

affects:
  - 05-02 (pipeline.py uses generator functions to produce cluster artifact files)
  - 05-03 (factory CLI calls pipeline which calls generators)
  - 05-04 (e2e tests rely on generator output structure)

# Tech tracking
tech-stack:
  added: [pyyaml (yaml.dump), shutil.copytree, textwrap.dedent]
  patterns:
    - "Pure function generators — all take typed inputs, return strings (or copy files); no LLM calls, no side effects except copy_runtime"
    - "yaml.dump() for all YAML output — never f-string YAML"
    - "textwrap.dedent for multiline shell scripts"
    - "Baseline packages hardcoded in _BASELINE_PACKAGES list; role tool_allowlist entries merged via set union then sorted"
    - "Dockerfile base image selected by any(r.requires_glibc for r in roles)"

key-files:
  created: []
  modified:
    - factory/models.py
    - factory/generator.py
    - tests/test_factory_generator.py

key-decisions:
  - "yaml.dump(default_flow_style=False, allow_unicode=True) used for all YAML output — ensures valid multi-line YAML, never f-string YAML"
  - "render_dockerfile uses python:3.12-slim default; switches to ubuntu:22.04 when any role has requires_glibc=True"
  - "render_requirements_txt baseline packages: anthropic, aiosqlite, click, pydantic, tabulate — always included regardless of roles"
  - "_offset helper function removed (dead code) — stagger offset passed explicitly as parameter to render_agent_yaml"
  - "xfail markers removed from test_factory_generator.py after GEN-01 to GEN-05 all pass"

patterns-established:
  - "Stagger offset formula: offset_i = round(i * (interval_seconds / total_count), 1) where total_count = len(roles) + 2"
  - "docker-compose always includes boss (index 0) and critic (index 1) as structural services; worker roles start at index 2"
  - "copy_runtime: shutil.copytree(Path(__file__).parent.parent / 'runtime', dest_dir / 'runtime', dirs_exist_ok=True)"

requirements-completed: [GEN-01, GEN-02, GEN-03, GEN-04, GEN-05]

# Metrics
duration: 6min
completed: 2026-03-07
---

# Phase 5 Plan 01: Factory Models and Generator Summary

**Deterministic YAML/Dockerfile/shell-script artifact generators using yaml.dump() and Pydantic RoleSpec models — no LLM calls**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-07T11:49:47Z
- **Completed:** 2026-03-07T11:55:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented `factory/models.py` with full Pydantic models: `RoleSpec` (name, responsibilities, personality_system_prompt, tool_allowlist, requires_glibc), `RolesResult`, `FitCheckResult`
- Implemented all seven artifact generators in `factory/generator.py`: `render_agent_yaml`, `render_docker_compose`, `render_cluster_yaml`, `render_launch_sh`, `render_dockerfile`, `render_requirements_txt`, `copy_runtime`
- Promoted GEN-01 through GEN-05 from xfail stubs to GREEN — 116 tests passing at 94.01% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement factory/models.py — RoleSpec, RolesResult, FitCheckResult** - `9643738` (feat)
2. **Task 2: Implement factory/generator.py — seven artifact generator functions** - `5dac3c9` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `factory/models.py` — Added module docstring, `from __future__ import annotations`; RoleSpec, RolesResult, FitCheckResult Pydantic models
- `factory/generator.py` — Full implementation of 7 generator functions replacing NotImplementedError stubs
- `tests/test_factory_generator.py` — Removed xfail markers from all 5 tests (GEN-01 to GEN-05 now GREEN)

## Decisions Made

- Used `yaml.dump(default_flow_style=False, allow_unicode=True)` for all YAML — never f-string YAML for correctness
- `render_dockerfile` inspects `any(r.requires_glibc for r in roles)` to select base image: `python:3.12-slim` vs `ubuntu:22.04`
- Baseline packages (`anthropic`, `aiosqlite`, `click`, `pydantic`, `tabulate`) always included in `render_requirements_txt` regardless of roles
- Removed dead `_offset` inner function from `render_docker_compose` (stagger offset is a caller concern, not docker-compose concern)
- boss=index 0, critic=index 1, worker roles start at index 2 in docker-compose service ordering

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `factory/models.py` and `factory/generator.py` fully implemented and tested
- GEN-01 to GEN-05 all GREEN; 116 tests at 94.01% coverage
- Ready for Plan 05-02: `factory/pipeline.py` LLM-orchestrated role decomposition pipeline that calls these generators

## Self-Check: PASSED

- factory/models.py: FOUND
- factory/generator.py: FOUND
- tests/test_factory_generator.py: FOUND
- .planning/phases/05-factory-cluster-core-product/05-01-SUMMARY.md: FOUND
- Commit 9643738 (Task 1): FOUND
- Commit 5dac3c9 (Task 2): FOUND
- 116 tests GREEN at 94.01% coverage: CONFIRMED

---
*Phase: 05-factory-cluster-core-product*
*Completed: 2026-03-07*
