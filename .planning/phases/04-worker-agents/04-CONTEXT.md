# Phase 4: Worker Agents - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Functional worker agents (researcher, writer, strategist) that claim and execute tasks, produce versioned documents, and perform independent peer reviews. Delivers `runtime/worker.py` (`WorkerAgent(BaseAgent)`), role YAML config loading (base+overlay), and the full worker heartbeat cycle. Factory cluster generation, tool integration, and agent health monitoring are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Task claiming
- Add `assigned_role TEXT` column to `tasks` table via `ALTER TABLE tasks ADD COLUMN assigned_role TEXT`
- Boss stores `assigned_role` (e.g., `'researcher'`) at task creation — the existing `TaskSpec.assigned_role` field already captures this, just needs to be persisted
- Workers claim by role: `SELECT ... FROM tasks WHERE assigned_role = ? AND status = 'todo' ORDER BY priority DESC LIMIT 1`
- Atomic claim guard on the UPDATE: `WHERE id = ? AND status = 'todo'` prevents double-claim if stagger timing is ever tight
- **Resume-first priority**: each heartbeat checks for an existing `WHERE assigned_to = my_id AND status = 'in-progress'` task first; if found, re-execute and resubmit before claiming anything new
- **One task per heartbeat**: worker claims and executes one task then stops; no draining loop
- Supports multiple agents of the same role — natural load balancing falls out of the stagger design (each agent picks up the next available task on its own heartbeat cadence)

### Role YAML config (base + overlay)
- `config/cluster.yaml` — shared fields for all agents: `db_path`, `interval_seconds`, `jitter_seconds`
- `config/agents/<role>.yaml` — role-specific fields: `agent_id`, `agent_role`, `stagger_offset_seconds`, `system_prompt`, `tool_allowlist`
- Worker merges both at startup: cluster.yaml provides defaults, role YAML overrides/extends
- `AgentConfig` (runtime/config.py) gains two new fields: `system_prompt: str` and `tool_allowlist: list[str]`
- `load_agent_config()` updated to accept an optional cluster config path and merge the two dicts before validation

### Tool allowlist enforcement
- API-level enforcement only: worker reads `tool_allowlist` from config and passes only those tools to `messages.create(tools=[...])` — LLM cannot call unlisted tools because they are never offered
- **Phase 4: no tools** — workers use text-only LLM calls (`tools=[]` or omitted); tool definitions wired in Phase 5/6 when the cluster workspace exists
- Tool allowlist field is present in YAML and config model now so Phase 5 can populate it without touching worker logic

### Execution output
- All roles produce **free-form markdown** — no per-role structured Pydantic output
- The role's `system_prompt` in YAML guides the LLM to write in-role (researcher writes findings/sources sections, writer writes prose, strategist writes recommendations)
- Output saved as a new row in `documents` table: `title`, `content` (markdown), `version`, `created_by`, `task_id`
- **Version increments on re-submission**: each execution attempt creates a new `documents` row with `version = prior_max + 1`; old versions are preserved for audit

### Re-execution context (resumed/rejected tasks)
- When resuming an in-progress task, worker fetches: (1) latest document version content, (2) all `task_comments` of type `feedback` or `rejection` for that task
- Both are included in the LLM user message so the model sees what it produced before and specifically why it was rejected
- First-time execution (no prior document): prompt contains only task title + description

### Peer review execution
- **Independent review**: reviewer sees task title, task description, and the latest document content only — no prior reviewer comments
- Prevents anchoring bias; LLM reviewers pile onto whatever is already flagged rather than independently evaluating
- Reviewer always uses **Sonnet tier** regardless of reviewer agent's configured model tier (carried from Phase 3)
- Structured output via `messages.parse()`: `ReviewDecision(decision: Literal['approve', 'reject'], feedback: str, required_changes: str | None)`
- `feedback` must be substantive (enforced via system prompt instruction — "minimum 2 sentences with specific observations")
- `required_changes` is populated only on rejection and describes what specifically must change
- After decision: post `task_comment` of type `feedback` with combined feedback + required_changes text; update `task_reviews` row for this reviewer to `approved` or `rejected`

### Claude's Discretion
- Exact system prompt wording for each built-in role (researcher, writer, strategist)
- Exact rejection threshold language in the reviewer system prompt
- How to handle the edge case where a task has no document yet but is in `peer_review` (log warning, skip review)
- Whether `load_agent_config()` takes two paths or auto-discovers cluster.yaml from the role YAML's parent directory

</decisions>

<specifics>
## Specific Ideas

- Multiple agents of the same role are a first-class design target — the role-based claiming model (not pre-assignment to agent_id) enables this without any coordination logic
- Anchoring bias concern drove the independent review decision: LLM reviewers should each bring a fresh perspective; aggregation happens at the boss level, not the review level

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseAgent` (runtime/heartbeat.py): `WorkerAgent` subclasses this, overriding `do_peer_reviews()` and `do_own_tasks()`. All heartbeat loop, stagger, state file, and DB status machinery is inherited.
- `BossAgent` (runtime/boss.py): implementation template — same `messages.parse()` pattern, same `open_write()`/`open_read()` DB pattern, same activity_log insert pattern. Worker mirrors this structure.
- `TaskStateMachine` (runtime/state_machine.py): `todo → in-progress` (claim) and `in-progress → peer_review` (submit) transitions already defined. Worker uses `machine.apply()` for all state changes.
- `ReviewStatus` enum (runtime/models.py): `pending | approved | rejected` — worker sets reviewer's row to approved/rejected after review decision.
- `AgentConfig` (runtime/config.py): gains `system_prompt: str` and `tool_allowlist: list[str]` fields; `load_agent_config()` gains cluster.yaml merge logic.
- `_uuid()`, `_now_iso()` (runtime/models.py): use for document IDs and timestamps.

### Established Patterns
- LLM structured output: `await self._llm.messages.parse(..., output_format=SomePydanticModel)` — same as `DecompositionResult`, `GoalCompletionResult`, `UnblockingHint` in boss.py
- DB write cycle: `db = await self._db.open_write()` → `execute()` → `commit()` → `close()` in finally block
- DB read cycle: `db = await self._db.open_read()` → `async with db.execute(...) as cur` → `fetchall()`/`fetchone()` → `close()` in finally block
- Activity log insert: `INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) VALUES (...)` with `json.dumps()` for details

### Integration Points
- `tasks` table: needs `ALTER TABLE tasks ADD COLUMN assigned_role TEXT` (schema migration in `schema.sql` + `DatabaseManager.up()`)
- `task_reviews` table: worker updates `status` column for its own reviewer row after review decision
- `documents` table: worker inserts new rows; version computed as `SELECT MAX(version) FROM documents WHERE task_id = ?` + 1
- `task_comments` table: worker inserts `feedback` type comment after peer review; inserts `progress` type comment after task execution
- Worker is launched identically to boss: `asyncio.run(WorkerAgent(config).start())`; Docker Compose service per worker (Phase 5)

</code_context>

<deferred>
## Deferred Ideas

- Actual tool definitions (web_search, read_file, write_file, run_bash) — Phase 5/6 when cluster workspace exists; tool_allowlist field is already in config model
- Agent health monitoring (detecting missed heartbeats across agents) — Phase 7 hardening
- Worker reassigning a stuck task to a peer of the same role — boss handles stuck detection; worker just resumes its own in-progress tasks

</deferred>

---

*Phase: 04-worker-agents*
*Context gathered: 2026-03-04*
