"""Tests for runtime.database — DatabaseManager connection lifecycle and CLI commands.

Covers: DB-01, DB-02, DB-03, DB-04, DB-05, CLI-01, CLI-02

All tests are marked xfail (strict=False) until runtime.database is implemented in
Plan 04. The xfail marker means the suite collects cleanly and shows as expected
failures rather than errors.
"""
import pytest

pytestmark = pytest.mark.xfail(
    reason="runtime.database not yet implemented (Plan 04)",
    strict=False,
)

# Lazy import inside each test body so collection never raises ImportError.


async def test_open_write(db) -> None:
    """DB-01: open_write() returns a connected aiosqlite.Connection."""
    import aiosqlite

    assert isinstance(db, aiosqlite.Connection), (
        "open_write() must return an aiosqlite.Connection"
    )


async def test_wal_mode(db) -> None:
    """DB-02: journal_mode is 'wal' after open_write()."""
    async with db.execute("PRAGMA journal_mode") as cursor:
        row = await cursor.fetchone()
    assert row[0] == "wal", f"Expected 'wal', got {row[0]!r}"


async def test_busy_timeout(db) -> None:
    """DB-03: busy_timeout is set to 5000 ms after open_write()."""
    async with db.execute("PRAGMA busy_timeout") as cursor:
        row = await cursor.fetchone()
    assert row[0] == 5000, f"Expected 5000, got {row[0]!r}"


async def test_foreign_keys(db) -> None:
    """DB-04: foreign_keys enforcement is ON after open_write()."""
    async with db.execute("PRAGMA foreign_keys") as cursor:
        row = await cursor.fetchone()
    assert row[0] == 1, f"Expected 1 (ON), got {row[0]!r}"


async def test_init_schema_creates_all_tables(db) -> None:
    """DB-05: init_schema() creates all 7 required tables."""
    expected_tables = {
        "goals",
        "tasks",
        "task_comments",
        "task_reviews",
        "agent_status",
        "documents",
        "activity_log",
    }
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ) as cursor:
        rows = await cursor.fetchall()

    actual_tables = {row[0] for row in rows}
    missing = expected_tables - actual_tables
    assert not missing, f"Tables missing after init_schema: {missing}"


async def test_db_up_idempotent() -> None:
    """CLI-01: db up is idempotent — running twice raises no error."""
    import asyncio
    from pathlib import Path

    from runtime.database import DatabaseManager

    manager = DatabaseManager(Path(":memory:"))
    conn = await manager.open_write()
    try:
        await manager.init_schema(conn)
        # Second call must not raise
        await manager.init_schema(conn)
    finally:
        await conn.close()


async def test_db_reset() -> None:
    """CLI-02: db reset drops and recreates all tables."""
    from pathlib import Path

    from runtime.database import DatabaseManager

    manager = DatabaseManager(Path(":memory:"))
    conn = await manager.open_write()
    try:
        await manager.init_schema(conn)
        # Verify tables exist
        async with conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] == 7, f"Expected 7 tables, got {row[0]}"

        await manager.reset(conn)

        # Verify tables were recreated
        async with conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] == 7, f"Expected 7 tables after reset, got {row[0]}"
    finally:
        await conn.close()
