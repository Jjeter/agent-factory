"""Security tests for Phase 7 — SEC-01 and SEC-02.

Covers SEC-01 (tool allowlist enforcement) and SEC-02 (cross-cluster DB isolation).
"""
import pytest
from pathlib import Path


# ── SEC-01: Tool allowlist enforcement ───────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_allowlist_blocks_disallowed_call(tmp_path):
    """WorkerAgent logs+skips a disallowed tool call — does NOT forward it."""
    from runtime.worker import WorkerAgent
    from runtime.config import AgentConfig
    from runtime.database import DatabaseManager
    from unittest.mock import AsyncMock, MagicMock, patch
    import aiosqlite

    db_path = tmp_path / "cluster.db"
    cfg = AgentConfig(
        agent_id="worker-01",
        agent_role="researcher",
        interval_seconds=0.01,
        db_path=str(db_path),
        tool_allowlist=["allowed_tool"],
    )
    worker = WorkerAgent(cfg)

    # Seed DB with one in-progress task
    manager = DatabaseManager(db_path)
    conn = await manager.open_write()
    await manager.init_schema(conn)
    await conn.execute(
        "INSERT INTO goals (id, title, description) VALUES ('g1', 'T', 'D')"
    )
    await conn.execute(
        "INSERT INTO tasks (id, goal_id, title, description, assigned_to, status, model_tier) "
        "VALUES ('t1', 'g1', 'Test Task', 'Desc', 'worker-01', 'in-progress', 'haiku')"
    )
    await conn.commit()
    await conn.close()

    # Mock LLM to return a tool_use block for a DISALLOWED tool
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.name = "disallowed_tool"
    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        # Should NOT raise — log+skip behavior
        await worker._execute_task({"id": "t1", "title": "Test Task",
                                    "description": "Desc", "model_tier": "haiku"})

    # Verify task was NOT moved to peer_review (stays in-progress)
    conn = await manager.open_read()
    async with conn.execute("SELECT status FROM tasks WHERE id = 't1'") as cur:
        row = await cur.fetchone()
    await conn.close()
    assert row[0] == "in-progress", "Disallowed tool call must NOT advance task to peer_review"


# ── SEC-02: Cross-cluster DB isolation ───────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_cluster_db_isolation(tmp_path):
    """Two DatabaseManager instances pointing to different paths are fully isolated."""
    from runtime.database import DatabaseManager

    db_a_path = tmp_path / "cluster_a" / "cluster.db"
    db_b_path = tmp_path / "cluster_b" / "cluster.db"
    db_a_path.parent.mkdir()
    db_b_path.parent.mkdir()

    manager_a = DatabaseManager(db_a_path)
    manager_b = DatabaseManager(db_b_path)

    # Seed cluster A
    conn_a = await manager_a.open_write()
    await manager_a.init_schema(conn_a)
    await conn_a.execute(
        "INSERT INTO goals (id, title, description) VALUES ('g1', 'Cluster A Goal', 'Description')"
    )
    await conn_a.commit()
    await conn_a.close()

    # Initialize cluster B (empty)
    conn_b = await manager_b.open_write()
    await manager_b.init_schema(conn_b)
    async with conn_b.execute("SELECT COUNT(*) FROM goals") as cur:
        row = await cur.fetchone()
    count = row[0]
    await conn_b.close()

    assert count == 0, f"Cluster B must not see Cluster A's data, got {count} goals"
