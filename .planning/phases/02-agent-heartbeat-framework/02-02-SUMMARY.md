---
phase: 02-agent-heartbeat-framework
plan: "02"
subsystem: agents
tags: [asyncio, sqlite, heartbeat, state-machine, pydantic, aiosqlite, tempfile]

requires:
  - phase: 01-core-runtime
    provides: Database.upsert_agent_status(), AgentStatusRecord, AgentRole, AgentState, ActivityLog
  - phase: 02-agent-heartbeat-framework/02-01
    provides: AgentConfig (frozen Pydantic model with interval/stagger/jitter/state_dir), Notifier protocol, StdoutNotifier

provides:
  - BaseAgent ABC with async heartbeat loop (runtime/heartbeat.py)
  - Stagger offset (one-time, before first cycle) and interval jitter (each cycle)
  - Atomic state file persistence via tempfile + Path.replace()
  - DB agent_status upsert on every cycle (working -> idle)
  - Graceful stop() via asyncio.Event with CancelledError always re-raised
  - run_for_n_cycles() test helper for bounded async test loops

affects:
  - 03-boss-agent (BossAgent subclasses BaseAgent)
  - 04-worker-agents (WorkerAgent subclasses BaseAgent)

tech-stack:
  added: []
  patterns:
    - "BaseAgent ABC with two abstract hooks (do_peer_reviews, do_own_tasks)"
    - "Stagger applied once before while loop, jitter inside interval sleep each cycle"
    - "Path.replace() for atomic state file writes on Windows and POSIX"
    - "run_in_executor wraps blocking os.fsync() to avoid blocking event loop"
    - "CancelledError always re-raised in every except handler"

key-files:
  created:
    - runtime/heartbeat.py
  modified:
    - runtime/config.py (interval_seconds ge constraint 1.0 -> 0.01)
    - tests/test_heartbeat.py (HB-14 updated to check Path.replace not Path.rename)

key-decisions:
  - "Path.replace() over Path.rename() for atomic state file writes — rename() raises FileExistsError on Windows when target exists; replace() is cross-platform"
  - "AgentConfig.interval_seconds ge=0.01 (not ge=1.0) — allows fast test configs (0.1s) without sacrificing validation against zero/negative values"
  - "run_in_executor wraps _write_state_atomic so os.fsync() does not block the async event loop"
  - "No asyncio.Lock around DB calls — stagger design + SQLite WAL timeout=5s handles concurrency"

requirements-completed: [HB-01, HB-02, HB-03, HB-04, HB-05, HB-06, HB-12, HB-13, HB-14]

duration: 10min
completed: 2026-03-01
---

# Phase 02 Plan 02: BaseAgent Async Heartbeat Loop Summary

**BaseAgent ABC with asyncio heartbeat loop, stagger/jitter timing, atomic state file persistence via Path.replace(), and DB upsert per cycle — all 8 Phase 2 tests GREEN, 94.5% total coverage**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-01T04:20:51Z
- **Completed:** 2026-03-01T04:30:09Z
- **Tasks:** 2 (1 implementation + 1 coverage verification)
- **Files modified:** 3 created/modified

## Accomplishments

- Implemented `runtime/heartbeat.py` with `BaseAgent` ABC (241 lines): two abstract hooks, async heartbeat loop with stagger+jitter, DB status upserts, activity logging, atomic state file writes
- All 8 heartbeat tests (HB-01 through HB-06, HB-12, HB-13, HB-14) pass GREEN — including concurrency test (two agents, 3 cycles each, no SQLite BUSY errors)
- Full 93-test suite passes at 94.5% coverage (well above 80% gate); `runtime/heartbeat.py` itself at 81%

## Task Commits

1. **Task 1: Implement BaseAgent with heartbeat loop and local state persistence** - `29369ac` (feat)
2. **Task 2: Run full test suite and verify 80% coverage gate** - no commit needed (verification-only, 94.5% achieved)

## Files Created/Modified

- `runtime/heartbeat.py` — BaseAgent ABC: run(), stop(), do_peer_reviews(), do_own_tasks() hooks, _heartbeat(), _upsert_status(), _log_heartbeat_activity(), _handle_error(), _save_local_state(), _write_state_atomic(), _load_local_state()
- `runtime/config.py` — Lowered interval_seconds ge constraint from 1.0 to 0.01 (bug fix for test compatibility)
- `tests/test_heartbeat.py` — Updated HB-14 to check Path.replace() instead of Path.rename()

## Decisions Made

- `Path.replace()` chosen over `Path.rename()` for atomic state file writes. On Windows, `rename()` raises `FileExistsError` when the target already exists (second and subsequent heartbeat cycles). `replace()` is atomic and cross-platform on both POSIX and NTFS.
- `interval_seconds ge=0.01` (not `ge=1.0`) allows the test fixtures to use 0.1s cycles without validation errors, while still rejecting zero/negative values.
- `run_in_executor` wraps `os.fsync()` calls to avoid blocking the asyncio event loop during disk I/O.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Path.rename() fails on Windows when target exists**
- **Found during:** Task 1 (implement BaseAgent)
- **Issue:** `Path.rename()` on Windows raises `FileExistsError` when the destination file already exists. This means the state file write succeeds on cycle 1 but raises on every subsequent cycle (cycle 2+), causing the heartbeat to silently loop without completing work.
- **Fix:** Changed `tmp_path.rename(self._state_path)` to `tmp_path.replace(self._state_path)`. `Path.replace()` atomically overwrites the destination on both POSIX and Windows.
- **Files modified:** `runtime/heartbeat.py`, `tests/test_heartbeat.py` (HB-14 assertion updated)
- **Verification:** All 8 tests pass, jitter test no longer hangs, two-agent concurrency test completes
- **Committed in:** `29369ac` (Task 1 commit)

**2. [Rule 1 - Bug] AgentConfig interval_seconds ge=1.0 blocked test fixtures using 0.1s intervals**
- **Found during:** Task 1 (first test run)
- **Issue:** `fast_config` fixture uses `interval_seconds=0.1` but Plan 01 set `ge=1.0`. Pydantic raises `ValidationError` on fixture setup, blocking all 8 tests.
- **Fix:** Changed `Field(default=600.0, ge=1.0)` to `Field(default=600.0, ge=0.01)` in `runtime/config.py`. The constraint still prevents zero/negative intervals.
- **Files modified:** `runtime/config.py`
- **Verification:** All fixtures instantiate successfully; test_config.py still passes (existing constraint tests unaffected)
- **Committed in:** `29369ac` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 x Rule 1 bugs)
**Impact on plan:** Both fixes essential for cross-platform correctness and test operation. No scope creep. The Path.replace() fix is the more significant one — it prevented the heartbeat loop from silently failing after the first cycle on Windows.

## Issues Encountered

- The `asyncio.sleep` mock in HB-04 (jitter test) exposed the `Path.rename()` Windows bug. The jitter test appeared to hang because the interval sleep ran but the second heartbeat never completed — `_write_state_atomic` raised `FileExistsError` on cycle 2+, which was swallowed by `_handle_error`. Added instrumentation to identify the root cause and applied the `Path.replace()` fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `BaseAgent` is ready for subclassing in Phase 3 (BossAgent) and Phase 4 (WorkerAgent)
- Both abstract hooks (`do_peer_reviews`, `do_own_tasks`) are well-defined and documented
- Phase 2 complete: all 14 HB requirements (HB-01 through HB-14) satisfied across Plans 01 and 02

## Self-Check: PASSED

- `runtime/heartbeat.py`: FOUND
- `.planning/phases/02-agent-heartbeat-framework/02-02-SUMMARY.md`: FOUND
- Commit `29369ac`: FOUND
- All 93 tests: PASSED (94.5% coverage)

---
*Phase: 02-agent-heartbeat-framework*
*Completed: 2026-03-01*
