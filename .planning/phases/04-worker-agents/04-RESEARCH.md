# Phase 4: Worker Agents - Research

**Researched:** 2026-03-04
**Domain:** Python async agent implementation — WorkerAgent subclass, role YAML config, LLM task execution, structured peer review
**Confidence:** HIGH

## Summary

Phase 4 is an internal implementation phase that extends the existing codebase, not a green-field technology selection problem. All dependencies are already installed (anthropic, pydantic, aiosqlite, pyyaml). The primary question is "how to wire WorkerAgent correctly given what already exists," not "what libraries to use."

The architecture is deeply constrained by Phase 3 decisions: WorkerAgent subclasses BaseAgent, overrides exactly two methods (`do_peer_reviews` and `do_own_tasks`), and replicates the BossAgent structural pattern — same `messages.parse()` LLM calls, same `open_write`/`open_read` DB cycles, same `activity_log` inserts. The schema needs one migration (`ALTER TABLE tasks ADD COLUMN assigned_role TEXT`) and the config model needs two new fields (`system_prompt`, `tool_allowlist`).

The peer review path uses `messages.parse()` with a `ReviewDecision` Pydantic model (approve/reject + feedback) and always uses Sonnet regardless of the reviewer agent's configured model tier. Task execution uses the task's `model_tier` column to select the LLM model dynamically. Phase 4 intentionally has no tool calls — workers do text-only LLM calls; the `tool_allowlist` field is seeded in YAML now so Phase 5 can populate it without touching worker logic.

**Primary recommendation:** Mirror the BossAgent pattern precisely. Every structural choice in WorkerAgent should match boss.py: async helpers as private methods, DB open/close in try/finally, `_uuid()` + `_now_iso()` for IDs and timestamps, `json.dumps()` for details in activity_log.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Task claiming:**
- Add `assigned_role TEXT` column to `tasks` table via `ALTER TABLE tasks ADD COLUMN assigned_role TEXT`
- Boss stores `assigned_role` (e.g., `'researcher'`) at task creation — the existing `TaskSpec.assigned_role` field already captures this, just needs to be persisted
- Workers claim by role: `SELECT ... FROM tasks WHERE assigned_role = ? AND status = 'todo' ORDER BY priority DESC LIMIT 1`
- Atomic claim guard on the UPDATE: `WHERE id = ? AND status = 'todo'` prevents double-claim if stagger timing is ever tight
- **Resume-first priority**: each heartbeat checks for an existing `WHERE assigned_to = my_id AND status = 'in-progress'` task first; if found, re-execute and resubmit before claiming anything new
- **One task per heartbeat**: worker claims and executes one task then stops; no draining loop
- Supports multiple agents of the same role — natural load balancing falls out of the stagger design

**Role YAML config (base + overlay):**
- `config/cluster.yaml` — shared fields for all agents: `db_path`, `interval_seconds`, `jitter_seconds`
- `config/agents/<role>.yaml` — role-specific fields: `agent_id`, `agent_role`, `stagger_offset_seconds`, `system_prompt`, `tool_allowlist`
- Worker merges both at startup: cluster.yaml provides defaults, role YAML overrides/extends
- `AgentConfig` gains two new fields: `system_prompt: str` and `tool_allowlist: list[str]`
- `load_agent_config()` updated to accept an optional cluster config path and merge the two dicts before validation

**Tool allowlist enforcement:**
- API-level enforcement only: pass only listed tools to `messages.create(tools=[...])`
- **Phase 4: no tools** — workers use text-only LLM calls (`tools=[]` or omitted)
- Tool allowlist field is present in YAML and config model now so Phase 5 can populate it without touching worker logic

**Execution output:**
- All roles produce **free-form markdown** — no per-role structured Pydantic output
- Output saved as new row in `documents` table: `title`, `content` (markdown), `version`, `created_by`, `task_id`
- **Version increments on re-submission**: `version = SELECT MAX(version) FROM documents WHERE task_id = ? + 1`; old versions preserved

**Re-execution context (resumed/rejected tasks):**
- When resuming in-progress task, worker fetches: (1) latest document version content, (2) all `task_comments` of type `feedback` or `rejection` for that task
- Both included in LLM user message so model sees prior output and specific rejection reasons
- First-time execution (no prior document): prompt contains only task title + description

**Peer review execution:**
- **Independent review**: reviewer sees task title, task description, and latest document content only — no prior reviewer comments
- Reviewer always uses **Sonnet tier** regardless of reviewer agent's configured model tier
- Structured output via `messages.parse()`: `ReviewDecision(decision: Literal['approve', 'reject'], feedback: str, required_changes: str | None)`
- `feedback` must be substantive (enforced via system prompt — "minimum 2 sentences with specific observations")
- `required_changes` populated only on rejection
- After decision: post `task_comment` of type `feedback`; update `task_reviews` row for this reviewer

### Claude's Discretion
- Exact system prompt wording for each built-in role (researcher, writer, strategist)
- Exact rejection threshold language in the reviewer system prompt
- How to handle the edge case where a task has no document yet but is in `peer_review` (log warning, skip review)
- Whether `load_agent_config()` takes two paths or auto-discovers cluster.yaml from the role YAML's parent directory

### Deferred Ideas (OUT OF SCOPE)
- Actual tool definitions (web_search, read_file, write_file, run_bash) — Phase 5/6 when cluster workspace exists
- Agent health monitoring (detecting missed heartbeats across agents) — Phase 7 hardening
- Worker reassigning a stuck task to a peer of the same role — boss handles stuck detection; worker just resumes its own in-progress tasks
</user_constraints>

## Standard Stack

### Core (already installed — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.40.0 | LLM calls via AsyncAnthropic | Already used in BossAgent; `messages.parse()` for structured output |
| pydantic | >=2.0.0 | `ReviewDecision` model, `AgentConfig` extension | Already used throughout; locked pattern |
| aiosqlite | >=0.20.0 | Async SQLite for all DB operations | Already used; WAL mode established |
| pyyaml | >=6.0.0 | Load cluster.yaml + role YAML files | Already used in `load_agent_config()` |

### No New Dependencies

Phase 4 requires zero new packages. All required libraries are already in `pyproject.toml`. The implementation is purely additive to the existing runtime package.

**Installation:** None required.

## Architecture Patterns

### New Files This Phase

```
runtime/
└── worker.py              # WorkerAgent(BaseAgent) — the entire phase deliverable

config/
├── cluster.yaml           # Shared base config (db_path, interval_seconds, jitter_seconds)
└── agents/
    ├── researcher.yaml    # agent_id, agent_role, stagger_offset_seconds, system_prompt, tool_allowlist
    ├── writer.yaml
    └── strategist.yaml

tests/
└── test_worker.py         # TDD test file for WorkerAgent
```

### Changes to Existing Files

```
runtime/config.py          # Add system_prompt: str, tool_allowlist: list[str] to AgentConfig
                           # Update load_agent_config() to accept optional cluster config path
runtime/schema.sql         # ALTER TABLE tasks ADD COLUMN assigned_role TEXT
runtime/database.py        # Update up() to run the migration (ADD COLUMN if not exists)
runtime/boss.py            # Update _insert_task() to persist spec.assigned_role
```

### Pattern 1: WorkerAgent Class Structure

Mirror BossAgent exactly. Single file, private async methods, two public overrides.

```python
# Source: runtime/boss.py (established pattern)
class WorkerAgent(BaseAgent):
    def __init__(self, config: AgentConfig, notifier: Notifier | None = None) -> None:
        super().__init__(config, notifier)
        self._llm = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

    async def do_peer_reviews(self) -> None:
        """Priority gate: handle all pending peer reviews before own tasks."""
        pending = await self._fetch_pending_reviews()
        for task_id in pending:
            await self._perform_review(task_id)

    async def do_own_tasks(self) -> None:
        """Resume-first: check in-progress task before claiming new one."""
        task = await self._fetch_in_progress_task()
        if task is None:
            task = await self._claim_next_task()
        if task is None:
            return  # Nothing to do this heartbeat
        await self._execute_task(task)
```

### Pattern 2: Resume-First Task Claiming

Two separate DB queries. Resume-first is mandatory.

```python
# Step 1: check for own in-progress task
async def _fetch_in_progress_task(self):
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT id, title, description, model_tier FROM tasks "
            "WHERE assigned_to = ? AND status = 'in-progress'",
            (self._config.agent_id,),
        ) as cur:
            return await cur.fetchone()
    finally:
        await db.close()

# Step 2: claim by role with atomic guard
async def _claim_next_task(self):
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT id, title, description, model_tier FROM tasks "
            "WHERE assigned_role = ? AND status = 'todo' ORDER BY priority DESC LIMIT 1",
            (self._config.agent_role,),
        ) as cur:
            candidate = await cur.fetchone()
    finally:
        await db.close()

    if candidate is None:
        return None

    # Atomic claim: UPDATE only if still 'todo'
    db = await self._db.open_write()
    try:
        await db.execute(
            "UPDATE tasks SET status = 'in-progress', assigned_to = ?, updated_at = ? "
            "WHERE id = ? AND status = 'todo'",
            (self._config.agent_id, _now_iso(), candidate["id"]),
        )
        await db.execute(
            "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
            "VALUES (?, ?, ?, 'task_claimed', ?, ?)",
            (_uuid(), self._config.agent_id, candidate["id"],
             json.dumps({"role": self._config.agent_role}), _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()
    return candidate
```

### Pattern 3: Conditional LLM Prompt (First vs. Re-execution)

```python
async def _build_execution_prompt(self, task_id: str, title: str, description: str) -> str:
    # Check for prior document
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT content FROM documents WHERE task_id = ? ORDER BY version DESC LIMIT 1",
            (task_id,),
        ) as cur:
            doc_row = await cur.fetchone()
        async with db.execute(
            "SELECT content FROM task_comments "
            "WHERE task_id = ? AND comment_type IN ('feedback', 'rejection') "
            "ORDER BY created_at ASC",
            (task_id,),
        ) as cur:
            feedback_rows = await cur.fetchall()
    finally:
        await db.close()

    if doc_row is None:
        # First execution
        return f"Task: {title}\n\n{description}"
    else:
        # Re-execution with context
        feedback_text = "\n\n".join(r["content"] for r in feedback_rows)
        return (
            f"Task: {title}\n\n{description}\n\n"
            f"--- Your previous output ---\n{doc_row['content']}\n\n"
            f"--- Rejection feedback ---\n{feedback_text}\n\n"
            "Please revise your output addressing all feedback above."
        )
```

### Pattern 4: Document Version Computation

```python
async def _compute_next_version(self, task_id: str) -> int:
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT MAX(version) as max_ver FROM documents WHERE task_id = ?",
            (task_id,),
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    return (row["max_ver"] or 0) + 1
```

### Pattern 5: ReviewDecision Structured Output

```python
# New Pydantic model in worker.py (not models.py — internal to worker)
class ReviewDecision(pydantic.BaseModel):
    decision: Literal["approve", "reject"]
    feedback: str
    required_changes: str | None = None
```

The peer review LLM call pattern mirrors BossAgent's `messages.parse()` usage:

```python
# Source: runtime/boss.py _post_unblocking_hint / _decompose_goal pattern
parsed = await self._llm.messages.parse(
    model="claude-sonnet-4-6",   # Always Sonnet for reviews regardless of agent tier
    max_tokens=1024,
    system=(
        "You are a peer reviewer. Evaluate the work objectively. "
        "Write a minimum of 2 sentences with specific observations. "
        "Only reject if there are substantive quality issues."
    ),
    messages=[{
        "role": "user",
        "content": (
            f"Task: {title}\n\nDescription: {description}\n\n"
            f"--- Work to review ---\n{document_content}"
        ),
    }],
    output_format=ReviewDecision,
)
decision = parsed.parsed_output
```

### Pattern 6: AgentConfig Extension

```python
# runtime/config.py additions
class AgentConfig(BaseModel):
    # ... existing fields ...
    system_prompt: str = Field(default="")
    tool_allowlist: list[str] = Field(default_factory=list)
```

### Pattern 7: load_agent_config() with Base Overlay

The CONTEXT.md gives Claude discretion on whether `load_agent_config()` takes two paths or auto-discovers. Recommendation: **take two paths explicitly** — simpler to test, no magic directory traversal.

```python
def load_agent_config(path: Path, cluster_config_path: Path | None = None) -> AgentConfig:
    """Load and validate AgentConfig from role YAML, optionally merged with cluster base."""
    raw: dict = yaml.safe_load(path.read_text(encoding="utf-8"))
    if cluster_config_path is not None:
        cluster_raw: dict = yaml.safe_load(cluster_config_path.read_text(encoding="utf-8"))
        # cluster provides defaults; role YAML overrides/extends
        merged = {**cluster_raw, **raw}
    else:
        merged = raw
    return AgentConfig.model_validate(merged)
```

### Pattern 8: Schema Migration in DatabaseManager.up()

SQLite does not support `IF NOT EXISTS` on `ALTER TABLE ADD COLUMN` directly, but the column's absence can be detected and handled:

```python
# In DatabaseManager.up() — after init_schema()
# Add assigned_role column if not already present
try:
    await conn.execute("ALTER TABLE tasks ADD COLUMN assigned_role TEXT")
    await conn.commit()
except Exception:
    pass  # Column already exists — aiosqlite raises OperationalError on duplicate
```

The correct approach is to catch `aiosqlite.OperationalError` (or the base `Exception`) when the column already exists. SQLite returns "duplicate column name: assigned_role" for repeated ALTER TABLE.

### Pattern 9: Boss Persists assigned_role

Update `_insert_task()` in boss.py to include `assigned_role` in the INSERT:

```python
# In BossAgent._insert_task() — add assigned_role to INSERT
await db.execute(
    "INSERT INTO tasks (id, goal_id, title, description, assigned_to, status, "
    "priority, model_tier, escalation_count, reviewer_roles, assigned_role, created_at, updated_at) "
    "VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, 0, ?, ?, ?, ?)",
    (
        task_id, goal_id, spec.title, spec.description, None,
        spec.priority, spec.model_tier,
        json.dumps(spec.reviewer_roles),
        spec.assigned_role,    # NEW
        now, now,
    ),
)
```

### Pattern 10: Peer Review — Fetch Pending Reviews for This Agent

```python
async def _fetch_pending_reviews(self) -> list[str]:
    """Return task_ids where this agent is a pending reviewer and task is in peer_review."""
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT tr.task_id FROM task_reviews tr "
            "JOIN tasks t ON t.id = tr.task_id "
            "WHERE tr.reviewer_id = ? AND tr.status = 'pending' AND t.status = 'peer_review'",
            (self._config.agent_id,),
        ) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()
    return [row["task_id"] for row in rows]
```

### Anti-Patterns to Avoid

- **Draining loop in do_own_tasks**: worker processes exactly ONE task per heartbeat. No `while` loop claiming multiple tasks.
- **Nesting asyncio.run()**: already enforced by BaseAgent pattern. Never call `asyncio.run()` inside async context.
- **Fetching reviewer comments during peer review**: independent review means the reviewer sees ONLY task title, description, and latest document. No prior `task_comments` of type `feedback` from other reviewers.
- **Using messages.create() instead of messages.parse()**: all structured LLM calls use `messages.parse()` with Pydantic models. Only the task execution call (free-form markdown) uses `messages.create()`.
- **Mutating config dicts**: always use `{**base, **override}` spread, never mutate in place.
- **Calling machine.apply() but not persisting the result**: the state machine validates and returns the new status; the caller must UPDATE the DB immediately.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output parsing | Custom JSON extraction regex | `messages.parse(output_format=ReviewDecision)` | Already established in boss.py; handles schema validation, retry, error surfacing |
| Async DB connection pooling | Custom semaphore/pool | `DatabaseManager.open_write()` / `open_read()` | Already built in Phase 1; WAL mode handles concurrent reads |
| State transition validation | `if status == 'todo' and target == 'in-progress'` | `TaskStateMachine.apply()` | Already built; raises typed `InvalidTransitionError` |
| UUID generation | `str(uuid.uuid4())` inline | `_uuid()` from `runtime.models` | Project convention; consistent with all existing code |
| ISO timestamp generation | `datetime.now().isoformat()` inline | `_now_iso()` from `runtime.models` | Project convention; UTC-aware, consistent |
| YAML loading | Custom parser | `yaml.safe_load()` | Already used in `load_agent_config()`; `safe_load` prevents code execution |

**Key insight:** Every utility this phase needs already exists in the codebase. The work is wiring, not building primitives.

## Common Pitfalls

### Pitfall 1: Double-Claim Race (Stagger Timing)
**What goes wrong:** Two workers of the same role both SELECT the same `todo` task and both try to claim it.
**Why it happens:** If stagger timing is imperfect or a heartbeat runs long, two agents could see the same `todo` row.
**How to avoid:** The UPDATE must use `WHERE id = ? AND status = 'todo'`. Check `rowcount` after execute — if 0 rows affected, another agent claimed it first; abandon and return.
**Warning signs:** Tasks appearing with two `assigned_to` values in logs (impossible with atomic guard, so this validates the guard is working).

### Pitfall 2: Missing `assigned_role` on Existing Tasks
**What goes wrong:** Tasks inserted by old BossAgent code (before the migration) have `assigned_role = NULL`. Workers filtering by `assigned_role = ?` never pick them up.
**Why it happens:** Schema migration adds the column but existing rows have NULL; boss INSERT was not updated.
**How to avoid:** In the same Wave that adds the column migration, also update `boss.py`'s `_insert_task()` to include `assigned_role`. Tests for the worker claim query must insert tasks WITH `assigned_role` set.

### Pitfall 3: `ALTER TABLE` Fails on Second `up()` Call
**What goes wrong:** `DatabaseManager.up()` is called in tests before each test; the second call fails because the column already exists.
**Why it happens:** SQLite `ALTER TABLE ADD COLUMN` raises `OperationalError: duplicate column name` on repeat.
**How to avoid:** Catch the `OperationalError` (or check `PRAGMA table_info(tasks)` first). The try/except pattern is simpler and well-established in SQLite migration code.

### Pitfall 4: Anchoring Bias in Peer Review (Already Decided, Enforce in Code)
**What goes wrong:** Reviewer fetches all prior `task_comments` including other reviewers' feedback, causing all reviewers to pile onto the same issues.
**Why it happens:** It seems natural to include all context. The CONTEXT.md explicitly bans this.
**How to avoid:** The peer review query fetches ONLY the latest document (`documents` table) and NO `task_comments`. This is enforced by code structure, not just convention.

### Pitfall 5: Using Wrong Model for Peer Review
**What goes wrong:** Peer reviewer uses `self._config.model_tier` (haiku by default) for the review call instead of Sonnet.
**Why it happens:** Task execution correctly uses the `model_tier` from the task row; it's natural to reuse that pattern for reviews.
**How to avoid:** In `_perform_review()`, always hardcode `model="claude-sonnet-4-6"`. The reviewer's config tier is irrelevant to review quality.

### Pitfall 6: Forgetting to Update `task_reviews` After Review Decision
**What goes wrong:** Feedback comment is posted but `task_reviews.status` stays `pending`. BossAgent's `_evaluate_reviews()` never sees approval/rejection, so tasks never promote.
**Why it happens:** Two separate DB writes are needed; easy to write only the `task_comment` insert.
**How to avoid:** `_perform_review()` must do both in the same write cycle: INSERT task_comment + UPDATE task_reviews WHERE task_id = ? AND reviewer_id = ?.

### Pitfall 7: Version Count Off-By-One on First Document
**What goes wrong:** `MAX(version)` returns NULL when no prior documents exist. `NULL + 1` in Python is a TypeError.
**Why it happens:** SQL `MAX()` on empty set returns NULL; Python doesn't coerce NULL→0.
**How to avoid:** `(row["max_ver"] or 0) + 1` — the `or 0` handles the NULL case.

### Pitfall 8: `messages.parse()` Attribute Path
**What goes wrong:** Code accesses `parsed.output` or `parsed.result` instead of `parsed.parsed_output`.
**Why it happens:** The attribute name is not obvious.
**How to avoid:** Match boss.py exactly: `parsed = await self._llm.messages.parse(...)` then `parsed.parsed_output.field`. This is verified in existing test_boss.py mocks.

## Code Examples

### Task Execution — Full LLM Call

```python
# Source: mirrors runtime/boss.py _decompose_goal pattern
async def _execute_task(self, task: aiosqlite.Row) -> None:
    task_id = task["id"]
    model = task["model_tier"]  # haiku | sonnet | opus from tasks table

    # Map model_tier string to actual model ID
    MODEL_MAP = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-6",
        "opus": "claude-opus-4-6",
    }
    model_id = MODEL_MAP.get(model, "claude-haiku-4-5-20251001")

    prompt = await self._build_execution_prompt(task_id, task["title"], task["description"])
    try:
        response = await self._llm.messages.create(
            model=model_id,
            max_tokens=4096,
            system=self._config.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
    except Exception:
        logger.exception("LLM execution failed for task %s", task_id)
        raise  # Let BaseAgent._tick() catch and set ERROR status

    version = await self._compute_next_version(task_id)
    now = _now_iso()
    db = await self._db.open_write()
    try:
        # Insert document
        await db.execute(
            "INSERT INTO documents (id, task_id, title, content, version, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_uuid(), task_id, task["title"], content, version, self._config.agent_id, now),
        )
        # Post progress comment
        await db.execute(
            "INSERT INTO task_comments (id, task_id, agent_id, comment_type, content, created_at) "
            "VALUES (?, ?, ?, 'progress', ?, ?)",
            (_uuid(), task_id, self._config.agent_id, f"Submitted version {version}", now),
        )
        # Transition to peer_review
        await db.execute(
            "UPDATE tasks SET status = 'peer_review', updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        # Log activity
        await db.execute(
            "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
            "VALUES (?, ?, ?, 'task_submitted', ?, ?)",
            (_uuid(), self._config.agent_id, task_id,
             json.dumps({"version": version, "model": model}), now),
        )
        await db.commit()
    finally:
        await db.close()
```

### Role YAML Example — researcher.yaml

```yaml
# config/agents/researcher.yaml
agent_id: researcher-01
agent_role: researcher
stagger_offset_seconds: 150.0   # 2.5 minutes
system_prompt: |
  You are a researcher agent. Produce well-structured findings in markdown.
  Include: an executive summary, key findings with supporting evidence,
  sources or reasoning cited inline, and open questions if any remain.
  Be concise but thorough. Write for a technical audience.
tool_allowlist: []  # No tools in Phase 4; populated in Phase 5
```

### cluster.yaml Example

```yaml
# config/cluster.yaml
db_path: db/cluster.db
interval_seconds: 600.0
jitter_seconds: 30.0
```

### Test Pattern — Mocking the LLM

```python
# Source: test_boss.py established pattern
async def test_worker_executes_task(tmp_path):
    from runtime.worker import WorkerAgent
    from runtime.config import AgentConfig

    db_mgr = await _make_db(tmp_path)
    config = AgentConfig(
        agent_id="researcher-01",
        agent_role="researcher",
        db_path=str(tmp_path / "test.db"),
        system_prompt="You are a researcher.",
        tool_allowlist=[],
    )
    worker = WorkerAgent(config)
    worker._db = db_mgr

    # Set up: goal + task with assigned_role
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(db_mgr, goal_id)
    await _insert_task_with_role(db_mgr, task_id, goal_id, "todo", "researcher")

    # Mock LLM
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="# Findings\n\nResearch output here.")]
    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await worker.do_own_tasks()

    # Verify task moved to peer_review + document created
    db = await db_mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
        assert row["status"] == "peer_review"
        async with db.execute("SELECT content, version FROM documents WHERE task_id = ?", (task_id,)) as cur:
            doc = await cur.fetchone()
        assert doc["version"] == 1
        assert "Research output" in doc["content"]
    finally:
        await db.close()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `messages.create()` + manual JSON parse | `messages.parse(output_format=PydanticModel)` | Phase 3 (boss.py) | Structured LLM output with schema validation — use for ReviewDecision |
| `Path.rename()` for atomic writes | `Path.replace()` | Phase 1 (models.py note) | Windows-safe atomic file replacement |
| `asyncio.run()` per-tick | `asyncio.run()` once in `__main__` wrapping `agent.start()` | Phase 1 (CLI) | Never nested; already enforced |
| `agent_role` only | `role` or `agent_role` interchangeable | Phase 2 (config.py model_validator) | Both accepted; validator normalizes |

## Open Questions

1. **`load_agent_config()` signature: two paths vs. auto-discovery**
   - What we know: CONTEXT.md leaves this to Claude's discretion
   - What's unclear: whether callers in Phase 5 will know both paths at call time
   - Recommendation: explicit two-path signature `load_agent_config(role_path, cluster_config_path=None)` — simpler to test and more transparent than magic directory traversal

2. **Edge case: task in `peer_review` with no document yet**
   - What we know: CONTEXT.md leaves handling to Claude's discretion
   - What's unclear: should this warn+skip or raise?
   - Recommendation: log WARNING and skip (`return` early). An empty document causes a confusing review; skipping lets boss handle via stuck detection.

3. **`escalation_count` increment on rejection**
   - What we know: REQUIREMENTS.md says rejection increments `escalation_count`; CONTEXT.md says boss handles escalation based on count threshold
   - What's unclear: does the worker increment it, or does the boss increment it when resetting to in-progress?
   - Recommendation: boss increments it in `_reject_back_to_in_progress()`. Worker reads it via `model_tier` column (already escalated by boss). Check existing `_reject_back_to_in_progress` — it does NOT increment currently. Boss's stuck detection escalates via `escalation_count`. This is a gap to address: either worker increments on submission to peer_review, or boss increments when rejecting. **Boss is the right owner** (it has the full picture of all review outcomes). Add `escalation_count = escalation_count + 1` to `_reject_back_to_in_progress()` in boss.py.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_worker.py -x` |
| Full suite command | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| W-01 | WorkerAgent subclasses BaseAgent with correct override signatures | unit | `pytest tests/test_worker.py::test_worker_inherits_base_agent -x` | Wave 0 |
| W-02 | AgentConfig accepts system_prompt + tool_allowlist fields | unit | `pytest tests/test_config.py -x` | Extend existing |
| W-03 | load_agent_config() merges cluster.yaml + role YAML correctly | unit | `pytest tests/test_worker.py::test_load_agent_config_merge -x` | Wave 0 |
| W-04 | schema.sql / up() adds assigned_role column idempotently | unit | `pytest tests/test_worker.py::test_schema_migration_idempotent -x` | Wave 0 |
| W-05 | Resume-first: in-progress task is resumed before claiming new | unit | `pytest tests/test_worker.py::test_resume_first -x` | Wave 0 |
| W-06 | Claim query filters by assigned_role | unit | `pytest tests/test_worker.py::test_claim_by_role -x` | Wave 0 |
| W-07 | Atomic claim guard: second worker cannot steal claimed task | unit | `pytest tests/test_worker.py::test_atomic_claim_guard -x` | Wave 0 |
| W-08 | First execution: prompt contains only title + description | unit | `pytest tests/test_worker.py::test_first_execution_prompt -x` | Wave 0 |
| W-09 | Re-execution: prompt includes prior doc + feedback comments | unit | `pytest tests/test_worker.py::test_reexecution_prompt -x` | Wave 0 |
| W-10 | Execution saves document + posts progress comment + moves to peer_review | unit | `pytest tests/test_worker.py::test_execute_task_full_cycle -x` | Wave 0 |
| W-11 | Document version increments on re-submission | unit | `pytest tests/test_worker.py::test_document_version_increment -x` | Wave 0 |
| W-12 | Peer review: fetches pending reviews for this agent | unit | `pytest tests/test_worker.py::test_fetch_pending_reviews -x` | Wave 0 |
| W-13 | Peer review: always uses Sonnet model regardless of agent tier | unit | `pytest tests/test_worker.py::test_review_uses_sonnet -x` | Wave 0 |
| W-14 | Peer review: ReviewDecision structured output parsed correctly | unit | `pytest tests/test_worker.py::test_review_decision_parsed -x` | Wave 0 |
| W-15 | Peer review: posts feedback comment + updates task_reviews status | unit | `pytest tests/test_worker.py::test_review_posts_comment_and_updates_status -x` | Wave 0 |
| W-16 | Peer review: reviewer does NOT see prior reviewer comments | unit | `pytest tests/test_worker.py::test_review_independent -x` | Wave 0 |
| W-17 | Peer review: skips task with no document (logs warning) | unit | `pytest tests/test_worker.py::test_review_skips_no_document -x` | Wave 0 |
| W-18 | No tasks available: do_own_tasks returns without error | unit | `pytest tests/test_worker.py::test_no_tasks_noop -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_worker.py -x`
- **Per wave merge:** `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_worker.py` — all 18 stubs above (RED phase)
- [ ] Extend `tests/test_config.py` — cover new `system_prompt` + `tool_allowlist` fields
- [ ] No framework install needed — pytest already configured

## Sources

### Primary (HIGH confidence)

- Direct code reading: `runtime/boss.py` — established LLM call patterns, DB write cycle, activity_log inserts
- Direct code reading: `runtime/heartbeat.py` — BaseAgent interface, `do_peer_reviews` / `do_own_tasks` signatures
- Direct code reading: `runtime/config.py` — AgentConfig fields, `load_agent_config()` signature
- Direct code reading: `runtime/schema.sql` — current schema, missing `assigned_role` column confirmed
- Direct code reading: `runtime/models.py` — `_uuid()`, `_now_iso()`, `ReviewStatus`, `TaskStatus` exports
- Direct code reading: `tests/test_boss.py` — mock patterns (`patch.object`, `AsyncMock`, `parsed_output` attribute)
- Direct code reading: `.planning/phases/04-worker-agents/04-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- `pyproject.toml` — confirmed all required dependencies already present, no new installs needed
- `tests/conftest.py` — `_make_db` helper pattern, `create_goal`/`create_task` async helpers

### Tertiary (LOW confidence)

- None — all findings sourced from direct codebase inspection, no external research required for this phase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all libraries already in pyproject.toml and used in phases 1-3
- Architecture: HIGH — WorkerAgent pattern directly derived from BossAgent source; no speculation
- Pitfalls: HIGH — all pitfalls sourced from actual code (NULL handling, OperationalError, attribute names) or locked decisions in CONTEXT.md
- Validation architecture: HIGH — test framework already running; 18 test names derived from phase deliverables + success criteria

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (stable — no external dependencies, internal implementation only)
