---
phase: "02"
plan: "01"
subsystem: agent-heartbeat-framework
tags: [config, notifier, pydantic, yaml, protocol, structural-typing]
dependency_graph:
  requires: [runtime/models.py, runtime/database.py]
  provides: [runtime/config.py, runtime/notifier.py]
  affects: [runtime/heartbeat.py]
tech_stack:
  added: []
  patterns:
    - "Pydantic BaseModel frozen=True for immutable config"
    - "yaml.safe_load() exclusively for YAML deserialization"
    - "@runtime_checkable Protocol for structural notification interface"
    - "Structural subtyping: StdoutNotifier satisfies Notifier without inheritance"
key_files:
  created:
    - runtime/config.py
    - runtime/notifier.py
  modified: []
decisions:
  - "frozen=True on AgentConfig — immutable after construction, consistent with Phase 1 models"
  - "yaml.safe_load() enforced — never yaml.load() to prevent arbitrary object deserialization"
  - "state_dir as Path field with default Path('runtime/state') — enables test fixture injection via tmp_path"
  - "StdoutNotifier does NOT inherit from Notifier — proves structural subtyping works for external implementors"
  - "@runtime_checkable on Notifier — enables isinstance() checks in tests and at runtime"
metrics:
  duration: "2m 16s"
  completed_date: "2026-03-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 2 Plan 01: Config and Notifier Implementation Summary

**One-liner:** Frozen Pydantic AgentConfig with yaml.safe_load() loader and @runtime_checkable Notifier Protocol with structural StdoutNotifier implementation.

## What Was Built

Two leaf modules that `BaseAgent` (Wave 2) depends on:

1. **`runtime/config.py`** — `AgentConfig` frozen Pydantic model + `load_agent_config()` function.
   - `AgentConfig` is immutable (frozen=True), with validated fields: `agent_id`, `role`, `interval_seconds` (ge=1.0), `stagger_offset_seconds` (ge=0.0), `jitter_seconds` (ge=0.0), `state_dir` (default `Path("runtime/state")`).
   - `load_agent_config()` uses `yaml.safe_load()` exclusively, raises `pydantic.ValidationError` on missing required fields.

2. **`runtime/notifier.py`** — `@runtime_checkable Notifier` Protocol + `StdoutNotifier` implementation.
   - `Notifier` defines three async methods: `notify_review_ready()`, `notify_escalation()`, `notify_cluster_ready()`.
   - `StdoutNotifier` satisfies the Protocol structurally (no inheritance) — external Discord/Slack notifiers can do the same.

## Tests Results

```
pytest tests/test_config.py tests/test_notifier.py -v --no-cov

tests/test_config.py::TestAgentConfigLoad::test_load_agent_config_valid PASSED
tests/test_config.py::TestAgentConfigLoad::test_load_agent_config_invalid PASSED
tests/test_notifier.py::TestNotifierProtocol::test_stdout_notifier_satisfies_protocol PASSED
tests/test_notifier.py::TestStdoutNotifier::test_stdout_notifier_review_ready PASSED
tests/test_notifier.py::TestStdoutNotifier::test_stdout_notifier_escalation PASSED

5 passed in 0.17s
```

Full suite (85 tests, includes Phase 1): 98.07% coverage, all passing.

## Requirements Satisfied

| Req ID | Behavior | Status |
|--------|----------|--------|
| HB-07 | `Notifier` Protocol satisfied by `StdoutNotifier` at runtime | PASSED |
| HB-08 | `StdoutNotifier.notify_review_ready()` prints task_id and task_title | PASSED |
| HB-09 | `StdoutNotifier.notify_escalation()` prints task_id and reason | PASSED |
| HB-10 | `AgentConfig` loads from valid YAML file | PASSED |
| HB-11 | `AgentConfig` raises on missing required fields | PASSED |

## Decisions Made

1. **frozen=True on AgentConfig** — Immutable after construction, consistent with all Phase 1 Pydantic models. Prevents accidental mutation in agent loop.

2. **yaml.safe_load() enforced** — Never `yaml.load()`. Prevents arbitrary Python object deserialization from agent YAML config files (security requirement from RESEARCH anti-patterns).

3. **state_dir as Path field** — Added `state_dir: Path = Field(default=Path("runtime/state"))` to `AgentConfig` to resolve RESEARCH open question 1. Test fixtures pass `tmp_path / "state"`; production YAML omits the field.

4. **StdoutNotifier does NOT inherit from Notifier** — This proves structural subtyping works. Future external implementors (DiscordNotifier, SlackNotifier) can satisfy the Protocol without importing from `notifier.py`.

5. **@runtime_checkable on Notifier** — Enables `isinstance(StdoutNotifier(), Notifier)` at runtime. Required for HB-07 and for runtime type verification in `BaseAgent.__init__`.

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Implement AgentConfig + load_agent_config() | 207f96a |
| 2 | Implement Notifier Protocol + StdoutNotifier | e8198ad |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `runtime/config.py` exists and exports `AgentConfig`, `load_agent_config`
- [x] `runtime/notifier.py` exists and exports `Notifier`, `StdoutNotifier`
- [x] Commit 207f96a exists (Task 1)
- [x] Commit e8198ad exists (Task 2)
- [x] 5 tests GREEN (HB-07 through HB-11)
- [x] `yaml.safe_load()` confirmed — no `yaml.load()` in config.py
- [x] `StdoutNotifier` does NOT inherit from `Notifier` (confirmed in source)
- [x] `AgentConfig.state_dir` field exists with default `Path("runtime/state")`
