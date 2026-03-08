# Agent Factory — Roadmap

*Last updated: 2026-03-08*
*Milestone: v0.1.0 — Factory MVP*

---

## Milestone Goal

Ship a working Factory cluster that can accept a natural-language goal, spin up a self-contained agent cluster artifact, and run the cluster autonomously with boss + worker heartbeats, peer review gating, and CLI status reporting.

---

## Phase 1: Core Runtime (Database + State Machine)

**Goal**: A working database layer and task state machine that any agent can use.

**Deliverables:**
- `runtime/database.py` — SQLite WAL connection manager with timeout handling
- `runtime/models.py` — Pydantic models for Goal, Task, Comment, Review, AgentStatus, Document, ActivityLog
- `runtime/schema.sql` — Canonical schema (all 7 tables)
- Database migration runner (`db up` / `db reset`)
- Full unit test coverage for state transitions (valid + invalid)

**Success Criteria:**
- Can create a goal, decompose it into tasks, and walk a task through the full state machine via Python API
- Invalid state transitions raise typed exceptions
- All DB writes use parameterized queries (no SQL injection)
- WAL mode verified via `PRAGMA journal_mode`

**Not included:** Agents, LLM calls, Docker

**Status: COMPLETE** — 5/5 plans executed, 40 GREEN tests, 97% coverage

Plans:
- [x] 01-01-PLAN.md — Test scaffold + runtime/__init__.py + runtime/schema.sql
- [x] 01-02-PLAN.md — runtime/models.py (7 Pydantic models + 4 str Enums)
- [x] 01-03-PLAN.md — runtime/state_machine.py (TDD: TaskStateMachine + InvalidTransitionError)
- [x] 01-04-PLAN.md — runtime/database.py (DatabaseManager with WAL pragmas)
- [x] 01-05-PLAN.md — runtime/cli.py (cluster db up/reset) + full test suite to GREEN (97%)

---

## Phase 2: Agent Heartbeat Framework

**Goal**: A generic heartbeat loop any agent can plug into, with stagger support and local state file.

**Deliverables:**
- `runtime/heartbeat.py` — `BaseAgent` class with async heartbeat loop
- Configurable interval and stagger offset (from `agents/*.yaml`)
- Local state file (`runtime/state/<agent-id>.json`) with last heartbeat, current task
- Heartbeat jitter (±30s random)
- `runtime/notifier.py` — `Notifier` protocol + `StdoutNotifier` implementation [DONE - Plan 01]
- `runtime/config.py` — `AgentConfig` Pydantic model + `load_agent_config()` [DONE - Plan 01]
- Integration tests: two agents run staggered heartbeats without DB collision

**Success Criteria:**
- `BaseAgent` subclass can override `do_peer_reviews()` and `do_own_tasks()` hooks
- Two agents running simultaneously never hold the SQLite write lock at the same time
- Local state file updated after every heartbeat

**Not included:** LLM calls (agents are no-op stubs in this phase)

**Status: COMPLETE** — 3/3 plans executed, 13 GREEN tests (Phase 2), 97% total coverage

Plans:
- [x] 02-00-PLAN.md — TDD RED stubs: 13 heartbeat tests (HB-01 through HB-13)
- [x] 02-01-PLAN.md — AgentConfig (Pydantic), Notifier Protocol, StdoutNotifier
- [x] 02-02-PLAN.md — BaseAgent heartbeat loop (stagger, UPSERT, state file, graceful shutdown)

---

## Phase 3: Boss Agent

**Goal**: A functional boss agent that decomposes goals, creates tasks, coordinates reviews, and detects blocked agents.

**Deliverables:**
- `runtime/boss.py` — `BossAgent(BaseAgent)` with all boss-exclusive authorities
- Goal → task decomposition via Claude Sonnet 4.6
- Task creation with priority, model tier, and reviewer assignment
- Peer review promotion: `peer_review` → `review` when all reviewers approve
- Blocked task detection: tasks stuck > 30 min trigger investigation + escalation
- Model tier escalation: auto-upgrade on 2+ rejections
- Cron-based new task generation (every 3 heartbeats)
- CLI: `cluster goal set`, `cluster tasks list`, `cluster agents status`, `cluster approve`

**Success Criteria:**
- Boss creates tasks that cover the entire stated goal (validated by a second LLM call)
- Boss correctly promotes tasks when all reviews are approved
- Boss logs all escalations with reason to `activity_log`
- Stuck detection fires within 2 heartbeat cycles after threshold

**Status: COMPLETE** — 4/4 plans executed, 29 GREEN boss tests, 98.43% coverage

Plans:
- [x] 03-00-PLAN.md — TDD RED stubs: 19 boss tests + 7 CLI stubs; schema + tabulate
- [x] 03-01-PLAN.md — BossAgent core: peer review promotion + goal decomposition (10 GREEN)
- [x] 03-02-PLAN.md — Stuck detection + escalation + gap-fill cron (19 GREEN)
- [x] 03-03-PLAN.md — CLI commands: goal set, tasks list, agents status, approve (26 GREEN)
- [x] 03-04-PLAN.md — Coverage gate + documentation finalization (29 GREEN, 98.43% coverage)

---

## Phase 4: Worker Agents

**Goal**: Functional worker agents (researcher, writer, strategist) that execute tasks and perform peer reviews.

**Deliverables:**
- `runtime/worker.py` — `WorkerAgent(BaseAgent)` base with role configuration
- Role-specific system prompts loaded from `config/agents/<role>.yaml`
- Task execution: LLM call → document creation → `task_comment` → move to `peer_review`
- Peer review execution: fetch pending reviews → generate substantive feedback → approve/reject
- Tool allowlist enforcement (no tools used outside yaml-defined list)
- Per-task model selection from `model_tier` column (haiku/sonnet/opus)

**Success Criteria:**
- Worker picks up a `todo` task, completes it, and submits to `peer_review` within one heartbeat
- Peer reviewer produces ≥2 sentences of feedback and sets status to approved or rejected
- Rejected tasks increment `escalation_count` correctly
- Worker cannot call tools not listed in its `agents/<role>.yaml`

**Plans:** 7/7 plans complete

Plans:
- [x] 04-00-PLAN.md — TDD RED stubs: 18 worker tests + 2 config stubs (Wave 0)
- [x] 04-01-PLAN.md — Schema migration, AgentConfig extension, load_agent_config merge, boss persistence (Wave 1)
- [x] 04-02-PLAN.md — WorkerAgent skeleton: do_own_tasks with resume-first claiming (Wave 2)
- [x] 04-03-PLAN.md — WorkerAgent execution: LLM call, document, progress comment, peer_review transition (Wave 3)
- [x] 04-04-PLAN.md — WorkerAgent peer review: do_peer_reviews, ReviewDecision, feedback comment (Wave 4)
- [x] 04-05-PLAN.md — Role YAML configs (researcher, writer, strategist) + coverage gate (Wave 5)

---

## Phase 5: Factory Cluster (Core Product)

**Goal**: The factory cluster itself — accepts a goal, generates a fully runnable cluster artifact.

**Deliverables:**
- `factory/generator.py` — Cluster artifact generator (YAML configs, docker-compose.yml, schema, runtime copy)
- Factory boss: decomposes goal into agent roles, generates per-agent system prompts
- `clusters/<name>/docker-compose.yml` generator (parameterized by role count)
- `clusters/<name>/config/cluster.yaml` and `agents/*.yaml` generators
- `clusters/<name>/launch.sh` with env var validation
- Factory CLI: `agent-factory create <goal>`, `agent-factory list`, `agent-factory status`, `agent-factory add-role`
- End-to-end test: factory creates a cluster artifact; artifact passes schema and docker-compose validation

**Success Criteria:**
- `agent-factory create "Build a MTG deckbuilding advisor"` produces a valid cluster directory
- `docker compose config` validates the generated `docker-compose.yml` without errors
- The seeded database contains the correct goal and initial agent_status rows
- `./launch.sh` fails fast with a clear error if `ANTHROPIC_API_KEY` is not set

**Plans:** 5/5 plans complete

Plans:
- [x] 05-00-PLAN.md — TDD RED stubs + factory/ package scaffolding (Wave 1)
- [x] 05-01-PLAN.md — factory/models.py + factory/generator.py — pure artifact generators (Wave 2)
- [x] 05-02-PLAN.md — factory/pipeline.py + factory/boss.py — role decomposition pipeline (Wave 3)
- [x] 05-03-PLAN.md — factory CLI subcommands + factory/runner.py — fire-and-forget create (Wave 4)
- [x] 05-04-PLAN.md — E2E tests + coverage gate (Wave 5)

---

## Phase 6: Demo Cluster + Integration Validation

**Goal**: Run a real end-to-end scenario: factory creates a coding cluster, cluster runs autonomously for one full task cycle.

**Deliverables:**
- Demo cluster: "Write a Python utility library for date arithmetic"
- Full heartbeat cycle: boss creates tasks → workers execute → peer review → boss promotes → user approves via CLI
- All activity logged and accessible via CLI
- `README.md` with quickstart instructions (factory setup + demo cluster walkthrough)
- Docker Compose smoke test in CI (GitHub Actions)

**Success Criteria:**
- Cluster completes at least one task from `todo` → `approved` without human intervention beyond final approval
- All `activity_log` entries are present and coherent
- `cluster tasks list --status approved` shows the completed task with correct document attached
- CI smoke test passes on clean environment

**Plans:** 4 plans

Plans:
- [ ] 06-01-PLAN.md — TDD RED stubs: 9 factory_cli stubs (approve + logs + demo) + test_demo_artifact.py (5 stubs)
- [ ] 06-02-PLAN.md — agent-factory approve + agent-factory logs subcommands
- [ ] 06-03-PLAN.md — agent-factory demo command + clusters/demo-date-arithmetic/ artifact + .gitignore fix
- [ ] 06-04-PLAN.md — CI smoke test (.github/workflows/smoke-test.yml) + README.md + human checkpoint

---

## Phase 7: Hardening + v0.1.0 Release

**Goal**: Security audit, observability, error resilience, and package release.

**Deliverables:**
- Security review: secrets audit, tool allowlist enforcement test, no cross-cluster DB access test
- Error recovery: agent crash recovery on next heartbeat (reads local state, resumes)
- Heartbeat monitoring: boss detects agents that miss 3+ consecutive heartbeats and alerts user
- PyPI package or install script (`pip install agent-factory`)
- Full test suite: unit + integration + E2E smoke test
- CHANGELOG.md and GitHub release v0.1.0

**Success Criteria:**
- No hardcoded secrets found by `truffleHog` scan
- All security checklist items from REQUIREMENTS §8 pass
- Agent crash-and-restart cycle preserves task state correctly
- 80%+ test coverage measured by `pytest --cov`

---

## Dependency Graph

```
Phase 1 (DB + State Machine)
    └── Phase 2 (Heartbeat Framework)
            ├── Phase 3 (Boss Agent)
            └── Phase 4 (Worker Agents)
                    └── Phase 5 (Factory Cluster)
                            └── Phase 6 (Demo + Integration)
                                    └── Phase 7 (Hardening + Release)
```

Phases 3 and 4 can be developed in parallel after Phase 2 is complete.

---

## Open Questions (to resolve during implementation)

| Question | Impact | Resolution |
|----------|--------|------------|
| How does the factory copy the runtime into cluster dirs? | Phase 5 | Symlink vs. copy — copy preferred for true isolation |
| Should `docker-compose.yml` use a shared base image or per-role images? | Phase 5 | Single shared image with role passed as `AGENT_ROLE` env var |
| How does the boss know when the overall goal is "done"? | Phase 3 | Boss checks all tasks completed + asks LLM to evaluate goal coverage |
| Should clusters support hot-adding new agents post-launch? | Future | Out of scope for v0.1.0 |
