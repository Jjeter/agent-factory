# Phase 2: Agent Heartbeat Framework - Research

**Researched:** 2026-03-01
**Domain:** Python asyncio heartbeat loops, Pydantic v2 config, atomic file I/O, SQLite WAL concurrency
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Loop lifecycle**
- `start()` is `async def` — returns a coroutine; caller does `await agent.start()` or `asyncio.create_task(agent.start())`
- Production entrypoints use `asyncio.run(Agent(config).start())` — one line, no complexity added
- Stagger offset delays the **first tick only** — then agent runs free on its own `interval ± jitter` cadence
- Hook structure is **linear**: each tick runs `do_peer_reviews()` then `do_own_tasks()` in sequence, both `async def`, both overridable
- Hook registry pattern deferred — can be added in Phase 3/4 as a refactor of `BaseAgent._tick()` without breaking subclasses
- Shutdown uses **both signals**: `asyncio.Event` for graceful self-initiated stop; `CancelledError` for external/emergency cancellation

**Error handling**
- Unexpected exceptions in hooks: **log, set `agent_status.status = 'error'` in DB, continue next tick** — loop never dies from a single bad tick
- Tiered handling: LLM billing/auth errors (`anthropic.APIStatusError` subclasses) → set stop event for graceful halt (retrying won't help); all other exceptions → log and continue
- `agent_status.status` transitions: set to `'working'` at **tick start**, `'idle'` at **tick end** — boss can detect crashed agents by stale `working` state
- `CancelledError` is **never caught** — cleanup runs in `try/finally`, then `CancelledError` re-raises

**Local state file**
- Location: `runtime/state/<agent-id>.json`
- Fields: minimal — `{last_heartbeat, current_task_id}` only
- Written at **end of tick**, after all DB writes complete — file reflects what actually finished
- Writes are **atomic**: write to `.tmp` sibling file, then `Path.replace()` — Windows-safe, crash-safe
- On startup, if file is missing or corrupt: **log a warning** and treat as fresh start — agent re-checks DB for current task

**Integration test design**
- Use **real SQLite in a tmp file** — the only way to surface `OperationalError: database is locked`
- "No collision" assertion = **no exceptions raised** during concurrent runs (no timing assertions — fragile on CI)
- Fast tests via **tiny `AgentConfig.interval_seconds`** (e.g., 0.05s) — consistent with `ge=0.01` constraint in existing spec
- Each agent runs a **fixed tick count** (e.g., 3 ticks) then sets its stop event — deterministic, no sleep-based timeouts

### Claude's Discretion
- Exact jitter implementation (±30s random offset applied to `interval`)
- `AgentConfig` field names and YAML key mapping
- Exact log message format for warning on missing state file
- How `current_task_id` is set in the state file (None when idle)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

</user_constraints>

---

## Summary

Phase 2 implements a generic async heartbeat framework in pure Python, using only libraries already declared in `pyproject.toml`. The central class `BaseAgent` wraps an `asyncio.Event`-driven loop that staggered agents share safely via SQLite WAL. No new dependencies are required. The pattern is a well-established Python idiom: a `while not event.is_set()` loop with `asyncio.wait_for` on the sleep, wrapped in `try/finally` for cleanup and re-raising `CancelledError`.

The three deliverables (`heartbeat.py`, `config.py`, `notifier.py`) integrate directly with Phase 1 artifacts: `DatabaseManager.open_write()` for DB access, `AgentStatus` + `AgentStatusEnum` for status tracking, `ActivityLog` for audit entries, and `_now_iso()` for timestamps. The deleted prior implementation failed because it imported non-existent class names (`Database`, `AgentRole`, `AgentState`, `AgentStatusRecord`). This research documents the exact correct names from the live codebase.

The integration test design avoids fragile timing assertions by running each agent for a fixed tick count. Concurrent agents are launched with `asyncio.gather()`, which surfaces any `OperationalError: database is locked` as a test failure — the correct signal for a write-lock collision.

**Primary recommendation:** Implement all three modules in one wave (`config.py` first, `notifier.py` second, `heartbeat.py` third), since `heartbeat.py` imports both others. Tests are written first per TDD workflow.

---

## Standard Stack

### Core (all already in pyproject.toml — zero new installs)

| Library | Version (pinned in pyproject.toml) | Purpose | Why Standard |
|---------|-------------------------------------|---------|--------------|
| `asyncio` | Python 3.12 stdlib | Heartbeat loop, Event, gather, sleep, CancelledError | No dependency cost; asyncio.Event is the canonical graceful-stop primitive |
| `pydantic` | `>=2.0.0` | `AgentConfig` model with Field constraints | Already used in models.py; `ge=0.01` constraint is Field-native |
| `pyyaml` | `>=6.0.0` | Load `agents/*.yaml` config files | Already declared; standard YAML loader for Python |
| `aiosqlite` | `>=0.20.0` | Async DB writes for `agent_status` + `activity_log` | Already used in DatabaseManager; WAL + busy_timeout already configured |
| `pathlib.Path` | Python 3.12 stdlib | Atomic state file write via `.replace()` | Windows-safe atomic rename — documented in project memory |
| `logging` | Python 3.12 stdlib | Structured agent log messages | No external dep; sufficient for Phase 2 no-op stubs |
| `random` | Python 3.12 stdlib | Jitter offset (`random.uniform(-30, 30)`) | Stdlib; no need for numpy/etc. for simple uniform jitter |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `typing.Protocol` | Python 3.12 stdlib | `Notifier` protocol definition | Structural subtyping — no ABC inheritance required |
| `json` | Python 3.12 stdlib | Serialize/deserialize local state file | Simple dict in/out; no external serializer needed |
| `tempfile` / `tmp_path` | pytest fixture | Integration test: real SQLite tmp file | `tmp_path` is a built-in pytest fixture returning a `pathlib.Path` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.Event` for stop | `asyncio.CancelledError` only | Event allows agent-self-stop; CancelledError is external-only. CONTEXT.md requires both. |
| `asyncio.sleep` with wait_for | `asyncio.wait_for(event.wait(), timeout=interval)` | The wait_for pattern lets the stop Event interrupt sleep cleanly — preferred. |
| `random.uniform` for jitter | `secrets.SystemRandom` | `random.uniform` sufficient for timing jitter; secrets is for crypto, not scheduling. |
| `logging` module | `structlog` | structlog adds dependency and complexity; stdlib logging is fine for Phase 2 stubs. |
| `Path.replace()` for atomic write | `os.rename()` | `Path.replace()` is identical behavior but Pythonic — already called out in project memory. |

**Installation:** No new packages required. All dependencies already present.

---

## Architecture Patterns

### Recommended File Structure

```
runtime/
├── config.py          # AgentConfig Pydantic model + load_agent_config()
├── notifier.py        # Notifier Protocol + StdoutNotifier
├── heartbeat.py       # BaseAgent with async start() loop
├── state/             # Created at runtime by BaseAgent (gitignored)
│   └── <agent-id>.json
tests/
├── test_config.py     # Unit tests for AgentConfig + load_agent_config()
├── test_notifier.py   # Unit tests for StdoutNotifier
├── test_heartbeat.py  # Unit + integration tests for BaseAgent
```

### Pattern 1: AgentConfig — Pydantic v2 Model with YAML Loading

**What:** A Pydantic BaseModel with Field constraints loaded from a YAML file via `yaml.safe_load`.
**When to use:** Whenever agent configuration is read from `agents/<role>.yaml`.

```python
# runtime/config.py
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
import yaml


class AgentConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    agent_id: str
    agent_role: str
    db_path: str
    interval_seconds: float = Field(default=600.0, ge=0.01)
    stagger_offset_seconds: float = Field(default=0.0, ge=0.0)


def load_agent_config(path: Path) -> AgentConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AgentConfig.model_validate(raw)
```

Note: `Field(ge=0.01)` is native Pydantic v2 syntax — verified via Context7.
`model_validate(dict)` is the Pydantic v2 API (not v1's `parse_obj`).

### Pattern 2: Notifier Protocol

**What:** `typing.Protocol` for structural subtyping — no ABC or inheritance needed.
**When to use:** `StdoutNotifier` is the Phase 2 implementation; Discord/Slack added later without changing the protocol.

```python
# runtime/notifier.py
from typing import Protocol


class Notifier(Protocol):
    async def notify_review_ready(self, task_id: str, task_title: str) -> None: ...
    async def notify_escalation(self, task_id: str, reason: str) -> None: ...
    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None: ...


class StdoutNotifier:
    async def notify_review_ready(self, task_id: str, task_title: str) -> None:
        print(f"[REVIEW READY] task={task_id} title={task_title!r}")

    async def notify_escalation(self, task_id: str, reason: str) -> None:
        print(f"[ESCALATION] task={task_id} reason={reason!r}")

    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None:
        print(f"[CLUSTER READY] name={cluster_name!r} path={path!r}")
```

### Pattern 3: BaseAgent Heartbeat Loop

**What:** `async def start()` runs stagger delay, then loops `_tick()` with jitter-adjusted sleep until stop event or CancelledError.
**When to use:** All agent types (Boss, Worker) subclass BaseAgent and override `do_peer_reviews()` and `do_own_tasks()`.

```python
# runtime/heartbeat.py  — illustrative skeleton
import asyncio
import json
import logging
import random
from pathlib import Path

from runtime.config import AgentConfig
from runtime.database import DatabaseManager
from runtime.models import AgentStatus, AgentStatusEnum, ActivityLog, _now_iso
from runtime.notifier import Notifier, StdoutNotifier

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).parent / "state"


class BaseAgent:
    def __init__(self, config: AgentConfig, notifier: Notifier | None = None) -> None:
        self._config = config
        self._notifier = notifier or StdoutNotifier()
        self._db = DatabaseManager(Path(config.db_path))
        self._stop_event = asyncio.Event()
        self._state_path = STATE_DIR / f"{config.agent_id}.json"

    async def start(self) -> None:
        """Main entry point. Await this or wrap in asyncio.create_task()."""
        # Stagger: delay first tick only
        if self._config.stagger_offset_seconds > 0:
            await asyncio.sleep(self._config.stagger_offset_seconds)

        try:
            while not self._stop_event.is_set():
                await self._tick()
                # Sleep interval ± jitter, interruptible by stop event
                jitter = random.uniform(-30, 30)
                sleep_secs = max(0.0, self._config.interval_seconds + jitter)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=sleep_secs,
                    )
                except asyncio.TimeoutError:
                    pass  # Normal: sleep elapsed, continue loop
        finally:
            await self._on_shutdown()

    async def _tick(self) -> None:
        """One heartbeat cycle. Sets status working → idle around hooks."""
        await self._set_db_status(AgentStatusEnum.WORKING)
        try:
            await self.do_peer_reviews()
            await self.do_own_tasks()
            await self._set_db_status(AgentStatusEnum.IDLE)
        except Exception as exc:
            logger.exception("Unhandled error in tick for %s", self._config.agent_id)
            await self._set_db_status(AgentStatusEnum.ERROR)
            # If it's an LLM billing/auth error, halt gracefully
            # (anthropic.APIStatusError check added in Phase 4 when LLM calls exist)
        await self._write_state_file()

    async def do_peer_reviews(self) -> None:
        """Override in subclasses. No-op stub in Phase 2."""

    async def do_own_tasks(self) -> None:
        """Override in subclasses. No-op stub in Phase 2."""

    async def _set_db_status(self, status: AgentStatusEnum) -> None:
        db = await self._db.open_write()
        try:
            await db.execute(
                """INSERT INTO agent_status (id, agent_role, status, last_heartbeat)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       status=excluded.status,
                       last_heartbeat=excluded.last_heartbeat""",
                (self._config.agent_id, self._config.agent_role,
                 status.value, _now_iso()),
            )
            await db.commit()
        finally:
            await db.close()

    async def _write_state_file(self) -> None:
        """Atomic write to runtime/state/<agent-id>.json."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state = {"last_heartbeat": _now_iso(), "current_task_id": None}
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(self._state_path)

    async def _on_shutdown(self) -> None:
        await self._set_db_status(AgentStatusEnum.IDLE)
        logger.info("Agent %s shut down", self._config.agent_id)
```

**Key detail:** `asyncio.wait_for(self._stop_event.wait(), timeout=sleep_secs)` catches `asyncio.TimeoutError` (normal sleep completion). `CancelledError` from external cancellation is NOT caught — it propagates through `wait_for` and then through the `while` loop into the `try/finally` which calls `_on_shutdown()`.

### Pattern 4: Atomic State File Write

**What:** Write to `.tmp` then `Path.replace()` — crash-safe, Windows-safe.
**When to use:** Every `_write_state_file()` call. Never write directly to the target path.

```python
# Correct atomic write pattern (Windows-safe)
tmp = self._state_path.with_suffix(".tmp")
tmp.write_text(json.dumps(state), encoding="utf-8")
tmp.replace(self._state_path)  # NOT os.rename(), NOT Path.rename()
```

`Path.replace()` is the Windows-safe method per project memory. `Path.rename()` raises on Windows if destination exists.

### Pattern 5: Integration Test — Two Staggered Agents, No Lock Collision

**What:** `asyncio.gather()` two `BaseAgent.start()` coroutines using a real tmp SQLite file.
**When to use:** The integration test for concurrent heartbeat safety.

```python
# tests/test_heartbeat.py — integration test sketch
import asyncio
import pytest
from pathlib import Path
from runtime.config import AgentConfig
from runtime.database import DatabaseManager
from runtime.heartbeat import BaseAgent


class FixedTickAgent(BaseAgent):
    """Subclass that stops after N ticks — deterministic, no timeouts."""

    def __init__(self, config, ticks: int):
        super().__init__(config)
        self._remaining = ticks

    async def _tick(self):
        await super()._tick()
        self._remaining -= 1
        if self._remaining <= 0:
            self._stop_event.set()


@pytest.mark.asyncio
async def test_two_agents_no_db_collision(tmp_path):
    db_file = tmp_path / "cluster.db"
    mgr = DatabaseManager(db_file)
    await mgr.up()

    cfg1 = AgentConfig(
        agent_id="agent-1", agent_role="worker",
        db_path=str(db_file), interval_seconds=0.05, stagger_offset_seconds=0.0,
    )
    cfg2 = AgentConfig(
        agent_id="agent-2", agent_role="worker",
        db_path=str(db_file), interval_seconds=0.05, stagger_offset_seconds=0.025,
    )

    a1 = FixedTickAgent(cfg1, ticks=3)
    a2 = FixedTickAgent(cfg2, ticks=3)

    # gather raises if either raises — surfaces OperationalError: database is locked
    await asyncio.gather(a1.start(), a2.start())
```

### Anti-Patterns to Avoid

- **Catching `CancelledError`:** Never wrap the main loop body in `except asyncio.CancelledError`. Cleanup belongs in `finally`, not in `except`. The CONTEXT.md is explicit: `CancelledError` must always re-raise.
- **`asyncio.sleep(interval)` as the sole sleep mechanism:** `asyncio.sleep` cannot be interrupted by a stop Event. Use `asyncio.wait_for(event.wait(), timeout=interval)` so graceful stop is immediate.
- **Writing state file before DB commit:** The state file reflects what *actually finished*. Write it after `await db.commit()`, not before.
- **`Path.rename()` on Windows:** Raises `FileExistsError` if destination exists. Always use `Path.replace()`.
- **In-memory SQLite for collision test:** `:memory:` databases are per-connection — no WAL, no shared locking. The integration test MUST use a real file in `tmp_path`.
- **Importing non-existent names:** The deleted implementation imported `Database`, `AgentRole`, `AgentState`, `AgentStatusRecord`. The correct names are `DatabaseManager`, `AgentStatusEnum`, `AgentStatus`. Never import names that don't exist in `runtime/models.py` or `runtime/database.py`.
- **`asyncio.get_event_loop()`:** Deprecated in Python 3.10+. Use `asyncio.run()` at entrypoints; within async context, `asyncio.create_task()` is sufficient.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graceful stop primitive | Custom flag variable | `asyncio.Event` | Thread-safe, awaitable, integrates with `wait_for` |
| Interruptible sleep | `asyncio.sleep` + polling | `asyncio.wait_for(event.wait(), timeout=N)` | Clean interrupt on stop without busy-loop |
| YAML parsing | Custom file reader | `yaml.safe_load()` (pyyaml) | Already in pyproject.toml; handles all YAML edge cases |
| Config validation | Manual type checks | Pydantic `Field(ge=0.01)` | Already in use project-wide; catches bad configs at load time |
| Atomic file write | Non-atomic writes | `write_text` to `.tmp` then `Path.replace()` | Windows-safe, crash-safe — project memory documents this |
| Structural typing | ABC + register | `typing.Protocol` | No inheritance needed; future implementations just match the interface |

**Key insight:** Every problem in this phase has a stdlib or already-declared-dependency solution. Adding new libraries would be premature complexity.

---

## Common Pitfalls

### Pitfall 1: CancelledError Swallowed by Broad Exception Handler

**What goes wrong:** `except Exception` in `_tick()` catches `CancelledError` (which inherits from `BaseException` in Python 3.8+, NOT `Exception`) — actually, this is safe in Python 3.8+. But if someone writes `except BaseException`, CancelledError IS caught and must be explicitly re-raised.

**Why it happens:** Confusion about Python's exception hierarchy. `asyncio.CancelledError` inherits from `BaseException` (not `Exception`) since Python 3.8. `except Exception` does NOT catch it — this is the safe pattern.

**How to avoid:** Use `except Exception` in `_tick()` (not `except BaseException`). The `CancelledError` propagates naturally. Cleanup lives in `try/finally`.

**Warning signs:** If cancellation hangs or the agent doesn't respond to `task.cancel()`, check for `except BaseException` or `except:` (bare except).

### Pitfall 2: asyncio.wait_for Timeout Semantics Changed

**What goes wrong:** In Python 3.11+, `asyncio.wait_for` cancels the inner coroutine and re-raises `asyncio.TimeoutError` (which is now a subclass of `TimeoutError` builtin). In earlier versions it raised `asyncio.TimeoutError` only.

**Why it happens:** Python 3.11 made `asyncio.TimeoutError` an alias for the builtin `TimeoutError`.

**How to avoid:** Catch `asyncio.TimeoutError` (works on all 3.12 — the only target version). The project requires Python 3.12+, so this is consistent.

### Pitfall 3: aiosqlite Connection Left Open on Exception

**What goes wrong:** If `db.execute()` raises and the `finally: await db.close()` is absent, the connection leaks. Under SQLite WAL with `busy_timeout=5000ms`, a leaked write connection eventually causes other agents to time out.

**Why it happens:** The `DatabaseManager` is a connection factory — it does NOT manage connection lifecycle. The caller (BaseAgent) must always close.

**How to avoid:** Always open connections in a `try/finally`:
```python
db = await self._db.open_write()
try:
    # ... use db ...
finally:
    await db.close()
```

Note: `aiosqlite.Connection` supports async context manager (`async with`) but `DatabaseManager.open_write()` returns the raw connection, not a context manager. Use `try/finally` to match the existing pattern in Phase 1.

### Pitfall 4: State Directory Not Created Before First Write

**What goes wrong:** `runtime/state/` does not exist on first run. `Path.write_text()` raises `FileNotFoundError`.

**Why it happens:** The directory is created at runtime, not checked into git.

**How to avoid:** `STATE_DIR.mkdir(parents=True, exist_ok=True)` before every write, or once in `__init__`.

### Pitfall 5: Jitter Causes Negative Sleep Duration

**What goes wrong:** If `interval_seconds` is small (e.g., 0.05s for tests) and jitter is ±30s, `interval + jitter` is always negative. `asyncio.sleep(-1)` raises `ValueError`.

**Why it happens:** Jitter range (±30s) is specified for production (10-minute intervals). Test fixtures use tiny intervals.

**How to avoid:** `sleep_secs = max(0.0, interval + jitter)`. Always clamp to zero.

### Pitfall 6: pytest-asyncio Fixture Scope with asyncio_mode=auto

**What goes wrong:** In `asyncio_mode=auto`, all async fixtures are automatically treated as asyncio fixtures. Mixing `scope="session"` async fixtures with function-scoped event loops causes `ScopeMismatch`.

**Why it happens:** pytest-asyncio creates a new event loop per test function by default. Session-scoped async fixtures conflict.

**How to avoid:** Keep all new test fixtures at function scope (default). The existing `db` fixture in `conftest.py` is already function-scoped — follow that pattern. The `tmp_path` fixture is also function-scoped.

### Pitfall 7: INSERT vs UPSERT for agent_status

**What goes wrong:** On first heartbeat, there is no row for the agent in `agent_status`. A plain `UPDATE` silently does nothing.

**Why it happens:** `agent_status.id` is the PRIMARY KEY (agent_id). The agent must insert on first run and update on subsequent runs.

**How to avoid:** Use `INSERT ... ON CONFLICT(id) DO UPDATE SET ...` (SQLite UPSERT syntax). This handles both first-run and subsequent ticks correctly.

---

## Code Examples

### AgentConfig with YAML Field Mapping

```python
# Source: Pydantic v2 docs (Context7: /pydantic/pydantic)
from pydantic import BaseModel, ConfigDict, Field

class AgentConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    agent_id: str
    agent_role: str
    db_path: str
    interval_seconds: float = Field(default=600.0, ge=0.01)
    stagger_offset_seconds: float = Field(default=0.0, ge=0.0)
```

Corresponding `agents/worker.yaml`:
```yaml
agent_id: worker-1
agent_role: worker
db_path: /data/cluster.db
interval_seconds: 600
stagger_offset_seconds: 150
```

### Graceful Stop with asyncio.Event + wait_for

```python
# Interruptible sleep — stop event wakes the agent immediately
try:
    await asyncio.wait_for(
        self._stop_event.wait(),
        timeout=sleep_secs,
    )
except asyncio.TimeoutError:
    pass  # Normal: sleep expired, continue loop
# CancelledError propagates through wait_for naturally — do NOT catch it here
```

### UPSERT agent_status on Every Tick

```python
# SQLite UPSERT — handles first-run insert and subsequent updates
await db.execute(
    """INSERT INTO agent_status (id, agent_role, status, last_heartbeat)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
           status=excluded.status,
           last_heartbeat=excluded.last_heartbeat,
           current_task=excluded.current_task""",
    (agent_id, agent_role, status_value, _now_iso()),
)
await db.commit()
```

### Atomic State File Write

```python
# Windows-safe atomic write — Path.replace() not Path.rename()
import json
STATE_DIR.mkdir(parents=True, exist_ok=True)
state = {"last_heartbeat": _now_iso(), "current_task_id": None}
tmp = state_path.with_suffix(".tmp")
tmp.write_text(json.dumps(state), encoding="utf-8")
tmp.replace(state_path)  # atomic on Windows and POSIX
```

### Startup State File Load (with Corruption Handling)

```python
def _load_state(self) -> dict:
    try:
        return json.loads(self._state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(
            "State file missing or corrupt for agent %s — treating as fresh start",
            self._config.agent_id,
        )
        return {"last_heartbeat": None, "current_task_id": None}
```

### ActivityLog Write After Tick

```python
# Append to activity_log after each tick
await db.execute(
    "INSERT INTO activity_log (id, agent_id, action, details, created_at) "
    "VALUES (?, ?, ?, ?, ?)",
    (_uuid(), agent_id, "heartbeat", None, _now_iso()),
)
await db.commit()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.CancelledError` inherits `Exception` | Inherits `BaseException` | Python 3.8 | `except Exception` no longer catches it — correct for Phase 2 |
| `asyncio.TimeoutError` is custom class | Alias for builtin `TimeoutError` | Python 3.11 | `except asyncio.TimeoutError` still works in 3.12 |
| Pydantic v1 `parse_obj()` | Pydantic v2 `model_validate()` | Pydantic 2.0 | All project code uses v2 — confirmed in models.py |
| `asyncio.get_event_loop()` | Implicit event loop via `asyncio.run()` | Python 3.10 (deprecated) | Use `asyncio.run()` at entrypoints; no manual loop management |

**Deprecated/outdated:**
- `pydantic.BaseModel.parse_obj()`: Removed in Pydantic v2. Use `model_validate()`.
- `asyncio.get_event_loop()`: Deprecated since 3.10, emits warning in 3.12. Never use in new code.
- `Path.rename()` on Windows: Raises `FileExistsError` if destination exists. Use `Path.replace()`.

---

## Open Questions

1. **Activity log action type for heartbeat**
   - What we know: `activity_log.action` is free-text (no enum constraint in schema). CONTEXT.md says "appends an entry after each tick (action type TBD by planner)."
   - What's unclear: Should Phase 2 use `"heartbeat"` or leave the log write to Phase 3/4 when agents do real work?
   - Recommendation: Write `"heartbeat"` entries in Phase 2. It keeps the audit trail continuous and the action string is not constrained by the schema.

2. **`current_task` field in agent_status UPSERT**
   - What we know: Phase 2 agents are no-op stubs — they have no current task. The field should be `NULL`.
   - What's unclear: Should the UPSERT always write `current_task=NULL` or omit the field entirely?
   - Recommendation: Always write `current_task=NULL` in Phase 2 UPSERT to establish the pattern. Phase 4 Worker agents will update this field.

3. **`runtime/state/` in .gitignore**
   - What we know: State files are runtime-generated and agent-id-specific.
   - What's unclear: Is `.gitignore` managed in this phase?
   - Recommendation: Add `runtime/state/` to `.gitignore` as part of Phase 2 Wave 0 setup. The `.gitignore` file already exists (shown in git status as untracked `??`) — check if it needs this entry.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_heartbeat.py tests/test_config.py tests/test_notifier.py -x` |
| Full suite command | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HB-01 | `AgentConfig` validates `interval_seconds >= 0.01` | unit | `pytest tests/test_config.py::test_interval_ge_constraint -x` | ❌ Wave 0 |
| HB-02 | `load_agent_config()` reads YAML and returns `AgentConfig` | unit | `pytest tests/test_config.py::test_load_agent_config -x` | ❌ Wave 0 |
| HB-03 | `StdoutNotifier` implements `Notifier` protocol | unit | `pytest tests/test_notifier.py::test_stdout_notifier -x` | ❌ Wave 0 |
| HB-04 | `BaseAgent.start()` runs stagger delay before first tick | unit | `pytest tests/test_heartbeat.py::test_stagger_delay -x` | ❌ Wave 0 |
| HB-05 | `agent_status` row is UPSERTED on every tick | unit | `pytest tests/test_heartbeat.py::test_status_upsert -x` | ❌ Wave 0 |
| HB-06 | `agent_status.status` is `working` during tick, `idle` after | unit | `pytest tests/test_heartbeat.py::test_status_transitions -x` | ❌ Wave 0 |
| HB-07 | State file written atomically after every tick | unit | `pytest tests/test_heartbeat.py::test_state_file_written -x` | ❌ Wave 0 |
| HB-08 | Missing/corrupt state file logs warning, uses fresh state | unit | `pytest tests/test_heartbeat.py::test_state_file_corrupt -x` | ❌ Wave 0 |
| HB-09 | `CancelledError` is never caught — propagates through `start()` | unit | `pytest tests/test_heartbeat.py::test_cancelled_error_propagates -x` | ❌ Wave 0 |
| HB-10 | Stop event terminates loop gracefully within one sleep interval | unit | `pytest tests/test_heartbeat.py::test_stop_event_graceful -x` | ❌ Wave 0 |
| HB-11 | Two concurrent agents never raise `OperationalError: database is locked` | integration | `pytest tests/test_heartbeat.py::test_two_agents_no_db_collision -x` | ❌ Wave 0 |
| HB-12 | `do_peer_reviews()` called before `do_own_tasks()` each tick | unit | `pytest tests/test_heartbeat.py::test_hook_order -x` | ❌ Wave 0 |
| HB-13 | Jitter sleep is clamped to >= 0.0 (negative sleep prevented) | unit | `pytest tests/test_heartbeat.py::test_jitter_clamped -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_config.py tests/test_notifier.py tests/test_heartbeat.py -x`
- **Per wave merge:** `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_config.py` — covers HB-01, HB-02 (new file)
- [ ] `tests/test_notifier.py` — covers HB-03 (new file)
- [ ] `tests/test_heartbeat.py` — covers HB-04 through HB-13 (new file)
- [ ] `runtime/state/` added to `.gitignore`
- [ ] Framework already installed — no install step needed

---

## Sources

### Primary (HIGH confidence)

- Context7 `/pydantic/pydantic` — `BaseModel`, `ConfigDict`, `Field(ge=...)`, `model_validate()` API verified
- Context7 `/pytest-dev/pytest-asyncio` — `asyncio_mode="auto"`, fixture scope behavior, async fixture ownership verified
- `C:/Projects/Agent Creation/runtime/models.py` — exact class names: `DatabaseManager`, `AgentStatus`, `AgentStatusEnum`, `_now_iso()`, `_uuid()` verified by direct file read
- `C:/Projects/Agent Creation/runtime/database.py` — `open_write()`, `open_read()`, `init_schema()`, `up()`, `reset()` signatures verified by direct file read
- `C:/Projects/Agent Creation/pyproject.toml` — dependency versions: pydantic>=2.0.0, aiosqlite>=0.20.0, pyyaml>=6.0.0 verified
- `C:/Projects/Agent Creation/tests/conftest.py` — `tmp_path`-equivalent pattern (uses `Path(":memory:")`), function-scope fixture pattern verified
- Python 3.12 stdlib documentation — `asyncio.Event`, `asyncio.wait_for`, `asyncio.CancelledError` (BaseException hierarchy), `Path.replace()`

### Secondary (MEDIUM confidence)

- Project MEMORY.md — `Path.replace()` preference over `Path.rename()` for Windows-safe atomic writes — confirmed in file read of CONTEXT.md (code_context section)
- REQUIREMENTS.md Section 9 — jitter ±30s, busy_timeout 5000ms, Python 3.12+ requirement

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in pyproject.toml and direct code reads
- Architecture: HIGH — patterns derived from locked CONTEXT.md decisions and verified existing codebase patterns
- Pitfalls: HIGH — CancelledError hierarchy and wait_for semantics verified against Python 3.12 stdlib; Windows Path behavior documented in project memory and CONTEXT.md
- Integration test design: HIGH — verified against pytest-asyncio `asyncio_mode=auto` behavior via Context7

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable stdlib + pydantic v2 — 30 days)
