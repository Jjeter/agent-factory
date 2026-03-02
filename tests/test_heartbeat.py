"""TDD stub tests for Phase 2 — BaseAgent heartbeat loop behaviors.

Covers HB-04 through HB-13 (all heartbeat loop requirements).

Uses a module-level import sentinel so pytest can collect this file before
runtime/heartbeat.py and runtime/config.py exist. All tests skip cleanly
when the implementation modules are absent.
"""
import pytest

# Module-level guard: import heartbeat components if available, else set sentinel.
try:
    from runtime.heartbeat import BaseAgent  # noqa: F401 — used in subclasses below
    from runtime.config import AgentConfig  # noqa: F401 — used in all tests
    _has_heartbeat = True
except ImportError:
    _has_heartbeat = False
    BaseAgent = object  # placeholder so class bodies parse without error
    AgentConfig = None  # placeholder


# FixedTickAgent: subclass that stops after a fixed number of ticks.
# Only defined when the real BaseAgent is available.
if _has_heartbeat:
    class FixedTickAgent(BaseAgent):
        """BaseAgent subclass that self-terminates after `ticks` _tick() calls."""

        def __init__(self, config, ticks: int):
            super().__init__(config)
            self._remaining = ticks

        async def _tick(self):
            await super()._tick()
            self._remaining -= 1
            if self._remaining <= 0:
                self._stop_event.set()
else:
    FixedTickAgent = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _init_db(db_file):
    """Initialize the agent_factory schema on a fresh SQLite file."""
    from runtime.database import DatabaseManager
    mgr = DatabaseManager(db_file)
    await mgr.up()


def _make_config(db_file, agent_id="agent-1", interval=0.05, stagger=0.0):
    """Return an AgentConfig pointed at a real SQLite file."""
    return AgentConfig(
        agent_id=agent_id,
        agent_role="worker",
        db_path=str(db_file),
        interval_seconds=interval,
        stagger_offset_seconds=stagger,
    )


# ---------------------------------------------------------------------------
# HB-04: Stagger delay
# ---------------------------------------------------------------------------

async def test_stagger_delay(tmp_path):
    """HB-04: Agent with stagger_offset_seconds=0.1 delays at least 0.09s before first tick."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import time

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    tick_times: list[float] = []

    class TimingAgent(BaseAgent):
        async def _tick(self):
            tick_times.append(time.monotonic())
            await super()._tick()
            self._stop_event.set()

    cfg = _make_config(db_file, stagger=0.1)
    agent = TimingAgent(cfg)
    start = time.monotonic()
    await agent.start()

    assert tick_times, "Agent must have executed at least one tick"
    elapsed = tick_times[0] - start
    assert elapsed >= 0.09, f"Expected stagger >= 0.09s, got {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# HB-05: UPSERT — one row regardless of tick count
# ---------------------------------------------------------------------------

async def test_status_upsert(tmp_path):
    """HB-05: Two ticks still yield exactly one agent_status row (UPSERT semantics)."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import aiosqlite

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    cfg = _make_config(db_file)
    agent = FixedTickAgent(cfg, ticks=2)
    await agent.start()

    async with aiosqlite.connect(str(db_file)) as conn:
        async with conn.execute(
            "SELECT COUNT(*) FROM agent_status WHERE agent_id = ?", (cfg.agent_id,)
        ) as cur:
            row = await cur.fetchone()
    assert row[0] == 1, f"Expected 1 agent_status row, got {row[0]}"


# ---------------------------------------------------------------------------
# HB-06: Status transitions — working during tick, idle after
# ---------------------------------------------------------------------------

async def test_status_transitions(tmp_path):
    """HB-06: status='working' during tick body, status='idle' after tick completes."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import aiosqlite

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    mid_tick_statuses: list[str] = []

    class StatusSnapshotAgent(BaseAgent):
        async def do_own_tasks(self):
            # Read status from DB while still inside the tick
            async with aiosqlite.connect(str(db_file)) as conn:
                async with conn.execute(
                    "SELECT status FROM agent_status WHERE agent_id = ?",
                    (self._config.agent_id,),
                ) as cur:
                    row = await cur.fetchone()
            if row:
                mid_tick_statuses.append(row[0])
            self._stop_event.set()

    cfg = _make_config(db_file)
    agent = StatusSnapshotAgent(cfg)
    await agent.start()

    assert mid_tick_statuses, "do_own_tasks must have been called"
    assert mid_tick_statuses[0] == "working", (
        f"Expected 'working' during tick, got '{mid_tick_statuses[0]}'"
    )

    # After start() returns the agent should be idle
    async with aiosqlite.connect(str(db_file)) as conn:
        async with conn.execute(
            "SELECT status FROM agent_status WHERE agent_id = ?", (cfg.agent_id,)
        ) as cur:
            final_row = await cur.fetchone()

    assert final_row is not None
    assert final_row[0] == "idle", f"Expected 'idle' after tick, got '{final_row[0]}'"


# ---------------------------------------------------------------------------
# HB-07: State file written after tick
# ---------------------------------------------------------------------------

async def test_state_file_written(tmp_path, monkeypatch):
    """HB-07: runtime/state/<agent-id>.json exists with last_heartbeat and current_task_id."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import json
    import runtime.heartbeat as heartbeat_mod

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(heartbeat_mod, "STATE_DIR", state_dir)

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    cfg = _make_config(db_file)
    agent = FixedTickAgent(cfg, ticks=1)
    await agent.start()

    state_file = state_dir / f"{cfg.agent_id}.json"
    assert state_file.exists(), f"State file not found: {state_file}"

    data = json.loads(state_file.read_text())
    assert "last_heartbeat" in data, "State file missing 'last_heartbeat' key"
    assert "current_task_id" in data, "State file missing 'current_task_id' key"


# ---------------------------------------------------------------------------
# HB-08: Corrupt state file — logs warning, does not raise
# ---------------------------------------------------------------------------

async def test_state_file_corrupt(tmp_path, monkeypatch, caplog):
    """HB-08: Corrupt <agent-id>.json at startup logs a warning and starts normally."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import logging
    import runtime.heartbeat as heartbeat_mod

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(heartbeat_mod, "STATE_DIR", state_dir)

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    cfg = _make_config(db_file)

    # Pre-write corrupt JSON
    corrupt_file = state_dir / f"{cfg.agent_id}.json"
    corrupt_file.write_text("{this is not valid json!!!}")

    with caplog.at_level(logging.WARNING):
        agent = FixedTickAgent(cfg, ticks=1)
        await agent.start()  # Must not raise

    warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "corrupt" in m.lower() or "missing" in m.lower() for m in warning_msgs
    ), f"Expected WARNING about corrupt/missing state file. Got: {warning_msgs}"


# ---------------------------------------------------------------------------
# HB-09: CancelledError propagates — not swallowed
# ---------------------------------------------------------------------------

async def test_cancelled_error_propagates(tmp_path):
    """HB-09: Cancelling agent.start() task raises CancelledError (not suppressed)."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import asyncio

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    cfg = _make_config(db_file)
    agent = FixedTickAgent(cfg, ticks=5)

    task = asyncio.create_task(agent.start())

    # Let at least one tick start, then cancel
    await asyncio.sleep(cfg.interval_seconds + 0.02)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# HB-10: Stop event terminates loop gracefully
# ---------------------------------------------------------------------------

async def test_stop_event_graceful(tmp_path):
    """HB-10: Setting _stop_event terminates the loop within interval + small buffer."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import asyncio

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    cfg = _make_config(db_file, interval=0.05)
    agent = FixedTickAgent(cfg, ticks=99)  # would run forever without stop

    task = asyncio.create_task(agent.start())
    await asyncio.sleep(0.03)
    agent._stop_event.set()

    timeout = cfg.interval_seconds * 2 + 0.5
    await asyncio.wait_for(task, timeout=timeout)  # raises TimeoutError if it hangs


# ---------------------------------------------------------------------------
# HB-11: Two concurrent agents — no DB collision
# ---------------------------------------------------------------------------

async def test_two_agents_no_db_collision(tmp_path):
    """HB-11: Two FixedTickAgents (3 ticks each) run concurrently without OperationalError."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    import asyncio
    import aiosqlite

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    cfg1 = _make_config(db_file, agent_id="agent-1", interval=0.05, stagger=0.0)
    cfg2 = _make_config(db_file, agent_id="agent-2", interval=0.05, stagger=0.025)

    agent1 = FixedTickAgent(cfg1, ticks=3)
    agent2 = FixedTickAgent(cfg2, ticks=3)

    # Must complete without OperationalError ("database is locked")
    await asyncio.gather(agent1.start(), agent2.start())

    async with aiosqlite.connect(str(db_file)) as conn:
        async with conn.execute("SELECT COUNT(*) FROM agent_status") as cur:
            row = await cur.fetchone()

    assert row[0] == 2, f"Expected 2 agent_status rows, got {row[0]}"


# ---------------------------------------------------------------------------
# HB-12: Hook order — do_peer_reviews before do_own_tasks
# ---------------------------------------------------------------------------

async def test_hook_order(tmp_path):
    """HB-12: Within a tick, do_peer_reviews() executes before do_own_tasks()."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    call_order: list[str] = []

    class OrderTrackingAgent(BaseAgent):
        async def do_peer_reviews(self):
            call_order.append("do_peer_reviews")

        async def do_own_tasks(self):
            call_order.append("do_own_tasks")
            self._stop_event.set()

    cfg = _make_config(db_file)
    agent = OrderTrackingAgent(cfg)
    await agent.start()

    assert call_order == ["do_peer_reviews", "do_own_tasks"], (
        f"Expected ['do_peer_reviews', 'do_own_tasks'], got {call_order}"
    )


# ---------------------------------------------------------------------------
# HB-13: Jitter clamped — sleep never called with negative value
# ---------------------------------------------------------------------------

async def test_jitter_clamped(tmp_path):
    """HB-13: asyncio.sleep never receives a negative value even at minimum interval."""
    if not _has_heartbeat:
        pytest.skip("runtime.heartbeat not yet available")

    db_file = tmp_path / "agent.db"
    await _init_db(db_file)

    # Run 5 ticks at minimum interval — if jitter is unclamped this may raise ValueError
    cfg = _make_config(db_file, interval=0.01)
    agent = FixedTickAgent(cfg, ticks=5)

    # Should complete without ValueError from asyncio.sleep receiving a negative float
    await agent.start()
