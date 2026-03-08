---
gsd_state_version: 1.0
milestone: v0.1
milestone_name: milestone
status: unknown
last_updated: "2026-03-08T14:00:00.000Z"
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 29
  completed_plans: 29
---

# Agent Factory — State

*Milestone: v0.1.0 — Factory MVP*

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** A working factory cluster that generates self-contained AI agent cluster artifacts
**Current focus:** Phase 5 — Factory Cluster Core Product

## Session Log

### 2026-03-08 — Plan 06-04 complete (CI smoke test + README; checkpoint:human-verify approved)
- Stopped at: Completed 06-04-PLAN.md — Phase 6 fully closed
- Last commit: 2ec8ad2 feat(06-04): write project README.md
- Key decisions: actions/checkout@v4 + docker compose (space, v2) in CI; no real API key in CI — placeholder .env sufficient (no LLM calls in 15s window); on: parsed as Python True by PyYAML (known quirk, GitHub reads correctly); no fabricated terminal output in README — descriptive prose only; 128 passed + 14 xpassed at 85.78% coverage; checkpoint:human-verify approved — all checks passed

### 2026-03-08 — Plan 06-03 executed (demo subcommand + cluster artifact)
- Stopped at: Completed 06-03-PLAN.md
- Last commit: 268e40a feat(06-03): generate clusters/demo-date-arithmetic/ artifact and fix .gitignore
- Key decisions: copy_runtime(base) not copy_runtime(base/runtime) — function appends /runtime/ internally; render_schema_sql() absent from factory.generator — use Path(runtime/schema.sql).read_text() directly; clusters/demo-date-arithmetic/runtime/state/ NOT committed (transient); gitignore negation !clusters/demo-date-arithmetic/db/cluster.db after exclusion rules; test_demo_exists and 4 test_demo_artifact stubs xpassed; 128 GREEN + 1 xfailed + 13 xpassed at 85.78% coverage

### 2026-03-08 — Plan 06-01 executed (TDD RED gate — 14 xfail stubs for approve/logs/demo/artifact)
- Stopped at: Completed 06-01-PLAN.md
- Last commit: 34a5a04 test(06-01): create tests/test_demo_artifact.py — 5 xfail artifact structure stubs
- Key decisions: xfail(strict=False) for all 14 stubs (consistent with prior phase pattern); shared stdlib sqlite3 helpers for DB seeding in test_factory_cli.py (no asyncio complexity); test_demo_artifact.py checks filesystem paths only — no importorskip needed; 128 GREEN + 14 xfailed at 89.03% coverage

### 2026-03-07 — Plan 05-04 complete (E2E tests — checkpoint:human-verify approved, Phase 5 closed)
- Stopped at: Completed 05-04-PLAN.md — Phase 5 fully closed
- Last commit: ba33475 fix(05-04): isolate test_add_role from real clusters/ filesystem state
- Key decisions: open_write()/open_read() return aiosqlite.Connection directly (await required, not async with) — plan template had incorrect async with pattern; fixed per existing test_boss.py usage; E2E tests use no LLM calls — fixture RoleSpec data drives generator functions directly; agent_status table queryability verified via SELECT count(*) — actual rows seeded at agent startup not factory time; test_add_role isolation: pass FACTORY_CLUSTERS_BASE via env so test resolves to empty tmp_path — prevents filesystem bleed from manual CLI demo directories; 128 tests GREEN at 89.03% coverage; E2E-01 and E2E-02 both GREEN; checkpoint:human-verify approved

### 2026-03-07 — Plan 05-03 executed (factory CLI + runner — CLI-01 to CLI-07 GREEN)
- Stopped at: Completed 05-03-PLAN.md
- Last commit: 4f7c7b2 feat(05-03): implement factory/runner.py — background subprocess entry point (boss + workers)
- Key decisions: FACTORY_CLUSTERS_BASE env var for testable cluster dir resolution (default: Path.cwd()/clusters); status/add-role exit 0 with info message on not-found (tests require exit 0); interval_seconds=30.0 for factory agents (batch mode); stagger offsets 0/7.5/15/22.5s across 30s interval; factory imports lazy in runner.py to prevent circular import; 126 tests GREEN at 87.58% coverage; CLI-01 through CLI-07 all GREEN

### 2026-03-07 — Plan 05-02 executed (pipeline + boss + workers — PIPELINE-01 to PIPELINE-03 GREEN)
- Stopped at: Completed 05-02-PLAN.md
- Last commit: f574e57 feat(05-02): implement factory/boss.py and factory/workers.py
- Key decisions: decompose_roles always injects boss (index 0) and critic (appended) structural roles after LLM response — never left to LLM discretion; fit_check is single-shot, retry logic (max 2) is caller responsibility; enrich_roles uses asyncio.gather for parallel per-role LLM calls; FactoryBossAgent.decompose_goal is deterministic (no LLM) because factory workflow is fixed; reviewer_agents=["factory-critic-01"] hardcoded for all factory tasks; design-roles task uses model_tier=sonnet, others haiku; lazy imports of TaskSpec and _uuid inside decompose_goal body to avoid circular import; 119 tests GREEN at 93.59% coverage

### 2026-03-07 — Plan 05-01 executed (generator implementation — GEN-01 to GEN-05 GREEN)
- Stopped at: Completed 05-01-PLAN.md
- Last commit: 5dac3c9 feat(05-01): implement factory/generator.py — seven artifact generator functions
- Key decisions: yaml.dump(default_flow_style=False, allow_unicode=True) for all YAML output — never f-string YAML; render_dockerfile uses python:3.12-slim default, ubuntu:22.04 when any role has requires_glibc=True; baseline packages (anthropic, aiosqlite, click, pydantic, tabulate) always in render_requirements_txt; boss=index 0, critic=index 1, workers start at index 2 in docker-compose; _offset inner function removed (dead code); 116 tests GREEN at 94.01% coverage

### 2026-03-07 — Plan 05-00 executed (TDD RED gate — factory package scaffolding)
- Stopped at: Completed 05-00-PLAN.md
- Last commit: a7e6032 test(05-00): add 17 factory test stubs (TDD RED gate)
- Key decisions: pytest.importorskip inside test body (not module level) — prevents collection crash on stub-only modules; CLI-07 collision_policy uses AND assertion (exit_code != 0 AND "already exists") to avoid trivial xpass; FactoryResearcherAgent/FactorySecurityCheckerAgent/FactoryExecutorAgent are pass-through stubs inheriting WorkerAgent — role behavior via AgentConfig.system_prompt at runtime; factory package importable with 7 stub modules; 17 xfail test stubs establish full Phase 5 test contract; 111 tests GREEN at 95.76% coverage

### 2026-03-07 — Phase 5 context gathered
- Stopped at: Phase 5 context gathered
- Resume file: .planning/phases/05-factory-cluster-core-product/05-CONTEXT.md
- Key decisions: factory IS a cluster (boss/worker/heartbeat machinery); fire-and-forget create; dynamic roles with personality woven into system prompts; boss+critic always structural; multi-step role decomposition pipeline (responsibilities → cluster → fit check → enrich → RoleSpec Pydantic → deterministic YAML); researcher agent finds tool dependencies; security-checker audits allowlists + glibc flags; executor writes artifact files; FACTORY_HOME env var; clusters in ./clusters/<name>/; --name flag with auto-slug fallback; --force to overwrite; generated Dockerfile (slim default, Ubuntu if glibc needed); requirements.txt baked at build time; task progress table status output

### 2026-03-06 — Plan 04-06 executed (gap closure — escalation_count + xfail cleanup)
- Stopped at: Completed 04-06-PLAN.md
- Last commit: aa5a186 fix(04-06): remove stale xfail marker from test_load_agent_config_role_wins_on_conflict
- Key decisions: escalation_count incremented atomically in SQL UPDATE (no application-level read-modify-write); xfail marker removed (not replaced with skip) since test passes since 04-01; 111 tests GREEN at 98.31% coverage; all Phase 4 ROADMAP success criteria satisfied

### 2026-03-06 — Plan 04-03 executed (WorkerAgent execution prompt verification)
- Stopped at: Completed 04-03-PLAN.md
- Last commit: b1b4e33 fix(04-03): fix W-09/W-16 test column name author_id -> agent_id
- Key decisions: task_comments uses agent_id not author_id; 04-02 already implemented full _execute_task; W-08/W-09/W-10/W-11 GREEN; 98.24% coverage

### 2026-03-06 — Plan 04-00 executed (WorkerAgent TDD RED gate)
- Stopped at: Completed 04-00-PLAN.md
- Last commit: 49cd8d8 feat(04-01): add assigned_role schema migration and boss persistence (W-04)
- Key decisions: pytest.importorskip inside test body for runtime.worker stubs (module-level crashes collection); AgentConfig system_prompt+tool_allowlist added immediately with empty defaults; load_agent_config cluster_config_path merge implemented at same time as field addition; assigned_role added to schema.sql DDL and DatabaseManager.up() idempotent migration

### 2026-03-06 — Plan 04-01 executed (WorkerAgent prerequisites)
- Stopped at: Completed 04-01-PLAN.md
- Last commit: 49cd8d8 feat(04-01): add assigned_role schema migration and boss persistence (W-04)
- Key decisions: cluster_config_path is load-time concern only (not on AgentConfig model); assigned_role in both schema.sql DDL and ALTER TABLE migration for fresh+existing DB; bare except catches SQLite OperationalError on duplicate column; role values win on merge {**cluster_raw, **role_raw}

### 2026-03-04 — Phase 4 context gathered
- Stopped at: Phase 4 context gathered
- Resume file: .planning/phases/04-worker-agents/04-CONTEXT.md
- Key decisions: assigned_role column added to tasks (role-based claiming, multi-agent support); base+overlay YAML (cluster.yaml shared, role files have system_prompt+tool_allowlist); free-form markdown output with version increment; independent peer review (task+doc only, no anchoring bias); ReviewDecision structured output via messages.parse()

### 2026-03-03 — Phase 3 executed (BossAgent — all 4 plans complete)
- Stopped at: Completed 03-04-PLAN.md
- Last commit: c92efef test(03-04): add 10 coverage gap tests — boss.py from 89% to 98%
- Key decisions: BossAgent subclasses BaseAgent overriding do_peer_reviews/do_own_tasks; reviewer_roles stored as JSON TEXT on tasks table; tabulate used for CLI table output; AsyncAnthropic.messages.parse() for structured LLM output; cluster goal set archives old active goal before inserting new; INSERT OR REPLACE handles task_reviews UNIQUE constraint on rejection path

### 2026-03-03 — Plan 03-03 executed (BossAgent Wave 3 — CLI commands)
- Stopped at: Completed 03-03-PLAN.md
- Last commit: cdcfeb6 docs(03): capture phase context
- Key decisions: goal set command archives previous active goal; tasks list supports --status filter and --json flag; approve command validates peer_review state before approval; tabulate used for human-readable table output

### 2026-03-03 — Plan 03-02 executed (BossAgent Wave 2 — stuck detection + gap-fill)
- Stopped at: Completed 03-02-PLAN.md
- Last commit: 8e0b368 feat(03-02): implement gap-fill cron tests and confirm full BossAgent GREEN
- Key decisions: gap-fill implementation bundled in Task 1 feat commit; timezone-naive fix via replace(tzinfo=timezone.utc); TIER_ESCALATION dict prevents KeyError on opus; all 19 test_boss.py tests GREEN; 93.80% coverage

### 2026-03-03 — Plan 03-01 executed (BossAgent core — Wave 1)
- Stopped at: Completed 03-01-PLAN.md
- Last commit: c76ca6b feat(03-01): implement BossAgent core — peer review promotion and goal decomposition
- Key decisions: all 10 Wave 1 tests written in single RED commit (shared helpers); patch.object(boss._llm.messages, 'parse') worked directly — no class-level mock needed; 10 GREEN, 9 xfail, 97% coverage

### 2026-03-03 — Plan 03-00 executed (TDD RED — 19 BossAgent stubs + 7 CLI stubs)
- Stopped at: Completed 03-00-PLAN.md
- Last commit: 9d1cf77 test(03-00): add 7 Boss CLI integration test stubs (TDD RED)
- Key decisions: pytest.importorskip inside test body for boss stubs (boss.py absent — module-level crash); reviewer_roles as nullable TEXT on tasks (JSON list, no join table); 19 stubs created (plan stated 18 but template listed 19 — template authoritative)

### 2026-03-02 — Plan 02-02 executed (BaseAgent heartbeat loop implementation)
- Stopped at: Completed 02-02-PLAN.md
- Last commit: 45ed7e4 feat(02-02): implement BaseAgent async heartbeat loop
- Key decisions: AgentConfig model_validator normalizes role/agent_role and adds db_path; agent_status schema column renamed id->agent_id; _load_state() called at start() entry to trigger corrupt-file warning; module-level STATE_DIR constant for monkeypatching; error in hooks sets ERROR status but does not stop loop

### 2026-03-02 — Plan 02-00 executed (TDD RED — all 13 heartbeat test stubs)
- Stopped at: Completed 02-00-PLAN.md
- Last commit: 65c6423 chore(02-00): verify .gitignore has runtime/state/ and full Phase 2 collection
- Key decisions: module-level _has_heartbeat sentinel for test_heartbeat.py (enables FixedTickAgent helper); pytest.importorskip inside test body for simpler single-module stubs; FixedTickAgent stops loop via _stop_event.set() after N ticks

### 2026-03-02 — Plan 02-01 executed (AgentConfig + Notifier Protocol)
- Stopped at: Completed 02-01-PLAN.md
- Last commit: 83691af fix(02-01): align AgentConfig fields with heartbeat test expectations
- Key decisions: AgentConfig uses role (not agent_role); jitter_seconds and state_dir added for Wave 2 BaseAgent; StdoutNotifier satisfies Notifier Protocol structurally (no inheritance); @runtime_checkable on Notifier

### 2026-03-01 — Plan 01-05 executed (CLI entry points + Phase 1 coverage gate)
- Stopped at: Completed 01-05-PLAN.md
- Last commit: ff800ef test(01-05): add tests/test_cli.py for CLI coverage to 97%
- Key decisions: Lazy DatabaseManager import inside async helpers; asyncio.run() once per command wrapping single coroutine; factory_cli is empty stub group; added tests/test_cli.py (not inline in test_models.py) for clean separation

### 2026-03-02 — Plan 01-04 executed (DatabaseManager + aiosqlite WAL)
- Stopped at: Completed 01-04-PLAN.md
- Last commit: 9b101b0 feat(01-04): update test_database.py from xfail stubs to GREEN tests
- Key decisions: WAL mode assertion uses tmp_path (not :memory:) — WAL silently falls back to "memory" mode on in-memory DBs; DatabaseManager is connection factory only, no DML; pragmas via individual execute() not executescript to avoid implicit COMMIT

### 2026-03-02 — Plan 01-03 executed (TaskStateMachine + TDD)
- Stopped at: Completed 01-03-PLAN.md
- Last commit: 1bbd4df feat(01-03): implement TaskStateMachine with InvalidTransitionError
- Key decisions: TRANSITIONS.get(current, set()) defensive pattern; TaskStatus re-exported from state_machine; 100% coverage achieved (14/14 stmts)

### 2026-03-02 — Plan 01-01 executed (package structure + schema + test scaffold)
- Stopped at: Completed 01-01-PLAN.md
- Last commit: df02bcd feat(01-01): create test scaffold
- Key decisions: importorskip at module level for test_models.py and test_state_machine.py; xfail for test_database.py; create_goal/create_task as plain async helpers (not fixtures)

### 2026-02-28 — Phase 1 context gathered
- Stopped at: Phase 1 context gathered
- Resume file: .planning/phases/01-core-runtime-database-state-machine/01-CONTEXT.md
- Key decisions: WAL-native connection pool, TaskStateMachine + Pydantic validation, cluster db up/reset runner, in-memory test fixtures

## Current Position

- Phase 6 of 7: COMPLETE — All 4 plans executed; checkpoint:human-verify approved
- Status: 128 tests GREEN + 14 xpassed at 85.78% coverage; Phase 6 all deliverables committed
- Next: Phase 7 (hardening + v0.1.0 release)

## Blockers / Concerns

None.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| aiosqlite connection: 1 write + 1 read per agent | WAL-native, stagger handles write serialization | — Done (01-04): open_write/open_read both apply STARTUP_PRAGMAS |
| TaskStateMachine class + Pydantic enum validation | Defense in depth, typed exceptions | — Done (01-03): TRANSITIONS dict + InvalidTransitionError with from_state/to_state attrs |
| rejected = action not state | Cleaner state machine, rejection recorded in task_comment | — Done (TaskStatus has 5 values, no "rejected") |
| Python runner over schema.sql, no Alembic | SQLite doesn't need migration versioning in v0.1 | — Done (01-04): up()/reset() async methods call init_schema() |
| 100% coverage for state machine, 80% for DB layer | Pure logic fully testable, DB layer has I/O edges | — Done (01-03): state_machine.py at 100% (14/14 stmts) |
| TRANSITIONS.get(current, set()) defensive pattern | Unknown current states raise InvalidTransitionError not KeyError | — Done (01-03) |
| TaskStatus re-exported from runtime.state_machine | Single import line for callers instead of two | — Done (01-03) |
| schema.sql is source of truth; DatabaseManager uses Path(__file__).parent / 'schema.sql' | Keeps DDL co-located with code; factory copies to cluster output in Phase 5 | — Done (01-01) |
| importorskip at module level for test_models.py and test_state_machine.py | Cleaner than per-test skip; entire module skips when implementation absent | — Done (01-01) |
| create_goal/create_task as plain async helpers (not fixtures) | Callers pass open db connection explicitly — test bodies stay readable | — Done (01-01) |
| Lazy DatabaseManager import in CLI async helpers | Keeps CLI startup fast, avoids circular import risk | — Done (01-05) |
| asyncio.run() once per command wrapping single coroutine | Never nested per RESEARCH.md Pitfall 6 | — Done (01-05) |
| factory_cli is empty @click.group() stub | Prevents entry point resolution failures on pip install -e .; Phase 5 adds subcommands | — Done (01-05) |
| tests/test_cli.py separate file (not inline in test_models.py) | Clean separation by module under test | — Done (01-05) |
| AgentConfig uses role (not agent_role); no db_path | heartbeat tests use role; BaseAgent receives db via constructor injection not config | — Updated (02-02): model_validator normalizes both role/agent_role; db_path field added |
| StdoutNotifier satisfies Notifier Protocol structurally — no inheritance | Follows structural typing pattern; Notifier is @runtime_checkable for isinstance() checks | — Done (02-01) |
| module-level _has_heartbeat sentinel for test_heartbeat.py (vs importorskip) | Enables FixedTickAgent helper class to be conditionally defined at module level; keeps tests DRY | — Done (02-00) |
| FixedTickAgent stops loop via _stop_event.set() after N ticks | Assumes BaseAgent exposes _stop_event (asyncio.Event) and _tick() as overridable method | — Done (02-00) |
| agent_status schema uses agent_id (not id) as PRIMARY KEY | test queries use WHERE agent_id = ? — column name must match | — Done (02-02): schema.sql updated |
| BaseAgent._write_state_file() references module-level STATE_DIR | monkeypatch.setattr(heartbeat_mod, "STATE_DIR", ...) redirects state files in tests | — Done (02-02) |
| Error in tick body sets status=ERROR, loop continues (stop_event NOT set) | Transient errors should not kill agent; subclass can override _tick() for custom behavior | — Done (02-02) |
| pytest.importorskip inside test body for boss stubs (not module level) | boss.py absent until Wave 1 — module-level import crashes collection | — Done (03-00) |
| reviewer_roles as nullable TEXT column on tasks (JSON list) | Avoids join table complexity for V1; boss writes JSON string at task creation time | — Done (03-00): schema.sql updated |
| tabulate>=0.9.0 added to project dependencies | Required for human-readable table output in cluster CLI commands (Wave 3) | — Done (03-00): pyproject.toml updated |
| All Wave 1 tests written in single RED commit (both Task 1 + Task 2 test groups) | Shared helpers (_make_db, _insert_*) benefit all groups; plan noted no boss.py changes for Task 2 | — Done (03-01) |
| patch.object(boss._llm.messages, 'parse') worked directly for mock | No class-level AsyncAnthropic patch needed; simpler test setup | — Done (03-01) |
| TIER_ESCALATION dict maps opus->opus (no error on already-max tier) | Prevents KeyError; no-op on already-escalated tasks when repeated escalation runs | — Done (03-02) |
| Second intervention check: row['stuck_since'] is not None | First intervention sets stuck_since; second intervention checks it to avoid double-escalation | — Done (03-02) |
| timezone-naive datetime fix: replace(tzinfo=timezone.utc) after fromisoformat() | SQLite datetime('now') returns naive timestamps; UTC-aware comparison required for stuck detection | — Done (03-02) |
| Gap-fill: only trigger decompose_goal() when cnt==0 active tasks | Prevents task explosion; gap-fill is only for when no work is in flight | — Done (03-02) |
| goal set command archives old active goal before inserting new | Prevents orphaned goals; ensures single active goal at all times | — Done (03-03) |
| INSERT OR REPLACE handles task_reviews UNIQUE constraint on rejection path | Avoids IntegrityError when boss re-creates review rows after rejection resets | — Done (03-03) |
| cluster_config_path is a load-time concern, not on AgentConfig model | AgentConfig holds runtime values only; file merging is a loading concern (keeps model clean) | — Done (04-01): load_agent_config() accepts optional 2nd path |
| assigned_role in schema.sql DDL AND ALTER TABLE migration in up() | Fresh DBs get column from DDL; existing pre-04-01 DBs get column from migration — both paths covered | — Done (04-01): up() now idempotent with assigned_role |
| Role YAML wins on merge conflict: {**cluster_raw, **role_raw} | Role file is more specific; cluster provides shared defaults (db_path, interval_seconds) | — Done (04-01): load_agent_config merge pattern |
| task_comments uses agent_id (not author_id) | Schema FK defined in Phase 1 as agent_id; W-09/W-16 tests had wrong column name — fixed in tests not schema | — Done (04-03): tests/test_worker.py lines 493, 790 |
| W-08/W-09/W-10/W-11 confirmed GREEN from 04-02 implementation | 04-02 pre-implemented full _execute_task; 04-03 is verification + test bug fix plan | — Done (04-03): 98.24% coverage |
| escalation_count incremented atomically in SQL UPDATE (no application-level read-modify-write) | Avoids race condition; simpler than read-then-update | — Done (04-06): _reject_back_to_in_progress() line ~418 |
| xfail removed (not replaced with skip) from test_load_agent_config_role_wins_on_conflict | Test passes since 04-01 shipped load_agent_config merge — marker was stale XPASS noise | — Done (04-06): tests/test_worker.py line 232 |
| pytest.importorskip inside test body (not module level) for factory stubs | factory.* absent until 05-01+ implementation — module-level import crashes collection; consistent with Phase 3/4 pattern | — Done (05-00): all 4 factory test files |
| CLI-07 collision_policy assertion uses AND (exit_code != 0 AND "already exists" in output) | OR condition trivially xpasses since 'create' subcommand doesn't exist yet (returns exit_code=2 for unknown command) | — Done (05-00): tests/test_factory_cli.py |
| FactoryResearcherAgent/FactorySecurityCheckerAgent/FactoryExecutorAgent are pass-through stubs | Role-specific behavior injected via AgentConfig.system_prompt at runtime per CONTEXT.md locked decision | — Done (05-00): factory/workers.py |
| yaml.dump(default_flow_style=False, allow_unicode=True) for all YAML output in generator.py | Ensures valid multi-line YAML; never f-string YAML which risks injection/formatting errors | — Done (05-01): factory/generator.py |
| render_dockerfile uses python:3.12-slim by default; switches to ubuntu:22.04 when any role has requires_glibc=True | Slim base is smaller/faster for most clusters; glibc required only for native lib roles | — Done (05-01): factory/generator.py |
| render_requirements_txt baseline packages: anthropic, aiosqlite, click, pydantic, tabulate — always included | Runtime dependencies always needed; role tool_allowlist adds extras via set union then sort | — Done (05-01): factory/generator.py |
| decompose_roles always injects boss (index 0) and critic (appended) structural roles after LLM response | Boss and critic mandatory in every cluster — never left to LLM discretion | — Done (05-02): factory/pipeline.py |
| fit_check is single-shot; retry logic (max 2 retries) is caller responsibility | Clean separation of concerns — pipeline function does one thing | — Done (05-02): factory/pipeline.py |
| enrich_roles uses asyncio.gather for parallel per-role LLM calls | Concurrency matches RESEARCH.md enrichment pattern; O(N roles) latency not O(1) | — Done (05-02): factory/pipeline.py |
| FactoryBossAgent.decompose_goal is deterministic (no LLM) — 7 fixed factory tasks | Factory artifact workflow is fixed and well-known; pipeline handles LLM decomposition separately | — Done (05-02): factory/boss.py |
| reviewer_agents=["factory-critic-01"] hardcoded for all factory tasks | Critic is always structural reviewer for factory work — consistent with boss+critic injection in pipeline | — Done (05-02): factory/boss.py |
| design-roles task uses model_tier="sonnet", all others "haiku" | Role design step warrants stronger model; haiku sufficient for artifact generation tasks | — Done (05-02): factory/boss.py |
| Lazy imports of TaskSpec and _uuid inside decompose_goal body | Avoids potential circular import at module import time | — Done (05-02): factory/boss.py |
| FactoryResearcherAgent/FactorySecurityCheckerAgent/FactoryExecutorAgent use SYSTEM_PROMPT ClassVar[str] | WorkerAgent specialization via class attribute — all execution logic inherited from WorkerAgent | — Done (05-02): factory/workers.py |
| FACTORY_CLUSTERS_BASE env var for cluster dir resolution | CliRunner does not change CWD; env var allows CLI-07 collision test to target tmp_path without filesystem coupling; defaults to Path.cwd()/clusters | — Done (05-03): runtime/cli.py |
| status/add-role exit 0 with info message on not-found | CLI-02/03/05 tests require exit 0 on missing data; ClickException would return exit 1 | — Done (05-03): runtime/cli.py |
| interval_seconds=30.0 for all factory agents in runner.py | Batch job mode — needs to complete quickly rather than poll every 600s | — Done (05-03): factory/runner.py |
| run_factory() stagger offsets: 0, 7.5, 15, 22.5s across 30s interval | Prevents all four agents hitting SQLite WAL write lock simultaneously | — Done (05-03): factory/runner.py |
| open_write()/open_read() return aiosqlite.Connection directly (await required, not async with) | Plan template used incorrect async with pattern; DatabaseManager API uses plain await + explicit close per conftest.py and test_boss.py | — Done (05-04): tests/test_factory_e2e.py |
| CLI tests that touch filesystem must pass FACTORY_CLUSTERS_BASE env var via runner.invoke(..., env=env) | Prevents test failure when CWD clusters/ directory contains real cluster dirs from manual demos; isolates to tmp_path — matches test_collision_policy pattern | — Done (05-04): tests/test_factory_cli.py test_add_role |
| xfail(strict=False) for all Phase 6 stubs | Allows unexpected passes without breaking the gate; consistent with Phases 3-5 TDD RED pattern | — Done (06-01): all 14 stubs |
| stdlib sqlite3 seeding helpers in test_factory_cli.py (not aiosqlite) | Avoids asyncio.run() nesting in synchronous test setup; cleaner fixtures | — Done (06-01): _make_cluster_db/_seed_* helpers |
| test_demo_artifact.py uses bare Path() relative to project root, no importorskip | Artifact tests check filesystem paths only — no module imports; pytest CWD is project root | — Done (06-01): tests/test_demo_artifact.py |
| copy_runtime(base) not copy_runtime(base/runtime) | Function appends /runtime/ internally; calling with parent produces single-level cluster/runtime/ not nested cluster/runtime/runtime/ | — Done (06-03): clusters/demo-date-arithmetic/runtime/ |
| render_schema_sql() absent from factory.generator | Plan interface block was aspirational; use Path('runtime/schema.sql').read_text() directly — same content, no functional difference | — Done (06-03): clusters/demo-date-arithmetic/db/schema.sql |
| gitignore negation !clusters/demo-date-arithmetic/db/cluster.db after exclusion rules | Git processes negation in order; negation must appear after clusters/*/db/*.db and *.db rules to take effect | — Done (06-03): .gitignore |
| actions/checkout@v4 + docker compose (space, v2) in smoke-test.yml | v2/v3 deprecated; docker-compose (hyphen, v1) removed from ubuntu-latest 2024; v2 is correct | — Done (06-04): .github/workflows/smoke-test.yml |
| No real ANTHROPIC_API_KEY in CI; placeholder .env from .env.example is sufficient | Agents don't make LLM calls within the 15s startup window before docker compose down | — Done (06-04): .github/workflows/smoke-test.yml |
| README walkthrough uses descriptive prose, no fabricated task IDs or terminal output | Per RESEARCH.md Pitfall 6: trace should only be added after running actual demo | — Done (06-04): README.md |
