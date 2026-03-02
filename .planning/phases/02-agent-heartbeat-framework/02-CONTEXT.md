# Phase 2: Agent Heartbeat Framework - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

A generic async heartbeat loop that Boss and Worker agents subclass. Delivers `BaseAgent`, `AgentConfig`, `Notifier` protocol, and `StdoutNotifier`. No LLM calls — agents are no-op stubs in this phase. Integration tests verify two staggered agents never collide on the SQLite write lock.

</domain>

<decisions>
## Implementation Decisions

### Loop lifecycle
- `start()` is `async def` — returns a coroutine; caller does `await agent.start()` or `asyncio.create_task(agent.start())`
- Production entrypoints use `asyncio.run(Agent(config).start())` — one line, no complexity added
- Stagger offset delays the **first tick only** — then agent runs free on its own `interval ± jitter` cadence
- Hook structure is **linear**: each tick runs `do_peer_reviews()` then `do_own_tasks()` in sequence, both `async def`, both overridable
- Hook registry pattern deferred — can be added in Phase 3/4 as a refactor of `BaseAgent._tick()` without breaking subclasses
- Shutdown uses **both signals**: `asyncio.Event` for graceful self-initiated stop; `CancelledError` for external/emergency cancellation

### Error handling
- Unexpected exceptions in hooks: **log, set `agent_status.status = 'error'` in DB, continue next tick** — loop never dies from a single bad tick
- Tiered handling: LLM billing/auth errors (`anthropic.APIStatusError` subclasses) → set stop event for graceful halt (retrying won't help); all other exceptions → log and continue
- `agent_status.status` transitions: set to `'working'` at **tick start**, `'idle'` at **tick end** — boss can detect crashed agents by stale `working` state
- `CancelledError` is **never caught** — cleanup runs in `try/finally`, then `CancelledError` re-raises

### Local state file
- Location: `runtime/state/<agent-id>.json`
- Fields: minimal — `{last_heartbeat, current_task_id}` only
- Written at **end of tick**, after all DB writes complete — file reflects what actually finished
- Writes are **atomic**: write to `.tmp` sibling file, then `Path.replace()` — Windows-safe, crash-safe
- On startup, if file is missing or corrupt: **log a warning** and treat as fresh start — agent re-checks DB for current task

### Integration test design
- Use **real SQLite in a tmp file** — the only way to surface `OperationalError: database is locked`
- "No collision" assertion = **no exceptions raised** during concurrent runs (no timing assertions — fragile on CI)
- Fast tests via **tiny `AgentConfig.interval_seconds`** (e.g., 0.05s) — consistent with `ge=0.01` constraint in existing spec
- Each agent runs a **fixed tick count** (e.g., 3 ticks) then sets its stop event — deterministic, no sleep-based timeouts

### Claude's Discretion
- Exact jitter implementation (±30s random offset applied to `interval`)
- `AgentConfig` field names and YAML key mapping
- Exact log message format for warning on missing state file
- How `current_task_id` is set in the state file (None when idle)

</decisions>

<specifics>
## Specific Ideas

- LLM credit/auth exhaustion should fail gracefully: the tiered error handler catches it, sets `agent_status.status = 'error'`, then triggers the stop event so the agent exits cleanly and the operator sees the error in `cluster agents status`
- The stop event is the bridge between error handling and graceful shutdown — error handler calls `self._stop_event.set()` rather than raising

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DatabaseManager` (`runtime/database.py`): `open_write()` / `open_read()` with WAL + `busy_timeout=5000ms` already configured — heartbeat writes `agent_status` using `open_write()`
- `AgentStatus` model (`runtime/models.py`): `id`, `agent_role`, `status` (AgentStatusEnum), `last_heartbeat`, `current_task` — maps directly to what the heartbeat loop updates
- `AgentStatusEnum` (`runtime/models.py`): `idle | working | error` — matches the tick start/end transitions decided above
- `_now_iso()` helper (`runtime/models.py`): UTC ISO 8601 timestamp factory — use for `last_heartbeat` in state file

### Established Patterns
- `aiosqlite` async context: connections opened with `open_write()`, used raw, closed explicitly — heartbeat follows the same pattern
- Pydantic v2 with `ConfigDict(use_enum_values=True)`: status fields serialize to plain strings — `AgentConfig` should follow the same convention
- `Path.replace()` for atomic writes: already called out in project memory as the Windows-safe pattern

### Integration Points
- `agent_status` table: heartbeat writes `status`, `last_heartbeat`, `current_task` on every tick
- `activity_log` table: heartbeat appends an entry after each tick (action type TBD by planner)
- Phase 3 (`BossAgent`) and Phase 4 (`WorkerAgent`) both subclass `BaseAgent` — the `async def start()` interface must be stable

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-agent-heartbeat-framework*
*Context gathered: 2026-03-01*
