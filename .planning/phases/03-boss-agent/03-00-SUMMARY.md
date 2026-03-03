---
phase: 03-boss-agent
plan: "00"
subsystem: testing
tags: [tdd, pytest, sqlite, schema, tabulate]

# Dependency graph
requires:
  - phase: 02-heartbeat-framework
    provides: BaseAgent class that BossAgent extends
  - phase: 01-core-runtime
    provides: schema.sql, TaskStateMachine, DatabaseManager, models

provides:
  - 19 BossAgent unit test stubs (TDD RED) in tests/test_boss.py
  - 7 Boss CLI integration test stubs in tests/test_boss_cli.py
  - reviewer_roles TEXT column in tasks table (schema.sql)
  - tabulate>=0.9.0 dependency in pyproject.toml

affects:
  - 03-01 (BossAgent implementation — uses these stubs as GREEN targets)
  - 03-02 (gap-fill and stuck detection implementation)
  - 03-03 (CLI implementation — uses test_boss_cli.py stubs as GREEN targets)

# Tech tracking
tech-stack:
  added:
    - tabulate>=0.9.0 (table rendering for cluster CLI commands)
  patterns:
    - pytest.importorskip("runtime.boss") inside each test body (not module level) — prevents ImportError when boss.py absent
    - All TDD RED stubs end with pytest.xfail("not implemented yet")
    - Schema columns added as nullable TEXT for backward compatibility

key-files:
  created:
    - tests/test_boss.py
    - tests/test_boss_cli.py
  modified:
    - runtime/schema.sql
    - pyproject.toml

key-decisions:
  - "pytest.importorskip inside test body (not module level) for boss stubs — boss.py absent causes collection crash at module scope"
  - "reviewer_roles as nullable TEXT column (JSON list) on tasks table — avoids join table complexity for V1"
  - "19 stubs in test_boss.py (plan stated 18 but listed 19 distinct test names — template is authoritative)"

patterns-established:
  - "importorskip-in-body pattern: use when implementation module does not yet exist and module-level import would crash collection"
  - "TDD RED commit message: test(phase-plan): add N [subsystem] test stubs (TDD RED)"

requirements-completed:
  - boss-agent

# Metrics
duration: 4min
completed: 2026-03-03
---

# Phase 3 Plan 00: Boss Agent TDD RED Stubs Summary

**26 xfail test stubs (19 BossAgent unit + 7 CLI integration) scaffolding Phase 3 behavior contracts, plus reviewer_roles schema column and tabulate dependency**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-03T00:41:59Z
- **Completed:** 2026-03-03T00:46:12Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Created tests/test_boss.py with 19 BossAgent unit test stubs covering all boss behaviors (structure, peer review promotion, goal decomposition, heartbeat/gap-fill, stuck detection, activity log, re-review upsert)
- Created tests/test_boss_cli.py with 7 CLI integration stubs for cluster goal/tasks/agents/approve commands
- Added reviewer_roles TEXT column to tasks table in runtime/schema.sql (nullable JSON list, inserted after stuck_since)
- Added tabulate>=0.9.0 to pyproject.toml dependencies (required for human-readable table output in Wave 3 CLI)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add reviewer_roles to schema.sql and tabulate to pyproject.toml** - `b99be8b` (chore)
2. **Task 2: Create tests/test_boss.py — 19 BossAgent unit test stubs** - `2148c6c` (test)
3. **Task 3: Create tests/test_boss_cli.py — 7 CLI integration test stubs** - `9d1cf77` (test)

## Files Created/Modified

- `tests/test_boss.py` — 19 xfail BossAgent unit test stubs using importorskip-in-body pattern
- `tests/test_boss_cli.py` — 7 xfail Boss CLI integration test stubs
- `runtime/schema.sql` — reviewer_roles TEXT column added to tasks table after stuck_since
- `pyproject.toml` — tabulate>=0.9.0 added to [project] dependencies

## Decisions Made

- Used `pytest.importorskip("runtime.boss")` inside each test body (not at module level) because boss.py does not exist yet — module-level import would crash pytest collection for all 26 stubs.
- reviewer_roles stored as nullable TEXT (JSON list like '["researcher","strategist"]') on the tasks table rather than a separate join table — simpler for V1, matches the CONTEXT.md decision.
- Plan described "18 xfail stubs" in the objective but listed 19 distinct test function names in the behavior section (stuck detection group has 4 tests, not 3). The action template with 19 stubs is authoritative — all 19 were created.

## Deviations from Plan

None — plan executed exactly as written (the 18 vs 19 stub count discrepancy is in the plan document itself; the template provided in the action section has 19 stubs and was followed exactly).

## Issues Encountered

None. All verifications passed:
- 26 stubs collected without ImportError
- All 26 run as skipped (importorskip skips when runtime.boss absent)
- Schema check confirms reviewer_roles in tasks table columns
- tabulate 0.9.0 imports successfully
- 53 existing tests still pass (no regressions from schema or dependency changes)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 1 (03-01): BossAgent core implementation — all 19 test stubs in test_boss.py serve as the GREEN targets
- Wave 2 (03-02): Gap-fill and stuck detection — test stubs already cover these behaviors
- Wave 3 (03-03): CLI commands — all 7 test stubs in test_boss_cli.py serve as the GREEN targets
- Schema gap (reviewer_roles) and tabulate dependency are already in place for Wave 1

## Self-Check: PASSED

- tests/test_boss.py: FOUND
- tests/test_boss_cli.py: FOUND
- .planning/phases/03-boss-agent/03-00-SUMMARY.md: FOUND
- Commit b99be8b (Task 1): FOUND
- Commit 2148c6c (Task 2): FOUND
- Commit 9d1cf77 (Task 3): FOUND

---
*Phase: 03-boss-agent*
*Completed: 2026-03-03*
