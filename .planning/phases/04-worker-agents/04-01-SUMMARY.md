---
phase: 04-worker-agents
plan: "01"
subsystem: runtime
tags: [worker-agent, config, schema, migration, tdd]
dependency_graph:
  requires: [04-00]
  provides: [assigned_role-column, config-merge, worker-agent-prerequisites]
  affects: [runtime/config.py, runtime/schema.sql, runtime/database.py, runtime/boss.py]
tech_stack:
  added: []
  patterns: [base+overlay YAML merge, idempotent ALTER TABLE migration, pydantic optional fields]
key_files:
  created: []
  modified:
    - runtime/config.py
    - runtime/schema.sql
    - runtime/database.py
    - runtime/boss.py
    - tests/test_config.py
    - tests/test_worker.py
decisions:
  - load_agent_config cluster_config_path is a loading concern only (not on AgentConfig model)
  - ALTER TABLE migration uses bare except to catch both OperationalError and any future variant
  - assigned_role added to schema.sql DDL AND via ALTER TABLE for both fresh and existing DBs
metrics:
  duration: "8 minutes"
  completed_date: "2026-03-06"
  tasks_completed: 2
  files_changed: 6
---

# Phase 4 Plan 01: WorkerAgent Prerequisites Summary

WorkerAgent infrastructure prerequisites: two-path config merge for cluster+role YAML, assigned_role column migration in DatabaseManager.up(), and boss._insert_task() persistence.

## Tasks Completed

| # | Task | Commit | Key Changes |
|---|------|--------|-------------|
| TDD RED | W-03 xfail + W-04 test stub | 511f2a8 | test_config.py W-03 xfail; test_worker.py test_schema_migration_idempotent |
| 1 | Extend AgentConfig + load_agent_config | 6b6b753 | load_agent_config accepts cluster_config_path; {**cluster_raw, **role_raw} merge |
| 2 | Schema migration + boss assigned_role | 49cd8d8 | schema.sql column; database.py ALTER TABLE; boss.py INSERT persists assigned_role |

## Success Criteria Verification

- [x] AgentConfig has `system_prompt` (str, default "") and `tool_allowlist` (list[str], default []) — already implemented in 04-00, verified passing
- [x] `load_agent_config` accepts optional `cluster_config_path` and merges correctly — implemented in Task 1
- [x] tasks table has `assigned_role` column after `up()` — implemented in Task 2
- [x] `up()` is idempotent (safe to call twice) — ALTER TABLE wrapped in bare except
- [x] boss._insert_task persists spec.assigned_role — column added to INSERT statement
- [x] All prior tests remain GREEN — 92 passed, 18 skipped (worker stubs), 0 failed

## Test Results

```
tests/test_config.py    4 passed
tests/test_worker.py::test_schema_migration_idempotent  1 passed
tests/test_boss.py      29 passed
Total: 92 passed, 18 skipped, 0 failed
Coverage: 98.29% (exceeds 80% threshold)
```

## Deviations from Plan

### Pre-existing Implementation (W-02 fields)

AgentConfig `system_prompt` and `tool_allowlist` fields were already added in phase 04-00 (confirmed by running tests). The test `test_agent_config_system_prompt_and_tool_allowlist` was already GREEN at plan start. No action needed for W-02 — only W-03 and W-04 required implementation.

### xfail Marker Added by Linter (Rule 3 - auto-fixed)

After adding `test_schema_migration_idempotent` to test_worker.py in the RED commit, a project hook added `@pytest.mark.xfail` to the new test. This was correct behavior at the time (test was RED before implementation). After implementing the migration, the marker was already removed by the linter/hook system (XPASS → hook removed it), resulting in a clean GREEN test.

### test_worker.py Already Existed (Pre-created in 04-00)

The test file `tests/test_worker.py` was pre-created in phase 04-00 with 18 test stubs (W-01 through W-18), all gated by `pytest.importorskip("runtime.worker")`. This plan only needed to add the standalone `test_schema_migration_idempotent` test (not gated by runtime.worker) and remove the xfail from W-03 in test_config.py.

## Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| `cluster_config_path` is a loading concern only, not an `AgentConfig` field | AgentConfig represents runtime config, not file loading logic — keeps model clean |
| Bare `except Exception: pass` for ALTER TABLE | Catches both `OperationalError` (SQLite column already exists) and any edge-case DB error |
| `assigned_role` in both schema.sql DDL and ALTER TABLE migration | Fresh DBs get column from DDL; existing pre-04-01 DBs get column from migration |
| Role values win on merge conflict: `{**cluster_raw, **role_raw}` | Role YAML is more specific; cluster YAML provides shared defaults |

## Self-Check: PASSED

Files verified:
- runtime/config.py — contains `cluster_config_path` parameter and merge logic
- runtime/schema.sql — contains `assigned_role TEXT` column definition
- runtime/database.py — contains ALTER TABLE migration in up()
- runtime/boss.py — INSERT includes `assigned_role` column and `spec.assigned_role` value

Commits verified:
- 511f2a8 (TDD RED)
- 6b6b753 (Task 1 feat)
- 49cd8d8 (Task 2 feat)
