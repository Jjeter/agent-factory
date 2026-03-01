# Phase 1: Core Runtime (Database + State Machine) - Research

**Researched:** 2026-02-28
**Domain:** Python async SQLite (aiosqlite), Pydantic v2 models, state machine design, pytest async testing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Connection pattern:**
- WAL-native pool: one shared write connection + one dedicated read connection per agent
- Each agent gets its own read connection at startup (no contention on reads)
- WAL mode allows concurrent reads natively — no read locking needed
- Write failures raise immediately with no retry — the heartbeat framework (Phase 2) owns restart/recovery
- No asyncio.Lock needed; stagger system + WAL handle write serialization

**State machine location:**
- Defense in depth: both a dedicated `TaskStateMachine` class AND Pydantic enum validation
- `TaskStateMachine` owns the transition table and applies transitions
- Pydantic validates that `task.status` is always a valid `TaskStatus` enum value
- Invalid transition raises `InvalidTransitionError` (custom typed exception)
  - Message format: `"Cannot transition {from_state} → {to_state}"`
  - Downstream code can `except InvalidTransitionError` specifically
- `rejected` is an **action, not a persistent state**:
  - Rejection immediately transitions task back to `in-progress`
  - The rejection is recorded as a `task_comment` of type `feedback` + increments `escalation_count`
  - `rejected` does NOT appear as a `task.status` value in the enum
- Phase 1 enforces transition validity only — role-based checks (boss-only for `peer_review → review`) added in Phase 3

**Migration runner:**
- Source of truth: single `runtime/schema.sql` file
- Python runner reads and executes the SQL file — no Alembic, no versioning
- CLI: `cluster db up` (idempotent) and `cluster db reset` (hard reset)
- `cluster db up`: uses `CREATE TABLE IF NOT EXISTS` — safe to run on existing DB, no-op if already initialized
- `cluster db reset`: drops all tables + recreates from schema.sql — no confirmation prompt (dev tool only, production safety is Phase 7)
- Both commands live under the `cluster` Click group (already declared in `pyproject.toml`)

**Test strategy:**
- Database backend: in-memory `:memory:` SQLite per test — fully isolated, no temp file cleanup
- State machine tests: parametrized with `@pytest.mark.parametrize` over a `(from_state, to_state, should_succeed)` table — one function covers all valid and invalid transitions
- Test fixtures: minimal factory helpers (`create_goal()`, `create_task()`) called per-test — no shared/session-scoped fixtures to prevent state bleed
- Coverage targets:
  - `runtime/state_machine.py`: **100%** — pure logic, every path testable
  - `runtime/database.py`, `runtime/models.py`: **80%** minimum (existing `--cov-fail-under=80` in pyproject.toml)
- Test file layout mirrors module structure:
  - `tests/test_database.py`
  - `tests/test_models.py`
  - `tests/test_state_machine.py`

### Claude's Discretion
- Exact SQL column types and index design
- Pydantic field validators beyond enum enforcement
- Error message wording beyond the format noted above
- WAL pragma settings (page size, checkpoint threshold)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 1 establishes the persistence and domain-model foundation for the entire agent factory. The stack is locked: aiosqlite 0.22.1 for async SQLite access, Pydantic 2.12.5 for model validation, Click 8.1+ for the migration CLI. All three are already declared in `pyproject.toml` — no new dependencies needed. The research confirms the user's architectural decisions are technically sound and well-aligned with current best practices.

The key design choice — one write connection + one read connection per agent with WAL mode — is the correct pattern for this workload. WAL permits concurrent readers without locking, and since the stagger system serializes writers, a single write connection per agent is all that is needed. aiosqlite 0.22.0+ requires explicit `await db.close()` or context manager usage (breaking change from the old `threading.Thread` inheritance model).

The `TaskStateMachine` class with a flat transition dict is the right implementation approach: pure data lookup (no if/elif chains), easily parametrize-testable, and fully decoupled from the database layer. The Pydantic `str` enum pattern (`class TaskStatus(str, Enum)`) makes serialization to SQLite TEXT columns trivially simple — enum values are already strings.

**Primary recommendation:** Implement `database.py` as an async context manager that sets WAL + busy_timeout + foreign_keys on every connection open. Implement `TaskStateMachine` as a class holding a `dict[TaskStatus, set[TaskStatus]]` transition table. Use `str, Enum` for all status enums to get free TEXT serialization.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | 0.22.1 | Async bridge to sqlite3; non-blocking SQLite access | Standard asyncio SQLite driver; mirrors sqlite3 API; active maintenance (Dec 2025 release) |
| pydantic | 2.12.5 | Data models, validation, serialization | v2 is Python's dominant data validation library; Rust core for speed; required by pyproject.toml |
| click | 8.1+ | CLI command group for `cluster db up/reset` | Already declared; project entry point `cluster` already wired |
| pytest + pytest-asyncio | 8.0+ / 0.24+ | Async test runner | asyncio_mode = "auto" already configured; no decorator boilerplate |
| pytest-cov | 5.0+ | Coverage tracking | `--cov-fail-under=80` already in pyproject.toml |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid (stdlib) | Python 3.12 | Generate PRIMARY KEY TEXT values | All row IDs; use `str(uuid.uuid4())` |
| datetime (stdlib) | Python 3.12 | Timestamps stored as ISO 8601 TEXT | All `_at` columns; use `datetime.utcnow().isoformat()` |
| sqlite3 (stdlib) | Python 3.12 | Underlying driver used by aiosqlite | Never call directly in async code; aiosqlite wraps it |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiosqlite direct | SQLAlchemy async | SQLAlchemy adds ORM abstraction; overkill for single-agent SQLite; more setup complexity |
| aiosqlite direct | aiosqlitepool | Pool adds pooling overhead; not needed — stagger already serializes writers, WAL handles concurrent reads |
| schema.sql + Python runner | Alembic | Alembic versioning is valuable for multi-environment migration; unnecessary for single-cluster dev tool in v0.1 |
| `str, Enum` | plain `Enum` | Plain Enum requires `.value` to get the string; `str, Enum` makes instances directly usable as strings with SQLite |

**Installation:**
```bash
# All already declared in pyproject.toml — install with:
pip install -e ".[dev]"
```

---

## Architecture Patterns

### Recommended Project Structure
```
runtime/
├── __init__.py          # Package marker; exports public API
├── database.py          # DatabaseManager: open_write(), open_read(), init_schema()
├── models.py            # Pydantic models: Goal, Task, TaskComment, TaskReview, AgentStatus, Document, ActivityLog
├── state_machine.py     # TaskStateMachine class + InvalidTransitionError
├── schema.sql           # Canonical schema (7 tables, CREATE TABLE IF NOT EXISTS)
└── cli.py               # Click cluster_cli group; db subgroup with up/reset commands

tests/
├── __init__.py
├── conftest.py          # Shared async fixtures: db_connection(), create_goal(), create_task()
├── test_database.py     # DatabaseManager tests: connection lifecycle, WAL mode, pragma verification
├── test_models.py       # Pydantic model tests: valid construction, invalid enum values, serialization
└── test_state_machine.py # Parametrized transition table tests: all valid + invalid transitions
```

### Pattern 1: DatabaseManager as Async Context Manager

**What:** A class wrapping aiosqlite.connect() that sets WAL, busy_timeout, and foreign_keys on each new connection. Provides separate write and read connection factory methods.

**When to use:** Any time a database connection is needed. Never call `aiosqlite.connect()` directly outside this class.

**Example:**
```python
# Source: aiosqlite docs (https://aiosqlite.omnilib.dev/) + SQLite pragma docs
import aiosqlite
from pathlib import Path

STARTUP_PRAGMAS = """
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;
    PRAGMA foreign_keys = ON;
    PRAGMA busy_timeout = 5000;
"""

class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def open_write(self) -> aiosqlite.Connection:
        """Open a write-capable connection with WAL and timeout configured."""
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        await db.executescript(STARTUP_PRAGMAS)
        return db

    async def open_read(self) -> aiosqlite.Connection:
        """Open a read-only connection (same WAL pragmas apply)."""
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        await db.executescript(STARTUP_PRAGMAS)
        return db

    async def init_schema(self, db: aiosqlite.Connection) -> None:
        """Execute schema.sql against an open connection."""
        schema = (Path(__file__).parent / "schema.sql").read_text()
        await db.executescript(schema)
        await db.commit()
```

**Important:** aiosqlite 0.22.0+ no longer inherits from `threading.Thread`. Always `await db.close()` or use `async with aiosqlite.connect(...) as db:`. Prefer the explicit factory pattern (above) over the context manager for long-lived agent connections that persist across heartbeat cycles.

### Pattern 2: TaskStateMachine with Dict Transition Table

**What:** A class holding the valid-transition map as a plain dict. `apply()` looks up the current state, checks the target is reachable, raises `InvalidTransitionError` if not.

**When to use:** Every task status change must go through `TaskStateMachine.apply()`. Never mutate `task.status` directly.

**Example:**
```python
# Source: project design decision (CONTEXT.md) + Python state machine patterns
from enum import Enum

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    PEER_REVIEW = "peer_review"
    REVIEW = "review"
    APPROVED = "approved"

class InvalidTransitionError(Exception):
    """Raised when a state transition is not permitted."""
    pass

class TaskStateMachine:
    TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.TODO:        {TaskStatus.IN_PROGRESS},
        TaskStatus.IN_PROGRESS: {TaskStatus.PEER_REVIEW},
        TaskStatus.PEER_REVIEW: {TaskStatus.REVIEW, TaskStatus.IN_PROGRESS},  # IN_PROGRESS = rejection
        TaskStatus.REVIEW:      {TaskStatus.APPROVED},
        TaskStatus.APPROVED:    set(),  # terminal
    }

    def apply(self, current: TaskStatus, target: TaskStatus) -> TaskStatus:
        allowed = self.TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition {current} → {target}"
            )
        return target
```

**Key note:** `rejected` is NOT a `TaskStatus` value. Rejection is recorded as a `task_comment` (type `feedback`), `escalation_count` is incremented on the task row, and the state machine transitions `PEER_REVIEW → IN_PROGRESS`. The comment captures the rejection context; the state machine captures the new status.

### Pattern 3: Pydantic Models with `str, Enum` Fields

**What:** Pydantic BaseModel subclasses use `str, Enum` for all status fields, `uuid4` as default_factory for ID, and ISO 8601 strings for timestamps.

**When to use:** All entity models (Goal, Task, TaskComment, etc.).

**Example:**
```python
# Source: Pydantic v2 docs (https://docs.pydantic.dev/latest/concepts/models/)
import uuid
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class Goal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

**Why `str, Enum`:** Enum values are already strings — SQLite stores them in TEXT columns without `.value` unwrapping. Pydantic v2 accepts both the enum member and the raw string `"active"` when constructing models from DB rows, making round-tripping seamless.

### Pattern 4: Parametrized State Machine Tests

**What:** A single test function parametrized over a `(from_state, to_state, should_succeed)` table covers every valid and invalid transition.

**When to use:** `tests/test_state_machine.py` — this is the 100% coverage target.

**Example:**
```python
# Source: pytest docs (https://docs.pytest.org/en/stable/how-to/parametrize.html)
import pytest
from runtime.state_machine import TaskStateMachine, TaskStatus, InvalidTransitionError

machine = TaskStateMachine()

TRANSITION_CASES = [
    # Valid transitions
    (TaskStatus.TODO,        TaskStatus.IN_PROGRESS, True),
    (TaskStatus.IN_PROGRESS, TaskStatus.PEER_REVIEW,  True),
    (TaskStatus.PEER_REVIEW, TaskStatus.REVIEW,        True),
    (TaskStatus.PEER_REVIEW, TaskStatus.IN_PROGRESS,   True),  # rejection path
    (TaskStatus.REVIEW,      TaskStatus.APPROVED,       True),
    # Invalid transitions
    (TaskStatus.TODO,        TaskStatus.APPROVED,        False),
    (TaskStatus.TODO,        TaskStatus.PEER_REVIEW,     False),
    (TaskStatus.APPROVED,    TaskStatus.TODO,             False),
    (TaskStatus.IN_PROGRESS, TaskStatus.APPROVED,         False),
    (TaskStatus.REVIEW,      TaskStatus.IN_PROGRESS,       False),
]

@pytest.mark.parametrize("from_state,to_state,should_succeed", TRANSITION_CASES)
def test_transition(from_state: TaskStatus, to_state: TaskStatus, should_succeed: bool) -> None:
    if should_succeed:
        result = machine.apply(from_state, to_state)
        assert result == to_state
    else:
        with pytest.raises(InvalidTransitionError) as exc_info:
            machine.apply(from_state, to_state)
        assert f"{from_state}" in str(exc_info.value)
        assert f"{to_state}" in str(exc_info.value)
```

**Note:** `asyncio_mode = "auto"` in pyproject.toml — state machine tests are pure sync, no `async def` needed. Only `test_database.py` needs `async def test_*` functions.

### Pattern 5: Migration Runner CLI Structure

**What:** Click nested group. `cluster` is the top-level group (wired in pyproject.toml). `db` is a sub-group. `up` and `reset` are commands under `db`.

**Example:**
```python
# Source: Click docs (https://click.palletsprojects.com/en/stable/commands-and-groups/)
import click
from pathlib import Path

@click.group()
def cluster_cli() -> None:
    """Cluster management CLI."""

@cluster_cli.group()
def db() -> None:
    """Database management commands."""

@db.command()
@click.option("--db-path", default="cluster.db", envvar="CLUSTER_DB_PATH")
def up(db_path: str) -> None:
    """Initialize database schema (idempotent)."""
    import asyncio
    from runtime.database import DatabaseManager
    manager = DatabaseManager(Path(db_path))
    asyncio.run(manager.up())
    click.echo(f"Database initialized: {db_path}")

@db.command()
@click.option("--db-path", default="cluster.db", envvar="CLUSTER_DB_PATH")
def reset(db_path: str) -> None:
    """Drop all tables and recreate schema. DESTRUCTIVE."""
    import asyncio
    from runtime.database import DatabaseManager
    manager = DatabaseManager(Path(db_path))
    asyncio.run(manager.reset())
    click.echo(f"Database reset: {db_path}")
```

### Anti-Patterns to Avoid

- **Calling `aiosqlite.connect()` directly outside DatabaseManager:** Bypasses WAL and busy_timeout setup; any connection opened without pragmas will default to rollback journal + 0ms timeout.
- **Using plain `Enum` instead of `str, Enum`:** Forces `.value` everywhere; breaks direct SQLite TEXT round-tripping; prefer `str, Enum` for all status types.
- **Shared/session-scoped test fixtures with DB state:** Causes test order dependency and false passes. Per-test `:memory:` connections ensure full isolation.
- **Mutating `task.status` directly:** Bypasses `TaskStateMachine` entirely; invalid transitions become possible. Always call `machine.apply()` first, then persist the result.
- **Using `executescript()` without `await db.commit()` after DDL:** `executescript()` implicitly commits, but for clarity and correctness in mixed DDL/DML scenarios, always follow with an explicit commit.
- **Storing Python `datetime` objects in SQLite without `.isoformat()`:** SQLite has no native datetime type; store as ISO 8601 TEXT (`"2026-02-28T14:30:00+00:00"`) for correct string ordering and round-trip parsing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async SQLite access | Custom threading wrapper | aiosqlite 0.22.1 | aiosqlite handles thread-safety, request queue, and event loop integration correctly; rolling this is complex and error-prone |
| Data validation and serialization | Manual dict validation | Pydantic v2 BaseModel | Pydantic handles type coercion, enum validation, JSON serialization, and field defaults; manual validation misses edge cases |
| WAL pragma initialization | Per-query pragma checks | Startup pragma sequence in connection factory | Per-query checks add latency; one-time setup at connection open is the correct pattern |
| UUID generation | Sequential integer IDs | `str(uuid.uuid4())` | TEXT UUIDs are globally unique across clusters; no shared sequence required; SQLite has no auto-increment TEXT |
| Transition validation logic | Custom if/elif chain | Dict-based transition table | Dict lookup is O(1), fully data-driven, trivially testable with parametrize, and easy to extend |

**Key insight:** The project already has all dependencies declared. The only custom code needed is the thin application layer: `DatabaseManager`, `TaskStateMachine`, and Pydantic models. Everything else is stdlib or declared deps.

---

## Common Pitfalls

### Pitfall 1: aiosqlite 0.22 Breaking Change — No More threading.Thread
**What goes wrong:** Code that does `db = await aiosqlite.connect(...)` and then proceeds without `await db.close()` at the end will leak the background helper thread, producing resource warnings and eventually hanging test runners.
**Why it happens:** Before 0.22.0, Connection inherited from threading.Thread; the thread would be cleaned up automatically. Since 0.22.0, the thread is owned separately and must be explicitly stopped.
**How to avoid:** Always use `await db.close()` in a `finally` block, or use `async with aiosqlite.connect(...) as db:`. For long-lived agent connections (not context-managed), store the connection object and close it in the agent teardown path.
**Warning signs:** `ResourceWarning: unclosed database` in test output; test suite hangs after all tests complete.

### Pitfall 2: WAL PRAGMA Persistence vs. Per-Connection Setup
**What goes wrong:** Developer sets `PRAGMA journal_mode = WAL` once, assumes it persists. foreign_keys and busy_timeout are per-connection pragmas and are NOT persisted — they reset to defaults on every new connection.
**Why it happens:** WAL journal mode IS persistent (stored in DB file). `PRAGMA foreign_keys` and `PRAGMA busy_timeout` are NOT persistent — they must be set per-connection.
**How to avoid:** Set all four pragmas (journal_mode, synchronous, foreign_keys, busy_timeout) in the DatabaseManager connection factory for every connection opened, even though journal_mode only needs setting once. The idempotent call costs nothing and is safer.
**Warning signs:** Foreign key constraints pass in isolation tests but fail in integration; SQLITE_BUSY errors with 0ms wait time.

### Pitfall 3: `executescript()` Commits Any Pending Transaction
**What goes wrong:** Calling `await db.executescript(schema_sql)` mid-transaction will silently commit the in-progress transaction before executing the script.
**Why it happens:** `executescript()` issues an implicit `COMMIT` before executing multiple statements. This matches the sqlite3 stdlib behavior.
**How to avoid:** Only call `executescript()` at connection open (before any transactional work) for schema initialization. For all other DML, use `db.execute()` and `await db.commit()` explicitly.
**Warning signs:** Tests that rely on transaction rollback for isolation find their setup changes committed unexpectedly.

### Pitfall 4: Pydantic v2 Enum — Input Must Match Value, Not Name
**What goes wrong:** Pydantic v2 validates enum fields against enum VALUES, not names. If a DB row has `status = "IN_PROGRESS"` (uppercase) and the enum value is `"in-progress"`, validation raises `ValidationError`.
**Why it happens:** SQLite TEXT is case-sensitive. If the schema stores lowercase values but a query returns mixed case, Pydantic rejects it.
**How to avoid:** Schema stores lowercase strings (`DEFAULT 'todo'`, `DEFAULT 'in-progress'`). All Python-side inserts must use `task_status.value` or the `str, Enum` auto-cast. Verify with a round-trip test: insert a row, fetch it, assert it round-trips to a valid model.
**Warning signs:** `ValidationError: Input should be 'todo' or 'in-progress'` when loading rows fetched from DB.

### Pitfall 5: In-Memory SQLite and Schema Per-Test Setup
**What goes wrong:** Shared `:memory:` connections across tests contaminate state. If two async tests share a connection fixture without re-creating the schema, mutations from test A appear in test B.
**Why it happens:** `:memory:` databases are connection-scoped — the DB lives as long as the connection. Session-scoped fixtures keep the same connection alive across tests.
**How to avoid:** Create a new `:memory:` connection per test in a function-scoped fixture. Run `init_schema()` inside each test fixture setup. This ensures full isolation with zero filesystem cleanup.
**Warning signs:** Test pass/fail outcomes depend on execution order; tests that individually pass fail when run as a suite.

### Pitfall 6: Click `asyncio.run()` Inside Commands
**What goes wrong:** Click commands are synchronous. Calling async database methods requires `asyncio.run()` inside the command. On Windows (the project target platform), `asyncio.run()` creates a new event loop correctly, but nested `asyncio.run()` calls (if any) raise `RuntimeError: This event loop is already running`.
**Why it happens:** Click is a sync framework; aiosqlite requires an event loop.
**How to avoid:** Each CLI command that calls async code uses `asyncio.run(coroutine)` at the top level. Never nest `asyncio.run()`. Keep each command's async body a single top-level coroutine.
**Warning signs:** `RuntimeError: This event loop is already running` in CLI tests.

---

## Code Examples

Verified patterns from official sources:

### aiosqlite Connection with WAL Pragmas
```python
# Source: https://aiosqlite.omnilib.dev/ + https://sqlite.org/pragma.html
import aiosqlite
from pathlib import Path

async def open_connection(db_path: Path) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    # WAL is persistent; others are per-connection
    await db.execute("PRAGMA journal_mode = WAL")
    await db.execute("PRAGMA synchronous = NORMAL")
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("PRAGMA busy_timeout = 5000")
    return db
```

### Schema Initialization via executescript
```python
# Source: aiosqlite API docs (https://aiosqlite.omnilib.dev/en/stable/api.html)
async def init_schema(db: aiosqlite.Connection, schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    # executescript implicitly commits — call before any transactional work
    await db.executescript(schema_sql)
```

### Pydantic v2 str Enum Round-Trip
```python
# Source: https://docs.pydantic.dev/2.0/usage/types/enums/
from enum import Enum
from pydantic import BaseModel

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    PEER_REVIEW = "peer_review"
    REVIEW = "review"
    APPROVED = "approved"

class Task(BaseModel):
    status: TaskStatus = TaskStatus.TODO

# Both of these work:
t1 = Task(status=TaskStatus.TODO)
t2 = Task(status="todo")  # raw string accepted
assert t1.status == t2.status  # True
assert isinstance(t1.status, str)  # True — str, Enum
```

### Custom Exception with Message Pattern
```python
# Source: Project CONTEXT.md decision
class InvalidTransitionError(Exception):
    """Raised when a task state transition is not permitted."""

    def __init__(self, from_state: TaskStatus, to_state: TaskStatus) -> None:
        super().__init__(f"Cannot transition {from_state} → {to_state}")
        self.from_state = from_state
        self.to_state = to_state
```

### Async Test with In-Memory DB Fixture
```python
# Source: pytest-asyncio docs (https://pytest-asyncio.readthedocs.io/en/stable/)
# asyncio_mode = "auto" configured in pyproject.toml — no decorator needed
import pytest
import aiosqlite
from pathlib import Path
from runtime.database import DatabaseManager

@pytest.fixture
async def db():
    """Per-test isolated in-memory database with schema initialized."""
    manager = DatabaseManager(Path(":memory:"))
    conn = await manager.open_write()
    await manager.init_schema(conn)
    yield conn
    await conn.close()

async def test_insert_goal(db: aiosqlite.Connection) -> None:
    await db.execute(
        "INSERT INTO goals (id, title, description) VALUES (?, ?, ?)",
        ("test-id-1", "Test Goal", "A test goal")
    )
    await db.commit()
    async with db.execute("SELECT * FROM goals WHERE id = ?", ("test-id-1",)) as cursor:
        row = await cursor.fetchone()
    assert row["title"] == "Test Goal"
```

### Click Nested Group Pattern
```python
# Source: https://click.palletsprojects.com/en/stable/commands-and-groups/
import asyncio
import click
from pathlib import Path

@click.group()
def cluster_cli() -> None:
    """Cluster runtime management."""

@cluster_cli.group()
def db() -> None:
    """Database lifecycle commands."""

@db.command(name="up")
@click.option("--db-path", default="cluster.db", show_default=True)
def db_up(db_path: str) -> None:
    """Initialize the cluster database (idempotent)."""
    from runtime.database import DatabaseManager
    asyncio.run(_db_up(Path(db_path)))

async def _db_up(path: Path) -> None:
    from runtime.database import DatabaseManager
    manager = DatabaseManager(path)
    async with await manager.open_write() as db:
        await manager.init_schema(db)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| aiosqlite.Connection inherits threading.Thread | Connection owns thread internally, explicit close required | aiosqlite 0.22.0 (Dec 2025) | Must always close connections; resource warnings if not |
| Pydantic v1 `.dict()` / `.parse_obj()` | Pydantic v2 `.model_dump()` / `Model.model_validate()` | Pydantic 2.0 (2023) | v1 API removed in v2; use v2 methods |
| `@validator` in Pydantic | `@field_validator` / `@model_validator` | Pydantic 2.0 | Old decorator raises deprecation warning in v2 |
| `class Config:` in Pydantic | `model_config = ConfigDict(...)` | Pydantic 2.0 | `class Config` is deprecated |
| sqlite3 `isolation_level=None` for autocommit | Explicit `await db.commit()` with aiosqlite | — | aiosqlite does not expose `isolation_level` the same way; always commit explicitly |

**Deprecated/outdated:**
- `pydantic.validator`: Replaced by `@field_validator` in v2. Do not use.
- `aiosqlite.Connection` as `threading.Thread`: Gone since 0.22.0. Do not assume it.
- `db.isolation_level = None` pattern from sqlite3: Not applicable to aiosqlite's async model; use explicit commit.

---

## Open Questions

1. **Schema file location — `runtime/schema.sql` vs `db/schema.sql`**
   - What we know: REQUIREMENTS.md shows factory output puts schema at `db/schema.sql` in each cluster. CONTEXT.md says source of truth is `runtime/schema.sql`.
   - What's unclear: Does the migration runner read from `runtime/schema.sql` relative to itself, or from a configurable path?
   - Recommendation: Keep the authoritative schema at `runtime/schema.sql` (alongside the code that uses it). The factory copy step (Phase 5) will copy it to `db/schema.sql` in cluster output. `DatabaseManager.init_schema()` resolves path via `Path(__file__).parent / "schema.sql"`.

2. **WAL checkpoint strategy**
   - What we know: CONTEXT.md defers WAL pragma settings to Claude's discretion. Default WAL checkpoint is automatic at 1000 pages.
   - What's unclear: Whether agents need to trigger explicit checkpoints or rely on SQLite's auto-checkpoint.
   - Recommendation: Use SQLite's default auto-checkpoint (1000 pages) for v0.1. No manual checkpoint needed at this scale. Can be revisited in Phase 7 hardening.

3. **`row_factory = aiosqlite.Row` vs raw tuples for Pydantic model construction**
   - What we know: `aiosqlite.Row` allows column-name access (`row["title"]`). Pydantic `model_validate()` accepts dicts.
   - What's unclear: Whether to `dict(row)` before passing to `Model.model_validate()` or access fields individually.
   - Recommendation: Use `dict(row)` to convert `aiosqlite.Row` to plain dict, then `Model.model_validate(dict(row))`. This is the cleanest and most Pydantic-idiomatic approach.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_state_machine.py -x` |
| Full suite command | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| DB-01 | `DatabaseManager.open_write()` returns a connected aiosqlite.Connection | unit | `pytest tests/test_database.py::test_open_write -x` | ❌ Wave 0 |
| DB-02 | WAL mode verified via `PRAGMA journal_mode` returns `"wal"` | unit | `pytest tests/test_database.py::test_wal_mode -x` | ❌ Wave 0 |
| DB-03 | `busy_timeout` set to 5000ms (query `PRAGMA busy_timeout`) | unit | `pytest tests/test_database.py::test_busy_timeout -x` | ❌ Wave 0 |
| DB-04 | `foreign_keys` ON (query `PRAGMA foreign_keys`) | unit | `pytest tests/test_database.py::test_foreign_keys -x` | ❌ Wave 0 |
| DB-05 | `init_schema()` creates all 7 tables idempotently | unit | `pytest tests/test_database.py::test_init_schema -x` | ❌ Wave 0 |
| DB-06 | All DB writes use parameterized queries (no f-string SQL) | code review | Manual — enforced by code review, no runtime test | manual-only |
| SM-01 | All valid transitions succeed and return the target state | unit | `pytest tests/test_state_machine.py -x -k valid` | ❌ Wave 0 |
| SM-02 | All invalid transitions raise `InvalidTransitionError` | unit | `pytest tests/test_state_machine.py -x -k invalid` | ❌ Wave 0 |
| SM-03 | `InvalidTransitionError` message contains both states | unit | `pytest tests/test_state_machine.py::test_error_message -x` | ❌ Wave 0 |
| SM-04 | `rejected` does not appear as a `TaskStatus` enum value | unit | `pytest tests/test_models.py::test_task_status_values -x` | ❌ Wave 0 |
| MDL-01 | `Goal` model round-trips to/from DB dict correctly | unit | `pytest tests/test_models.py::test_goal_roundtrip -x` | ❌ Wave 0 |
| MDL-02 | `Task` model rejects invalid `status` string | unit | `pytest tests/test_models.py::test_invalid_status -x` | ❌ Wave 0 |
| MDL-03 | All 7 Pydantic models construct without error | unit | `pytest tests/test_models.py -x` | ❌ Wave 0 |
| CLI-01 | `cluster db up` initializes DB and is idempotent (run twice, no error) | integration | `pytest tests/test_database.py::test_db_up_idempotent -x` | ❌ Wave 0 |
| CLI-02 | `cluster db reset` drops and recreates all tables | integration | `pytest tests/test_database.py::test_db_reset -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_state_machine.py -x` (pure sync, runs in < 1 second)
- **Per wave merge:** `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Phase gate:** Full suite green with 100% state_machine.py coverage before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures: `db` (in-memory connection with schema), `create_goal()`, `create_task()`
- [ ] `tests/test_database.py` — covers DB-01 through DB-06, CLI-01, CLI-02
- [ ] `tests/test_models.py` — covers MDL-01 through MDL-03, SM-04
- [ ] `tests/test_state_machine.py` — covers SM-01 through SM-03; parametrized table with all transitions
- [ ] `runtime/__init__.py` — package marker
- Framework install: `pip install -e ".[dev]"` — packages declared but not yet installed (no runtime/ package exists yet)

---

## Sources

### Primary (HIGH confidence)
- aiosqlite official docs (https://aiosqlite.omnilib.dev/) — connection patterns, row_factory, context manager usage
- aiosqlite PyPI (https://pypi.org/project/aiosqlite/) — confirmed version 0.22.1, release Dec 23 2025
- aiosqlite changelog (https://aiosqlite.omnilib.dev/en/stable/changelog.html) — 0.22.0 breaking change: no threading.Thread inheritance; must close explicitly
- Pydantic v2 docs (https://docs.pydantic.dev/latest/concepts/models/) — confirmed version 2.12.5; BaseModel patterns, ConfigDict
- Pydantic v2 enum docs (https://docs.pydantic.dev/2.0/usage/types/enums/) — str Enum validation behavior
- SQLite PRAGMA docs (https://sqlite.org/pragma.html) — busy_timeout, foreign_keys, journal_mode persistence rules
- pytest-asyncio docs (https://pytest-asyncio.readthedocs.io/) — asyncio_mode=auto behavior, async fixtures
- Click docs (https://click.palletsprojects.com/en/stable/commands-and-groups/) — nested group pattern
- Project CONTEXT.md — locked decisions, existing pyproject.toml config

### Secondary (MEDIUM confidence)
- SQLite WAL internals (https://sqlite.org/wal.html) — WAL persistence, checkpoint behavior
- High-performance SQLite pragmas article (https://databaseschool.com/articles/sqlite-recommended-pragmas) — PRAGMA synchronous=NORMAL recommendation for WAL workloads (site redirected, content not directly verified; cross-referenced with sqlite.org)
- SQLite busy_timeout article (https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/) — SQLITE_BUSY error patterns and why 0ms default is problematic

### Tertiary (LOW confidence)
- aiosqlitepool README — connection pool pattern (https://github.com/slaily/aiosqlitepool); confirmed NOT needed for this design (stagger handles write serialization), but documents pool anti-pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified from PyPI and official docs; dependencies already declared in pyproject.toml
- Architecture: HIGH — connection manager + state machine patterns are well-established; verified against official aiosqlite and Pydantic v2 docs
- Pitfalls: HIGH — aiosqlite 0.22.0 breaking change verified from official changelog; pragma persistence rules verified from sqlite.org; Pydantic v2 enum behavior verified from official docs
- Validation architecture: HIGH — pytest-asyncio asyncio_mode=auto already configured; all test patterns match official docs

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable ecosystem; aiosqlite and Pydantic v2 have slow release cadence; SQLite pragma behavior is long-term stable)
