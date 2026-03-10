# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-03-10

### Added

- **Factory cluster**: `agent-factory create "<goal>"` generates a fully self-contained AI agent
  cluster artifact (docker-compose.yml, config YAML, runtime copy, seeded database, launch.sh)
  from a natural-language goal description.

- **Boss/worker heartbeat loop**: Generic async `BaseAgent` with configurable interval, jitter,
  and stagger offsets. `BossAgent` coordinates task lifecycle: decomposes goals into tasks,
  promotes tasks through peer review, escalates stuck tasks, detects AWOL agents, and fills
  gaps when no work is in flight. `WorkerAgent` executes tasks with role-based system prompts,
  submits outputs for peer review, and performs substantive peer reviews.

- **Task state machine**: Strict five-state machine (todo -> in-progress -> peer_review -> review
  -> approved) with typed `InvalidTransitionError`. Only the boss may promote to review; only the
  user may approve.

- **Model tier escalation**: Tasks escalate from haiku -> sonnet -> opus automatically after
  repeated peer review rejections.

- **Demo cluster**: Pre-built `clusters/demo-date-arithmetic/` artifact demonstrating a
  date arithmetic Python utility library cluster, ready to run with `./launch.sh`.

- **CLI**: `agent-factory` commands (create, list, status, approve, logs, demo) and
  `cluster` commands (goal set, tasks list, agents status, approve, logs).

- **Security hardening**: Tool allowlist enforcement (WorkerAgent rejects disallowed LLM tool
  calls), cross-cluster database isolation (path-based SQLite), AWOL agent detection with
  `activity_log` entries, and crash recovery (agent resumes prior in-progress task on restart).

- **CI**: GitHub Actions smoke test (Docker Compose cluster startup), secrets scan
  (truffleHog on every push and PR), and PyPI publish pipeline (TestPyPI gate -> PyPI ->
  GitHub Release) triggered on `v*` tag push with OIDC trusted publishing.
