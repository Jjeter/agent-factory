---
phase: 01-core-runtime-database-state-machine
plan: 05
subsystem: cli
tags: [click, cli, sqlite, asyncio, pytest-cov]

# Dependency graph
requires:
  - phase: 01-04
    provides: DatabaseManager with up()/reset() async methods
  - phase: 01-03
    provides: TaskStateMachine and TaskStatus enum
  - phase: 01-02
    provides: All 7 Pydantic models and TaskStatus enum
provides:
  - "runtime/cli.py: cluster_cli Click group with db up/reset commands"
  - "runtime/cli.py: factory_cli stub entry point for Phase 5"
  - "tests/test_cli.py: 6 CLI tests covering all commands and envvar"
  - "Phase 1 exit gate: 40 tests GREEN, 97% coverage (80%+ gate passed)"
affects:
  - phase-02-agent-heartbeat-framework
  - phase-05-factory-cluster

# Tech tracking
tech-stack:
  added: [click>=8.1.0 (already in pyproject.toml)]
  patterns:
    - "Lazy DatabaseManager import inside async helpers to avoid circular imports"
    - "asyncio.run() at top level of each Click command wrapping single coroutine"
    - "CLUSTER_DB_PATH envvar with --db-path option fallback for CLI commands"
    - "Click CliRunner for CLI unit tests (no subprocess required)"

key-files:
  created:
    - runtime/cli.py
    - tests/test_cli.py
  modified: []

key-decisions:
  - "Lazy import of DatabaseManager inside _do_up/_do_reset coroutines — keeps CLI startup fast and avoids circular import risk"
  - "asyncio.run() once per command wrapping a single top-level coroutine — never nested per RESEARCH.md Pitfall 6"
  - "factory_cli is an empty stub group — Phase 5 implements subcommands; stub prevents entry point resolution failures on pip install"
  - "Added tests/test_cli.py (not inline in test_models.py) for CLI test coverage — separation of concerns"

patterns-established:
  - "CLI pattern: Click group -> subgroup -> command with lazy async helper import"
  - "Test pattern: Click CliRunner with tmp_path fixture for DB path isolation"

requirements-completed:
  - "cluster CLI entry point with db subgroup"
  - "cluster db up initializes DB idempotently (reads CLUSTER_DB_PATH envvar or defaults to cluster.db)"
  - "cluster db reset drops and recreates all tables (no confirmation prompt)"
  - "Pydantic model tests updated to GREEN"
  - "Full test suite passes with 80%+ coverage"

# Metrics
duration: 12min
completed: 2026-03-01
---

# Phase 1 Plan 05: CLI Entry Points and Phase 1 Coverage Gate Summary

**Click CLI wiring cluster db up/reset commands to DatabaseManager, closing Phase 1 with 40 GREEN tests at 97% coverage**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-01T00:00:00Z
- **Completed:** 2026-03-01T00:12:00Z
- **Tasks:** 2
- **Files modified:** 2 (created: runtime/cli.py, tests/test_cli.py)

## Accomplishments

- Implemented runtime/cli.py with cluster_cli (db up + db reset) and factory_cli stub
- Both CLI commands use CLUSTER_DB_PATH envvar and --db-path option, wrapping DatabaseManager via asyncio.run()
- Added tests/test_cli.py with 6 tests covering help, create, idempotency, reset, envvar, and factory stub
- Phase 1 exit gate achieved: 40 tests pass, 97.24% coverage (required 80%)
- state_machine.py at 100% coverage (14/14 statements)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement runtime/cli.py with cluster db up/reset commands** - `3db06f0` (feat)
2. **Task 2: Add tests/test_cli.py for CLI coverage** - `ff800ef` (test)

## Files Created/Modified

- `runtime/cli.py` - Click CLI entry points: cluster_cli with db subgroup (up/reset) and factory_cli stub
- `tests/test_cli.py` - 6 CLI unit tests using Click CliRunner and tmp_path fixtures

## Decisions Made

- Lazy import of DatabaseManager inside async helpers: keeps CLI startup fast, avoids circular imports
- asyncio.run() at top level of each command wrapping a single coroutine: follows RESEARCH.md Pitfall 6 (never nest asyncio.run())
- factory_cli is an empty @click.group() stub: prevents entry point resolution failures; Phase 5 adds subcommands
- Created tests/test_cli.py as separate file rather than extending test_models.py: cleaner separation by module under test

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added tests/test_cli.py to meet coverage gate**
- **Found during:** Task 2 (run full suite after adding cli.py)
- **Issue:** Adding runtime/cli.py with 0% coverage dropped total from 97% to 79% — below the 80% gate in pyproject.toml
- **Fix:** Created tests/test_cli.py with 6 tests covering all CLI commands and envvar; cli.py now at 100% coverage
- **Files modified:** tests/test_cli.py (created)
- **Verification:** pytest exits 0, total coverage 97.24%
- **Committed in:** ff800ef (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — coverage gate)
**Impact on plan:** Plan described adding CLI tests as a contingency "if coverage is an issue." Coverage was below gate after cli.py was added, so test_cli.py was created as planned. No scope creep.

## Issues Encountered

- `cluster` script not on PATH in bash shell (Windows Scripts directory not in $PATH): resolved by using `python -m` invocation and Click CliRunner for all verification — no functional issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 complete: all 5 plans executed, 40 tests GREEN, 97% coverage
- cluster db up/reset CLI commands fully operational
- runtime/ package: __init__.py, models.py, state_machine.py, database.py, cli.py all complete
- Phase 2 (Heartbeat Framework) can import from runtime.models, runtime.database, runtime.state_machine without any blockers

---
*Phase: 01-core-runtime-database-state-machine*
*Completed: 2026-03-01*
