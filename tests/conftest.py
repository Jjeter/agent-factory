"""Shared pytest fixtures for Phase 2: Agent Heartbeat Framework tests."""
import pytest
import pytest_asyncio
from pathlib import Path

from runtime.database import Database


@pytest_asyncio.fixture
async def tmp_db(tmp_path: Path) -> Database:
    """A fresh Database in tmp_path, open for the duration of the test."""
    async with Database(tmp_path / "cluster.db") as db:
        yield db


@pytest.fixture
def fast_config(tmp_path: Path):
    """AgentConfig with fast intervals for testing (no jitter, 0.1s cycle, no stagger).
    Import AgentConfig lazily to avoid import errors before runtime/config.py exists.
    """
    from runtime.config import AgentConfig
    return AgentConfig(
        agent_id="test-agent",
        role="researcher",
        interval_seconds=0.1,
        stagger_offset_seconds=0.0,
        jitter_seconds=0.0,
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def stub_agent(tmp_db, fast_config):
    """A concrete StubAgent (no-op hooks) backed by tmp_db and fast_config."""
    from runtime.heartbeat import BaseAgent
    from runtime.notifier import StdoutNotifier

    class StubAgent(BaseAgent):
        async def do_peer_reviews(self) -> None:
            pass

        async def do_own_tasks(self) -> None:
            pass

    return StubAgent(
        agent_id=fast_config.agent_id,
        db=tmp_db,
        config=fast_config,
        notifier=StdoutNotifier(),
    )
