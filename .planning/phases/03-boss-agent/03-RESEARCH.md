# Phase 3: Boss Agent - Research

**Researched:** 2026-03-02
**Domain:** Async Python agent orchestration — LLM-driven task decomposition, peer-review promotion, stuck detection, CLI table output
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Task decomposition strategy**
- Hybrid scaffold: boss makes one LLM call upfront and creates 3-5 initial tasks covering the goal
- Every 3 heartbeats, boss runs a gap-fill check: generates missing tasks AND evaluates goal completion
- Goal completion check uses an LLM boolean judgment: "Is this goal fully achieved based on completed tasks?" — if yes, goal status moves to `completed` and task generation stops
- Tasks are role-targeted: boss assigns each task a specific worker role and tailors the description to that role's strengths

**Reviewer assignment**
- At task creation time, boss stores which roles should review the task (a `reviewer_roles` field) — no extra LLM call at promotion time
- At least 2 reviewers required per task; must be different roles than the worker who completed it
- All peer reviews are performed at Sonnet model tier regardless of the reviewer agent's own tier
- Any single rejection returns the task to `in-progress` (strict quality gate)
- Every heartbeat, boss scans all `peer_review` tasks and promotes to `review` when ALL assigned reviewers have approved

**Stuck task escalation**
- Stuck threshold: task in `in-progress` for > 30 min
- First intervention: escalate `model_tier` (haiku → sonnet → opus) and update `escalation_count`
- Second intervention (still stuck after another 30 min at escalated tier): boss makes an LLM call analyzing task description + comments, posts an unblocking hint as a `task_comment`
- Activity log entries for escalation include: `action="task_escalated"`, `details` with old tier, new tier, and `stuck_since` timestamp
- Agent health monitoring (missed heartbeats) is deferred to Phase 7

**CLI output style**
- Default: human-readable table (aligned columns), `--json` flag for machine-readable output
- `cluster tasks list` columns: short ID, title, status, assigned_to, model_tier, priority
- `cluster tasks list --status <state>` for filtering by task status
- `cluster approve <task-id>` validates task is in `review` state before applying transition — uses `TaskStateMachine.apply()` and raises a clear error otherwise

### Claude's Discretion
- Exact Rich/tabulate library choice for table rendering
- Precise LLM prompt wording for decomposition and goal-completion calls
- Whether `reviewer_roles` is a new column on `tasks` or a separate join table
- Stuck detection polling frequency within the heartbeat cycle

### Deferred Ideas (OUT OF SCOPE)
- Agent health monitoring (detecting missed heartbeats) — Phase 7 hardening
- Reassigning stuck tasks to a different worker (after investigation) — Claude's discretion during Phase 3 implementation if LLM hint doesn't unblock
</user_constraints>

---

## Summary

Phase 3 builds `BossAgent(BaseAgent)` in `runtime/boss.py`. The boss subclasses the existing `BaseAgent` from Phase 2, overriding `do_peer_reviews()` and `do_own_tasks()` — all heartbeat loop infrastructure, DB connection management, state file I/O, and shutdown handling are inherited without modification. The two primary new capabilities are: (1) LLM-driven task lifecycle management (decomposition on goal set, periodic gap-fill, goal-completion judgment, stuck detection with escalation) and (2) four CLI subcommands attached to the existing `cluster_cli` Click group.

The LLM integration uses `AsyncAnthropic` (already a project dependency at `anthropic>=0.40.0`) with structured output via Pydantic models and `messages.parse()`. All LLM calls are awaitable, keeping them non-blocking inside the async heartbeat loop. The schema already has all required columns (`model_tier`, `escalation_count`, `stuck_since` on `tasks`; `task_reviews` with `UNIQUE(task_id, reviewer_id)`). The only schema question is whether `reviewer_roles` lands as a column on `tasks` or a separate join table — this is discretionary.

For CLI table output, `tabulate` is the recommended choice: it is a single-function library with zero transitive dependencies, already used extensively in lightweight Python CLIs, and trivially produces aligned text tables with a `--json` fallback. Rich is heavier and more appropriate for TUI-style apps; it would be an over-engineered choice here.

**Primary recommendation:** Subclass `BaseAgent` with minimal surface area — two method overrides, one `AsyncAnthropic` client instance, one heartbeat counter. Keep LLM calls in private async helpers. Use `tabulate` for human-readable CLI output. Store `reviewer_roles` as a JSON-serialized text column on `tasks` (simpler than a join table for V1, no schema migration needed).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.40.0 (already in pyproject.toml) | LLM calls to Claude Sonnet 4.6 | Official Anthropic SDK; `AsyncAnthropic` matches the async event loop in `BaseAgent` |
| pydantic | >=2.0.0 (already in pyproject.toml) | Structured output parsing from LLM | `messages.parse()` returns typed Pydantic models; avoids fragile JSON string parsing |
| aiosqlite | >=0.20.0 (already in pyproject.toml) | Async DB access | Established in Phases 1-2; all DB patterns already in place |
| click | >=8.1.0 (already in pyproject.toml) | CLI subcommands | `cluster_cli` group exists in `runtime/cli.py`; `@cluster_cli.command()` and subgroups extend it |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tabulate | ~0.9.x | Human-readable table rendering | Use for `cluster tasks list` and `cluster agents status` human output; `--json` bypasses it entirely |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tabulate | rich | Rich adds TUI, color, progress bars — substantial extra dependency not needed for simple aligned tables |
| tabulate | f-string manual formatting | Fragile for variable-width columns; tabulate handles padding automatically |
| `messages.parse()` (Pydantic) | `json.loads(message.content[0].text)` | Manual JSON parsing fails silently on malformed output; `messages.parse()` raises a typed exception |
| reviewer_roles as JSON text column | separate `task_reviewer_roles` join table | Join table is cleaner long-term but adds a schema migration and extra JOIN on every peer-review scan; V1 JSON column suffices |

**Installation** (add to pyproject.toml dependencies):
```bash
pip install tabulate>=0.9.0
```

---

## Architecture Patterns

### Recommended Project Structure
```
runtime/
├── boss.py          # BossAgent(BaseAgent) — all boss logic
├── heartbeat.py     # BaseAgent — unchanged from Phase 2
├── cli.py           # cluster_cli group — add goal/tasks/agents/approve commands here
├── models.py        # Task, Goal, etc. — unchanged (reviewer_roles added as Optional[str])
└── ...              # all other Phase 1/2 files unchanged
```

### Pattern 1: BossAgent Subclass Structure
**What:** `BossAgent` overrides exactly two methods from `BaseAgent` — `do_peer_reviews()` and `do_own_tasks()`. All other behavior (heartbeat loop, stagger, state file, DB status UPSERT, activity log, shutdown) is inherited.

**When to use:** Always. Avoids duplicating loop machinery.

**Example:**
```python
# Source: Phase 2 BaseAgent (runtime/heartbeat.py) + Anthropic SDK docs
from anthropic import AsyncAnthropic
from runtime.heartbeat import BaseAgent
from runtime.config import AgentConfig
from runtime.notifier import Notifier

class BossAgent(BaseAgent):
    def __init__(self, config: AgentConfig, notifier: Notifier | None = None) -> None:
        super().__init__(config, notifier)
        self._llm = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
        self._heartbeat_counter: int = 0

    async def do_peer_reviews(self) -> None:
        """Scan peer_review tasks; promote to review when all reviewers approved."""
        ...

    async def do_own_tasks(self) -> None:
        """Stuck detection, gap-fill every 3 heartbeats, goal-completion check."""
        self._heartbeat_counter += 1
        await self._detect_stuck_tasks()
        if self._heartbeat_counter % 3 == 0:
            await self._gap_fill_and_completion_check()
```

### Pattern 2: AsyncAnthropic Structured Output with Pydantic
**What:** Use `AsyncAnthropic().messages.parse()` with a Pydantic model to get typed task lists back from the LLM decomposition call. This is the verified, type-safe way to extract structured data.

**When to use:** For goal decomposition (returns list of task specs) and goal-completion check (returns boolean + reason). Both are structured responses.

**Example:**
```python
# Source: Context7 /anthropics/anthropic-sdk-python — Parse Structured Outputs with Pydantic Models
import pydantic
from anthropic import AsyncAnthropic

class TaskSpec(pydantic.BaseModel):
    title: str
    description: str
    assigned_role: str
    reviewer_roles: list[str]
    priority: int
    model_tier: str  # haiku | sonnet | opus

class DecompositionResult(pydantic.BaseModel):
    tasks: list[TaskSpec]

class GoalCompletionResult(pydantic.BaseModel):
    is_complete: bool
    reason: str

async def _decompose_goal(self, goal_description: str) -> list[TaskSpec]:
    llm = AsyncAnthropic()  # ANTHROPIC_API_KEY from env
    parsed = await llm.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="You are a boss agent. Decompose the goal into 3-5 concrete tasks...",
        messages=[{"role": "user", "content": goal_description}],
        output_format=DecompositionResult,
    )
    return parsed.parsed_output.tasks
```

**IMPORTANT NOTE:** `messages.parse()` is a synchronous client method in the SDK. For the async variant, use `await async_client.messages.parse(...)`. The async client (`AsyncAnthropic`) is the correct choice here because `do_own_tasks()` and `do_peer_reviews()` are async methods.

### Pattern 3: Peer Review Promotion Scan
**What:** Every heartbeat, boss runs a read-only scan of all `peer_review` tasks, checks `task_reviews` for each, and promotes if all reviewer rows are `approved`.

**When to use:** Inside `do_peer_reviews()`.

**Example:**
```python
# Pattern derived from Phase 2 DB access patterns (heartbeat.py:77-98)
async def do_peer_reviews(self) -> None:
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT id, title FROM tasks WHERE status = 'peer_review'"
        ) as cur:
            tasks_in_review = await cur.fetchall()
    finally:
        await db.close()

    for task_row in tasks_in_review:
        task_id = task_row["id"]
        # Check if ALL reviews are approved (no pending, no rejected)
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved "
                "FROM task_reviews WHERE task_id = ?",
                (task_id,),
            ) as cur:
                counts = await cur.fetchone()
        finally:
            await db.close()

        total = counts["total"]
        approved = counts["approved"]
        if total > 0 and total == approved:
            await self._promote_to_review(task_id, task_row["title"])
```

### Pattern 4: Stuck Detection with ISO 8601 Arithmetic
**What:** Compare `stuck_since` (ISO 8601 text) or task `updated_at` against current time. Tasks `in-progress` for > 30 min without a `task_comment` since `updated_at` are considered stuck.

**When to use:** Inside `do_own_tasks()` on every heartbeat.

**Example:**
```python
from datetime import datetime, timezone, timedelta

STUCK_THRESHOLD = timedelta(minutes=30)

async def _detect_stuck_tasks(self) -> None:
    now = datetime.now(timezone.utc)
    db = await self._db.open_read()
    try:
        async with db.execute(
            "SELECT id, title, model_tier, escalation_count, stuck_since, updated_at "
            "FROM tasks WHERE status = 'in-progress'"
        ) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()

    for row in rows:
        # Use stuck_since if set, else updated_at as the baseline
        baseline_str = row["stuck_since"] or row["updated_at"]
        baseline = datetime.fromisoformat(baseline_str)
        if baseline.tzinfo is None:
            baseline = baseline.replace(tzinfo=timezone.utc)
        if now - baseline >= STUCK_THRESHOLD:
            await self._escalate_task(row)
```

### Pattern 5: Heartbeat Counter for Cron Logic
**What:** Increment `_heartbeat_counter` on each `do_own_tasks()` call; trigger gap-fill when `counter % 3 == 0`.

**When to use:** The only cron mechanism inside the heartbeat loop (no separate timer or `asyncio.create_task`).

**Example:**
```python
async def do_own_tasks(self) -> None:
    self._heartbeat_counter += 1
    await self._detect_stuck_tasks()
    if self._heartbeat_counter % 3 == 0:
        await self._gap_fill_and_completion_check()
```

### Pattern 6: CLI Table Output with tabulate + --json Flag
**What:** Default output renders rows with `tabulate(rows, headers, tablefmt="simple")`. `--json` flag serializes rows as JSON array and prints to stdout.

**When to use:** All `cluster tasks list` and `cluster agents status` commands.

**Example:**
```python
import json
import click
from tabulate import tabulate

@cluster_cli.command(name="list")
@click.option("--status", default=None, help="Filter by task status")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
def tasks_list(status: str | None, as_json: bool) -> None:
    """List tasks with optional status filter."""
    import asyncio
    rows = asyncio.run(_fetch_tasks(status))
    if as_json:
        click.echo(json.dumps(rows, indent=2))
    else:
        headers = ["ID", "Title", "Status", "Assigned To", "Tier", "Priority"]
        click.echo(tabulate(rows, headers=headers, tablefmt="simple"))
```

### Anti-Patterns to Avoid
- **Calling `asyncio.run()` inside an async function:** CLI commands are sync Click handlers that call `asyncio.run(_async_helper())`. Never nest `asyncio.run()` inside another coroutine. (Established decision from Phase 1, STATE.md line 93.)
- **Catching `CancelledError` in async loops:** `BaseAgent.start()` already handles this correctly. `BossAgent` must not suppress `CancelledError` in any overridden method. (STATE.md: "CancelledError must always be re-raised.")
- **Mutating task objects:** Follow immutable pattern — build new dicts for UPDATE queries rather than modifying fetched row objects.
- **SQL injection via f-strings:** All DB queries use parameterized `?` placeholders. Never construct SQL from user input strings.
- **Blocking LLM calls in async context:** Use `AsyncAnthropic`, not `Anthropic`. Synchronous `client.messages.create()` blocks the event loop.
- **`messages.parse()` with sync client in async context:** Use `await async_client.messages.parse(...)` — the async version is non-blocking.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM response parsing | Custom JSON regex/parse after `content[0].text` | `messages.parse()` with Pydantic model | Handles malformed output, validation errors, retries; verified by Context7 |
| Table rendering | Manual f-string column formatting | `tabulate(rows, headers, tablefmt="simple")` | Handles variable column widths, padding, alignment automatically |
| State machine transitions | Custom if/elif transition checks | `TaskStateMachine.apply()` already in `runtime/state_machine.py` | Already built in Phase 1; raises `InvalidTransitionError` on bad transitions |
| UUID generation | `random.random()` or sequential IDs | `_uuid()` from `runtime/models.py` | Already established; consistent with all DB PKs |
| ISO 8601 timestamps | `datetime.strftime(...)` custom format | `_now_iso()` from `runtime/models.py` | Already established; UTC-aware, consistent with DB storage |
| Activity log writes | Custom insert logic | Pattern from `heartbeat.py:100-111` | Already established; parameterized, uses `_uuid()` and `_now_iso()` |

**Key insight:** Almost all primitives are already built. Phase 3 is wiring together existing pieces (BaseAgent, TaskStateMachine, DatabaseManager, ActivityLog patterns) with LLM calls as the new element.

---

## Common Pitfalls

### Pitfall 1: Schema Gap — `reviewer_roles` Column Missing
**What goes wrong:** `reviewer_roles` (the list of reviewer role names stored at task creation time) does not exist on the `tasks` table in the current `schema.sql`. Without this column, the boss cannot know which reviewers to check at promotion time without an extra LLM call.
**Why it happens:** The CONTEXT.md decision says "boss stores which roles should review the task" but the existing schema has no such column.
**How to avoid:** Add `reviewer_roles TEXT` (JSON-serialized list, e.g. `'["researcher","strategist"]'`) to the `tasks` table in `schema.sql`. Use `json.dumps(roles)` on write and `json.loads(row["reviewer_roles"])` on read. Because `schema.sql` uses `IF NOT EXISTS`, existing databases need a manual `ALTER TABLE tasks ADD COLUMN reviewer_roles TEXT;` or a `db reset`. Phase 3 Wave 0 must include schema migration.
**Warning signs:** `KeyError: 'reviewer_roles'` when fetching task rows.

### Pitfall 2: `messages.parse()` vs `messages.create()` Confusion
**What goes wrong:** `messages.parse()` is the Pydantic-structured-output path. It is available on the Anthropic SDK as of `anthropic>=0.40.0` (confirmed by REQUIREMENTS.md version pin). Using `messages.create()` and then `json.loads(response.content[0].text)` is fragile — the LLM may wrap JSON in markdown fences.
**Why it happens:** Older SDK examples show `messages.create()` + manual parsing.
**How to avoid:** Use `await async_client.messages.parse(..., output_format=MyPydanticModel)` for all structured responses. Verify `anthropic` version at install time.
**Warning signs:** `json.JSONDecodeError` from `content[0].text` containing ```json fences.

### Pitfall 3: `datetime.fromisoformat()` Timezone Naivety
**What goes wrong:** SQLite stores timestamps as TEXT via `datetime('now')` (no timezone suffix). `datetime.fromisoformat("2026-03-02T10:00:00")` returns a naive datetime. Comparing naive vs UTC-aware datetimes raises `TypeError`.
**Why it happens:** `_now_iso()` in `models.py` uses `datetime.now(timezone.utc).isoformat()` (produces `+00:00` suffix), but SQLite's `DEFAULT (datetime('now'))` produces naive timestamps. Mixed sources in the DB.
**How to avoid:** Always apply `.replace(tzinfo=timezone.utc)` when `tzinfo is None` after `fromisoformat()`. Use this pattern in `_detect_stuck_tasks()` and anywhere timestamps are compared.
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes`.

### Pitfall 4: Heartbeat Counter Reset on Agent Restart
**What goes wrong:** `_heartbeat_counter` is an in-memory int. If the boss process restarts, counter resets to 0, meaning the gap-fill runs immediately on heartbeat 3 post-restart even if it ran recently.
**Why it happens:** Counter is not persisted to the state file.
**How to avoid:** This is acceptable behavior — gap-fill is idempotent (creates tasks only if goal is incomplete). No fix needed in V1. Document it as known behavior.
**Warning signs:** N/A — this is a known, acceptable behavior.

### Pitfall 5: `task_reviews` Unique Constraint on Re-review
**What goes wrong:** `task_reviews` has `UNIQUE(task_id, reviewer_id)`. After a rejection sends a task back to `in-progress`, the review record still exists with `status='rejected'`. When the boss re-creates reviewer assignments for the re-worked task, an INSERT will fail on the unique constraint.
**Why it happens:** Task rejection does not delete the existing `task_reviews` rows.
**How to avoid:** Use `INSERT OR REPLACE INTO task_reviews` (SQLite's `ON CONFLICT DO UPDATE`) when creating review assignments, updating `status` back to `pending`. Alternatively, `UPDATE task_reviews SET status='pending' WHERE task_id=? AND reviewer_id=?` when task returns to `in-progress`.
**Warning signs:** `sqlite3.IntegrityError: UNIQUE constraint failed: task_reviews.task_id, task_reviews.reviewer_id`.

### Pitfall 6: Reviewer Roles vs Reviewer Agent IDs
**What goes wrong:** `task_reviews` stores `reviewer_id` (an agent_id, e.g. `"agent-2"`), but `reviewer_roles` on tasks stores role names (e.g. `["researcher", "strategist"]`). Boss must translate: "which agents currently have these roles?" by querying `agent_status`.
**Why it happens:** Roles and IDs are two different concepts. Tasks are assigned by role (abstract), but reviews are tracked by agent_id (concrete).
**How to avoid:** At task creation time, query `agent_status` to find current agents matching `reviewer_roles`, then create `task_reviews` rows with their concrete `agent_id` values. If no agent for a role exists, log a warning and skip (or assign the boss itself as reviewer in last resort).
**Warning signs:** Empty `task_reviews` table despite tasks being in `peer_review` state.

### Pitfall 7: `cluster approve` Must Use TaskStateMachine
**What goes wrong:** Directly executing `UPDATE tasks SET status='approved'` bypasses the state machine and could approve a task that is not in `review` state.
**Why it happens:** Convenience — direct UPDATE seems simpler.
**How to avoid:** Always call `TaskStateMachine().apply(current_status, TaskStatus.APPROVED)` before the UPDATE. This raises `InvalidTransitionError` for any task not in `review` state, which the CLI should catch and display as a user-friendly error.
**Warning signs:** Tasks jumping from `todo` or `peer_review` directly to `approved`.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### AsyncAnthropic Structured Decomposition Call
```python
# Source: Context7 /anthropics/anthropic-sdk-python — Async + Parse Structured Outputs
import pydantic
from anthropic import AsyncAnthropic

class TaskSpec(pydantic.BaseModel):
    title: str
    description: str
    assigned_role: str          # e.g. "researcher"
    reviewer_roles: list[str]   # e.g. ["strategist", "writer"]
    priority: int               # 1-100
    model_tier: str             # "haiku" | "sonnet" | "opus"

class DecompositionResult(pydantic.BaseModel):
    tasks: list[TaskSpec]

async def _decompose_goal(self, goal_description: str) -> list[TaskSpec]:
    parsed = await self._llm.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=(
            "You are a boss agent coordinating a cluster of AI workers. "
            "Decompose the goal into 3-5 concrete, non-overlapping tasks. "
            "Each task must be assigned to exactly one worker role and must specify "
            "at least 2 reviewer roles (different from the assigned role)."
        ),
        messages=[{"role": "user", "content": f"Goal: {goal_description}"}],
        output_format=DecompositionResult,
    )
    return parsed.parsed_output.tasks
```

### Goal Completion Judgment Call
```python
# Source: Context7 /anthropics/anthropic-sdk-python — Parse Structured Outputs
class GoalCompletionResult(pydantic.BaseModel):
    is_complete: bool
    reason: str

async def _check_goal_completion(self, goal_desc: str, completed_task_summaries: list[str]) -> bool:
    completed_summary = "\n".join(f"- {t}" for t in completed_task_summaries)
    parsed = await self._llm.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system="You are evaluating goal completion. Answer strictly with the structured format.",
        messages=[{
            "role": "user",
            "content": (
                f"Goal: {goal_desc}\n\n"
                f"Completed tasks:\n{completed_summary}\n\n"
                "Is the goal fully achieved by these completed tasks?"
            )
        }],
        output_format=GoalCompletionResult,
    )
    return parsed.parsed_output.is_complete
```

### Activity Log — Escalation Entry
```python
# Source: Phase 2 established pattern (runtime/heartbeat.py:100-111)
from runtime.models import _uuid, _now_iso

async def _log_escalation(self, task_id: str, old_tier: str, new_tier: str, stuck_since: str) -> None:
    import json
    db = await self._db.open_write()
    try:
        await db.execute(
            "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                _uuid(),
                self._config.agent_id,
                task_id,
                "task_escalated",
                json.dumps({"old_tier": old_tier, "new_tier": new_tier, "stuck_since": stuck_since}),
                _now_iso(),
            ),
        )
        await db.commit()
    finally:
        await db.close()
```

### CLI: tasks list with tabulate
```python
# Source: tabulate PyPI (verified), Click docs (Context7 /pallets/click)
import json
import asyncio
import click
from tabulate import tabulate
from runtime.cli import cluster_cli

@cluster_cli.group(name="tasks")
def tasks_group() -> None:
    """Task management commands."""

@tasks_group.command(name="list")
@click.option("--status", default=None, help="Filter by task status.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON array.")
@click.option("--db-path", default="cluster.db", envvar="CLUSTER_DB_PATH", show_default=True)
def tasks_list(status: str | None, as_json: bool, db_path: str) -> None:
    """List tasks (optionally filtered by status)."""
    rows = asyncio.run(_fetch_tasks_rows(db_path, status))
    if as_json:
        click.echo(json.dumps(rows, indent=2))
    else:
        headers = ["ID", "Title", "Status", "Assigned To", "Tier", "Priority"]
        click.echo(tabulate(rows, headers=headers, tablefmt="simple"))

async def _fetch_tasks_rows(db_path: str, status: str | None) -> list[list]:
    from pathlib import Path
    from runtime.database import DatabaseManager
    mgr = DatabaseManager(Path(db_path))
    db = await mgr.open_read()
    try:
        sql = "SELECT id, title, status, assigned_to, model_tier, priority FROM tasks"
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY priority DESC"
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [[r["id"][:8], r["title"], r["status"], r["assigned_to"] or "—",
                 r["model_tier"], r["priority"]] for r in rows]
    finally:
        await db.close()
```

### TaskStateMachine in cluster approve
```python
# Source: runtime/state_machine.py (Phase 1 implementation)
from runtime.state_machine import TaskStateMachine, InvalidTransitionError, TaskStatus

@cluster_cli.command(name="approve")
@click.argument("task_id")
@click.option("--db-path", default="cluster.db", envvar="CLUSTER_DB_PATH", show_default=True)
def approve(task_id: str, db_path: str) -> None:
    """Approve a task in 'review' state."""
    try:
        asyncio.run(_do_approve(db_path, task_id))
        click.echo(f"Task {task_id} approved.")
    except InvalidTransitionError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

async def _do_approve(db_path: str, task_id: str) -> None:
    from pathlib import Path
    from runtime.database import DatabaseManager
    from runtime.models import _now_iso
    mgr = DatabaseManager(Path(db_path))
    db = await mgr.open_write()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Task {task_id!r} not found")
        machine = TaskStateMachine()
        machine.apply(TaskStatus(row["status"]), TaskStatus.APPROVED)  # raises if invalid
        await db.execute(
            "UPDATE tasks SET status='approved', updated_at=? WHERE id=?",
            (_now_iso(), task_id)
        )
        await db.commit()
    finally:
        await db.close()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual JSON parsing of LLM text output | `messages.parse()` with Pydantic models | anthropic SDK 0.40+ | Eliminates markdown-fence stripping, reduces errors |
| Synchronous Anthropic client in async code | `AsyncAnthropic` with `await` | anthropic SDK 0.20+ | Non-blocking LLM calls in asyncio event loops |
| Rich for CLI tables | tabulate for simple tables | Established convention | Right-sized tool — tabulate for data, Rich for TUI |

**Deprecated/outdated:**
- Synchronous `client.messages.create()` inside async functions: blocks the event loop, do not use in `BossAgent`.
- `json.loads(response.content[0].text)`: fragile manual parsing, replaced by `messages.parse()`.

---

## Open Questions

1. **`messages.parse()` availability on `AsyncAnthropic`**
   - What we know: Context7 shows `messages.parse()` on the sync `Anthropic` client with Pydantic models. The async usage pattern (`await async_client.messages.parse(...)`) is shown in the async examples.
   - What's unclear: Exact method signature confirmation for `AsyncAnthropic.messages.parse()` — is it `await client.messages.parse(...)` or is it called differently?
   - Recommendation: At implementation time, verify with a quick smoke test: `parsed = await self._llm.messages.parse(model=..., output_format=SomePydanticModel, ...)`. If `parse()` is not available on `AsyncAnthropic`, fall back to `messages.create()` + `json.loads()` wrapped in a try/except with markdown-fence stripping. LOW confidence on this specific API method for the async client.

2. **Schema change for `reviewer_roles`**
   - What we know: The CONTEXT.md decision says to store reviewer roles at task creation time. The current `tasks` table has no such column. Claude's discretion: column vs join table.
   - What's unclear: Whether to use a new column (simpler) or a join table (more normalized).
   - Recommendation: Add `reviewer_roles TEXT` (nullable, JSON string) to `tasks` in schema.sql. Use `json.dumps(["role1", "role2"])` on write. This avoids a join table and its associated complexity. Medium confidence: this is a clean V1 solution.

3. **`cluster goal set` with existing active goal**
   - What we know: REQUIREMENTS.md states "one active goal per cluster in V1". CONTEXT.md shows `cluster goal set "<description>"` as a CLI command.
   - What's unclear: Should setting a new goal archive the old one? Should it fail if one is already active?
   - Recommendation: When `cluster goal set` is called and an active goal exists, archive the existing goal (set `status='archived'`) before inserting the new one. This preserves history and enforces the single-active-goal invariant. LOW confidence — not specified in REQUIREMENTS.md; planner should make final call.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `pytest tests/test_boss.py -x --no-cov` |
| Full suite command | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |

### Phase Requirements → Test Map

| Behavior | Test Type | Automated Command | Notes |
|----------|-----------|-------------------|-------|
| `BossAgent` subclasses `BaseAgent`, inherits heartbeat loop | unit | `pytest tests/test_boss.py::test_boss_agent_is_base_agent -x` | Structural check |
| `do_peer_reviews()`: scans `peer_review` tasks and promotes when all reviews approved | unit | `pytest tests/test_boss.py::test_promote_to_review_when_all_approved -x` | Mock DB rows |
| `do_peer_reviews()`: any rejection returns task to `in-progress` | unit | `pytest tests/test_boss.py::test_rejection_returns_to_in_progress -x` | Check state transition |
| Goal decomposition: one LLM call creates 3-5 tasks | unit (mocked LLM) | `pytest tests/test_boss.py::test_decompose_goal_creates_tasks -x` | Patch `AsyncAnthropic` |
| Gap-fill runs every 3 heartbeats (not every 1) | unit | `pytest tests/test_boss.py::test_gap_fill_runs_every_3_heartbeats -x` | Counter check |
| Goal completion check: goal moves to `completed` when LLM says yes | unit (mocked LLM) | `pytest tests/test_boss.py::test_goal_completion_marks_goal_done -x` | Patch LLM response |
| Stuck detection: task `in-progress` > 30 min escalates `model_tier` | unit | `pytest tests/test_boss.py::test_stuck_task_escalates_model_tier -x` | Inject old `updated_at` |
| Second intervention: boss posts unblocking hint as `task_comment` | unit (mocked LLM) | `pytest tests/test_boss.py::test_second_intervention_posts_comment -x` | Patch LLM, check task_comments |
| Escalation logs to `activity_log` with correct `action` and `details` | unit | `pytest tests/test_boss.py::test_escalation_logged_to_activity_log -x` | Check DB |
| `cluster goal set`: inserts goal, triggers decomposition | integration | `pytest tests/test_boss_cli.py::test_goal_set_command -x` | Click test runner |
| `cluster tasks list`: renders table with correct columns | integration | `pytest tests/test_boss_cli.py::test_tasks_list_table_output -x` | Click runner |
| `cluster tasks list --status peer_review`: filters correctly | integration | `pytest tests/test_boss_cli.py::test_tasks_list_status_filter -x` | Click runner |
| `cluster tasks list --json`: emits valid JSON array | integration | `pytest tests/test_boss_cli.py::test_tasks_list_json_output -x` | json.loads check |
| `cluster agents status`: renders agent table | integration | `pytest tests/test_boss_cli.py::test_agents_status_output -x` | Click runner |
| `cluster approve <task-id>`: approves task in `review` state | integration | `pytest tests/test_boss_cli.py::test_approve_review_task -x` | State machine check |
| `cluster approve <task-id>`: fails with clear error for non-`review` task | integration | `pytest tests/test_boss_cli.py::test_approve_wrong_state_fails -x` | Exit code check |
| Reviewer role → agent_id translation at task creation | unit | `pytest tests/test_boss.py::test_reviewer_role_to_agent_id_mapping -x` | agent_status query |
| `task_reviews` UNIQUE constraint handled on re-review (rejection path) | unit | `pytest tests/test_boss.py::test_re_review_upsert_on_rejection -x` | DB integrity check |

### Sampling Rate
- **Per task commit:** `pytest tests/test_boss.py -x --no-cov`
- **Per wave merge:** `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_boss.py` — unit tests for `BossAgent` class (LLM mocked)
- [ ] `tests/test_boss_cli.py` — integration tests for new CLI commands
- [ ] `runtime/schema.sql` — add `reviewer_roles TEXT` column to `tasks` table
- [ ] `pyproject.toml` — add `tabulate>=0.9.0` to `dependencies`

*(No new framework install needed — pytest-asyncio already configured and working from Phase 2.)*

---

## Sources

### Primary (HIGH confidence)
- `/anthropics/anthropic-sdk-python` (Context7) — AsyncAnthropic client, `messages.parse()` with Pydantic, `messages.create()`, env var API key loading
- `runtime/heartbeat.py` (project source) — BaseAgent patterns for DB access, activity log inserts, state file writing
- `runtime/state_machine.py` (project source) — TaskStateMachine.apply(), InvalidTransitionError, transition table
- `runtime/models.py` (project source) — _uuid(), _now_iso(), TaskStatus, GoalStatus, ReviewStatus enums
- `runtime/schema.sql` (project source) — exact column names, constraints, UNIQUE(task_id, reviewer_id) on task_reviews
- `runtime/cli.py` (project source) — cluster_cli group structure, asyncio.run() per command pattern
- `pyproject.toml` (project source) — dependency versions (anthropic>=0.40.0, click>=8.1.0, pydantic>=2.0.0)

### Secondary (MEDIUM confidence)
- tabulate PyPI page (duckduckgo verified, multiple sources) — `tabulate(rows, headers, tablefmt="simple")` API
- `/pallets/click` (Context7) — Click group/command/option patterns for CLI subcommands

### Tertiary (LOW confidence)
- `AsyncAnthropic.messages.parse()` exact signature — Context7 shows sync version clearly; async version inferred from async pattern examples. Verify at implementation time.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core dependencies already in pyproject.toml; LLM SDK verified via Context7
- Architecture: HIGH — BaseAgent subclass pattern is direct; all DB patterns established in prior phases
- Pitfalls: HIGH — schema gap (reviewer_roles), datetime naivety, UNIQUE constraint are all code-verifiable from existing schema.sql and models.py
- CLI patterns: HIGH — Click group extension pattern is established in Phase 1

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable stack — anthropic SDK, click, tabulate change slowly)
