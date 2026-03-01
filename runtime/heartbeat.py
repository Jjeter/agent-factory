"""Base agent class for the Agent Factory runtime.

All agents (boss and workers) subclass BaseAgent and override exactly two hooks:
- do_peer_reviews(): check and process pending peer reviews
- do_own_tasks(): claim and execute own assigned tasks

The heartbeat loop, stagger, jitter, DB status upsert, state file persistence,
error handling, and graceful shutdown are all handled by BaseAgent.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import tempfile
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from runtime.config import AgentConfig
from runtime.database import Database
from runtime.models import (
    ActivityLog,
    AgentRole,
    AgentState,
    AgentStatusRecord,
)
from runtime.notifier import Notifier


class BaseAgent(ABC):
    """Abstract base class for all Agent Factory agents.

    Concrete subclasses must implement:
    - do_peer_reviews(): process pending peer reviews (called first each cycle)
    - do_own_tasks(): claim and execute own assigned tasks (called second each cycle)

    Usage:
        class MyAgent(BaseAgent):
            async def do_peer_reviews(self) -> None:
                ...
            async def do_own_tasks(self) -> None:
                ...

        agent = MyAgent(agent_id="researcher-1", db=db, config=config, notifier=notifier)
        await agent.run()   # blocks until agent.stop() is called or task is cancelled
    """

    def __init__(
        self,
        agent_id: str,
        db: Database,
        config: AgentConfig,
        notifier: Notifier,
    ) -> None:
        self.agent_id = agent_id
        self.db = db
        self.config = config
        self.notifier = notifier
        self._stop_event = asyncio.Event()
        self._heartbeat_count: int = 0
        self._current_task_id: Optional[str] = None
        self._state_path = config.state_dir / f"{agent_id}.json"

        # Load prior state if agent is restarting after a crash
        prior = self._load_local_state()
        self._heartbeat_count = prior.get("heartbeat_count", 0)

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main heartbeat loop. Blocks until stop() is called or task is cancelled.

        Sequence per cycle:
          1. (First cycle only) Stagger sleep: wait config.stagger_offset_seconds
          2. _heartbeat(): upsert status working -> do_peer_reviews -> do_own_tasks
             -> log -> save state -> upsert idle
          3. Interval + jitter sleep before the next cycle

        CancelledError is always re-raised — never suppressed.
        Other exceptions are logged to DB and the loop continues (agent resilience).
        """
        # Stagger: one-time delay before first heartbeat to prevent thundering herd
        if self.config.stagger_offset_seconds > 0.0:
            try:
                await asyncio.sleep(self.config.stagger_offset_seconds)
            except asyncio.CancelledError:
                raise  # propagate — do not suppress

        while not self._stop_event.is_set():
            try:
                await self._heartbeat()
            except asyncio.CancelledError:
                raise  # ALWAYS propagate
            except Exception as exc:
                await self._handle_error(exc)

            if self._stop_event.is_set():
                break

            # Interval sleep with jitter: ±jitter_seconds random
            jitter = random.uniform(-self.config.jitter_seconds, self.config.jitter_seconds)
            sleep_seconds = max(0.0, self.config.interval_seconds + jitter)
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                raise  # propagate

    def stop(self) -> None:
        """Signal the heartbeat loop to exit cleanly after the current cycle completes."""
        self._stop_event.set()

    # ── Abstract hooks (subclasses implement these) ────────────────────────────

    @abstractmethod
    async def do_peer_reviews(self) -> None:
        """Process pending peer reviews where this agent is assigned as reviewer.

        Called at the start of every heartbeat cycle, before do_own_tasks().
        Subclasses fetch tasks in peer_review state, generate feedback, and
        post task_comment records with approved/rejected status.
        """

    @abstractmethod
    async def do_own_tasks(self) -> None:
        """Claim and execute tasks assigned to this agent.

        Called after do_peer_reviews() every heartbeat cycle.
        Subclasses fetch todo/in-progress tasks, execute work (LLM call,
        document creation), and transition task status to peer_review.
        """

    # ── Heartbeat cycle ────────────────────────────────────────────────────────

    async def _heartbeat(self) -> None:
        """Execute a single heartbeat cycle. Not intended to be overridden.

        Sequence: upsert working -> do_peer_reviews -> do_own_tasks -> log -> save state -> upsert idle
        """
        await self._upsert_status(AgentState.WORKING)
        await self.do_peer_reviews()
        await self.do_own_tasks()
        await self._log_heartbeat_activity()
        self._heartbeat_count += 1
        await self._save_local_state()
        await self._upsert_status(AgentState.IDLE)

    # ── DB operations ──────────────────────────────────────────────────────────

    async def _upsert_status(self, state: AgentState) -> None:
        """Upsert this agent's status row in the agent_status table."""
        record = AgentStatusRecord(
            id=self.agent_id,
            agent_role=AgentRole(self.config.role),
            status=state,
            last_heartbeat=datetime.now(timezone.utc),
            current_task=self._current_task_id,
        )
        await self.db.upsert_agent_status(record)

    async def _log_heartbeat_activity(self) -> None:
        """Append an activity_log entry for this heartbeat cycle."""
        entry = ActivityLog(
            id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_id=self._current_task_id,
            action="heartbeat",
            details=f"Cycle {self._heartbeat_count + 1} complete",
            created_at=datetime.now(timezone.utc),
        )
        await self.db.append_activity(entry)

    async def _handle_error(self, exc: Exception) -> None:
        """Log an error and update DB status to 'error'. Loop continues."""
        try:
            await self._upsert_status(AgentState.ERROR)
            entry = ActivityLog(
                id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                task_id=self._current_task_id,
                action="heartbeat_error",
                details=f"{type(exc).__name__}: {exc}",
                created_at=datetime.now(timezone.utc),
            )
            await self.db.append_activity(entry)
        except Exception:
            pass  # If DB is down, swallow the error-logging error silently

    # ── Local state file ───────────────────────────────────────────────────────

    async def _save_local_state(self) -> None:
        """Persist agent state to a local JSON file atomically.

        Uses write-to-temp + Path.rename() for crash safety.
        Runs in a thread executor to avoid blocking the event loop during fsync.
        """
        state = {
            "agent_id": self.agent_id,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "current_task_id": self._current_task_id,
            "heartbeat_count": self._heartbeat_count,
            "status": "idle",
        }
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_state_atomic, state)

    def _write_state_atomic(self, state: dict) -> None:
        """Write state dict to JSON atomically via write-then-rename (blocking I/O).

        Safe to call from run_in_executor. The rename() call is atomic on both
        POSIX (same filesystem guaranteed by dir= parameter) and NTFS.
        """
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=self._state_path.parent,
            suffix=".tmp",
        ) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(state, tmp, indent=2, default=str)
            tmp.flush()
            os.fsync(tmp.fileno())

        tmp_path.replace(self._state_path)

    def _load_local_state(self) -> dict:
        """Load prior state from JSON file, if it exists.

        Returns empty dict if file is missing or corrupt — agent starts fresh.
        """
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}
