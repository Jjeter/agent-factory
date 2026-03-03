"""Boss CLI integration tests — Phase 3.

Tests for cluster goal, cluster tasks, cluster agents, and cluster approve commands.
"""
import asyncio
import json
import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import AsyncMock, patch

from runtime.cli import cluster_cli
from runtime.database import DatabaseManager
from runtime.models import _uuid, _now_iso


async def _init_db(db_path: Path) -> DatabaseManager:
    mgr = DatabaseManager(db_path)
    await mgr.up()
    return mgr


async def _seed_goal(mgr: DatabaseManager, goal_id: str, description: str = "Test goal") -> None:
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO goals (id, title, description, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            (goal_id, "Test Goal", description, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_task(mgr: DatabaseManager, goal_id: str, title: str, status: str) -> str:
    task_id = _uuid()
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, ?, 'desc', ?, 50, 'haiku', 0, '[]', ?, ?)",
            (task_id, goal_id, title, status, _now_iso(), _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()
    return task_id


async def _seed_agent(mgr: DatabaseManager, agent_id: str, role: str, status: str = "idle") -> None:
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO agent_status (agent_id, agent_role, status, last_heartbeat) VALUES (?, ?, ?, ?)",
            (agent_id, role, status, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()


async def _fetch_goals(mgr: DatabaseManager) -> list:
    db = await mgr.open_read()
    try:
        async with db.execute("SELECT * FROM goals") as cur:
            return await cur.fetchall()
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Task 1 tests: goal set + tasks list
# ---------------------------------------------------------------------------


def test_goal_set_command(tmp_path):
    db_path = str(tmp_path / "test.db")
    asyncio.run(DatabaseManager(tmp_path / "test.db").up())

    runner = CliRunner()
    with patch("runtime.boss.BossAgent.decompose_goal", new_callable=AsyncMock):
        result = runner.invoke(
            cluster_cli,
            ["goal", "set", "Build a date arithmetic library", "--db-path", db_path],
        )
    assert result.exit_code == 0, f"CLI error: {result.output}\n{result.exception}"

    mgr = DatabaseManager(tmp_path / "test.db")
    db_rows = asyncio.run(_fetch_goals(mgr))
    assert len(db_rows) >= 1
    assert any("date arithmetic" in r["description"] for r in db_rows)


def test_tasks_list_table_output(tmp_path):
    db_path = str(tmp_path / "test.db")
    mgr = asyncio.run(_init_db(tmp_path / "test.db"))
    goal_id = _uuid()
    asyncio.run(_seed_goal(mgr, goal_id))
    asyncio.run(_seed_task(mgr, goal_id, "Research task", "todo"))
    asyncio.run(_seed_task(mgr, goal_id, "Write report", "in-progress"))

    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["tasks", "list", "--db-path", db_path])
    assert result.exit_code == 0, f"CLI error: {result.output}"
    # Check column headers present
    assert "Title" in result.output or "title" in result.output.lower()
    assert "Status" in result.output or "status" in result.output.lower()
    # Both task titles in output
    assert "Research task" in result.output
    assert "Write report" in result.output


def test_tasks_list_status_filter(tmp_path):
    db_path = str(tmp_path / "test.db")
    mgr = asyncio.run(_init_db(tmp_path / "test.db"))
    goal_id = _uuid()
    asyncio.run(_seed_goal(mgr, goal_id))
    asyncio.run(_seed_task(mgr, goal_id, "Todo task", "todo"))
    asyncio.run(_seed_task(mgr, goal_id, "Review task", "peer_review"))

    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["tasks", "list", "--status", "peer_review", "--db-path", db_path])
    assert result.exit_code == 0, f"CLI error: {result.output}"
    assert "Review task" in result.output
    assert "Todo task" not in result.output


def test_tasks_list_json_output(tmp_path):
    db_path = str(tmp_path / "test.db")
    mgr = asyncio.run(_init_db(tmp_path / "test.db"))
    goal_id = _uuid()
    asyncio.run(_seed_goal(mgr, goal_id))
    asyncio.run(_seed_task(mgr, goal_id, "My task", "todo"))

    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["tasks", "list", "--json", "--db-path", db_path])
    assert result.exit_code == 0, f"CLI error: {result.output}"
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    # Each item should have an id/title equivalent
    assert any("My task" in str(item) for item in data)


# ---------------------------------------------------------------------------
# Task 2 tests: agents status + approve
# ---------------------------------------------------------------------------


def test_agents_status_output(tmp_path):
    db_path = str(tmp_path / "test.db")
    mgr = asyncio.run(_init_db(tmp_path / "test.db"))
    asyncio.run(_seed_agent(mgr, "boss-1", "boss", "working"))
    asyncio.run(_seed_agent(mgr, "agent-1", "researcher", "idle"))

    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["agents", "status", "--db-path", db_path])
    assert result.exit_code == 0, f"CLI error: {result.output}"
    assert "boss-1" in result.output
    assert "agent-1" in result.output
    assert "boss" in result.output
    assert "researcher" in result.output


def test_approve_review_task(tmp_path):
    db_path = str(tmp_path / "test.db")
    mgr = asyncio.run(_init_db(tmp_path / "test.db"))
    goal_id = _uuid()
    asyncio.run(_seed_goal(mgr, goal_id))
    task_id = asyncio.run(_seed_task(mgr, goal_id, "Ready task", "review"))

    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["approve", task_id, "--db-path", db_path])
    assert result.exit_code == 0, f"CLI error: {result.output}\n{result.exception}"

    async def _get_status():
        db = await mgr.open_read()
        try:
            async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
                return await cur.fetchone()
        finally:
            await db.close()
    row = asyncio.run(_get_status())
    assert row["status"] == "approved"


def test_approve_wrong_state_fails(tmp_path):
    db_path = str(tmp_path / "test.db")
    mgr = asyncio.run(_init_db(tmp_path / "test.db"))
    goal_id = _uuid()
    asyncio.run(_seed_goal(mgr, goal_id))
    task_id = asyncio.run(_seed_task(mgr, goal_id, "Not ready task", "todo"))

    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["approve", task_id, "--db-path", db_path])
    assert result.exit_code != 0
    # Error message should mention the invalid transition or task state
    combined = (result.output or "") + str(result.exception or "")
    assert any(word in combined.lower() for word in ["cannot", "error", "invalid", "review"])
