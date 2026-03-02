---
phase: 01-core-runtime-database-state-machine
plan: 01
subsystem: database
tags: [sqlite, aiosqlite, pydantic, pytest, pytest-asyncio, schema, state-machine]

# Dependency graph
requires: []
provides:
  - runtime Python package marker (runtime/__init__.py)
  - Canonical SQLite DDL for all 7 tables (runtime/schema.sql) with WAL pragma preamble and 3 indexes
  - pytest test scaffold: conftest.py with async db fixture + create_goal/create_task helpers
  - Test stubs for DB-01 through DB-05, CLI-01, CLI-02 (xfail until Plan 04)
  - Test stubs for MDL-01 through MDL-03, SM-04 (importorskip until Plan 03)
  - Parametrized state machine tests for SM-01 through SM-03 (importorskip until Plan 02)
affects:
  - 01-02 (state_machine.py — imports TaskStatus from models, tests already wired)
  - 01-03 (models.py — test_models.py ready, importorskip will lift)
  - 01-04 (database.py — test_database.py ready, xfail will be removed)
  - 01-05 (cli.py — CLI tests wired into test_database.py)
  - All downstream phases that import runtime package

# Tech tracking
tech-stack:
  added: []  # All deps already declared in pyproject.toml
  patterns:
    - "CREATE TABLE IF NOT EXISTS for idempotent schema initialization"
    - "WAL + foreign_keys + busy_timeout pragmas set per-connection in schema preamble"
    - "Function-scoped in-memory SQLite per test (no temp files, no state bleed)"
    - "importorskip at module level for graceful skip before implementation exists"
    - "pytestmark xfail for async tests that need db fixture before runtime.database exists"
    - "Parametrized (from_state, to_state, should_succeed) table covers all state machine paths"

key-files:
  created:
    - runtime/__init__.py
    - runtime/schema.sql
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_database.py
    - tests/test_models.py
    - tests/test_state_machine.py
  modified: []

key-decisions:
  - "schema.sql is the single source of truth; DatabaseManager reads it via Path(__file__).parent / 'schema.sql'"
  - "All test files use importorskip or xfail — zero ImportError crashes before Plans 02-04 run"
  - "create_goal() and create_task() are plain async helpers, not fixtures — called directly in test bodies"
  - "rejected is not a TaskStatus enum value — rejection is recorded as task_comment, task returns to in-progress"

patterns-established:
  - "Wave 0 pattern: test scaffold written before implementation so each plan's verify command works immediately"
  - "Guard pattern: _has_runtime flag in conftest.py allows db fixture to skip instead of error"

requirements-completed:
  - "schema.sql (7 tables, WAL-native, CREATE TABLE IF NOT EXISTS)"
  - "test infrastructure (conftest, fixtures, all test stubs)"

# Metrics
duration: 4min
completed: 2026-03-02
---

# Phase 1 Plan 01: Package Structure + Schema + Test Scaffold Summary

**SQLite WAL schema for 7 tables (goals, tasks, task_comments, task_reviews, agent_status, documents, activity_log) plus full pytest scaffold with importorskip/xfail guards — suite runs 13 passed, 6 skipped, 2 xfailed, 0 errors before any implementation exists**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-02T00:27:24Z
- **Completed:** 2026-03-02T00:31:35Z
- **Tasks:** 2
- **Files modified:** 7 created

## Accomplishments

- runtime/ package established with canonical schema.sql (7 tables, WAL pragmas, 3 indexes)
- Full test scaffold ready for Plans 02-04: conftest.py db fixture, create_goal/create_task helpers, 3 test files
- All test files collect without ImportError before implementations exist (importorskip + xfail pattern)
- schema.sql uses CREATE TABLE IF NOT EXISTS throughout — idempotent for `cluster db up`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create runtime package and canonical schema.sql** - `7cdcd98` (feat)
2. **Task 2: Create test scaffold — conftest, test_database, test_models, test_state_machine** - `df02bcd` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `runtime/__init__.py` - Package marker with module docstring
- `runtime/schema.sql` - Canonical DDL: WAL preamble, 7 tables (CREATE TABLE IF NOT EXISTS), 3 indexes
- `tests/__init__.py` - Tests package marker
- `tests/conftest.py` - Async db fixture (in-memory, function-scoped), create_goal/create_task helpers, _has_runtime guard
- `tests/test_database.py` - xfail stubs for DB-01 through DB-05, CLI-01, CLI-02
- `tests/test_models.py` - importorskip guard; MDL-01 through MDL-03 + SM-04 tests
- `tests/test_state_machine.py` - importorskip guard; parametrized TRANSITION_CASES (5 valid + 6 invalid) for SM-01 through SM-03

## Decisions Made

- Used `pytestmark = pytest.mark.xfail(strict=False)` for test_database.py (entire module) since the async `db` fixture skips but the two non-fixture tests needed xfail as the fallback
- Used `pytest.importorskip()` at module level for test_models.py and test_state_machine.py — cleaner than per-test skip since the entire module requires the implementation module
- `create_goal()` and `create_task()` implemented as plain async helpers (not fixtures) per CONTEXT.md — callers pass the open `db` connection directly, keeping each test body explicit about its setup

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- runtime/schema.sql is ready for DatabaseManager.init_schema() to execute (Plan 04)
- tests/test_state_machine.py is ready to activate once runtime/state_machine.py exists (Plan 02)
- tests/test_models.py is ready to activate once runtime/models.py exists (Plan 03)
- tests/test_database.py is ready to activate once runtime/database.py exists (Plan 04)
- `pytest tests/ -q` exits 0 — no blockers for downstream plans

## Self-Check: PASSED

- FOUND: runtime/__init__.py
- FOUND: runtime/schema.sql
- FOUND: tests/__init__.py
- FOUND: tests/conftest.py
- FOUND: tests/test_database.py
- FOUND: tests/test_models.py
- FOUND: tests/test_state_machine.py
- FOUND: .planning/phases/01-core-runtime-database-state-machine/01-01-SUMMARY.md
- FOUND: 7cdcd98 (Task 1 commit)
- FOUND: df02bcd (Task 2 commit)

---
*Phase: 01-core-runtime-database-state-machine*
*Completed: 2026-03-02*
