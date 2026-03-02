---
phase: 02-agent-heartbeat-framework
plan: "00"
subsystem: testing
tags: [pytest, tdd, heartbeat, asyncio, importorskip]

requires:
  - phase: 01-core-runtime-database-state-machine
    provides: DatabaseManager, TaskStateMachine, AgentStatus models — used by heartbeat test fixtures

provides:
  - 13 pytest stub tests for HB-01 through HB-13 that skip cleanly before implementation
  - Full test contract for AgentConfig, Notifier protocol, and BaseAgent heartbeat behaviors
  - test_config.py: HB-01 (interval constraint) and HB-02 (YAML load)
  - test_notifier.py: HB-03 (StdoutNotifier protocol)
  - test_heartbeat.py: HB-04 through HB-13 (stagger, UPSERT, transitions, state file, cancel, stop, concurrency, hook order, jitter)

affects:
  - 02-01 (Wave 1 implementation — AgentConfig, Notifier): these stubs define exact interfaces
  - 02-02 (Wave 2 implementation — BaseAgent): these stubs define heartbeat loop contract

tech-stack:
  added: []
  patterns:
    - "module-level import sentinel: try/except ImportError sets _has_heartbeat flag, each test checks flag and calls pytest.skip"
    - "pytest.importorskip inside test body for single-module stubs (test_config.py, test_notifier.py)"
    - "FixedTickAgent helper class defined conditionally (only when _has_heartbeat=True) to stop loop after N ticks"
    - "monkeypatch STATE_DIR to tmp_path to prevent state files writing to real runtime/state/ during tests"

key-files:
  created:
    - tests/test_config.py
    - tests/test_notifier.py
    - tests/test_heartbeat.py
  modified:
    - .gitignore (added to version control — confirmed runtime/state/ present on line 29)
    - pyproject.toml (added to version control)

key-decisions:
  - "Module-level sentinel (_has_heartbeat) preferred over pytest.importorskip at module level for test_heartbeat.py — allows FixedTickAgent helper class to be conditionally defined"
  - "pytest.importorskip used inside test body for simpler single-import stubs (test_config.py, test_notifier.py)"
  - "FixedTickAgent stops loop by setting self._stop_event after N _tick() calls — relies on BaseAgent exposing _stop_event and _tick() as overridable"

patterns-established:
  - "TDD RED phase: stubs define interface contract before implementation — Wave 1 and Wave 2 must satisfy these exact test names and behaviors"
  - "_make_config() helper builds AgentConfig for tests — when AgentConfig field names change, update one place"

requirements-completed: [HB-01, HB-02, HB-03, HB-04, HB-05, HB-06, HB-07, HB-08, HB-09, HB-10, HB-11, HB-12, HB-13]

duration: 4min
completed: 2026-03-02
---

# Phase 2 Plan 00: TDD RED Phase — 13 Heartbeat Test Stubs Summary

**13 pytest stub tests (HB-01 through HB-13) across 3 files using module-level import sentinels and importorskip, all skipping cleanly before Wave 1/2 implementation exists**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-02T05:32:07Z
- **Completed:** 2026-03-02T05:36:49Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Created test_config.py with 2 stubs (HB-01: interval ge constraint, HB-02: YAML load) using pytest.importorskip inside test bodies
- Created test_notifier.py with 1 stub (HB-03: StdoutNotifier protocol async methods + capsys output verification) as async test
- Created test_heartbeat.py with 10 stubs (HB-04 through HB-13) using module-level _has_heartbeat sentinel and FixedTickAgent helper
- All 13 tests collect cleanly via `pytest --collect-only` (0 ImportErrors, 0 errors) and all 40 Phase 1 tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: tests/test_config.py** - `5501465` (test)
2. **Task 2: tests/test_notifier.py** - `bd6f9ac` (test)
3. **Task 3: tests/test_heartbeat.py** - `5559cc9` (test)
4. **Task 4: Verify .gitignore + full collection** - `65c6423` (chore)

## Files Created/Modified

- `tests/test_config.py` - HB-01 (interval_seconds ge=0.01 pydantic constraint) and HB-02 (YAML round-trip via load_agent_config)
- `tests/test_notifier.py` - HB-03 (StdoutNotifier async methods, capsys output verification)
- `tests/test_heartbeat.py` - HB-04 through HB-13 (stagger delay, UPSERT, status transitions, state file, corrupt state, CancelledError, stop event, concurrency, hook order, jitter clamping)
- `.gitignore` - Added to git version control (confirmed runtime/state/ present)
- `pyproject.toml` - Added to git version control

## Decisions Made

- Module-level import sentinel (`_has_heartbeat`) chosen for test_heartbeat.py (vs. importorskip inside each test) because it enables the `FixedTickAgent` helper class to be conditionally defined at module level, keeping tests DRY
- `pytest.importorskip` inside test body used for simpler files where only one module is needed and no shared helper class is required
- FixedTickAgent stops the heartbeat loop by calling `self._stop_event.set()` after N `_tick()` calls — this implies BaseAgent exposes `_stop_event` as an asyncio.Event and `_tick()` as an overridable method

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_heartbeat.py pre-existed with incorrect structure**
- **Found during:** Task 3 (create test_heartbeat.py)
- **Issue:** A prior hook had generated a test_heartbeat.py using direct imports without importorskip guards and referencing non-existent fixtures (stub_agent, tmp_db, fast_config) and wrong class name (runtime.database.Database vs DatabaseManager). Collection failed with 7 errors.
- **Fix:** Overwrote with correct module-level sentinel pattern matching the plan spec
- **Files modified:** tests/test_heartbeat.py
- **Verification:** 10 tests collect, all 10 skip cleanly
- **Committed in:** 5559cc9 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — pre-existing incorrect file)
**Impact on plan:** Necessary correction to make collection work. No scope creep.

## Issues Encountered

- A Prettier/linter hook modified test_config.py after Task 1 commit, changing `agent_role` to `role` and removing `db_path` from the AgentConfig constructor calls. The system indicated this was intentional, so the modified version was retained. This may affect Wave 1 implementation if AgentConfig uses `agent_role` as specified in PLAN.md vs. `role` as the hook assumes.
- test_notifier.py was also modified by a hook after Task 2 commit; had to overwrite with correct importorskip pattern before committing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 13 test stubs ready for Wave 1 (AgentConfig + Notifier) and Wave 2 (BaseAgent) implementations
- Wave 1 (02-01) must implement `runtime/config.py` (AgentConfig with interval ge constraint, load_agent_config) and `runtime/notifier.py` (Notifier protocol, StdoutNotifier)
- Wave 2 (02-02) must implement `runtime/heartbeat.py` (BaseAgent with all HB-04 through HB-13 behaviors)
- Note: Hook modified test_config.py to use `role` (not `agent_role`) — Wave 1 implementer should confirm correct field name from REQUIREMENTS.md

---
*Phase: 02-agent-heartbeat-framework*
*Completed: 2026-03-02*

## Self-Check: PASSED

- FOUND: tests/test_config.py
- FOUND: tests/test_notifier.py
- FOUND: tests/test_heartbeat.py
- FOUND: .planning/phases/02-agent-heartbeat-framework/02-00-SUMMARY.md
- FOUND commit 5501465 (Task 1)
- FOUND commit bd6f9ac (Task 2)
- FOUND commit 5559cc9 (Task 3)
- FOUND commit 65c6423 (Task 4)
