---
phase: 05-factory-cluster-core-product
plan: "02"
subsystem: factory
tags: [pipeline, role-decomposition, llm, pydantic, asyncio, boss-agent, worker-agent]

# Dependency graph
requires:
  - phase: 05-01
    provides: factory/models.py (RoleSpec, RolesResult, FitCheckResult), factory/generator.py
  - phase: 03-01
    provides: BossAgent base class with _insert_task, TaskSpec
  - phase: 04-01
    provides: WorkerAgent base class with SYSTEM_PROMPT ClassVar pattern
provides:
  - factory/pipeline.py — decompose_roles, fit_check, enrich_roles using messages.parse() pattern
  - factory/boss.py — FactoryBossAgent with 7-task deterministic decompose_goal (no LLM call)
  - factory/workers.py — FactoryResearcherAgent, FactorySecurityCheckerAgent, FactoryExecutorAgent
affects: [05-03, 05-04, factory-cli, factory-runner]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "messages.parse(output_format=PydanticModel) for all structured LLM output in pipeline"
    - "asyncio.gather for parallel per-role enrichment calls"
    - "Deterministic task set in FactoryBossAgent.decompose_goal — no LLM, fixed 7 tasks"
    - "SYSTEM_PROMPT ClassVar[str] on WorkerAgent subclasses for role specialization"
    - "Lazy imports inside decompose_goal body (runtime.boss.TaskSpec, runtime.models._uuid)"

key-files:
  created:
    - factory/pipeline.py
    - factory/boss.py
    - factory/workers.py
  modified: []

key-decisions:
  - "decompose_roles always injects boss (index 0) and critic (appended) structural roles after LLM response — never left to LLM discretion"
  - "fit_check is single-shot; retry logic (max 2) is caller responsibility — clean separation of concerns"
  - "enrich_roles uses asyncio.gather for parallel per-role LLM calls — O(N) latency not O(1)"
  - "FactoryBossAgent.decompose_goal is deterministic (no LLM) because factory workflow is fixed and well-known"
  - "reviewer_agents=['factory-critic-01'] hardcoded for all factory tasks — critic is always the structural reviewer"
  - "design-roles task uses model_tier=sonnet; all others haiku — design step warrants stronger model"
  - "Lazy imports of TaskSpec and _uuid inside decompose_goal body to avoid circular import risk"

patterns-established:
  - "Pipeline functions (decompose_roles, fit_check, enrich_roles) are pure async functions, not methods — caller orchestrates retry"
  - "WorkerAgent subclasses specialize only via SYSTEM_PROMPT — all execution logic inherited"

requirements-completed: [PIPELINE-01, PIPELINE-02, PIPELINE-03]

# Metrics
duration: 10min
completed: 2026-03-07
---

# Phase 5 Plan 02: Factory Pipeline and Agents Summary

**Three-stage role decomposition pipeline (decompose_roles, fit_check, enrich_roles) plus FactoryBossAgent with 7-task deterministic workflow and three factory WorkerAgent subclasses (researcher, security-checker, executor)**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-07T13:10:00Z
- **Completed:** 2026-03-07T13:19:41Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented `factory/pipeline.py` with all three pipeline stages using `messages.parse()` pattern; `decompose_roles` always injects structural boss and critic roles
- Implemented `factory/boss.py` with `FactoryBossAgent.decompose_goal` emitting 7 deterministic factory tasks — no LLM call in decompose_goal itself
- Implemented `factory/workers.py` with `FactoryResearcherAgent`, `FactorySecurityCheckerAgent`, `FactoryExecutorAgent` as `WorkerAgent` subclasses with role-specific `SYSTEM_PROMPT` class attributes
- PIPELINE-01, PIPELINE-02, PIPELINE-03 all GREEN; 119 tests GREEN at 93.59% coverage; no circular imports

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement factory/pipeline.py — role decomposition pipeline** - `a9701c1` (feat) — committed in prior session
2. **Task 2: Implement factory/boss.py + factory/workers.py** - `f574e57` (feat)

## Files Created/Modified

- `factory/pipeline.py` — decompose_roles (LLM + boss/critic injection), fit_check (single-shot quality eval), enrich_roles (asyncio.gather parallel enrichment), _PIPELINE_MODEL = claude-haiku-4-5-20251001
- `factory/boss.py` — FactoryBossAgent subclassing BossAgent, _FACTORY_TASKS list of 7 dicts, deterministic decompose_goal with lazy TaskSpec/_uuid imports
- `factory/workers.py` — FactoryResearcherAgent, FactorySecurityCheckerAgent, FactoryExecutorAgent with role-specific SYSTEM_PROMPT ClassVar[str]

## Decisions Made

- `decompose_roles` injects boss at index 0 and critic appended — structural roles always present, never LLM-discretionary
- `fit_check` is single-shot; callers handle max-2-retry loop — separates concerns cleanly
- `enrich_roles` uses `asyncio.gather` for concurrency — matches plan spec and RESEARCH.md pattern
- `FactoryBossAgent.decompose_goal` is deterministic (no LLM) because the factory artifact generation workflow is fixed and well-known
- `reviewer_agents=["factory-critic-01"]` hardcoded for all tasks — critic is the structural reviewer for factory work
- `design-roles` task uses `model_tier="sonnet"`, all others `"haiku"` — design step warrants stronger model
- Lazy imports of `TaskSpec` and `_uuid` inside `decompose_goal` body to avoid circular import risk

## Deviations from Plan

None — plan executed exactly as written. The implementation files were partially pre-implemented in a prior session (pipeline.py committed as `a9701c1`); boss.py and workers.py had stub implementations that were replaced with the full implementation per the plan spec.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `factory/pipeline.py`, `factory/boss.py`, `factory/workers.py` all fully implemented and tested
- PIPELINE-01, PIPELINE-02, PIPELINE-03 GREEN; 119 tests passing at 93.59% coverage
- Ready for Phase 5, Plan 05-03 (factory runner / CLI integration)
- No blockers

---
*Phase: 05-factory-cluster-core-product*
*Completed: 2026-03-07*
