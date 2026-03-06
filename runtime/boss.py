"""BossAgent — coordinates cluster lifecycle for Agent Factory.

Subclasses BaseAgent, overriding do_peer_reviews() and do_own_tasks().
All heartbeat loop, stagger, state file, and DB status machinery is inherited.

Boss exclusive authorities:
1. Peer review promotion: peer_review → review when all reviewers approved
2. Rejection handling: any rejection → reset task to in-progress
3. Goal decomposition: LLM call on goal set, creates 3-5 tasks
4. Gap-fill + completion check: every 3 heartbeats (Wave 2)
5. Stuck detection + escalation (Wave 2)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pydantic
from anthropic import AsyncAnthropic

from runtime.config import AgentConfig
from runtime.heartbeat import BaseAgent
from runtime.models import GoalStatus, ReviewStatus, TaskStatus, _now_iso, _uuid
from runtime.notifier import Notifier
from runtime.state_machine import InvalidTransitionError, TaskStateMachine

logger = logging.getLogger(__name__)

# Model used for all boss LLM calls (per CONTEXT.md: boss always uses Sonnet)
_BOSS_MODEL = "claude-sonnet-4-6"

# Stuck detection constants
STUCK_THRESHOLD = timedelta(minutes=30)
TIER_ESCALATION: dict[str, str] = {"haiku": "sonnet", "sonnet": "opus", "opus": "opus"}


# ---------------------------------------------------------------------------
# Structured output models for LLM calls
# ---------------------------------------------------------------------------


class TaskSpec(pydantic.BaseModel):
    """A single task spec returned by the goal decomposition LLM call."""

    title: str
    description: str
    assigned_role: str          # e.g. "researcher"
    reviewer_roles: list[str]   # e.g. ["strategist", "writer"] — at least 2, different from assigned_role
    priority: int               # 1-100
    model_tier: str             # haiku | sonnet | opus


class DecompositionResult(pydantic.BaseModel):
    """Structured output from goal decomposition LLM call."""

    tasks: list[TaskSpec]


class GoalCompletionResult(pydantic.BaseModel):
    """Structured output from goal completion judgment LLM call."""

    is_complete: bool
    reason: str


class UnblockingHint(pydantic.BaseModel):
    """Structured output for the stuck-task unblocking hint LLM call."""

    hint: str


# ---------------------------------------------------------------------------
# BossAgent
# ---------------------------------------------------------------------------


class BossAgent(BaseAgent):
    """Boss agent — coordinates cluster lifecycle.

    Overrides do_peer_reviews() and do_own_tasks() from BaseAgent.
    Wave 1 implements: __init__, do_peer_reviews (promotion + rejection),
    decompose_goal.
    Wave 2 adds: stuck detection, gap-fill cron, goal completion check.
    """

    def __init__(self, config: AgentConfig, notifier: Notifier | None = None) -> None:
        super().__init__(config, notifier)
        self._llm = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
        self._heartbeat_counter: int = 0

    # ── Public overrides ───────────────────────────────────────────────────

    async def do_peer_reviews(self) -> None:
        """Scan peer_review tasks; promote to review or reset to in-progress."""
        tasks_in_review = await self._fetch_peer_review_tasks()
        for task_id, task_title in tasks_in_review:
            outcome = await self._evaluate_reviews(task_id)
            if outcome == "all_approved":
                await self._promote_to_review(task_id, task_title)
            elif outcome == "any_rejected":
                await self._reject_back_to_in_progress(task_id)
            # "pending" → do nothing

    async def do_own_tasks(self) -> None:
        """Stuck detection (every tick) + gap-fill (every 3 ticks)."""
        self._heartbeat_counter += 1
        await self._detect_stuck_tasks()
        if self._heartbeat_counter % 3 == 0:
            await self._gap_fill_and_completion_check()

    # ── Stuck detection helpers ────────────────────────────────────────────

    async def _detect_stuck_tasks(self) -> None:
        """Check all in-progress tasks; escalate if stuck > 30 min."""
        now = datetime.now(timezone.utc)
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT id, title, description, model_tier, escalation_count, "
                "stuck_since, updated_at "
                "FROM tasks WHERE status = 'in-progress'"
            ) as cur:
                rows = await cur.fetchall()
        finally:
            await db.close()

        for row in rows:
            # Use stuck_since if already set, otherwise updated_at as baseline
            baseline_str = row["stuck_since"] or row["updated_at"]
            baseline = datetime.fromisoformat(baseline_str)
            if baseline.tzinfo is None:
                baseline = baseline.replace(tzinfo=timezone.utc)
            if now - baseline < STUCK_THRESHOLD:
                continue  # Not stuck yet

            if row["stuck_since"] is not None:
                # Second intervention: post unblocking hint via LLM
                await self._post_unblocking_hint(
                    row["id"], row["title"], row["description"]
                )
            else:
                # First intervention: escalate model tier, set stuck_since
                old_tier = row["model_tier"]
                new_tier = TIER_ESCALATION.get(old_tier, "opus")
                await self._escalate_task(row["id"], old_tier, new_tier, baseline_str)

    async def _escalate_task(
        self, task_id: str, old_tier: str, new_tier: str, stuck_since: str
    ) -> None:
        """Escalate model_tier, set stuck_since, increment escalation_count, log."""
        now = _now_iso()
        db = await self._db.open_write()
        try:
            await db.execute(
                "UPDATE tasks SET model_tier = ?, escalation_count = escalation_count + 1, "
                "stuck_since = ?, updated_at = ? WHERE id = ?",
                (new_tier, stuck_since, now, task_id),
            )
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
                "VALUES (?, ?, ?, 'task_escalated', ?, ?)",
                (
                    _uuid(),
                    self._config.agent_id,
                    task_id,
                    json.dumps(
                        {"old_tier": old_tier, "new_tier": new_tier, "stuck_since": stuck_since}
                    ),
                    now,
                ),
            )
            await db.commit()
        finally:
            await db.close()
        logger.info(
            "Boss escalated task %s: %s -> %s (stuck since %s)",
            task_id,
            old_tier,
            new_tier,
            stuck_since,
        )

    async def _post_unblocking_hint(
        self, task_id: str, title: str, description: str
    ) -> None:
        """Call LLM to generate an unblocking hint; post as task_comment."""
        try:
            parsed = await self._llm.messages.parse(
                model=_BOSS_MODEL,
                max_tokens=512,
                system=(
                    "You are a boss agent. A task is stuck. Provide a single concrete, "
                    "actionable hint to unblock the assigned worker. Be specific."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Task title: {title}\n"
                            f"Description: {description}\n"
                            "What should the worker try next?"
                        ),
                    }
                ],
                output_format=UnblockingHint,
            )
            hint = parsed.parsed_output.hint
        except Exception:
            logger.exception("LLM unblocking hint failed for task %s", task_id)
            hint = (
                "Boss investigation: task appears stuck. "
                "Review task requirements and try a smaller sub-step."
            )

        now = _now_iso()
        db = await self._db.open_write()
        try:
            await db.execute(
                "INSERT INTO task_comments (id, task_id, agent_id, comment_type, content, created_at) "
                "VALUES (?, ?, ?, 'progress', ?, ?)",
                (_uuid(), task_id, self._config.agent_id, f"[Boss unblocking hint] {hint}", now),
            )
            await db.commit()
        finally:
            await db.close()
        logger.info("Boss posted unblocking hint for task %s", task_id)

    # ── Gap-fill and completion check ──────────────────────────────────────

    async def _gap_fill_and_completion_check(self) -> None:
        """Every 3 heartbeats: check goal completion; if incomplete, create gap tasks.

        Goal completion check:
        1. Fetch active goal and all completed (approved) tasks
        2. LLM judgment: is the goal fully achieved?
        3. If yes: set goal.status='completed', stop
        4. If no: generate additional tasks to fill gaps (same decompose pattern)
        """
        # Fetch active goal
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT id, title, description FROM goals WHERE status = 'active' LIMIT 1"
            ) as cur:
                goal_row = await cur.fetchone()
        finally:
            await db.close()

        if goal_row is None:
            return  # No active goal; nothing to do

        goal_id = goal_row["id"]

        # Fetch approved task summaries
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT title, description FROM tasks WHERE goal_id = ? AND status = 'approved'",
                (goal_id,),
            ) as cur:
                approved_rows = await cur.fetchall()
        finally:
            await db.close()

        completed_summaries = [
            f"{r['title']}: {r['description'][:100]}" for r in approved_rows
        ]

        # LLM judgment: is goal complete?
        is_complete = await self._check_goal_completion(
            goal_row["description"], completed_summaries
        )

        if is_complete:
            await self._mark_goal_complete(goal_id)
            logger.info("Boss: goal %s marked as completed", goal_id)
        else:
            # Gap fill: generate additional tasks only if no active work remains
            db = await self._db.open_read()
            try:
                async with db.execute(
                    "SELECT COUNT(*) as cnt FROM tasks WHERE goal_id = ? "
                    "AND status IN ('todo', 'in-progress', 'peer_review', 'review')",
                    (goal_id,),
                ) as cur:
                    row = await cur.fetchone()
            finally:
                await db.close()
            if row["cnt"] == 0:
                logger.info("Boss: gap fill for goal %s — generating new tasks", goal_id)
                await self.decompose_goal(goal_id, goal_row["description"])

    async def _check_goal_completion(
        self, goal_desc: str, completed_summaries: list[str]
    ) -> bool:
        """LLM call: is goal fully achieved by the completed tasks?"""
        if not completed_summaries:
            return False  # No completed work — cannot be done
        summary_text = "\n".join(f"- {s}" for s in completed_summaries)
        try:
            parsed = await self._llm.messages.parse(
                model=_BOSS_MODEL,
                max_tokens=512,
                system=(
                    "You are evaluating whether a goal has been fully achieved. "
                    "Answer strictly with the structured format."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Goal: {goal_desc}\n\n"
                            f"Completed tasks:\n{summary_text}\n\n"
                            "Is this goal fully achieved by these completed tasks?"
                        ),
                    }
                ],
                output_format=GoalCompletionResult,
            )
            return parsed.parsed_output.is_complete
        except Exception:
            logger.exception("LLM goal completion check failed")
            return False  # Fail safe: treat as incomplete

    async def _mark_goal_complete(self, goal_id: str) -> None:
        """Set goal.status = 'completed' in DB."""
        db = await self._db.open_write()
        try:
            await db.execute(
                "UPDATE goals SET status = 'completed' WHERE id = ?",
                (goal_id,),
            )
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, action, details, created_at) "
                "VALUES (?, ?, 'goal_completed', ?, ?)",
                (
                    _uuid(),
                    self._config.agent_id,
                    json.dumps({"goal_id": goal_id}),
                    _now_iso(),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    # ── Peer review helpers ────────────────────────────────────────────────

    async def _fetch_peer_review_tasks(self) -> list[tuple[str, str]]:
        """Return list of (task_id, task_title) for all peer_review tasks."""
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT id, title FROM tasks WHERE status = 'peer_review'"
            ) as cur:
                rows = await cur.fetchall()
        finally:
            await db.close()
        return [(row["id"], row["title"]) for row in rows]

    async def _evaluate_reviews(self, task_id: str) -> str:
        """Return 'all_approved', 'any_rejected', or 'pending' for a task."""
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT status FROM task_reviews WHERE task_id = ?",
                (task_id,),
            ) as cur:
                review_rows = await cur.fetchall()
        finally:
            await db.close()

        if not review_rows:
            return "pending"  # No reviews yet

        statuses = [r["status"] for r in review_rows]
        if any(s == ReviewStatus.REJECTED for s in statuses):
            return "any_rejected"
        if all(s == ReviewStatus.APPROVED for s in statuses):
            return "all_approved"
        return "pending"

    async def _promote_to_review(self, task_id: str, task_title: str) -> None:
        """Transition peer_review → review, notify user, log to activity_log."""
        db = await self._db.open_write()
        try:
            await db.execute(
                "UPDATE tasks SET status = 'review', updated_at = ? WHERE id = ?",
                (_now_iso(), task_id),
            )
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _uuid(),
                    self._config.agent_id,
                    task_id,
                    "task_promoted",
                    json.dumps({"to_state": "review"}),
                    _now_iso(),
                ),
            )
            await db.commit()
        finally:
            await db.close()
        await self._notifier.notify_review_ready(task_id, task_title)
        logger.info("Boss promoted task %s to review", task_id)

    async def _reject_back_to_in_progress(self, task_id: str) -> None:
        """Transition peer_review → in-progress; reset all task_reviews to pending."""
        db = await self._db.open_write()
        try:
            # Reset task status
            await db.execute(
                "UPDATE tasks SET status = 'in-progress', updated_at = ? WHERE id = ?",
                (_now_iso(), task_id),
            )
            # Reset reviews to pending (reviewer can re-review after worker re-submits)
            await db.execute(
                "UPDATE task_reviews SET status = 'pending' WHERE task_id = ?",
                (task_id,),
            )
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _uuid(),
                    self._config.agent_id,
                    task_id,
                    "task_rejected",
                    json.dumps({"to_state": "in-progress"}),
                    _now_iso(),
                ),
            )
            await db.commit()
        finally:
            await db.close()
        logger.info("Boss reset rejected task %s to in-progress", task_id)

    # ── Goal decomposition helpers ─────────────────────────────────────────

    async def decompose_goal(self, goal_id: str, goal_description: str) -> None:
        """One-shot LLM call to create 3-5 initial tasks for the goal.

        Called by 'cluster goal set' CLI command after inserting the goal.
        Queries agent_status to resolve reviewer_roles → concrete agent_ids.
        """
        task_specs = await self._decompose_goal(goal_description)
        for spec in task_specs:
            task_id = _uuid()
            reviewer_agents = await self._resolve_reviewer_agents(spec.reviewer_roles, spec.assigned_role)
            await self._insert_task(goal_id, task_id, spec, reviewer_agents)

    async def _decompose_goal(self, goal_description: str) -> list[TaskSpec]:
        """Call LLM to decompose goal into 3-5 TaskSpec objects."""
        try:
            parsed = await self._llm.messages.parse(
                model=_BOSS_MODEL,
                max_tokens=2048,
                system=(
                    "You are a boss agent coordinating a cluster of AI workers. "
                    "Decompose the goal into 3-5 concrete, non-overlapping tasks. "
                    "Each task must be assigned to exactly one worker role and must specify "
                    "at least 2 reviewer roles that are DIFFERENT from the assigned_role. "
                    "Use model_tier 'haiku' by default, 'sonnet' for complex tasks."
                ),
                messages=[{"role": "user", "content": f"Goal: {goal_description}"}],
                output_format=DecompositionResult,
            )
            return parsed.parsed_output.tasks
        except Exception:
            logger.exception("LLM decomposition failed for goal: %s", goal_description[:80])
            raise

    async def _resolve_reviewer_agents(
        self, reviewer_roles: list[str], assigned_role: str
    ) -> list[str]:
        """Translate reviewer role names → agent_ids from agent_status table.

        Per CONTEXT.md: at least 2 reviewers, different roles from assigned worker.
        If no agent found for a role, logs a warning and skips that role.
        """
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT agent_id, agent_role FROM agent_status"
            ) as cur:
                rows = await cur.fetchall()
        finally:
            await db.close()

        role_to_agent: dict[str, str] = {r["agent_role"]: r["agent_id"] for r in rows}
        agents = []
        for role in reviewer_roles:
            if role == assigned_role:
                continue  # Cannot review own work
            if role in role_to_agent:
                agents.append(role_to_agent[role])
            else:
                logger.warning("No agent found for reviewer role %r — skipping", role)
        return agents

    async def _insert_task(
        self, goal_id: str, task_id: str, spec: TaskSpec, reviewer_agents: list[str]
    ) -> None:
        """Insert task row and task_review rows for each reviewer agent."""
        now = _now_iso()
        db = await self._db.open_write()
        try:
            await db.execute(
                "INSERT INTO tasks (id, goal_id, title, description, assigned_to, status, "
                "priority, model_tier, escalation_count, reviewer_roles, assigned_role, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, 0, ?, ?, ?, ?)",
                (
                    task_id,
                    goal_id,
                    spec.title,
                    spec.description,
                    None,   # assigned_to set by worker when claimed
                    spec.priority,
                    spec.model_tier,
                    json.dumps(spec.reviewer_roles),
                    spec.assigned_role,
                    now,
                    now,
                ),
            )
            # Create task_review rows for each resolved reviewer agent
            for reviewer_id in reviewer_agents:
                await db.execute(
                    "INSERT OR REPLACE INTO task_reviews (id, task_id, reviewer_id, status, created_at) "
                    "VALUES (?, ?, ?, 'pending', ?)",
                    (_uuid(), task_id, reviewer_id, now),
                )
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
                "VALUES (?, ?, ?, 'task_created', ?, ?)",
                (_uuid(), self._config.agent_id, task_id, json.dumps({"title": spec.title}), now),
            )
            await db.commit()
        finally:
            await db.close()
