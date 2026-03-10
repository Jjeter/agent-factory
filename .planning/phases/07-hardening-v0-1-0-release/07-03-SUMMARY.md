---
phase: 07-hardening-v0-1-0-release
plan: "03"
subsystem: runtime
tags: [python, asyncio, aiosqlite, sqlite, heartbeat, boss-agent, worker-agent, crash-recovery, awol-detection]

# Dependency graph
requires:
  - phase: 07-hardening-v0-1-0-release
    provides: "07-01 TDD RED stubs for AWOL-01/02 and CRASH-01/02; 07-02 tool allowlist enforcement"

provides:
  - "BossAgent._check_awol_agents() — scans agent_status, detects 3x interval gap, alerts notifier once per session"
  - "BossAgent._alert_awol_agent() — dedup via self._alerted_awol set + activity_log entry with action='agent_awol'"
  - "BaseAgent._current_task_id and _resumed_task_id fields; start() captures prior state; _write_state_file() persists real task id"
  - "WorkerAgent.do_own_tasks() crash recovery path using _resumed_task_id before normal claiming"
  - "WorkerAgent._fetch_task_if_still_mine() — re-queries DB to guard against stale state file (Pitfall 5)"
  - "4 new GREEN tests replacing xfail stubs: AWOL-01, AWOL-02 in test_boss.py; CRASH-01, CRASH-02 in test_heartbeat.py"

affects:
  - 07-04 (packaging/release — no direct code dep but full suite must be GREEN before release)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AWOL detection: query agent_status, compare last_heartbeat to now using (now - last).total_seconds() > threshold"
    - "Dedup alerting: self._alerted_awol: set[str] prevents repeated notifier calls per session"
    - "Crash recovery guard: always re-query DB with AND assigned_to = ? AND status = 'in-progress' before resuming (Pitfall 5)"
    - "_current_task_id managed with set-before/clear-after pattern in do_own_tasks"
    - "Naive timestamp fix: .replace(tzinfo=timezone.utc) after fromisoformat() — consistent with Phase 3 pattern"

key-files:
  created: []
  modified:
    - runtime/boss.py
    - runtime/heartbeat.py
    - runtime/worker.py
    - tests/test_boss.py
    - tests/test_heartbeat.py

key-decisions:
  - "AWOL uses 4-column activity_log INSERT (no task_id column) — agent-level event, not task-level; schema task_id is nullable"
  - "notify_escalation(agent_id, reason) repurposes the task_id parameter position for agent_id — Notifier protocol is general enough (first param is an ID, second is reason)"
  - "WorkerAgent.__init__ initializes _resumed_task_id = None; BaseAgent.start() overwrites it from state file before first tick — subclass init runs before start()"
  - "Normal do_own_tasks path also sets/clears _current_task_id so state file captures task in all execution branches"
  - "getattr(self, '_current_task_id', None) in _write_state_file() provides safe fallback for subclasses that don't set the field"

patterns-established:
  - "AWOL detection mirrors _detect_stuck_tasks() structure: read-only query → per-row decision → write action method"
  - "Crash recovery: set _resumed_task_id at start(), clear it on first tick regardless of outcome — one-shot semantics"

requirements-completed: [AWOL-01, AWOL-02, CRASH-01, CRASH-02]

# Metrics
duration: 10min
completed: 2026-03-10
---

# Phase 7 Plan 03: AWOL Detection + Crash Recovery Summary

**AWOL detection via 3x-interval heartbeat comparison with per-session dedup, and crash recovery via state-file resume with DB re-validation guard — 4 xfail stubs replaced with GREEN tests (134 passed, 86.17% coverage)**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-10T09:33:31Z
- **Completed:** 2026-03-10T09:43:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Implemented `BossAgent._check_awol_agents()` and `_alert_awol_agent()` with dedup via `self._alerted_awol: set[str]`; each AWOL detection writes an `activity_log` entry with `action='agent_awol'` and calls `notifier.notify_escalation()` exactly once per session per agent
- Extended `BaseAgent` with `_current_task_id` and `_resumed_task_id` fields; `start()` now captures the prior state file result and sets `_resumed_task_id`; `_write_state_file()` persists the real `_current_task_id` instead of always writing `None`
- Added `WorkerAgent._fetch_task_if_still_mine()` and crash recovery path in `do_own_tasks()` that checks `_resumed_task_id` before normal claiming, re-queries DB to guard against stale state (Pitfall 5 per RESEARCH.md)
- Replaced all 4 xfail stubs (AWOL-01, AWOL-02, CRASH-01, CRASH-02) with real GREEN tests; full suite: 134 passed + 14 xpassed at 86.17% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: AWOL detection in BossAgent + replace AWOL test stubs** - `81164dc` (feat)
2. **Task 2: Crash recovery in BaseAgent/WorkerAgent + replace crash stubs** - `90f8475` (feat)

## Files Created/Modified

- `runtime/boss.py` - Added `_alerted_awol` set to `__init__`, `_check_awol_agents()`, `_alert_awol_agent()`, call in `do_own_tasks()`
- `runtime/heartbeat.py` - Added `_current_task_id`, `_resumed_task_id` to `__init__`; `start()` captures state; `_write_state_file()` persists real task id
- `runtime/worker.py` - Added `_resumed_task_id` init, crash recovery path in `do_own_tasks()`, `_fetch_task_if_still_mine()` helper
- `tests/test_boss.py` - Replaced 2 xfail stubs with `test_check_awol_agents_fires_notifier` and `test_check_awol_agents_does_not_double_alert`
- `tests/test_heartbeat.py` - Replaced 2 xfail stubs with `test_crash_resume_in_progress_task` and `test_crash_resume_skips_reassigned_task`

## Decisions Made

- AWOL activity_log insert uses 4-column form without `task_id` — AWOL is an agent-level event (no task involved); schema has `task_id` as nullable, so omitting it is correct
- `notify_escalation(agent_id, reason)` reuses the `task_id` parameter position for `agent_id` — the Notifier Protocol parameter name is misleading but the signature accepts any string ID as first arg
- `WorkerAgent.__init__` initializes `_resumed_task_id = None`; `BaseAgent.start()` then sets it before the first tick — subclass constructor runs first, parent's `start()` overwrites cleanly
- Normal claiming path (non-crash) also sets and clears `_current_task_id` so that state file always records the active task regardless of which code path executed the task
- `getattr(self, '_current_task_id', None)` in `_write_state_file()` provides safe fallback for `FixedTickAgent` and other test subclasses that don't call `WorkerAgent.__init__`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AWOL-01, AWOL-02, CRASH-01, CRASH-02 all GREEN — error resilience requirements complete for v0.1.0
- Full suite at 86.17% coverage (above 80% gate) — ready for Phase 7 Plan 04 (packaging/release)
- 14 xpassed tests (from prior phases): no action needed per established pattern (strict=False markers remain)

---
*Phase: 07-hardening-v0-1-0-release*
*Completed: 2026-03-10*

## Self-Check: PASSED

- runtime/boss.py: FOUND
- runtime/heartbeat.py: FOUND
- runtime/worker.py: FOUND
- tests/test_boss.py: FOUND
- tests/test_heartbeat.py: FOUND
- .planning/phases/07-hardening-v0-1-0-release/07-03-SUMMARY.md: FOUND
- Commit 81164dc (AWOL detection + stubs): FOUND
- Commit 90f8475 (crash recovery + stubs): FOUND
