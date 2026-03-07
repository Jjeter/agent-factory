---
phase: 05-factory-cluster-core-product
plan: "04"
subsystem: testing
tags: [e2e, pytest, aiosqlite, factory, artifact-generation, cluster]

# Dependency graph
requires:
  - phase: 05-factory-cluster-core-product/05-01
    provides: generator functions (render_dockerfile, render_requirements_txt, copy_runtime, etc.)
  - phase: 05-factory-cluster-core-product/05-03
    provides: factory CLI + runner, all 126 tests GREEN
  - phase: 01-core-runtime-database-state-machine
    provides: DatabaseManager with open_write/open_read/up() and schema.sql

provides:
  - E2E-01: test_full_artifact_created verifying complete cluster directory (Dockerfile, requirements.txt, launch.sh, docker-compose.yml, runtime/, config/agents/, db/schema.sql, .env.example)
  - E2E-02: test_db_seeded_correctly verifying goal row roundtrip and agent_status table queryability
  - 128 tests GREEN at 88.41% coverage with factory/ measured

affects: [phase-6-demo-cluster, phase-7-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "E2E tests exercise generator + DB layers with no LLM calls — pure fixture-driven"
    - "open_write()/open_read() must be awaited (not used as async context managers) — return aiosqlite.Connection directly"

key-files:
  created: []
  modified:
    - tests/test_factory_e2e.py

key-decisions:
  - "open_write()/open_read() return aiosqlite.Connection directly (await required, not async with) — plan template had incorrect async with pattern; fixed per existing test_boss.py usage"
  - "E2E tests use no LLM calls — fixture RoleSpec data drives generator functions directly"
  - "agent_status table queryability verified by SELECT count(*) after DatabaseManager.up() — actual rows seeded at agent startup not factory time"

patterns-established:
  - "E2E fixture pattern: importorskip at test function body scope (not module), direct await of open_write/open_read with finally/close"

requirements-completed: [E2E-01, E2E-02]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 5 Plan 04: E2E Tests Summary

**E2E-01 and E2E-02 integration tests close Phase 5 — 128 tests GREEN at 88.41% coverage with factory/ package measured**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T13:33:56Z
- **Completed:** 2026-03-07T13:36:57Z
- **Tasks:** 1 (of 1 auto tasks; checkpoint:human-verify pending)
- **Files modified:** 1

## Accomplishments
- test_full_artifact_created (E2E-01): verifies full cluster artifact directory structure matching REQUIREMENTS §5, including Dockerfile (FROM python:3.12-slim), requirements.txt (contains "anthropic"), launch.sh (ANTHROPIC_API_KEY guard + exit 1), docker-compose.yml (valid YAML with boss/critic/analyst services), runtime/__init__.py, config/agents/*.yaml, db/schema.sql, .env.example
- test_db_seeded_correctly (E2E-02): verifies goal row INSERT and SELECT roundtrip with id/title/description/status fields, and agent_status table queryability after DatabaseManager.up()
- Full pytest suite: 128 tests GREEN, 88.41% overall coverage (factory/ included)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement E2E tests** - `fd9ca1e` (feat)

## Files Created/Modified
- `tests/test_factory_e2e.py` - Replaced xfail stubs with full E2E-01 and E2E-02 tests

## Decisions Made
- `open_write()/open_read()` return `aiosqlite.Connection` directly — must be awaited (not used as `async with`). Plan template used `async with mgr.open_write() as conn:` which is incorrect. Fixed to `conn = await mgr.open_write()` with explicit `finally: await conn.close()`.
- E2E tests use no LLM calls — all generator functions called directly with fixture RoleSpec data.
- agent_status table queryability verified via `SELECT count(*) as cnt FROM agent_status` — table must exist and be queryable; actual agent rows populated at runner startup (not factory time).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect async context manager usage of open_write/open_read**
- **Found during:** Task 1 (test_db_seeded_correctly first run)
- **Issue:** Plan template used `async with mgr.open_write() as conn:` but `open_write()` returns a coroutine yielding `aiosqlite.Connection` — no `__aexit__` method, so `async with` raises `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`
- **Fix:** Changed all three DB operations to `conn = await mgr.open_write()` / `await mgr.open_read()` with `try/finally: await conn.close()` — consistent with conftest.py and test_boss.py patterns
- **Files modified:** tests/test_factory_e2e.py
- **Verification:** `python -m pytest tests/test_factory_e2e.py -v --no-cov` — 2 passed
- **Committed in:** fd9ca1e (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in plan template)
**Impact on plan:** Necessary correctness fix. No scope creep. Both tests GREEN as specified.

## Issues Encountered
- Plan template contained incorrect `async with mgr.open_write() as conn:` pattern. The DatabaseManager API uses plain `await` + explicit close (not async context manager). Identified from test failure traceback and confirmed by inspecting conftest.py and test_boss.py. Auto-fixed per Rule 1.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 5 complete: 128 tests GREEN at 88.41% coverage, E2E-01 and E2E-02 GREEN
- checkpoint:human-verify pending — user should run full suite and confirm: `python -m pytest --cov=runtime --cov=factory --cov-report=term-missing --cov-fail-under=80 -q`
- Phase 6 (Demo Cluster + Integration) is unblocked

---
*Phase: 05-factory-cluster-core-product*
*Completed: 2026-03-07*
