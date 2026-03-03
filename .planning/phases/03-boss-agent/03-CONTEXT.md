# Phase 3: Boss Agent - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

A single `BossAgent(BaseAgent)` class that coordinates the cluster: decomposes goals into tasks, promotes tasks through peer review, detects stuck work, and escalates model tiers. Does NOT include worker task execution, factory output generation, or agent health monitoring (Phase 7).

</domain>

<decisions>
## Implementation Decisions

### Task decomposition strategy
- **Hybrid scaffold**: boss makes one LLM call upfront and creates 3-5 initial tasks covering the goal
- Every 3 heartbeats, boss runs a gap-fill check: generates missing tasks AND evaluates goal completion
- Goal completion check uses an LLM boolean judgment: "Is this goal fully achieved based on completed tasks?" — if yes, goal status moves to `completed` and task generation stops
- Tasks are **role-targeted**: boss assigns each task a specific worker role and tailors the description to that role's strengths

### Reviewer assignment
- At task creation time, boss stores which roles should review the task (e.g., a `reviewer_roles` field) — no extra LLM call at promotion time
- At least 2 reviewers required per task; must be different roles than the worker who completed it
- All peer reviews are performed at **Sonnet** model tier regardless of the reviewer agent's default tier
- **Any single rejection** returns the task to `in-progress` (strict quality gate)
- Every heartbeat, boss scans all `peer_review` tasks and promotes to `review` when ALL assigned reviewers have approved

### Stuck task escalation
- Stuck threshold: task in `in-progress` for > 30 min
- **First intervention**: escalate `model_tier` (haiku → sonnet → opus) and update `escalation_count`
- **Second intervention** (still stuck after another 30 min at escalated tier): boss makes an LLM call analyzing task description + comments, posts an unblocking hint as a `task_comment`
- Activity log entries for escalation include: `action="task_escalated"`, `details` with old tier, new tier, and `stuck_since` timestamp
- Agent health monitoring (missed heartbeats) is **deferred to Phase 7**

### CLI output style
- Default: **human-readable table** (aligned columns), `--json` flag for machine-readable output
- `cluster tasks list` columns: short ID, title, status, assigned_to, model_tier, priority
- `cluster tasks list --status <state>` for filtering by task status
- `cluster approve <task-id>` validates task is in `review` state before applying transition — uses `TaskStateMachine.apply()` and raises a clear error otherwise

### Claude's Discretion
- Exact Rich/tabulate library choice for table rendering
- Precise LLM prompt wording for decomposition and goal-completion calls
- Whether `reviewer_roles` is a new column on `tasks` or a separate join table
- Stuck detection polling frequency within the heartbeat cycle

</decisions>

<specifics>
## Specific Ideas

- Reviewer model tier is always Sonnet regardless of reviewer agent's own tier — boss enforces this at assignment time
- Boss is the only agent with authority to: create tasks, promote tasks (`peer_review` → `review`), escalate model tiers, mark goals complete
- The gap-fill every 3 heartbeats is a heartbeat counter check inside `do_own_tasks()`, not a separate timer

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseAgent` (runtime/heartbeat.py): `BossAgent` subclasses this, overriding `do_peer_reviews()` and `do_own_tasks()`. All heartbeat loop, state file, and DB status machinery is inherited.
- `TaskStateMachine` (runtime/state_machine.py): `peer_review → review` (promotion) and `peer_review → in-progress` (rejection) transitions already defined. Boss uses `machine.apply()` for all state changes.
- `Task` model (runtime/models.py): already has `model_tier`, `escalation_count`, `stuck_since`, `priority`, `assigned_to` fields — no schema changes needed for escalation logic.
- `ActivityLog` model (runtime/models.py): `action` + optional `details` (str) — boss logs escalation details here.
- `cluster_cli` Click group (runtime/cli.py:9-13): boss CLI subcommands (`goal set`, `tasks list`, `agents status`, `approve`) extend this existing group.

### Established Patterns
- Async DB writes: `db = await self._db.open_write()` → `await db.execute(...)` → `await db.commit()` → `await db.close()` (see heartbeat.py:77-98)
- Activity log inserts: `INSERT INTO activity_log (id, agent_id, action, details, created_at)` with `_uuid()` and `_now_iso()` (heartbeat.py:100-111)
- All DB writes use parameterized queries (no SQL injection)

### Integration Points
- `BossAgent.do_peer_reviews()` — scans `peer_review` tasks, checks `task_reviews` table, promotes or logs rejections
- `BossAgent.do_own_tasks()` — handles stuck detection, gap-fill (every 3 heartbeats), and goal-completion check
- Boss reads `agent_status` table to know which agents are idle (for reviewer assignment)
- New CLI commands attach to the existing `cluster_cli` group in `runtime/cli.py`

</code_context>

<deferred>
## Deferred Ideas

- Agent health monitoring (detecting missed heartbeats) — Phase 7 hardening
- Reassigning stuck tasks to a different worker (after investigation) — Claude's discretion during Phase 3 implementation if LLM hint doesn't unblock

</deferred>

---

*Phase: 03-boss-agent*
*Context gathered: 2026-03-02*
