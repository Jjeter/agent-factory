---
phase: 05-factory-cluster-core-product
plan: "00"
subsystem: factory
tags: [pydantic, factory, tdd-red, stubs, pytest-xfail]

# Dependency graph
requires:
  - phase: 04-worker-agents
    provides: WorkerAgent base class used by factory worker stubs
  - phase: 03-boss-agent
    provides: BossAgent base class used by FactoryBossAgent stub
  - phase: 01-core-runtime-database-state-machine
    provides: DatabaseManager and models used by E2E test stubs
provides:
  - factory Python package (importable, 7 stub modules)
  - factory/models.py: RoleSpec, RolesResult, FitCheckResult Pydantic models
  - factory/generator.py: 7 function stubs (render_agent_yaml, render_docker_compose, render_cluster_yaml, render_launch_sh, render_dockerfile, render_requirements_txt, copy_runtime)
  - factory/pipeline.py: 3 async function stubs (decompose_roles, fit_check, enrich_roles)
  - factory/boss.py: FactoryBossAgent(BossAgent) stub
  - factory/workers.py: FactoryResearcherAgent, FactorySecurityCheckerAgent, FactoryExecutorAgent stubs
  - factory/runner.py: run_factory() async entry point stub
  - 17 test stubs across 4 test files (all xfail — TDD RED contract established)
affects:
  - 05-01 (generator implementation — GEN-01 to GEN-05 test contracts)
  - 05-02 (pipeline implementation — PIPELINE-01 to PIPELINE-03 test contracts)
  - 05-03 (CLI implementation — CLI-01 to CLI-07 test contracts)
  - 05-04 (E2E — E2E-01 to E2E-02 test contracts)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pytest.importorskip inside test body (not module level) to prevent collection crash on stub-only modules
    - xfail stubs with explicit requirement IDs in reason strings (GEN-01, PIPELINE-02, etc.)
    - Pydantic BaseModel stubs as data contracts before any LLM integration
    - WorkerAgent pass-through subclasses — role behavior via AgentConfig.system_prompt at runtime

key-files:
  created:
    - factory/__init__.py
    - factory/models.py
    - factory/generator.py
    - factory/pipeline.py
    - factory/boss.py
    - factory/workers.py
    - factory/runner.py
    - tests/test_factory_generator.py
    - tests/test_factory_pipeline.py
    - tests/test_factory_cli.py
    - tests/test_factory_e2e.py
  modified:
    - pyproject.toml

key-decisions:
  - "pytest.importorskip inside test body (not module level) — consistent with Phase 3/4 pattern, prevents collection crash when factory stubs raise NotImplementedError"
  - "CLI-07 collision_policy test uses AND assertion (exit_code != 0 AND 'already exists' in output) — OR condition would xpass trivially since 'create' subcommand does not exist yet"
  - "FactoryResearcherAgent/FactorySecurityCheckerAgent/FactoryExecutorAgent are pass-through stubs inheriting WorkerAgent unchanged — role behavior injected via AgentConfig.system_prompt at runtime"
  - "FitCheckResult stub includes optional failing_role and reason fields — supports retry loop in pipeline implementation"
  - "generator.py includes render_dockerfile and render_requirements_txt stubs — required for standalone cluster Docker builds"

patterns-established:
  - "TDD RED gate pattern: stub package importable, all tests collectable, all xfail before any implementation"
  - "Pydantic models as data contracts: RoleSpec/RolesResult/FitCheckResult defined before generator/pipeline logic"

requirements-completed: [GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, PIPELINE-01, PIPELINE-02, PIPELINE-03, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07, E2E-01, E2E-02]

# Metrics
duration: 12min
completed: 2026-03-07
---

# Phase 5 Plan 00: Factory Package Scaffolding — TDD RED Gate Summary

**factory/ Python package with 7 stub modules and 17 xfail test stubs establishing the full Phase 5 test contract before any implementation**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-07T11:40:08Z
- **Completed:** 2026-03-07T11:52:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Created factory/ package with 7 importable stub modules (all raise NotImplementedError)
- Established Pydantic data contracts: RoleSpec, RolesResult, FitCheckResult with full field signatures
- Wrote 17 xfail test stubs across 4 test files covering GEN, PIPELINE, CLI, and E2E requirements
- Updated pyproject.toml with --cov=factory coverage and factory in wheel packages list
- Existing 111 tests remain GREEN at 95.76% coverage with factory stubs added

## Task Commits

Each task was committed atomically:

1. **Task 1: Factory package scaffolding + Pydantic stubs** - `4c92a69` (feat)
2. **Task 2: TDD RED — 17 test stubs across 4 test files** - `a7e6032` (test)

## Files Created/Modified

- `factory/__init__.py` - Empty package marker
- `factory/models.py` - RoleSpec, RolesResult, FitCheckResult Pydantic models
- `factory/generator.py` - 7 function stubs: render_agent_yaml, render_docker_compose, render_cluster_yaml, render_launch_sh, render_dockerfile, render_requirements_txt, copy_runtime
- `factory/pipeline.py` - 3 async function stubs: decompose_roles, fit_check, enrich_roles
- `factory/boss.py` - FactoryBossAgent(BossAgent) stub with decompose_goal override
- `factory/workers.py` - FactoryResearcherAgent, FactorySecurityCheckerAgent, FactoryExecutorAgent pass-through stubs
- `factory/runner.py` - run_factory() async entry point stub with __main__ guard
- `tests/test_factory_generator.py` - 5 xfail stubs (GEN-01 to GEN-05)
- `tests/test_factory_pipeline.py` - 3 xfail stubs (PIPELINE-01 to PIPELINE-03)
- `tests/test_factory_cli.py` - 7 xfail stubs (CLI-01 to CLI-07)
- `tests/test_factory_e2e.py` - 2 xfail stubs (E2E-01 to E2E-02)
- `pyproject.toml` - Added --cov=factory to addopts; factory to wheel packages list

## Decisions Made

- CLI-07 collision_policy assertion uses `AND` (exit_code != 0 AND "already exists" in output) rather than `OR` — the `OR` form would trivially xpass since the `create` subcommand doesn't exist yet, causing it to return exit_code=2 without ever running the collision check. Rule 1 auto-fix applied during Task 2.
- FactoryResearcherAgent, FactorySecurityCheckerAgent, FactoryExecutorAgent are pure pass-through subclasses (no method overrides) — role-specific behavior is injected via AgentConfig.system_prompt at runtime per the locked decision in CONTEXT.md.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed CLI-07 xpass — collision_policy assertion used OR instead of AND**
- **Found during:** Task 2 (test stub verification run)
- **Issue:** `assert result.exit_code != 0 or "already exists" in result.output` trivially xpassed because `create` subcommand returns exit_code=2 (unknown command) — satisfying the first condition before implementation
- **Fix:** Changed to `assert result.exit_code != 0 and "already exists" in result.output` — both conditions must hold, which requires the `create` subcommand to actually exist and run the collision check
- **Files modified:** tests/test_factory_cli.py
- **Verification:** Re-ran 17 stubs, all show XFAIL (not XPASS)
- **Committed in:** a7e6032 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test assertion logic)
**Impact on plan:** Fix required for test contract integrity. No scope creep.

## Issues Encountered

None beyond the CLI-07 assertion fix documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- factory/ package importable and ready for 05-01 generator implementation
- 17 test stubs define precise contracts for all 5 remaining Phase 5 plans
- Full test suite GREEN (111 passed, 17 xfailed) at 95.76% coverage
- Next: 05-01 — generator implementation (GEN-01 to GEN-05 GREEN)

## Self-Check: PASSED

All 12 files found. Both task commits verified (4c92a69, a7e6032).

---
*Phase: 05-factory-cluster-core-product*
*Completed: 2026-03-07*
