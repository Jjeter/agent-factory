# Phase 2: Agent Heartbeat Framework - Research

**Researched:** 2026-02-28
**Domain:** Python asyncio periodic tasks, SQLite WAL concurrency, typing.Protocol, local state persistence
**Confidence:** HIGH

---

## Summary

Phase 2 builds the generic heartbeat loop that all agents (boss and workers) run on. It is a pure Python asyncio engineering problem with no LLM calls — the goal is a robust `BaseAgent` class whose subclasses only need to override two hooks (`do_peer_reviews()`, `do_own_tasks()`). The heartbeat loop handles timing, stagger, jitter, local state persistence, DB status upsert, and graceful shutdown.

The existing Phase 1 foundation is solid: `Database` (aiosqlite, WAL, async context manager), immutable Pydantic v2 models, `AgentStatusRecord`, and full type coverage. Phase 2 layers on top without modifying Phase 1 code. The only new production dependencies are already in `pyproject.toml` — `pyyaml` for YAML config loading. No new packages are required.

The primary risk is SQLite write-lock collision when two agents run simultaneously. The stagger design (fixed offset + jitter) is the intended mitigation. The stagger ensures agents never write at the same time in normal operation; the 5-second `aiosqlite.connect(timeout=5.0)` already set in `Database.__init__` provides a safety net for coincidental overlap. Integration tests must verify that two agents with correct stagger never collide by monitoring for `OperationalError` (SQLITE_BUSY) during concurrent execution.

**Primary recommendation:** Use the `while True` + `asyncio.sleep()` loop with `CancelledError` propagation for the heartbeat. Do NOT use a third-party scheduler. Keep `BaseAgent` as an abstract class (ABC) and `Notifier` as a `typing.Protocol`. Write local state atomically with write-to-temp + `Path.rename()`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` | stdlib (3.12+) | Event loop, `sleep()`, `create_task()`, `TaskGroup` | Zero dependency; best fit for I/O-bound cooperative scheduling |
| `abc` | stdlib | `ABC`, `abstractmethod` for `BaseAgent` hooks | Enforces subclass contract at import time |
| `typing` | stdlib | `Protocol`, `runtime_checkable` for `Notifier` | Structural subtyping — `StdoutNotifier` needs no inheritance |
| `aiosqlite` | >=0.20.0 | Already used in Phase 1 `Database` | No new dep; WAL timeout already set to 5s |
| `pyyaml` | >=6.0.0 | Load `agents/*.yaml` config at agent startup | Already in `pyproject.toml`; use `yaml.safe_load()` only |
| `pydantic` | >=2.0.0 | Config model for parsed YAML (AgentConfig dataclass) | Validates required fields; consistent with Phase 1 models |
| `pathlib` | stdlib | State file paths, atomic rename pattern | Cleaner than `os.path` |
| `json` | stdlib | Serialize/deserialize local state JSON | No extra dep; human-readable state files |
| `random` | stdlib | `random.uniform(-30, 30)` for jitter | No dep needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tempfile` | stdlib | `NamedTemporaryFile` for atomic state writes | Write-then-rename crash safety |
| `os` | stdlib | `os.fsync()` | Flush before atomic rename |
| `datetime` | stdlib | ISO timestamps in state file and `AgentStatusRecord` | Consistent with Phase 1 |
| `pytest-asyncio` | >=0.24.0 | Integration tests with `asyncio_mode = "auto"` | Already in `pyproject.toml` dev deps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.sleep()` while-loop | `apscheduler`, `aiocron`, `celery` | External schedulers add significant weight and complexity for a simple fixed-interval loop; asyncio sleep is idiomatic and testable |
| `typing.Protocol` for Notifier | `abc.ABC` inheritance | Protocol is structurally typed — `StdoutNotifier` doesn't import from `notifier.py`, matches pluggable design requirement exactly |
| `pydantic` for AgentConfig | `dataclasses` + manual validation | Pydantic v2 validates on construction, gives clear errors, matches Phase 1 pattern |
| Atomic write via `tempfile` | Direct `Path.write_text()` | Direct write is not crash-safe; partial writes leave corrupt state files |

**Installation:** No new packages needed — all are already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended File Structure
```
runtime/
├── heartbeat.py        # BaseAgent ABC with async heartbeat loop
├── notifier.py         # Notifier Protocol + StdoutNotifier
├── config.py           # AgentConfig Pydantic model, load_agent_config()
├── state/              # Local state files (runtime-generated, not committed)
│   └── <agent-id>.json
```

### Pattern 1: BaseAgent ABC with Hook Methods

**What:** Abstract base class with a concrete `run()` coroutine that drives the heartbeat loop. Subclasses override only the domain-specific hooks.

**When to use:** Whenever you need a "template method" pattern — shared loop mechanics, customizable work units.

**Key design decisions for this project:**
- `run()` is the top-level coroutine started via `asyncio.create_task()` or `asyncio.run()`
- Loop sequence per heartbeat: stagger sleep (first cycle only) → jitter sleep → authenticate/upsert DB status → `do_peer_reviews()` → `do_own_tasks()` → log activity → save local state → interval sleep
- Both hook methods are `async def` and return `None`; they receive no arguments (agent accesses `self.db`, `self.agent_id`, etc.)
- `stop()` sets an internal `asyncio.Event` that causes the loop to exit cleanly

```python
# Source: Python docs asyncio-task + project requirements
import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone

class BaseAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        db: Database,
        config: AgentConfig,
        notifier: Notifier,
    ) -> None:
        self.agent_id = agent_id
        self.db = db
        self.config = config
        self.notifier = notifier
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        """Main heartbeat loop. Call via asyncio.create_task() or asyncio.run()."""
        # Stagger: wait for this agent's offset before first heartbeat
        if self.config.stagger_offset_seconds > 0:
            await asyncio.sleep(self.config.stagger_offset_seconds)

        while not self._stop_event.is_set():
            try:
                await self._heartbeat()
            except asyncio.CancelledError:
                raise  # Always propagate — do NOT suppress
            except Exception as exc:
                # Log error, update DB status to 'error', continue loop
                await self._handle_error(exc)

            # Interval sleep with jitter: ±30s random
            jitter = random.uniform(-self.config.jitter_seconds, self.config.jitter_seconds)
            sleep_seconds = max(0.0, self.config.interval_seconds + jitter)
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                raise

    async def _heartbeat(self) -> None:
        """Single heartbeat cycle. Not intended to be overridden."""
        await self._upsert_status("working")
        await self.do_peer_reviews()
        await self.do_own_tasks()
        await self._log_activity()
        await self._save_local_state()
        await self._upsert_status("idle")

    @abstractmethod
    async def do_peer_reviews(self) -> None:
        """Subclasses implement peer review logic here."""
        ...

    @abstractmethod
    async def do_own_tasks(self) -> None:
        """Subclasses implement own-task execution logic here."""
        ...

    def stop(self) -> None:
        """Signal the heartbeat loop to exit after current cycle."""
        self._stop_event.set()
```

### Pattern 2: Notifier as typing.Protocol

**What:** Structural protocol — any class with the right async methods satisfies the type, no inheritance required.

**When to use:** Pluggable interfaces where implementations come from outside the module (future Discord/Slack notifiers from external packages).

```python
# Source: Python typing docs - runtime_checkable Protocol
from typing import Protocol, runtime_checkable

@runtime_checkable
class Notifier(Protocol):
    async def notify_review_ready(self, task_id: str, task_title: str) -> None: ...
    async def notify_escalation(self, task_id: str, reason: str) -> None: ...
    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None: ...


class StdoutNotifier:
    """V1 implementation: prints to stdout. No import from notifier.py needed."""

    async def notify_review_ready(self, task_id: str, task_title: str) -> None:
        print(f"[REVIEW READY] Task {task_id}: {task_title}")

    async def notify_escalation(self, task_id: str, reason: str) -> None:
        print(f"[ESCALATION] Task {task_id}: {reason}")

    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None:
        print(f"[CLUSTER READY] {cluster_name} at {path}")
```

### Pattern 3: AgentConfig from YAML

**What:** Pydantic model validated on load from `agents/<role>.yaml`. Provides type-safe access to `interval_seconds`, `stagger_offset_seconds`, `role`, `agent_id`, `jitter_seconds`.

**When to use:** Every agent startup — reads its own config YAML before constructing `BaseAgent`.

```python
# Source: pyyaml docs (safe_load) + pydantic v2 docs
from pathlib import Path
import yaml
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    agent_id: str
    role: str
    interval_seconds: float = Field(default=600.0, ge=1.0)       # ~10 min default
    stagger_offset_seconds: float = Field(default=0.0, ge=0.0)
    jitter_seconds: float = Field(default=30.0, ge=0.0)           # ±N seconds

def load_agent_config(yaml_path: Path) -> AgentConfig:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return AgentConfig.model_validate(data)
```

### Pattern 4: Atomic Local State File Write

**What:** Write-then-rename ensures state file is always either the old complete version or the new complete version — never a partial write.

**When to use:** Every heartbeat cycle, after completing DB writes, to persist local state.

```python
# Source: iifx.dev atomic write pattern + Python tempfile docs
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

def _write_state_atomic(state_path: Path, state: dict) -> None:
    """Write state dict to JSON atomically via write-then-rename."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=state_path.parent,
        suffix=".tmp",
    ) as tmp:
        tmp_path = Path(tmp.name)
        json.dump(state, tmp, indent=2, default=str)
        tmp.flush()
        os.fsync(tmp.fileno())

    tmp_path.rename(state_path)   # atomic on POSIX and NTFS same-filesystem
```

State file schema (per `runtime/state/<agent-id>.json`):
```json
{
  "agent_id": "researcher-1",
  "last_heartbeat": "2026-02-28T10:00:00+00:00",
  "current_task_id": "task-abc123",
  "heartbeat_count": 42,
  "status": "idle"
}
```

### Pattern 5: Integration Test — Two Staggered Agents

**What:** Run two `BaseAgent` stubs concurrently via `asyncio.gather()` for a bounded number of cycles, then assert no `OperationalError` was raised and state files exist.

**When to use:** Phase 2 integration test requirement — "two agents run staggered heartbeats without DB collision."

```python
# Source: pytest-asyncio docs (asyncio_mode=auto already configured)
import asyncio
import pytest
from runtime.heartbeat import BaseAgent
from runtime.config import AgentConfig
from runtime.notifier import StdoutNotifier
from runtime.database import Database

class StubAgent(BaseAgent):
    async def do_peer_reviews(self) -> None:
        pass   # no-op stub; no LLM calls in Phase 2

    async def do_own_tasks(self) -> None:
        pass

async def run_for_n_cycles(agent: BaseAgent, n: int) -> None:
    """Run agent for exactly n heartbeat cycles then stop."""
    cycles = 0
    orig_heartbeat = agent._heartbeat.__func__

    async def counted(self_inner):
        nonlocal cycles
        await orig_heartbeat(self_inner)
        cycles += 1
        if cycles >= n:
            self_inner.stop()

    import types
    agent._heartbeat = types.MethodType(counted, agent)
    await agent.run()

async def test_two_agents_no_db_collision(tmp_path):
    async with Database(tmp_path / "test.db") as db:
        config_a = AgentConfig(
            agent_id="agent-a", role="researcher",
            interval_seconds=1.0, stagger_offset_seconds=0.0, jitter_seconds=0.0,
        )
        config_b = AgentConfig(
            agent_id="agent-b", role="writer",
            interval_seconds=1.0, stagger_offset_seconds=0.5, jitter_seconds=0.0,
        )
        notifier = StdoutNotifier()
        agent_a = StubAgent("agent-a", db, config_a, notifier)
        agent_b = StubAgent("agent-b", db, config_b, notifier)

        # Run both concurrently; any SQLITE_BUSY raises OperationalError
        await asyncio.gather(
            run_for_n_cycles(agent_a, 3),
            run_for_n_cycles(agent_b, 3),
        )

        # Verify state files written
        assert (tmp_path / "state" / "agent-a.json").exists()
        assert (tmp_path / "state" / "agent-b.json").exists()
```

### Anti-Patterns to Avoid

- **Suppressing `CancelledError`:** If you catch `CancelledError` during cleanup, you MUST re-raise it. Suppressing it breaks `asyncio.TaskGroup` and `asyncio.timeout()` structured concurrency. (Source: Python docs, HIGH confidence)
- **`yaml.load()` without SafeLoader:** Always use `yaml.safe_load()`. The unsafe `yaml.load()` deserializes arbitrary Python objects from YAML tags — a critical security risk for agent YAML configs loaded from the filesystem. (Source: PyYAML docs, HIGH confidence)
- **Direct `Path.write_text()` for state files:** Non-atomic. A crash mid-write leaves a corrupt JSON file; on restart the agent reads invalid state and errors. Use write-then-rename always.
- **Application-level asyncio.Lock around DB calls:** Python-level locks have no effect across Docker container process boundaries. SQLite WAL + stagger design is the correct mechanism. Do not add per-agent asyncio locks.
- **Blocking `time.sleep()` inside the async loop:** Blocks the entire event loop. Always use `await asyncio.sleep()`.
- **Global `asyncio.get_event_loop()` (deprecated):** Use `asyncio.run()` as entrypoint and `asyncio.get_running_loop()` inside coroutines. (Source: Python docs, HIGH confidence)
- **Applying stagger offset on every cycle:** Stagger is a one-time initial delay. Apply it once before the main `while` loop, not inside it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async periodic scheduling | Custom cron-like scheduler | `asyncio.sleep()` while-loop | Third-party schedulers add config complexity, persistence, and failure modes not needed here |
| Protocol checking | Manual duck-type `hasattr` checks | `typing.Protocol` + `@runtime_checkable` | Built-in, type-checker verified, `isinstance()` works at runtime |
| YAML config validation | Manual `dict.get()` chains | `pydantic.BaseModel.model_validate()` | Field presence, type coercion, and error messages handled automatically |
| Atomic file writes | `open().write()` then close | `tempfile.NamedTemporaryFile` + `Path.rename()` | OS-guaranteed atomicity; no partial-write risk |
| SQLite concurrency control | Custom file locks, semaphores | WAL mode + stagger design + 5s timeout (already in `Database`) | WAL allows one writer; stagger eliminates contention; timeout is safety net |

**Key insight:** The SQLite "concurrency problem" is already solved by design. Stagger prevents simultaneous writes. Do not add application-level locks around DB calls — they would only work within a single process, and agents run in separate Docker containers (or separate processes in tests).

---

## Common Pitfalls

### Pitfall 1: CancelledError Swallowed During Cleanup
**What goes wrong:** Agent catches `CancelledError` to do cleanup, but doesn't re-raise. The task never reports cancellation; `asyncio.TaskGroup` hangs waiting for it.
**Why it happens:** `CancelledError` inherits from `BaseException`, not `Exception`. A bare `except Exception` won't catch it — but explicit `except asyncio.CancelledError` without re-raise will suppress it.
**How to avoid:** Always `raise` in the `except asyncio.CancelledError` block after cleanup. Use `try/finally` for cleanup that must always run.
**Warning signs:** Task appears to hang at shutdown; `task.cancelled()` returns `False` after `task.cancel()`.

### Pitfall 2: SQLite BUSY on First Heartbeat Overlap (Thundering Herd)
**What goes wrong:** All agents start simultaneously (e.g., `docker compose up`), all attempt their first DB write at the same moment. WAL allows only one writer; others get `OperationalError: database is locked`.
**Why it happens:** Without stagger, first-cycle DB writes are synchronized to container start time.
**How to avoid:** Apply `stagger_offset_seconds` sleep BEFORE the first heartbeat (not inside the loop). The 5-second `timeout` in `aiosqlite.connect(timeout=5.0)` (Phase 1) means SQLite retries for 5 seconds before raising — covers coincidental overlaps in production. In tests, use very short intervals with proportionally short offsets and zero jitter.
**Warning signs:** `aiosqlite.OperationalError: database is locked` in integration tests when stagger is missing or zero for all agents.

### Pitfall 3: Local State Directory Not Created
**What goes wrong:** `runtime/state/` directory doesn't exist at startup. `NamedTemporaryFile(dir=...)` raises `FileNotFoundError`.
**Why it happens:** State directory is runtime-generated, not committed to git.
**How to avoid:** Call `state_path.parent.mkdir(parents=True, exist_ok=True)` inside `_write_state_atomic()` before every write. Or create it once in `BaseAgent.__init__`.
**Warning signs:** `FileNotFoundError` on first heartbeat state save.

### Pitfall 4: Negative Sleep Duration from Jitter
**What goes wrong:** `interval_seconds + jitter` goes negative when `interval_seconds` is small (e.g., 1s) and jitter draws -30s. `asyncio.sleep(negative)` raises `ValueError` in Python 3.13+.
**Why it happens:** `random.uniform(-30, 30)` can exceed the interval in magnitude.
**How to avoid:** `sleep_seconds = max(0.0, interval_seconds + jitter)`. In tests, set `jitter_seconds=0.0` in `AgentConfig` to eliminate non-determinism entirely.
**Warning signs:** `ValueError: sleep length must be non-negative` in tests using short intervals.

### Pitfall 5: yaml.load() Without SafeLoader
**What goes wrong:** Config loading uses `yaml.load()` without specifying a Loader, which enables deserialization of arbitrary Python objects embedded in YAML tags. An accidentally crafted or malicious YAML file in `agents/*.yaml` could trigger unintended object construction.
**Why it happens:** `yaml.load()` without a Loader defaults to the full Loader in older PyYAML versions and emits a `YAMLLoadWarning` in newer ones.
**How to avoid:** Always `yaml.safe_load()`. Never `yaml.load()` without `Loader=yaml.SafeLoader`.
**Warning signs:** PyYAML emits a `YAMLLoadWarning` at runtime if `yaml.load()` is called without a Loader.

### Pitfall 6: Test Heartbeat Interval Too Long
**What goes wrong:** Integration test uses production intervals (600s). Test hangs for 10 minutes or times out.
**Why it happens:** No test-specific config override.
**How to avoid:** `AgentConfig` exposes `interval_seconds`, `stagger_offset_seconds`, `jitter_seconds` as constructor parameters with defaults. Test fixtures inject fast configs: `interval_seconds=0.1`, `jitter_seconds=0.0`, `stagger_offset_seconds=0.0` (or `0.05` for the second agent).
**Warning signs:** Test suite takes O(minutes) to complete; CI timeouts.

---

## Code Examples

Verified patterns from official sources and Phase 1 codebase:

### Graceful Cancellation in Periodic Loop
```python
# Source: Python docs https://docs.python.org/3/library/asyncio-task.html
async def run(self) -> None:
    while not self._stop_event.is_set():
        try:
            await self._heartbeat()
        except asyncio.CancelledError:
            raise  # ALWAYS propagate
        except Exception as exc:
            await self._handle_error(exc)

        try:
            await asyncio.sleep(self._sleep_duration())
        except asyncio.CancelledError:
            raise  # Also propagate here
```

### Upserting Agent Status (uses Phase 1 Database API)
```python
# Uses existing Database.upsert_agent_status() from runtime/database.py
from runtime.models import AgentStatusRecord, AgentRole, AgentState
from datetime import datetime, timezone

async def _upsert_status(self, state: str) -> None:
    record = AgentStatusRecord(
        id=self.agent_id,
        agent_role=AgentRole(self.config.role),
        status=AgentState(state),
        last_heartbeat=datetime.now(timezone.utc),
        current_task=self._current_task_id,
    )
    await self.db.upsert_agent_status(record)
```

### Reading Local State on Restart
```python
# Allows agent to resume awareness of prior state after crash
def _load_local_state(self) -> dict:
    if self._state_path.exists():
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}   # corrupt/missing state — start fresh
    return {}
```

### Two Concurrent Agents with asyncio.gather + timeout
```python
# Source: Python docs create_task + asyncio.timeout (Python 3.11+)
async def test_staggered_agents_complete(tmp_path):
    async with Database(tmp_path / "cluster.db") as db:
        agent_a = StubAgent(...)
        agent_b = StubAgent(...)
        try:
            async with asyncio.timeout(5.0):   # Python 3.11+
                await asyncio.gather(
                    run_for_n_cycles(agent_a, 3),
                    run_for_n_cycles(agent_b, 3),
                )
        except TimeoutError:
            pytest.fail("Agents did not complete within timeout")
```

### Loading AgentConfig from YAML
```python
# Source: PyYAML docs (safe_load only)
from pathlib import Path
import yaml
from runtime.config import AgentConfig

def load_agent_config(yaml_path: Path) -> AgentConfig:
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return AgentConfig.model_validate(raw)
```

### Checking Notifier Protocol Compliance at Runtime
```python
# Source: Python typing docs - @runtime_checkable
from runtime.notifier import Notifier, StdoutNotifier

def test_stdout_notifier_satisfies_protocol():
    notifier = StdoutNotifier()
    assert isinstance(notifier, Notifier)  # works because @runtime_checkable
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@asyncio.coroutine` + `yield from` | `async def` + `await` | Python 3.5 / removed 3.11 | Use `async def` only; no migration needed |
| `asyncio.get_event_loop()` as entry | `asyncio.run()` | Deprecated 3.10, recommended 3.7+ | Always use `asyncio.run()` as top-level entry |
| `asyncio.gather()` for structured concurrency | `asyncio.TaskGroup` (Python 3.11+) | Python 3.11 | `TaskGroup` preferred for production; `gather()` still valid in test patterns |
| `asyncio.timeout()` standalone | `asyncio.timeout()` as async context manager | Python 3.11 | Use `async with asyncio.timeout(N)` in tests |
| `yaml.load()` without Loader | `yaml.safe_load()` | PyYAML 5.1 (2019) | Always `yaml.safe_load()` — `yaml.load()` emits warning without Loader |

**Deprecated/outdated:**
- `asyncio.get_event_loop()`: Deprecated as entry point in 3.10. Use `asyncio.get_running_loop()` inside coroutines only.
- Generator-based coroutines (`yield from`): Removed in Python 3.11. Not relevant to this project.
- `yaml.load()` without Loader: Emits `YAMLLoadWarning` since PyYAML 5.1. Never use without `Loader=yaml.SafeLoader`.

---

## Open Questions

1. **State file location: relative or configurable?**
   - What we know: Spec says `runtime/state/<agent-id>.json`. In Docker, this is inside the container filesystem.
   - What's unclear: Whether state dir path should be configurable (via `AgentConfig` or env var) or always relative to the `runtime/` package.
   - Recommendation: Add `state_dir: Path = Path("runtime/state")` to `AgentConfig`. Test fixtures pass `tmp_path / "state"`. Production YAML omits it (uses default).

2. **Should `BaseAgent` own the `Database` instance or receive it?**
   - What we know: Phase 2 spec shows agents share one DB file per cluster. In tests, using `async with Database(...) as db` and passing `db` into both agents is cleaner and matches Phase 1 patterns.
   - Recommendation: Inject the `Database` instance (constructor injection). The entrypoint manages DB lifecycle. Do not open DB connections inside `BaseAgent`.

3. **Should `do_peer_reviews()` and `do_own_tasks()` return anything?**
   - What we know: Phase 2 stubs are no-ops. Phase 3/4 implementations will do real work.
   - Recommendation: Return `None` in Phase 2. If Phase 3/4 needs structured results (e.g., task count for logging), add typed return then. Do not over-engineer the interface now.

4. **Jitter in integration tests — configurable or disabled by convention?**
   - Recommendation: Make jitter configurable via `AgentConfig.jitter_seconds: float = 30.0`. Set to `0.0` in test fixtures. Avoids non-deterministic test timing and `max(0.0, ...)` edge cases.

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` (`asyncio_mode = "auto"` already set) |
| Quick run command | `pytest tests/test_heartbeat.py tests/test_notifier.py tests/test_config.py -x` |
| Full suite command | `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HB-01 | `BaseAgent` subclass can override `do_peer_reviews()` | unit | `pytest tests/test_heartbeat.py::test_subclass_overrides_hooks -x` | ❌ Wave 0 |
| HB-02 | `BaseAgent` subclass can override `do_own_tasks()` | unit | `pytest tests/test_heartbeat.py::test_subclass_overrides_hooks -x` | ❌ Wave 0 |
| HB-03 | Local state file updated after every heartbeat | unit | `pytest tests/test_heartbeat.py::test_state_file_written_per_cycle -x` | ❌ Wave 0 |
| HB-04 | Heartbeat jitter applied to sleep duration | unit | `pytest tests/test_heartbeat.py::test_jitter_applied -x` | ❌ Wave 0 |
| HB-05 | Stagger offset delays first heartbeat only | unit | `pytest tests/test_heartbeat.py::test_stagger_offset_first_cycle_only -x` | ❌ Wave 0 |
| HB-06 | Two agents running simultaneously never hold write lock | integration | `pytest tests/test_heartbeat.py::test_two_agents_no_db_collision -x` | ❌ Wave 0 |
| HB-07 | `Notifier` Protocol satisfied by `StdoutNotifier` at runtime | unit | `pytest tests/test_notifier.py::test_stdout_notifier_satisfies_protocol -x` | ❌ Wave 0 |
| HB-08 | `StdoutNotifier.notify_review_ready()` prints correct output | unit | `pytest tests/test_notifier.py::test_stdout_notifier_review_ready -x` | ❌ Wave 0 |
| HB-09 | `StdoutNotifier.notify_escalation()` prints correct output | unit | `pytest tests/test_notifier.py::test_stdout_notifier_escalation -x` | ❌ Wave 0 |
| HB-10 | `AgentConfig` loads from valid YAML file | unit | `pytest tests/test_config.py::test_load_agent_config_valid -x` | ❌ Wave 0 |
| HB-11 | `AgentConfig` raises on missing required fields | unit | `pytest tests/test_config.py::test_load_agent_config_invalid -x` | ❌ Wave 0 |
| HB-12 | DB `agent_status` row upserted on each heartbeat | integration | `pytest tests/test_heartbeat.py::test_agent_status_upserted -x` | ❌ Wave 0 |
| HB-13 | `BaseAgent.stop()` causes clean loop exit without exception | unit | `pytest tests/test_heartbeat.py::test_stop_exits_cleanly -x` | ❌ Wave 0 |
| HB-14 | State file atomic write — rename-based, no partial writes | unit | `pytest tests/test_heartbeat.py::test_state_file_atomic_write -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_heartbeat.py tests/test_notifier.py tests/test_config.py -x`
- **Per wave merge:** `pytest --cov=runtime --cov-report=term-missing --cov-fail-under=80`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_heartbeat.py` — covers HB-01 through HB-06, HB-12 through HB-14
- [ ] `tests/test_notifier.py` — covers HB-07, HB-08, HB-09
- [ ] `tests/test_config.py` — covers HB-10, HB-11
- [ ] `tests/conftest.py` — shared fixtures: `tmp_db` (async Database in tmp_path), `fast_config` (interval=0.1s, jitter=0.0, stagger=0.0), `stub_agent`

No framework install needed — pytest + pytest-asyncio already in `pyproject.toml` dev deps.

---

## Sources

### Primary (HIGH confidence)
- Python stdlib docs (asyncio-task, 3.12+) — `asyncio.sleep()`, `CancelledError` semantics, `create_task()`, `TaskGroup`, `asyncio.timeout()`; fetched from `docs.python.org`
- `https://sqlite.org/wal.html` — WAL mode concurrency: one writer at a time, SQLITE_BUSY behavior, caller-managed retry responsibility
- `/python/typing` (Context7) — `Protocol`, `@runtime_checkable`, structural subtyping patterns
- `/omnilib/aiosqlite` (Context7) — `aiosqlite.connect(timeout=...)`, `row_factory`, async context manager
- `/pytest-dev/pytest-asyncio` (Context7) — `asyncio_mode = "auto"`, fixture patterns, async test structure
- Phase 1 source code (`runtime/database.py`, `runtime/models.py`) — confirmed `Database` API surface, `AgentStatusRecord`, `upsert_agent_status()`
- `pyproject.toml` — confirmed existing deps: `pyyaml>=6.0.0`, `pydantic>=2.0.0`, `pytest-asyncio>=0.24.0`

### Secondary (MEDIUM confidence)
- `https://pyyaml.org/wiki/PyYAMLDocumentation` — `yaml.safe_load()` API, file loading pattern, security warning for `yaml.load()` without SafeLoader
- `https://iifx.dev/en/articles/460341744/...` — atomic write via `tempfile.NamedTemporaryFile` + `Path.rename()`; cross-verified against stdlib `pathlib` and `tempfile` docs
- `https://www.johal.in/aiosqlite-wal-mode-python-trio-db-locks-8/` — WAL lock types (SHARED/RESERVED/PENDING/EXCLUSIVE); cross-verified with sqlite.org

### Tertiary (LOW confidence)
- None — all critical claims verified against official sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in `pyproject.toml`; APIs verified via Context7 and official docs
- Architecture: HIGH — asyncio while-loop pattern is idiomatic Python; Protocol pattern verified; atomic write pattern verified against stdlib docs
- Pitfalls: HIGH — CancelledError behavior from official Python docs; SQLITE_BUSY from sqlite.org; others from first-principles analysis of the stagger design

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (asyncio stdlib + SQLite WAL are extremely stable; PyYAML and aiosqlite APIs are stable; only pytest-asyncio may see minor releases)
