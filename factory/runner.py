"""factory/runner.py — subprocess entry point for the factory agent cluster.

Called by `agent-factory create` via subprocess.Popen:
    python -m factory.runner <goal_id> <factory_db_path>

Starts FactoryBossAgent plus all three factory workers concurrently.
Workers are required — without them, tasks emitted by the boss remain in 'todo' state.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


async def run_factory(goal_id: str, db_path: str) -> None:
    """Start factory boss + all factory workers concurrently until goal is completed."""
    from factory.boss import FactoryBossAgent
    from factory.workers import (
        FactoryResearcherAgent,
        FactorySecurityCheckerAgent,
        FactoryExecutorAgent,
    )
    from runtime.config import AgentConfig
    from runtime.notifier import StdoutNotifier

    factory_home = Path(os.environ.get("FACTORY_HOME", Path.home() / ".agent-factory"))
    state_dir = factory_home / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    notifier = StdoutNotifier()

    def _make_config(agent_id: str, agent_role: str, stagger: float = 0.0) -> AgentConfig:
        return AgentConfig(
            agent_id=agent_id,
            agent_role=agent_role,
            db_path=db_path,
            state_dir=state_dir,
            interval_seconds=30.0,  # factory batch job — needs to complete quickly
            stagger_offset_seconds=stagger,
        )

    boss = FactoryBossAgent(_make_config("factory-boss-01", "boss", stagger=0.0), notifier=notifier)
    researcher = FactoryResearcherAgent(
        _make_config("factory-researcher-01", "researcher", stagger=7.5), notifier=notifier
    )
    security_checker = FactorySecurityCheckerAgent(
        _make_config("factory-security-checker-01", "security-checker", stagger=15.0),
        notifier=notifier,
    )
    executor = FactoryExecutorAgent(
        _make_config("factory-executor-01", "executor", stagger=22.5), notifier=notifier
    )

    try:
        await asyncio.gather(
            boss.start(),
            researcher.start(),
            security_checker.start(),
            executor.start(),
        )
    except asyncio.CancelledError:
        raise  # never suppress CancelledError — project-wide invariant
    except Exception:
        logger.exception("Factory runner failed")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m factory.runner <goal_id> <db_path>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run_factory(sys.argv[1], sys.argv[2]))
