"""BaseAgent — generic async heartbeat loop for all Agent Factory agents."""
import asyncio
import json
import logging
import random
from pathlib import Path

from runtime.config import AgentConfig
from runtime.database import DatabaseManager
from runtime.models import AgentStatusEnum, _now_iso, _uuid
from runtime.notifier import Notifier, StdoutNotifier

logger = logging.getLogger(__name__)
STATE_DIR = Path(__file__).parent / "state"


class BaseAgent:
    """Generic async heartbeat agent base class.

    Subclasses override ``do_peer_reviews`` and ``do_own_tasks`` to implement
    role-specific behaviour. The loop, DB writes, state file, and shutdown are
    handled here.
    """

    def __init__(self, config: AgentConfig, notifier: Notifier | None = None) -> None:
        self._config = config
        self._notifier = notifier or StdoutNotifier()
        self._db = DatabaseManager(Path(config.db_path) if config.db_path else Path(":memory:"))
        self._stop_event = asyncio.Event()
        self._state_path = STATE_DIR / f"{config.agent_id}.json"
        self._current_task_id: str | None = None
        self._resumed_task_id: str | None = None

    async def start(self) -> None:
        """Entry point: load state, stagger delay, then run the heartbeat loop.

        CancelledError propagates through wait_for and the while loop into the
        finally block, triggering _on_shutdown, then re-raises. Never caught here.
        """
        prior_state = self._load_state()  # Logs WARNING if state file missing or corrupt
        self._resumed_task_id = prior_state.get("current_task_id")
        if self._config.stagger_offset_seconds > 0:
            await asyncio.sleep(self._config.stagger_offset_seconds)
        try:
            while not self._stop_event.is_set():
                await self._tick()
                jitter = random.uniform(-30, 30)
                sleep_secs = max(0.0, self._config.interval_seconds + jitter)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_secs)
                except asyncio.TimeoutError:
                    pass  # Normal: interval elapsed, continue loop
        finally:
            await self._on_shutdown()

    async def _tick(self) -> None:
        """One heartbeat cycle: set working, run hooks, log, set idle, write state."""
        await self._set_db_status(AgentStatusEnum.WORKING)
        try:
            await self.do_peer_reviews()
            await self.do_own_tasks()
            await self._log_heartbeat()
            await self._set_db_status(AgentStatusEnum.IDLE)
        except Exception:
            logger.exception(
                "Unhandled error in tick for agent %s", self._config.agent_id
            )
            await self._set_db_status(AgentStatusEnum.ERROR)
        # Always write state file — reflects what actually happened after DB writes
        await self._write_state_file()

    async def do_peer_reviews(self) -> None:
        """No-op stub. Phase 3/4 subclasses override this."""
        pass

    async def do_own_tasks(self) -> None:
        """No-op stub. Phase 3/4 subclasses override this."""
        pass

    async def _set_db_status(self, status: AgentStatusEnum) -> None:
        """UPSERT agent_status row with the given status."""
        db = await self._db.open_write()
        try:
            await db.execute(
                """INSERT INTO agent_status (agent_id, agent_role, status, last_heartbeat, current_task)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       status=excluded.status,
                       last_heartbeat=excluded.last_heartbeat,
                       current_task=excluded.current_task""",
                (
                    self._config.agent_id,
                    self._config.agent_role,
                    status.value,
                    _now_iso(),
                    None,
                ),
            )
            await db.commit()
        finally:
            await db.close()

    async def _log_heartbeat(self) -> None:
        """Append one heartbeat row to activity_log."""
        db = await self._db.open_write()
        try:
            await db.execute(
                "INSERT INTO activity_log (id, agent_id, action, details, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_uuid(), self._config.agent_id, "heartbeat", None, _now_iso()),
            )
            await db.commit()
        finally:
            await db.close()

    async def _write_state_file(self) -> None:
        """Write {last_heartbeat, current_task_id} atomically via tmp + Path.replace()."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "last_heartbeat": _now_iso(),
            "current_task_id": getattr(self, "_current_task_id", None),
        }
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(self._state_path)

    def _load_state(self) -> dict:
        """Load local state file. Returns fresh dict on missing or corrupt file."""
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(
                "State file missing or corrupt for agent %s — treating as fresh start",
                self._config.agent_id,
            )
            return {"last_heartbeat": None, "current_task_id": None}

    async def _on_shutdown(self) -> None:
        """Final cleanup called from start() finally block."""
        try:
            await self._set_db_status(AgentStatusEnum.IDLE)
        except Exception:
            logger.exception("Error during shutdown for agent %s", self._config.agent_id)
        logger.info("Agent %s shut down cleanly", self._config.agent_id)
