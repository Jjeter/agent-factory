"""Shared pytest fixtures and factory helpers for the Agent Factory test suite."""
import uuid
from pathlib import Path

import pytest

# Guard against ImportError before runtime.database is implemented (Plans 02-04)
try:
    from runtime.database import DatabaseManager
    _has_runtime = True
except ImportError:
    _has_runtime = False


@pytest.fixture
async def db():
    """Per-test isolated in-memory database with schema initialized.

    Function-scoped (default) so each test gets a fresh connection.
    Yields the open aiosqlite.Connection; closes it in finally.
    """
    if not _has_runtime:
        pytest.skip("runtime.database not yet available")

    manager = DatabaseManager(Path(":memory:"))
    conn = await manager.open_write()
    try:
        await manager.init_schema(conn)
        yield conn
    finally:
        await conn.close()


async def create_goal(db, *, title: str = "Test Goal", description: str = "A test goal") -> str:
    """Insert a goal row and return its id.

    Args:
        db: An open aiosqlite.Connection with schema initialized.
        title: Goal title (defaults to "Test Goal").
        description: Goal description (defaults to "A test goal").

    Returns:
        The UUID string id of the created goal.
    """
    goal_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO goals (id, title, description) VALUES (?, ?, ?)",
        (goal_id, title, description),
    )
    await db.commit()
    return goal_id


async def create_task(
    db,
    goal_id: str,
    *,
    title: str = "Test Task",
    description: str = "A test task",
) -> str:
    """Insert a task row linked to goal_id and return its id.

    Args:
        db: An open aiosqlite.Connection with schema initialized.
        goal_id: The goal this task belongs to.
        title: Task title (defaults to "Test Task").
        description: Task description (defaults to "A test task").

    Returns:
        The UUID string id of the created task.
    """
    task_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO tasks (id, goal_id, title, description) VALUES (?, ?, ?, ?)",
        (task_id, goal_id, title, description),
    )
    await db.commit()
    return task_id
