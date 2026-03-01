# Phase 1: Core Runtime (Database + State Machine) - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the SQLite persistence layer (WAL mode, 7 tables), Pydantic models for all entities, and the task state machine with enforced valid/invalid transitions. Deliverables: `runtime/database.py`, `runtime/models.py`, `runtime/schema.sql`, a migration runner (`cluster db up` / `cluster db reset`), and full unit tests.

Not included: agents, LLM calls, CLI beyond migration runner, Docker, heartbeat loop.

</domain>

<decisions>
## Implementation Decisions

### Connection pattern
- WAL-native pool: one shared write connection + one dedicated read connection per agent
- Each agent gets its own read connection at startup (no contention on reads)
- WAL mode allows concurrent reads natively — no read locking needed
- Write failures raise immediately with no retry — the heartbeat framework (Phase 2) owns restart/recovery
- No asyncio.Lock needed; stagger system + WAL handle write serialization

### State machine location
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

### Migration runner
- Source of truth: single `runtime/schema.sql` file
- Python runner reads and executes the SQL file — no Alembic, no versioning
- CLI: `cluster db up` (idempotent) and `cluster db reset` (hard reset)
- `cluster db up`: uses `CREATE TABLE IF NOT EXISTS` — safe to run on existing DB, no-op if already initialized
- `cluster db reset`: drops all tables + recreates from schema.sql — no confirmation prompt (dev tool only, production safety is Phase 7)
- Both commands live under the `cluster` Click group (already declared in `pyproject.toml`)

### Test strategy
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

</decisions>

<specifics>
## Specific Ideas

- No specific references — open to standard aiosqlite patterns
- The stagger design (Phase 2) is the primary write-collision prevention mechanism; connection management is a backstop, not the first line of defense

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` already declares `aiosqlite>=0.20.0`, `pydantic>=2.0.0`, `click>=8.1.0` — no new dependencies needed for Phase 1
- `pytest-asyncio` with `asyncio_mode = "auto"` configured — all `async def test_*` functions are auto-wrapped, no `@pytest.mark.asyncio` needed

### Established Patterns
- Entry points: `cluster` CLI group via `runtime.cli:cluster_cli` — `db up` and `db reset` subcommands plug in here
- Python 3.12+ — can use `match` statements for state machine transition table if desired

### Integration Points
- `runtime/` package is the single source of truth for all Phase 2+ agents — everything built here is consumed downstream
- Phase 2 (`heartbeat.py`) will import `database.py` for connection management and `models.py` for entity types
- Phase 3 (`boss.py`) will import `TaskStateMachine` to enforce role-gated transitions

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-core-runtime-database-state-machine*
*Context gathered: 2026-02-28*
