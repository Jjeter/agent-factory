# Project State

*Last updated: 2026-03-01*

## Project Reference

**What This Is**: An open-source, self-hosted Python system that creates and deploys independent, domain-specialized AI agent clusters.

**Core Value**: Given a goal, the system produces a running, independent agent cluster that works autonomously until completion.

## Current Position

- **Milestone**: v0.1.0 — Factory MVP
- **Phase**: 2 of 7 — Agent Heartbeat Framework
- **Current Plan**: 02-00 complete (Wave 0 test stubs)
- **Status**: IN PROGRESS
- **Progress**: `[██░░░░░░░░]` 14%

## Phase Completion Log

| Phase | Name | Status |
|-------|------|--------|
| 1 | Core Runtime (DB + State Machine) | ✓ Complete (98.5% coverage, 80 tests) |
| 2 | Agent Heartbeat Framework | In Progress — Plan 00 (Wave 0 stubs) complete |
| 3 | Boss Agent | — Pending |
| 4 | Worker Agents | — Pending |
| 5 | Factory Cluster | — Pending |
| 6 | Demo Cluster + Integration | — Pending |
| 7 | Hardening + v0.1.0 Release | — Pending |

## Phase 1 Deliverables (Verified)

- [x] `runtime/database.py` — SQLite WAL connection manager (98% coverage)
- [x] `runtime/models.py` — Pydantic models for all 7 entities (99% coverage)
- [x] `runtime/schema.sql` — Canonical schema
- [x] `tests/test_database.py` — Full DB state transition tests
- [x] `tests/test_models.py` — Model validation tests
- [x] 80 tests passing, 98.5% total coverage

## Phase 2 Progress (In Progress)

- [x] `tests/conftest.py` — Shared async fixtures: tmp_db, fast_config, stub_agent
- [x] `tests/test_config.py` — HB-10, HB-11 stubs (AgentConfig load + validation)
- [x] `tests/test_notifier.py` — HB-07, HB-08, HB-09 stubs (Notifier protocol + StdoutNotifier)
- [x] `tests/test_heartbeat.py` — HB-01 through HB-06, HB-12, HB-13, HB-14 stubs
- [ ] `runtime/config.py` — AgentConfig model + load_agent_config() (Wave 1)
- [ ] `runtime/notifier.py` — Notifier protocol + StdoutNotifier (Wave 1)
- [ ] `runtime/heartbeat.py` — BaseAgent ABC with async heartbeat loop (Wave 2)

## Recent Decisions

- Python + asyncio for heartbeat/agent runtime
- SQLite WAL for portability (zero-setup, file = cluster)
- Docker Compose per cluster for isolation
- CLI-first with pluggable `Notifier` protocol
- Lazy imports in conftest fixtures: Phase 2 module imports inside fixture bodies to avoid ImportError before implementation
- `run_for_n_cycles` helper uses direct attribute assignment (`agent._heartbeat = counted_heartbeat`) for bounded async test loops
- Wave 0 first: all 14 requirement test stubs committed before any implementation code

## Pending Todos

(None captured)

## Blockers / Concerns

(None)

## Session Continuity

Last session: 2026-03-01
Stopped at: Phase 2, Plan 00 (Wave 0 test stubs) complete — ready for Plan 01 (Wave 1: config + notifier implementation)
Resume file: (none)
