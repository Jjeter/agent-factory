---
phase: 02-agent-heartbeat-framework
plan: "00"
subsystem: testing
tags: [pytest, pytest-asyncio, tdd, heartbeat, wave-0, nyquist]

# Dependency graph
requires:
  - phase: 01-core-runtime
    provides: Database, AgentStatusRecord, models — all imported in test stubs and conftest fixtures
provides:
  - tests/conftest.py with tmp_db, fast_config, stub_agent shared fixtures
  - tests/test_config.py with HB-10, HB-11 stubs (AgentConfig load + validation)
  - tests/test_notifier.py with HB-07, HB-08, HB-09 stubs (Notifier protocol + StdoutNotifier)
  - tests/test_heartbeat.py with HB-01 through HB-06, HB-12, HB-13, HB-14 stubs (BaseAgent behaviors)
affects:
  - 02-01 (Wave 1: config + notifier implementation — tests are pre-written RED)
  - 02-02 (Wave 2: heartbeat implementation — tests are pre-written RED)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import pattern: Phase 2 modules imported inside fixture bodies to avoid ImportError before implementation"
    - "fast_config pattern: AgentConfig(interval_seconds=0.1, jitter_seconds=0.0, stagger_offset_seconds=0.0) for sub-second tests"
    - "run_for_n_cycles helper: wraps _heartbeat to count cycles and call stop() after N, enabling bounded async test loops"
    - "atomic rename tracking: patch Path.rename + check .tmp suffix to verify write-then-rename pattern"

key-files:
  created:
    - tests/conftest.py
    - tests/test_config.py
    - tests/test_notifier.py
    - tests/test_heartbeat.py
  modified: []

key-decisions:
  - "Lazy imports in conftest fixtures: all Phase 2 module imports (runtime.config, runtime.heartbeat, runtime.notifier) are inside fixture bodies, not at module level, so conftest.py itself always imports cleanly before implementation exists"
  - "run_for_n_cycles uses direct attribute assignment (_heartbeat = counted_heartbeat) rather than types.MethodType binding, avoiding the need for __func__ access on already-bound methods"
  - "Stagger test uses abs(duration - 0.05) < 0.001 tolerance to handle float comparison correctly"
  - "HB-14 atomic write test patches Path.rename and checks .tmp suffix — implementation-agnostic approach that works with both tempfile.NamedTemporaryFile and manual tmp path patterns"

patterns-established:
  - "Wave 0 first: test stubs committed before any implementation code, per Nyquist validation requirement in config.json"
  - "All 13 test functions named to match the validation map in 02-RESEARCH.md exactly"

requirements-completed: [HB-01, HB-02, HB-03, HB-04, HB-05, HB-06, HB-07, HB-08, HB-09, HB-10, HB-11, HB-12, HB-13, HB-14]

# Metrics
duration: 2min
completed: 2026-03-01
---

# Phase 2 Plan 00: Wave 0 Test Stubs Summary

**13 pytest stubs covering all 14 Phase 2 requirements written before any implementation, with lazy imports in conftest ensuring zero collection errors until runtime**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T04:10:09Z
- **Completed:** 2026-03-01T04:12:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `tests/conftest.py` with three shared async fixtures (tmp_db, fast_config, stub_agent) using lazy imports to prevent collection failures before Phase 2 modules exist
- Created `tests/test_config.py` (2 tests), `tests/test_notifier.py` (3 tests), `tests/test_heartbeat.py` (8 tests) — all 13 stubs collected by pytest with zero errors
- Established `run_for_n_cycles` helper pattern that wraps `_heartbeat` with a cycle counter for bounded async test loops without production-length sleeps
- All tests confirmed RED: `pytest --collect-only` collects 13 tests; full run would fail at import (runtime.config, runtime.notifier, runtime.heartbeat do not yet exist)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/conftest.py with shared fixtures** - `a05f1cf` (test)
2. **Task 2: Create test stubs for config, notifier, and heartbeat** - `73e3b91` (test)

**Plan metadata:** (committed as part of final docs commit)

## Files Created/Modified

- `tests/conftest.py` — Shared async fixtures: tmp_db (Database), fast_config (AgentConfig 0.1s interval), stub_agent (concrete no-op StubAgent)
- `tests/test_config.py` — HB-10: valid YAML load; HB-11: missing fields raise ValidationError
- `tests/test_notifier.py` — HB-07: isinstance Protocol check; HB-08: review_ready stdout; HB-09: escalation stdout
- `tests/test_heartbeat.py` — HB-01+02: hook override proof; HB-03: state file per cycle; HB-04: jitter sleep; HB-05: stagger once; HB-06: two agents no collision; HB-12: agent_status upsert; HB-13: stop() clean exit; HB-14: atomic rename

## Decisions Made

- Lazy imports inside fixture bodies instead of module-level imports so conftest.py always loads cleanly before Wave 1 implementation exists
- `run_for_n_cycles` uses direct attribute assignment (`agent._heartbeat = counted_heartbeat`) rather than `types.MethodType` to avoid needing `__func__` access on already-bound coroutine methods
- HB-14 atomic write test patches `Path.rename` and checks `.tmp` suffix — implementation-agnostic and compatible with `tempfile.NamedTemporaryFile` + rename pattern documented in RESEARCH.md

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 stubs complete: all 14 requirement test functions named and collecting
- Wave 1 executor can run `pytest tests/test_config.py tests/test_notifier.py -x` immediately to verify RED, then implement `runtime/config.py` and `runtime/notifier.py` to turn GREEN
- Wave 2 executor can run `pytest tests/test_heartbeat.py -x` to verify RED, then implement `runtime/heartbeat.py`
- No blockers

---
*Phase: 02-agent-heartbeat-framework*
*Completed: 2026-03-01*
