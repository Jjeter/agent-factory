---
phase: 02-agent-heartbeat-framework
plan: "01"
subsystem: agent-config
tags: [pydantic, yaml, protocol, typing, asyncio]

requires:
  - phase: 01-core-runtime-database-state-machine
    provides: Pydantic v2 model patterns, pyproject.toml with pyyaml dependency

provides:
  - AgentConfig Pydantic v2 model (role, interval_seconds, stagger_offset_seconds, jitter_seconds, state_dir)
  - load_agent_config() YAML loader using yaml.safe_load + model_validate
  - Notifier typing.Protocol (runtime_checkable) with notify_review_ready/notify_escalation/notify_cluster_ready
  - StdoutNotifier implementation satisfying Notifier structurally (no inheritance)

affects:
  - 02-02-heartbeat (BaseAgent imports AgentConfig and Notifier/StdoutNotifier)

tech-stack:
  added: []
  patterns:
    - "Pydantic v2 model with ConfigDict(use_enum_values=True) following models.py convention"
    - "runtime_checkable Protocol for structural typing without inheritance"
    - "yaml.safe_load exclusively — never yaml.load"
    - "No try/except in load_agent_config — let errors propagate to callers"

key-files:
  created:
    - runtime/config.py
    - runtime/notifier.py
  modified:
    - tests/test_config.py
    - tests/test_notifier.py

key-decisions:
  - "AgentConfig uses role (not agent_role) to match heartbeat test expectations and original design"
  - "AgentConfig includes jitter_seconds and state_dir fields required by BaseAgent in Wave 2"
  - "No db_path in AgentConfig — BaseAgent receives db via constructor injection, not config"
  - "StdoutNotifier satisfies Notifier Protocol structurally — no class inheritance"
  - "Notifier decorated with @runtime_checkable so isinstance() checks work at runtime"

patterns-established:
  - "Protocol: @runtime_checkable on Notifier enables isinstance(obj, Notifier) checks"
  - "Config: frozen=False (mutable) consistent with models.py — no frozen=True"

requirements-completed: [HB-01, HB-02, HB-03]

duration: 4min
completed: 2026-03-02
---

# Phase 2 Plan 01: Config + Notifier Summary

**AgentConfig Pydantic v2 model with ge=0.01 interval constraint and runtime_checkable Notifier Protocol with StdoutNotifier implementation for Wave 1 heartbeat dependencies**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-02T05:32:35Z
- **Completed:** 2026-03-02T05:35:48Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `runtime/config.py`: AgentConfig Pydantic model with validated interval_seconds (ge=0.01), stagger_offset_seconds, jitter_seconds, state_dir fields and load_agent_config() YAML loader
- `runtime/notifier.py`: Notifier runtime_checkable Protocol and StdoutNotifier with 3 async methods printing formatted output
- Wave 1 tests: 3 PASSED (test_config.py: 2, test_notifier.py: 1)
- Heartbeat tests: 10 SKIPPED cleanly (Wave 2 not yet implemented)
- Phase 1 suite: 40 PASSED unaffected

## Task Commits

1. **Task 1: Implement runtime/config.py** - `162fd2d` (feat)
2. **Task 2: Implement runtime/notifier.py** - `2bf052c` (feat)
3. **Task 3: Run combined test pass / align config fields** - `83691af` (fix)

## Files Created/Modified

- `runtime/config.py` - AgentConfig model + load_agent_config() YAML loader
- `runtime/notifier.py` - Notifier Protocol + StdoutNotifier implementation
- `tests/test_config.py` - Restored and corrected field names (role not agent_role)
- `tests/test_notifier.py` - Restored from git, 1 test covering all 3 async methods

## Decisions Made

- AgentConfig uses `role` (not `agent_role`) to match heartbeat test expectations from the original design intent; the PLAN.md interface spec had the wrong field names
- `db_path` omitted from AgentConfig — BaseAgent receives DatabaseManager via constructor injection, not from config file
- `state_dir: Path = Field(default=Path("runtime/state"))` added so BaseAgent knows where to write local state files
- `jitter_seconds: float = Field(default=30.0, ge=0.0)` added for heartbeat sleep variance
- StdoutNotifier does NOT inherit from Notifier — pure structural typing via Protocol
- `@runtime_checkable` on Notifier enables isinstance() checks in tests and BaseAgent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AgentConfig field names mismatched between plan spec and heartbeat tests**
- **Found during:** Task 3 (combined test pass)
- **Issue:** The PLAN.md INTERFACES section specified `agent_role` and `db_path` but the committed test_heartbeat.py (which defines Wave 2 contracts) uses `role`, `jitter_seconds`, and `state_dir`. Using the plan spec fields would break Wave 2 implementation.
- **Fix:** Updated AgentConfig to use `role`, added `jitter_seconds` and `state_dir`, removed `db_path`. Updated test_config.py stub to use correct field names.
- **Files modified:** `runtime/config.py`, `tests/test_config.py`
- **Verification:** 3 Wave 1 tests PASSED, 10 heartbeat tests SKIPPED cleanly, 40 Phase 1 tests GREEN
- **Committed in:** `83691af` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan's interface spec vs authoritative test file)
**Impact on plan:** Necessary correction — plan spec was inconsistent with committed test files. No scope creep. All tests pass.

## Issues Encountered

- The PLAN.md interface section described different field names than what the committed test_heartbeat.py used. The test file is authoritative (it was written alongside the original config.py in commit bdce9e1). Fixed via Rule 1 auto-fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `runtime/config.py` exports `AgentConfig` and `load_agent_config` — ready for BaseAgent import
- `runtime/notifier.py` exports `Notifier` and `StdoutNotifier` — ready for BaseAgent constructor
- Wave 2 (Plan 02-02) can proceed: implement `runtime/heartbeat.py` with BaseAgent ABC

---
*Phase: 02-agent-heartbeat-framework*
*Completed: 2026-03-02*
