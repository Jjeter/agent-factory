---
phase: 06-demo-cluster-integration-validation
plan: "01"
subsystem: tests
tags: [tdd, red-gate, phase-6, cli, artifact]
dependency_graph:
  requires: []
  provides: [TDD-RED-gate-approve-logs-demo-artifact]
  affects: [tests/test_factory_cli.py, tests/test_demo_artifact.py]
tech_stack:
  added: []
  patterns: [pytest.importorskip-inside-test-body, xfail-strict-false, sqlite3-seeding-helpers]
key_files:
  created:
    - tests/test_demo_artifact.py
  modified:
    - tests/test_factory_cli.py
decisions:
  - "xfail(strict=False) used for all 14 stubs — allows unexpected passes without breaking the gate"
  - "Shared helpers (_make_cluster_db, _seed_goal, _seed_task, _seed_activity_log) appended to test_factory_cli.py to avoid asyncio complexity"
  - "test_demo_artifact.py uses bare Path() relative to project root (pytest CWD) — no importorskip needed"
metrics:
  duration_seconds: 212
  completed_date: "2026-03-08"
  tasks_completed: 2
  files_modified: 2
---

# Phase 6 Plan 1: TDD RED Gate — Approve/Logs/Demo/Artifact Stubs Summary

Phase 6 TDD RED gate with 9 CLI stubs (approve x3, logs x4, demo x1) and 5 artifact stubs establishing the full test contract before any implementation begins.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add approve + logs + demo stubs to tests/test_factory_cli.py | 60b082d | tests/test_factory_cli.py |
| 2 | Create tests/test_demo_artifact.py with artifact structure stubs | 34a5a04 | tests/test_demo_artifact.py |

## Verification Results

- Full suite: 128 passed, 14 xfailed, 0 errors — exit 0
- Coverage: 89.03% (unchanged from Phase 5 baseline)
- All 9 new stubs in test_factory_cli.py xfail (not error, not skip)
- All 5 stubs in test_demo_artifact.py xfail (not error, not skip)
- All 7 pre-existing test_factory_cli.py tests remain GREEN

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions

1. `xfail(strict=False)` used for all stubs — allows any unexpected passes without failing the gate, consistent with prior phase patterns.
2. Shared seeding helpers (`_make_cluster_db`, `_seed_goal`, `_seed_task`, `_seed_activity_log`) appended to `tests/test_factory_cli.py`. These use stdlib `sqlite3` (not aiosqlite) so no `asyncio.run()` is needed in test setup, matching the plan specification.
3. `tests/test_demo_artifact.py` does not use `pytest.importorskip` — the file checks filesystem paths and a sqlite3 connection only, as specified.

## Self-Check: PASSED

- tests/test_factory_cli.py: exists and modified (FOUND)
- tests/test_demo_artifact.py: exists and created (FOUND)
- Commit 60b082d: FOUND
- Commit 34a5a04: FOUND
