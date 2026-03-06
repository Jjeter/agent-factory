"""WorkerAgent — role-based task execution agent for Agent Factory.

Subclasses BaseAgent, overriding do_peer_reviews() and do_own_tasks().
All heartbeat loop, stagger, state file, and DB status machinery is inherited.

Worker exclusive responsibilities:
1. Resume-first task claiming: check in-progress before claiming from todo
2. Role-based task claiming: only claim tasks whose assigned_role matches agent_role
3. Atomic claim guard: detect lost race via UPDATE rowcount=0
4. Task execution: LLM call, document insertion, progress comment, peer_review transition
5. Peer review: independent review context (no prior reviewer comments)
"""
from __future__ import annotations

import json
import logging
from typing import Any

import pydantic
from anthropic import AsyncAnthropic

from runtime.config import AgentConfig
from runtime.heartbeat import BaseAgent
from runtime.models import _now_iso, _uuid
from runtime.notifier import Notifier

logger = logging.getLogger(__name__)

# Model tier → Anthropic model ID
MODEL_MAP: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}

# Peer review always uses Sonnet regardless of agent's configured tier
_REVIEW_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------


class ReviewDecision(pydantic.BaseModel):
    """Structured output for peer review LLM calls."""

    decision: str  # "approve" | "reject"
    feedback: str
    required_changes: str = ""


# ---------------------------------------------------------------------------
# WorkerAgent
# ---------------------------------------------------------------------------


class WorkerAgent(BaseAgent):
    """Worker agent — claims and executes role-based tasks.

    Overrides do_peer_reviews() and do_own_tasks() from BaseAgent.
    Plan 04-02 implements: __init__, do_own_tasks (resume-first claiming).
    Plan 04-03 adds: _execute_task with conditional prompt + versioning.
    Plan 04-04 adds: do_peer_reviews with LLM-based independent review.
    """

    def __init__(self, config: AgentConfig, notifier: Notifier | None = None) -> None:
        super().__init__(config, notifier)
        self._llm = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

    # ── Public overrides ───────────────────────────────────────────────────

    async def do_peer_reviews(self) -> None:
        """Stub — implemented in Plan 04-04."""
        pass

    async def do_own_tasks(self) -> None:
        """Resume-first task claiming: check in-progress before claiming from todo."""
        task = await self._fetch_in_progress_task()
        if task is None:
            task = await self._try_claim_task()
        if task is None:
            return
        await self._execute_task(task)

    # ── Task claiming helpers ──────────────────────────────────────────────

    async def _fetch_in_progress_task(self) -> Any:
        """Return the in-progress task assigned to this agent, or None."""
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

    async def _try_claim_task(self) -> Any:
        """Claim the highest-priority todo task for this agent's role.

        Returns the claimed task row, or None if no tasks available or race was lost.
        Uses an atomic UPDATE with rowcount check to prevent double-claiming when
        two workers with the same role run concurrently.
        """
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

        now = _now_iso()
        db = await self._db.open_write()
        try:
            cur = await db.execute(
                "UPDATE tasks SET status = 'in-progress', assigned_to = ?, updated_at = ? "
                "WHERE id = ? AND status = 'todo'",
                (self._config.agent_id, now, candidate["id"]),
            )
            if cur.rowcount == 0:
                # Lost race — another worker claimed first
                await db.commit()
                return None
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
                "VALUES (?, ?, ?, 'task_claimed', ?, ?)",
                (
                    _uuid(),
                    self._config.agent_id,
                    candidate["id"],
                    json.dumps({"title": candidate["title"]}),
                    now,
                ),
            )
            await db.commit()
        finally:
            await db.close()

        logger.info(
            "Worker %s claimed task %s (%s)",
            self._config.agent_id,
            candidate["id"],
            candidate["title"],
        )
        return candidate

    # ── Task execution ─────────────────────────────────────────────────────

    async def _execute_task(self, task: Any) -> None:
        """Execute a task: call LLM, insert document, post progress comment, submit for peer review.

        Conditional prompt:
        - First execution (no prior document): title + description only
        - Re-execution (prior doc + feedback exists): includes prior output and feedback
        """
        task_id = task["id"]
        now = _now_iso()
        model = MODEL_MAP.get(task["model_tier"], MODEL_MAP["haiku"])

        # Fetch prior document and feedback (for re-execution prompt)
        prior_doc, feedback_comments = await self._fetch_prior_context(task_id)

        # Build prompt: first execution vs re-execution
        if prior_doc is None:
            prompt = f"Task: {task['title']}\n\nDescription: {task['description']}"
        else:
            feedback_text = "\n".join(
                f"- {c['content']}" for c in feedback_comments
            )
            prompt = (
                f"Task: {task['title']}\n\n"
                f"Description: {task['description']}\n\n"
                f"Prior output:\n{prior_doc['content']}\n\n"
                f"Feedback to address:\n{feedback_text}"
            )

        response = await self._llm.messages.create(
            model=model,
            max_tokens=4096,
            system=self._config.system_prompt or "You are a helpful AI assistant completing assigned tasks.",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text

        # Compute next document version
        next_version = 1 if prior_doc is None else (prior_doc["version"] + 1)

        db = await self._db.open_write()
        try:
            await db.execute(
                "INSERT INTO documents (id, task_id, title, content, version, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_uuid(), task_id, task["title"], content, next_version, self._config.agent_id, now),
            )
            await db.execute(
                "INSERT INTO task_comments (id, task_id, agent_id, comment_type, content, created_at) "
                "VALUES (?, ?, ?, 'progress', ?, ?)",
                (
                    _uuid(),
                    task_id,
                    self._config.agent_id,
                    "Task completed. Submitted for peer review.",
                    now,
                ),
            )
            await db.execute(
                "UPDATE tasks SET status = 'peer_review', updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, task_id, action, details, created_at) "
                "VALUES (?, ?, ?, 'task_submitted', ?, ?)",
                (
                    _uuid(),
                    self._config.agent_id,
                    task_id,
                    json.dumps({"version": next_version}),
                    now,
                ),
            )
            await db.commit()
        finally:
            await db.close()

        logger.info(
            "Worker %s submitted task %s for peer review (version %d)",
            self._config.agent_id,
            task_id,
            next_version,
        )

    async def _fetch_prior_context(self, task_id: str) -> tuple[Any, list[Any]]:
        """Fetch the most recent document and feedback comments for a task.

        Returns (latest_doc_row_or_None, list_of_feedback_comment_rows).
        """
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT id, content, version FROM documents "
                "WHERE task_id = ? ORDER BY version DESC LIMIT 1",
                (task_id,),
            ) as cur:
                prior_doc = await cur.fetchone()

            feedback: list[Any] = []
            if prior_doc is not None:
                async with db.execute(
                    "SELECT content FROM task_comments "
                    "WHERE task_id = ? AND comment_type = 'feedback' "
                    "ORDER BY created_at ASC",
                    (task_id,),
                ) as cur:
                    feedback = await cur.fetchall()
        finally:
            await db.close()

        return prior_doc, feedback

    # ── Peer review helpers (implemented in Plan 04-04) ────────────────────

    async def _fetch_pending_reviews(self) -> list[str]:
        """Return task_ids where this agent is a pending reviewer.

        Filters: task_reviews.reviewer_id = agent_id AND status = 'pending'.
        """
        db = await self._db.open_read()
        try:
            async with db.execute(
                "SELECT tr.task_id FROM task_reviews tr "
                "WHERE tr.reviewer_id = ? AND tr.status = 'pending'",
                (self._config.agent_id,),
            ) as cur:
                rows = await cur.fetchall()
        finally:
            await db.close()
        return [row["task_id"] for row in rows]
