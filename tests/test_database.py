"""Tests for runtime.database — DatabaseManager connection lifecycle and CLI commands.

Covers: DB-01, DB-02, DB-03, DB-04, DB-05, CLI-01, CLI-02
"""
from pathlib import Path

import aiosqlite
import pytest

from runtime.database import DatabaseManager

ALL_TABLES = {
    "goals",
    "tasks",
    "task_comments",
    "task_reviews",
    "agent_status",
    "documents",
    "activity_log",
}


async def get_tables(conn: aiosqlite.Connection) -> set[str]:
    """Return set of table names present in the database."""
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cur:
        return {row[0] for row in await cur.fetchall()}


async def test_open_write() -> None:
    """DB-01: open_write() returns a connected aiosqlite.Connection."""
    mgr = DatabaseManager(Path(":memory:"))
    conn = await mgr.open_write()
    try:
        assert conn is not None
        assert isinstance(conn, aiosqlite.Connection)
    finally:
        await conn.close()


async def test_wal_mode(tmp_path: Path) -> None:
    """DB-02: journal_mode is 'wal' after open_write() on a file-based database.

    WAL mode requires a real file — :memory: databases silently fall back to 'memory' mode.
    """
    db_file = tmp_path / "test_wal.db"
    mgr = DatabaseManager(db_file)
    conn = await mgr.open_write()
    try:
        async with conn.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
        assert row[0] == "wal", f"Expected 'wal', got {row[0]!r}"
    finally:
        await conn.close()


async def test_busy_timeout() -> None:
    """DB-03: busy_timeout is set to 5000 ms after open_write()."""
    mgr = DatabaseManager(Path(":memory:"))
    conn = await mgr.open_write()
    try:
        async with conn.execute("PRAGMA busy_timeout") as cursor:
            row = await cursor.fetchone()
        assert row[0] == 5000, f"Expected 5000, got {row[0]!r}"
    finally:
        await conn.close()


async def test_foreign_keys() -> None:
    """DB-04: foreign_keys enforcement is ON after open_write()."""
    mgr = DatabaseManager(Path(":memory:"))
    conn = await mgr.open_write()
    try:
        async with conn.execute("PRAGMA foreign_keys") as cursor:
            row = await cursor.fetchone()
        assert row[0] == 1, f"Expected 1 (ON), got {row[0]!r}"
    finally:
        await conn.close()


async def test_init_schema_creates_all_tables(db: aiosqlite.Connection) -> None:
    """DB-05: init_schema() creates all 7 required tables."""
    tables = await get_tables(db)
    assert ALL_TABLES.issubset(tables), f"Tables missing after init_schema: {ALL_TABLES - tables}"


async def test_db_up_idempotent(tmp_path: Path) -> None:
    """CLI-01: db up is idempotent — running twice raises no error and tables persist."""
    db_file = tmp_path / "test.db"
    mgr = DatabaseManager(db_file)
    await mgr.up()  # first call
    await mgr.up()  # second call — must not raise
    # tables still exist after second up
    conn = await mgr.open_write()
    try:
        tables = await get_tables(conn)
        assert ALL_TABLES.issubset(tables), f"Tables missing after second up: {ALL_TABLES - tables}"
    finally:
        await conn.close()


async def test_db_reset(tmp_path: Path) -> None:
    """CLI-02: db reset drops and recreates all tables; inserted data is gone."""
    db_file = tmp_path / "test.db"
    mgr = DatabaseManager(db_file)
    await mgr.up()
    # Insert a goal row
    conn = await mgr.open_write()
    try:
        await conn.execute(
            "INSERT INTO goals (id, title, description) VALUES (?, ?, ?)",
            ("g1", "Test", "Desc"),
        )
        await conn.commit()
    finally:
        await conn.close()
    # Reset — should drop and recreate all tables
    await mgr.reset()
    conn = await mgr.open_write()
    try:
        tables = await get_tables(conn)
        assert ALL_TABLES.issubset(tables), f"Tables missing after reset: {ALL_TABLES - tables}"
        async with conn.execute("SELECT COUNT(*) FROM goals") as cur:
            count = (await cur.fetchone())[0]
        assert count == 0, "goals table should be empty after reset"
    finally:
        await conn.close()
