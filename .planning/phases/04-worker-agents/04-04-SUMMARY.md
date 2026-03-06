---
phase: 04-worker-agents
plan: "04"
subsystem: worker
tags: [peer-review, llm, structured-output, tdd]
dependency_graph:
  requires: [04-03]
  provides: [do_peer_reviews, _perform_review, _fetch_pending_reviews]
  affects: [runtime/worker.py]
tech_stack:
  added: []
  patterns: [messages.parse structured output, ReviewDecision Pydantic model, independent review context]
key_files:
  created: []
  modified: [runtime/worker.py]
decisions:
  - "Literal type annotation on ReviewDecision.decision for strict approve/reject validation"
  - "_fetch_pending_reviews uses JOIN on tasks table to filter by t.status = peer_review (not just task_reviews.status)"
  - "Explicit mapping dict approve->approved / reject->rejected (clearer than string concatenation)"
  - "Both DB writes (task_comment + task_reviews update) plus activity_log in single open_write cycle"
  - "No task_comments query in _perform_review read phase (independence requirement W-16)"
metrics:
  duration_minutes: 10
  completed_date: "2026-03-06"
  tasks_completed: 2
  files_modified: 1
---

# Phase 4 Plan 04: WorkerAgent Peer Review Summary

**One-liner:** Full peer review cycle using messages.parse + ReviewDecision structured output, independent LLM context, and atomic dual-write (feedback comment + task_reviews update).

## What Was Built

Completed the WorkerAgent peer review loop in `runtime/worker.py`:

1. **`ReviewDecision` Pydantic model** — Updated to use `Literal["approve", "reject"]` for strict type validation and `str | None = None` for optional `required_changes`.

2. **`_fetch_pending_reviews()`** — Enhanced with JOIN on `tasks` table to filter by `t.status = 'peer_review'` in addition to `task_reviews.status = 'pending'`, ensuring workers only process tasks that are actually in peer review state.

3. **`do_peer_reviews()`** — Replaced stub with real implementation: fetches pending reviews and calls `_perform_review()` for each.

4. **`_perform_review(task_id)`** — Full implementation:
   - Reads task details + latest document via `open_read` (no task_comments query — independence requirement)
   - Skips gracefully with `logger.warning` if no document found
   - Calls `self._llm.messages.parse(model="claude-sonnet-4-6", output_format=ReviewDecision)` — always Sonnet regardless of agent tier
   - Extracts `parsed.parsed_output` as `ReviewDecision`
   - Builds feedback content (appends `required_changes` on rejection)
   - Single `open_write` cycle: inserts `task_comments` feedback row + updates `task_reviews` status + logs to `activity_log`

## Tests Results

All W-12 through W-17 GREEN. Full suite: **109 passed, 1 xpassed, 98.31% coverage**.

| Test | Requirement | Result |
|------|-------------|--------|
| W-12 | _fetch_pending_reviews filters by reviewer and status | GREEN |
| W-13 | Review always uses claude-sonnet-4-6 | GREEN |
| W-14 | ReviewDecision via messages.parse() parsed_output | GREEN |
| W-15 | task_comment + task_reviews updated after review | GREEN |
| W-16 | Review prompt excludes prior reviewer comments | GREEN |
| W-17 | Graceful skip when task has no document | GREEN |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Note:** W-17 appeared to pass before implementation because `do_peer_reviews` was a stub (did nothing). It continues to pass correctly after implementation because `_perform_review` returns early with a warning when `doc_row is None`.

## Key Decisions

1. **`Literal["approve", "reject"]` on ReviewDecision** — Stronger type safety than bare `str`; Pydantic validates LLM output at parse time.

2. **JOIN tasks in `_fetch_pending_reviews`** — The existing implementation only filtered by `task_reviews.status`. Adding `AND t.status = 'peer_review'` ensures we don't attempt to review tasks that have moved past peer_review state (e.g., approved or rejected back to in-progress).

3. **Explicit status mapping dict** — `{"approve": "approved", "reject": "rejected"}[decision.decision]` is clearer and less error-prone than string concatenation (`decision + "d"`).

4. **Single write cycle for both DB writes** — The feedback comment insert and task_reviews status update happen in the same `open_write` / `db.commit()` block, ensuring atomicity.

## Self-Check

- [x] `runtime/worker.py` modified with full peer review implementation
- [x] `_fetch_pending_reviews` uses JOIN query
- [x] `_perform_review` implemented with no task_comments read
- [x] `ReviewDecision` uses `Literal` type
- [x] All W-12 through W-17 tests GREEN
- [x] Full suite 109 passed, 98.31% coverage
