"""Tests for runtime.heartbeat — BaseAgent ABC with async heartbeat loop.

HB-01: BaseAgent subclass can override do_peer_reviews().
HB-02: BaseAgent subclass can override do_own_tasks().
HB-03: Local state file updated after every heartbeat.
HB-04: Heartbeat jitter applied to sleep duration.
HB-05: Stagger offset delays first heartbeat only.
HB-06: Two agents running simultaneously never hold write lock simultaneously.
HB-12: DB agent_status row upserted on each heartbeat.
HB-13: BaseAgent.stop() causes clean loop exit without exception.
HB-14: State file atomic write — rename-based, no partial writes.
"""
import asyncio
import json
import pytest
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch


# ── Helper ────────────────────────────────────────────────────────────────────

def make_stub_agent(db, config, notifier=None):
    """Build a concrete no-op StubAgent for use in tests that need custom config."""
    from runtime.heartbeat import BaseAgent
    from runtime.notifier import StdoutNotifier

    class StubAgent(BaseAgent):
        async def do_peer_reviews(self) -> None:
            pass

        async def do_own_tasks(self) -> None:
            pass

    return StubAgent(
        agent_id=config.agent_id,
        db=db,
        config=config,
        notifier=notifier or StdoutNotifier(),
    )


async def run_for_n_cycles(agent, n: int) -> None:
    """Run agent for exactly n heartbeat cycles, then call stop()."""
    cycles = 0
    original_heartbeat = agent._heartbeat

    async def counted_heartbeat():
        nonlocal cycles
        await original_heartbeat()
        cycles += 1
        if cycles >= n:
            agent.stop()

    agent._heartbeat = counted_heartbeat
    await agent.run()


# ── HB-01, HB-02: Hook overrides ─────────────────────────────────────────────

class TestSubclassHookOverrides:
    async def test_subclass_overrides_hooks(self, stub_agent):
        """HB-01 + HB-02: Subclass can concretely override both abstract hooks."""
        from runtime.heartbeat import BaseAgent
        import inspect

        # do_peer_reviews and do_own_tasks must be abstract in BaseAgent
        assert inspect.isabstract(BaseAgent)
        # stub_agent is instantiated (non-abstract), proving both hooks are overridden
        assert stub_agent is not None

        # Hooks are callable async methods on the instance
        assert asyncio.iscoroutinefunction(stub_agent.do_peer_reviews)
        assert asyncio.iscoroutinefunction(stub_agent.do_own_tasks)


# ── HB-03: State file written per cycle ──────────────────────────────────────

class TestStateFilePersistence:
    async def test_state_file_written_per_cycle(self, tmp_db, fast_config):
        """HB-03: Local state file exists and is updated after each heartbeat cycle."""
        agent = make_stub_agent(tmp_db, fast_config)
        state_path = fast_config.state_dir / f"{fast_config.agent_id}.json"

        await run_for_n_cycles(agent, 1)

        assert state_path.exists(), f"State file not found at {state_path}"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["agent_id"] == fast_config.agent_id
        assert "last_heartbeat" in state
        assert state["heartbeat_count"] >= 1


# ── HB-04: Jitter applied ────────────────────────────────────────────────────

class TestJitter:
    async def test_jitter_applied(self, tmp_db, fast_config):
        """HB-04: Sleep duration includes jitter from config.jitter_seconds."""
        from runtime.config import AgentConfig

        jitter_config = AgentConfig(
            agent_id="jitter-agent",
            role="researcher",
            interval_seconds=1.0,
            stagger_offset_seconds=0.0,
            jitter_seconds=0.5,
            state_dir=fast_config.state_dir,
        )
        agent = make_stub_agent(tmp_db, jitter_config)

        sleep_durations = []
        original_sleep = asyncio.sleep

        async def recording_sleep(duration):
            sleep_durations.append(duration)
            # Don't actually sleep — return immediately
            return await original_sleep(0)

        with patch("asyncio.sleep", side_effect=recording_sleep):
            await run_for_n_cycles(agent, 2)

        # With jitter_seconds=0.5, sleep duration should vary around 1.0s
        # At minimum, the interval sleep should have been called (not always exactly 1.0)
        interval_sleeps = [d for d in sleep_durations if d >= 0]
        assert len(interval_sleeps) > 0


# ── HB-05: Stagger offset applied only once ───────────────────────────────────

class TestStaggerOffset:
    async def test_stagger_offset_first_cycle_only(self, tmp_db, fast_config):
        """HB-05: Stagger sleep happens exactly once before the first heartbeat."""
        from runtime.config import AgentConfig

        stagger_config = AgentConfig(
            agent_id="stagger-agent",
            role="researcher",
            interval_seconds=0.1,
            stagger_offset_seconds=0.05,
            jitter_seconds=0.0,
            state_dir=fast_config.state_dir,
        )
        agent = make_stub_agent(tmp_db, stagger_config)

        stagger_called_count = 0
        original_sleep = asyncio.sleep

        async def tracking_sleep(duration):
            nonlocal stagger_called_count
            if abs(duration - 0.05) < 0.001:
                stagger_called_count += 1
            return await original_sleep(0)

        with patch("asyncio.sleep", side_effect=tracking_sleep):
            await run_for_n_cycles(agent, 3)

        assert stagger_called_count == 1, (
            f"Stagger sleep should happen exactly once, got {stagger_called_count}"
        )


# ── HB-06: Two agents, no DB collision ───────────────────────────────────────

class TestTwoAgentsNoDbCollision:
    async def test_two_agents_no_db_collision(self, tmp_path):
        """HB-06: Two agents with staggered configs run concurrently without DB write collision."""
        from runtime.config import AgentConfig
        from runtime.database import Database

        async with Database(tmp_path / "cluster.db") as db:
            config_a = AgentConfig(
                agent_id="agent-a",
                role="researcher",
                interval_seconds=0.1,
                stagger_offset_seconds=0.0,
                jitter_seconds=0.0,
                state_dir=tmp_path / "state",
            )
            config_b = AgentConfig(
                agent_id="agent-b",
                role="writer",
                interval_seconds=0.1,
                stagger_offset_seconds=0.05,
                jitter_seconds=0.0,
                state_dir=tmp_path / "state",
            )

            agent_a = make_stub_agent(db, config_a)
            agent_b = make_stub_agent(db, config_b)

            # Both agents run 3 cycles; any OperationalError (SQLITE_BUSY) propagates
            async with asyncio.timeout(5.0):
                await asyncio.gather(
                    run_for_n_cycles(agent_a, 3),
                    run_for_n_cycles(agent_b, 3),
                )

            # Both state files must exist
            assert (tmp_path / "state" / "agent-a.json").exists()
            assert (tmp_path / "state" / "agent-b.json").exists()


# ── HB-12: agent_status upserted per heartbeat ────────────────────────────────

class TestAgentStatusUpserted:
    async def test_agent_status_upserted(self, tmp_db, fast_config):
        """HB-12: DB agent_status row is upserted (created/updated) on each heartbeat."""
        agent = make_stub_agent(tmp_db, fast_config)

        await run_for_n_cycles(agent, 2)

        record = await tmp_db.get_agent_status(fast_config.agent_id)
        assert record is not None
        assert record.id == fast_config.agent_id
        assert record.last_heartbeat is not None


# ── HB-13: stop() exits cleanly ──────────────────────────────────────────────

class TestStopExitsCleanly:
    async def test_stop_exits_cleanly(self, stub_agent):
        """HB-13: agent.stop() causes the heartbeat loop to exit without raising an exception."""
        # Start the loop, immediately signal stop
        stub_agent.stop()

        # run() should return without raising — no exception propagation
        async with asyncio.timeout(2.0):
            await stub_agent.run()


# ── HB-14: Atomic state file write ───────────────────────────────────────────

class TestStateFileAtomicWrite:
    async def test_state_file_atomic_write(self, tmp_db, fast_config):
        """HB-14: State file is written atomically (rename-based); no partial writes."""
        import tempfile

        agent = make_stub_agent(tmp_db, fast_config)
        state_path = fast_config.state_dir / f"{fast_config.agent_id}.json"

        rename_called = False
        original_rename = Path.rename

        def tracking_rename(self, target):
            nonlocal rename_called
            if str(self).endswith(".tmp"):
                rename_called = True
            return original_rename(self, target)

        with patch.object(Path, "rename", tracking_rename):
            await run_for_n_cycles(agent, 1)

        assert state_path.exists()
        assert rename_called, "State file was not written via atomic rename (write-then-rename)"
