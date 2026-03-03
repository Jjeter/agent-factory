---
phase: "03"
plan: "01"
subsystem: boss-agent
tags: [boss, peer-review, goal-decomposition, tdd, asyncio, pydantic]
dependency_graph:
  requires: [runtime/heartbeat.py, runtime/state_machine.py, runtime/database.py, runtime/models.py, runtime/notifier.py]
  provides: [runtime/boss.py]
  affects: [tests/test_boss.py]
tech_stack:
  added: [anthropic.AsyncAnthropic, pydantic.BaseModel (TaskSpec / DecompositionResult)]
  patterns: [TDD red-green, async DB context manager, LLM structured output via messages.parse]
key_files:
  created: [runtime/boss.py]
  modified: [tests/test_boss.py]
decisions:
  - "All 10 tests written in one RED commit (tests for both Task 1 and Task 2) then boss.py made everything GREEN at once — plan allowed this as Task 2 noted 'no changes needed to boss.py'"
  - "mock patch.object(boss._llm.messages, 'parse', ...) works directly — no need for class-level AsyncAnthropic patch"
  - "9 xfail stubs remain for Wave 2 (gap-fill, stuck detection, activity log placeholders)"
metrics:
  duration_minutes: 6
  completed_date: "2026-03-03"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 3 Plan 01: BossAgent Core (Wave 1) Summary

**One-liner:** BossAgent(BaseAgent) with AsyncAnthropic LLM client, peer-review promotion/rejection, and goal decomposition via Pydantic structured output.

## What Was Built

### runtime/boss.py (300 lines)

BossAgent subclasses BaseAgent, overriding `do_peer_reviews()` and `do_own_tasks()`.

**Pydantic output models** (for LLM calls):
- `TaskSpec` — title, description, assigned_role, reviewer_roles, priority, model_tier
- `DecompositionResult` — wraps `list[TaskSpec]`
- `GoalCompletionResult` — is_complete + reason (Wave 2)
- `UnblockingHint` — hint string (Wave 2)

**BossAgent.__init__:**
- Calls `super().__init__(config, notifier)` — inherits all heartbeat machinery
- Sets `self._llm = AsyncAnthropic()` — reads ANTHROPIC_API_KEY from env
- Sets `self._heartbeat_counter = 0`

**do_peer_reviews():** Fetches all `peer_review` tasks, evaluates each:
- All approved → `_promote_to_review()`: UPDATE tasks status='review', INSERT activity_log action='task_promoted', call `notifier.notify_review_ready()`
- Any rejected → `_reject_back_to_in_progress()`: UPDATE tasks status='in-progress', UPDATE task_reviews SET status='pending', INSERT activity_log action='task_rejected'
- Pending → no-op

**decompose_goal():** Calls `_llm.messages.parse()` with `output_format=DecompositionResult`, resolves reviewer roles → agent_ids via `agent_status` table, inserts task rows + task_review rows + activity_log rows.

**do_own_tasks():** Increments `_heartbeat_counter` — Wave 2 stub for gap-fill/completion check.

### tests/test_boss.py (411 lines)

Full test implementations replacing all relevant xfail stubs:
- Structure group (3): isinstance check, _llm type, _heartbeat_counter initial value
- Promotion group (3): all-approved→review, pending→no-op, rejected→in-progress with review reset
- Decomposition group (3): task rows created, reviewer_roles JSON stored, task_review rows created
- Re-review UNIQUE constraint (1): INSERT OR REPLACE handles repeated rows after rejection

Remaining xfail stubs (9): gap-fill x3, stuck detection x4, activity log x2 (Wave 2/3).

## Test Results

```
63 passed, 16 xfailed in 72s
Coverage: 97.07% (required: 80%)
runtime/boss.py: 94% (7 uncovered lines — exception path + Wave 2 stubs)
```

## Deviations from Plan

### Deviation 1: All 10 Wave 1 tests implemented in a single RED commit

The plan split Task 1 (6 structure+promotion tests) and Task 2 (4 decompose+re-review tests) across two TDD cycles. Since the test helpers (`_make_db`, `_insert_*`, `_make_boss`) were shared by both groups, all 10 tests were written together in one commit. When `boss.py` was created, all 10 went GREEN simultaneously. This is a no-risk deviation — the plan itself noted "no changes needed to boss.py" for Task 2.

### Deviation 2: 10 GREEN (not 9) on first run

The plan's success criteria said "9 tests GREEN" for plan 03-01, but re-reading the task text more carefully, Task 1 done criteria says 6 GREEN and Task 2 done criteria says 10 total GREEN. Both were achieved. The 9-vs-10 discrepancy in the `<success_criteria>` block (which says "10 tests GREEN") vs the `<objective>` block (which says "9 stubs converted") reflects Wave-1 test count ambiguity. Actual result: **10 GREEN, 9 xfail** which matches `<success_criteria>`.

### Deviation 3: Mock strategy — patch.object worked directly

The plan noted: "If `boss._llm.messages.parse` cannot be mocked via `patch.object`, use `patch('runtime.boss.AsyncAnthropic')` at class construction time instead." Direct `patch.object(boss._llm.messages, 'parse', new=AsyncMock(...))` worked without needing the fallback.

## Self-Check

Files created:
- runtime/boss.py: EXISTS
- .planning/phases/03-boss-agent/03-01-SUMMARY.md: EXISTS (this file)

Commits:
- 36cb932 test(03-01): add failing tests for BossAgent structure + promotion (TDD RED)
- c76ca6b feat(03-01): implement BossAgent core — peer review promotion and goal decomposition
