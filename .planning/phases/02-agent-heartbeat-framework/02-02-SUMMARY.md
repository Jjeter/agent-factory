---
phase: 02-agent-heartbeat-framework
plan: "02"
subsystem: agent-runtime
tags: [asyncio, aiosqlite, sqlite-upsert, heartbeat-loop, state-machine, atomic-file-write]

# Dependency graph
requires:
  - phase: 02-agent-heartbeat-framework/02-00
    provides: "TDD stubs for HB-04 through HB-13 (test_heartbeat.py with FixedTickAgent)"
  - phase: 02-agent-heartbeat-framework/02-01
    provides: "AgentConfig, Notifier Protocol, StdoutNotifier"
  - phase: 01-core-runtime-database-state-machine
    provides: "DatabaseManager (open_write/open_read), schema.sql, models (AgentStatusEnum, _now_iso, _uuid)"
provides:
  - "BaseAgent class in runtime/heartbeat.py with full async heartbeat loop"
  - "start() with stagger delay, interruptible sleep, CancelledError propagation"
  - "_tick() with WORKING/IDLE status transitions and exception handling"
  - "do_peer_reviews() and do_own_tasks() no-op stubs for subclass override"
  - "_set_db_status() UPSERT to agent_status table"
  - "_log_heartbeat() insert to activity_log"
  - "_write_state_file() atomic JSON write via Path.replace()"
  - "_load_state() with WARNING on missing/corrupt state file"
  - "_on_shutdown() graceful cleanup on task cancellation or stop event"
affects:
  - phase-03-boss-agent
  - phase-04-worker-agents

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Interruptible sleep: asyncio.wait_for(_stop_event.wait(), timeout) — stop event wakes loop immediately"
    - "CancelledError propagation: no except CancelledError anywhere — BaseException subclass passes through except Exception"
    - "Jitter clamping: max(0.0, interval + random.uniform(-30, 30)) — prevents negative asyncio.sleep"
    - "Atomic file write: tmp.write_text() + tmp.replace(state_path) — Windows-safe"
    - "SQLite UPSERT: INSERT ... ON CONFLICT(agent_id) DO UPDATE SET ... — single row per agent"
    - "DB connection lifecycle: open_write() → try: execute/commit → finally: close()"

key-files:
  created:
    - runtime/heartbeat.py
  modified:
    - runtime/config.py
    - runtime/schema.sql

key-decisions:
  - "AgentConfig accepts both 'role' and 'agent_role' via model_validator(mode='before') — normalizes to both fields for backward compat"
  - "AgentConfig gains optional db_path field — BaseAgent constructs DatabaseManager from it"
  - "agent_status PRIMARY KEY renamed from 'id' to 'agent_id' in schema.sql — matches test query patterns (WHERE agent_id = ?)"
  - "_load_state() called at start() entry point to trigger WARNING on corrupt state files before first tick"
  - "_write_state_file() uses module-level STATE_DIR constant (not self attribute) — enables monkeypatching in tests"
  - "Error in tick hooks: logged via logger.exception, status set to ERROR, loop continues (stop_event NOT set)"

patterns-established:
  - "BaseAgent: subclasses override do_peer_reviews() and do_own_tasks(); base handles all loop/DB/file logic"
  - "All DB connections opened and closed within single method scope via try/finally — no shared connection state"

requirements-completed: [HB-04, HB-05, HB-06, HB-07, HB-08, HB-09, HB-10, HB-11, HB-12, HB-13]

# Metrics
duration: 30min
completed: 2026-03-02
---

# Phase 2 Plan 02: BaseAgent Heartbeat Loop Summary

**Async BaseAgent class with stagger delay, interruptible sleep, SQLite UPSERT status tracking, atomic JSON state file, and graceful CancelledError propagation — 10/10 HB tests GREEN, 97% total coverage**

## Performance

- **Duration:** ~30 min (plus ~3 min test run time due to real async timing tests)
- **Started:** 2026-03-02T05:41:08Z
- **Completed:** 2026-03-02T08:36:11Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Implemented complete `BaseAgent` class in `runtime/heartbeat.py` (140 lines) with all required methods
- All 10 heartbeat tests (HB-04 through HB-13) transitioned from SKIP to PASS, including concurrent agent test
- 53/53 total project tests GREEN, 97% coverage on runtime/ package
- Fixed `AgentConfig` to accept both `role` and `agent_role` field names, and added `db_path` field
- Fixed `agent_status` schema: renamed `id` column to `agent_id` to match test query expectations

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement runtime/heartbeat.py — BaseAgent core loop** - `45ed7e4` (feat)
2. **Task 2: Run full Phase 2 test suite to GREEN** - no additional commit (verification only)

## Files Created/Modified

- `runtime/heartbeat.py` - BaseAgent class with full async heartbeat loop implementation
- `runtime/config.py` - Updated AgentConfig to accept agent_role + db_path fields via model_validator
- `runtime/schema.sql` - Renamed agent_status.id -> agent_id (PRIMARY KEY column)

## Decisions Made

- **AgentConfig dual role fields:** Used `model_validator(mode='before')` to normalize `role`/`agent_role` — both test_config.py (uses `role`) and test_heartbeat.py (uses `agent_role`) work without changes to either test file
- **db_path in AgentConfig:** Added as `Optional[str]` — BaseAgent constructs DatabaseManager from it directly
- **Schema column rename:** `agent_status.id` renamed to `agent_id` so test queries like `WHERE agent_id = ?` work correctly
- **_load_state() at start() entry:** Called once before stagger delay so corrupt-file WARNING fires before any tick
- **Module-level STATE_DIR:** Kept as module constant (not instance variable) so tests can monkeypatch `runtime.heartbeat.STATE_DIR`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed AgentConfig field name mismatch (agent_role vs role)**
- **Found during:** Task 1 (reading AgentConfig model vs test helper)
- **Issue:** 02-01 plan implemented AgentConfig with `role` field, but test_heartbeat.py's `_make_config` helper passes `agent_role="worker"` and `db_path=str(db_file)` — Pydantic would reject unknown fields
- **Fix:** Updated AgentConfig with `model_validator(mode='before')` to normalize both `role` and `agent_role` to both fields; added `db_path: Optional[str]`
- **Files modified:** runtime/config.py
- **Verification:** test_config.py (2 tests) and test_heartbeat.py (10 tests) all pass
- **Committed in:** 45ed7e4 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed agent_status schema: id column -> agent_id**
- **Found during:** Task 1 (reading schema.sql against test queries)
- **Issue:** Schema used `id TEXT PRIMARY KEY` for agent_status but tests query `WHERE agent_id = ?` — always returns 0 rows
- **Fix:** Renamed column `id` -> `agent_id` in schema.sql and updated heartbeat.py UPSERT to match
- **Files modified:** runtime/schema.sql, runtime/heartbeat.py
- **Verification:** test_status_upsert, test_status_transitions both pass (verify agent_id column)
- **Committed in:** 45ed7e4 (Task 1 commit)

**3. [Rule 2 - Missing] Added _load_state() call in start() to trigger corrupt-file warning**
- **Found during:** Task 1 (test_state_file_corrupt expects WARNING during agent.start())
- **Issue:** _load_state() existed but was never called in start() or _tick() — warning would never fire
- **Fix:** Added `self._load_state()` at top of start() before stagger delay
- **Files modified:** runtime/heartbeat.py
- **Verification:** test_state_file_corrupt PASSES (caplog captures WARNING with 'corrupt'/'missing')
- **Committed in:** 45ed7e4 (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing behavior)
**Impact on plan:** All fixes required for test correctness. Schema rename is backward-compatible (no other code used agent_status.id by that name).

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `BaseAgent` is importable and fully functional; Phase 3 Boss Agent can subclass immediately
- `do_peer_reviews()` and `do_own_tasks()` are no-op stubs ready for override
- All Phase 2 infrastructure (config, notifier, database, heartbeat) is GREEN at 97% coverage
- No blockers for Phase 3

## Self-Check: PASSED

- runtime/heartbeat.py: FOUND
- runtime/config.py: FOUND
- runtime/schema.sql: FOUND
- 02-02-SUMMARY.md: FOUND
- Commit 45ed7e4: FOUND

---
*Phase: 02-agent-heartbeat-framework*
*Completed: 2026-03-02*
