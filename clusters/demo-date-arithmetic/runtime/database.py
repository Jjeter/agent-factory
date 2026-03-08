"""SQLite database connection manager with WAL mode and per-connection pragma setup."""

import aiosqlite
from pathlib import Path

STARTUP_PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
]


class DatabaseManager:
    """Async SQLite connection factory with WAL mode and per-connection pragma setup.

    This class is a connection factory only — it does not implement insert/update/delete
    methods. Higher-level agent classes use the raw aiosqlite.Connection to execute SQL.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _apply_pragmas(self, db: aiosqlite.Connection) -> None:
        """Apply all startup pragmas to an open connection.

        Uses individual execute() calls (not executescript) to avoid implicit COMMIT
        during normal connection setup.
        """
        for pragma in STARTUP_PRAGMAS:
            await db.execute(pragma)

    async def open_write(self) -> aiosqlite.Connection:
        """Open a connection with full pragma setup for writes.

        Returns:
            An open aiosqlite.Connection with WAL, synchronous=NORMAL,
            foreign_keys=ON, and busy_timeout=5000 applied.
        """
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        await self._apply_pragmas(db)
        return db

    async def open_read(self) -> aiosqlite.Connection:
        """Open a connection with full pragma setup for reads.

        Returns:
            An open aiosqlite.Connection with WAL, synchronous=NORMAL,
            foreign_keys=ON, and busy_timeout=5000 applied.
        """
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        await self._apply_pragmas(db)
        return db

    async def init_schema(self, db: aiosqlite.Connection) -> None:
        """Create all tables from schema.sql (idempotent — uses IF NOT EXISTS).

        Reads schema.sql from the same directory as this module file.
        Uses executescript which issues an implicit COMMIT before executing;
        safe here because this is called on a fresh connection before any transactions.

        Args:
            db: An open aiosqlite.Connection to initialize.
        """
        schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
        await db.executescript(schema)
        # executescript implicitly commits; explicit commit for clarity
        await db.commit()

    async def up(self) -> None:
        """Initialize schema (idempotent). Used by CLI 'cluster db up'.

        Opens its own connection, runs init_schema, applies any additive
        ALTER TABLE migrations, then closes the connection. Safe to call
        multiple times — the schema DDL uses IF NOT EXISTS and the ALTER TABLE
        migrations silently ignore duplicate-column errors.
        """
        db = await self.open_write()
        try:
            await self.init_schema(db)
            # Add assigned_role column if not already present (idempotent migration)
            try:
                await db.execute("ALTER TABLE tasks ADD COLUMN assigned_role TEXT")
                await db.commit()
            except Exception:
                pass  # Column already exists — SQLite raises OperationalError on duplicate column
        finally:
            await db.close()

    async def reset(self) -> None:
        """Drop all tables and recreate from schema.sql. DESTRUCTIVE.

        Drops tables in reverse dependency order to respect FK constraints,
        then recreates them via init_schema. Used by CLI 'cluster db reset'.
        """
        db = await self.open_write()
        try:
            await db.executescript("""
                DROP TABLE IF EXISTS activity_log;
                DROP TABLE IF EXISTS documents;
                DROP TABLE IF EXISTS task_reviews;
                DROP TABLE IF EXISTS task_comments;
                DROP TABLE IF EXISTS agent_status;
                DROP TABLE IF EXISTS tasks;
                DROP TABLE IF EXISTS goals;
            """)
            await self.init_schema(db)
        finally:
            await db.close()
