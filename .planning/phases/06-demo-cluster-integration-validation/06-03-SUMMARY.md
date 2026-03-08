---
phase: 06-demo-cluster-integration-validation
plan: 03
subsystem: cli
tags: [click, sqlite3, subprocess, factory-cli, demo, cluster-artifact, gitignore]

requires:
  - phase: 06-02
    provides: factory_approve and factory_logs subcommands; 8 xpassed stubs; established cluster DB path pattern

provides:
  - factory_demo subcommand on factory_cli with live polling loop via _poll_demo_until_approved()
  - clusters/demo-date-arithmetic/ full artifact directory committed to repo
  - clusters/demo-date-arithmetic/db/cluster.db pre-seeded with boss-01 and coder-01 in agent_status
  - .gitignore negation allowing cluster.db to be committed for CI smoke tests

affects: [06-04-artifact-validation, ci-smoke-tests]

tech-stack:
  added: []
  patterns:
    - "factory_demo = asyncio.run(_do_demo_setup()) then _poll_demo_until_approved() — async setup, sync poll"
    - "Sync polling loop with stdlib sqlite3 (_sqlite3 alias) + sys.stdout.write(\\r) for in-place status updates"
    - "cluster artifact generated via factory generator functions called from Python script (not subprocess)"
    - "copy_runtime(base) — not copy_runtime(base / 'runtime') — produces cluster/runtime/ not cluster/runtime/runtime/"
    - "render_schema_sql() does not exist; use runtime/schema.sql directly for artifact schema copy"
    - "gitignore negation !clusters/demo-date-arithmetic/db/cluster.db must appear after clusters/*/db/*.db"

key-files:
  created:
    - clusters/demo-date-arithmetic/docker-compose.yml
    - clusters/demo-date-arithmetic/Dockerfile
    - clusters/demo-date-arithmetic/requirements.txt
    - clusters/demo-date-arithmetic/launch.sh
    - clusters/demo-date-arithmetic/.env.example
    - clusters/demo-date-arithmetic/config/cluster.yaml
    - clusters/demo-date-arithmetic/config/agents/boss.yaml
    - clusters/demo-date-arithmetic/config/agents/critic.yaml
    - clusters/demo-date-arithmetic/config/agents/coder.yaml
    - clusters/demo-date-arithmetic/db/schema.sql
    - clusters/demo-date-arithmetic/db/cluster.db
    - clusters/demo-date-arithmetic/runtime/ (copied runtime package)
  modified:
    - runtime/cli.py
    - .gitignore

key-decisions:
  - "copy_runtime(base) not copy_runtime(base / 'runtime') — function appends /runtime/ internally, so pass parent"
  - "render_schema_sql() absent from factory.generator; use Path('runtime/schema.sql').read_text() directly"
  - "clusters/demo-date-arithmetic/runtime/state/ NOT committed — runtime state files are transient artifacts"
  - "Polling loop uses stdlib sqlite3 as _sqlite3 + time (module-level imports); NOT asyncio — polling is sync by design"
  - "gitignore: clusters/*/db/*.db-wal and *.db-shm added; !clusters/demo-date-arithmetic/db/cluster.db after exclusion rules"

patterns-established:
  - "demo poll pattern: asyncio.run(setup) then sync_poll() — separates async DB setup from sync terminal polling"
  - "cluster.db negation pattern: exclude all *.db globally, then negate specific committed DB path"

requirements-completed: [factory-demo-command, demo-cluster-artifact]

duration: 11min
completed: 2026-03-08
---

# Phase 6 Plan 03: Demo Subcommand + Cluster Artifact Summary

**agent-factory demo command with live polling loop and committed clusters/demo-date-arithmetic/ artifact pre-seeded with boss-01 and coder-01 in agent_status**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-08T13:10:24Z
- **Completed:** 2026-03-08T13:21:28Z
- **Tasks:** 2
- **Files modified:** 2 (runtime/cli.py, .gitignore) + 23 new cluster artifact files

## Accomplishments
- `agent-factory demo` subcommand registered on factory_cli group; creates demo-date-arithmetic goal in factory DB, fires runner subprocess, polls cluster.db with live terminal status updates using `sys.stdout.write(\r)`
- Full clusters/demo-date-arithmetic/ artifact directory committed: docker-compose.yml, Dockerfile, requirements.txt, .env.example, launch.sh, config/cluster.yaml, config/agents/*.yaml, db/schema.sql, runtime/
- clusters/demo-date-arithmetic/db/cluster.db pre-seeded with boss-01 and coder-01 (WAL checkpoint before close); committed via .gitignore negation rule
- test_demo_exists and all 4 test_demo_artifact path stubs now xpassed; test_readme_exists remains xfail (Wave 4); full suite: 128 passed, 1 xfailed, 13 xpassed at 85.78% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement agent-factory demo subcommand** - `cf81dea` (feat)
2. **Task 2: Generate cluster artifact + fix .gitignore** - `268e40a` (feat)

## Files Created/Modified
- `runtime/cli.py` - Added factory_demo, _do_demo_setup(), _poll_demo_until_approved() (80 new lines); added stdlib sqlite3 as _sqlite3 and time imports
- `.gitignore` - Added clusters/*/db/*.db-wal, clusters/*/db/*.db-shm exclusions; !clusters/demo-date-arithmetic/db/cluster.db negation
- `clusters/demo-date-arithmetic/` - Full artifact tree: 23 files committed including pre-seeded cluster.db

## Decisions Made
- `copy_runtime(base)` not `copy_runtime(base / "runtime")` — the function appends `/runtime/` internally; calling with the parent dir produces the correct single-level path. The plan's interface block had the call wrong.
- `render_schema_sql()` does not exist in factory.generator (plan interface block was aspirational); used `Path("runtime/schema.sql").read_text()` directly — same content, no functional difference.
- `clusters/demo-date-arithmetic/runtime/state/` NOT committed — state JSON files are transient runtime artifacts that don't belong in the repo.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] render_schema_sql() absent from factory.generator**
- **Found during:** Task 2 (cluster artifact generation)
- **Issue:** Plan's interface block listed `render_schema_sql` as an importable function, but the function does not exist in factory/generator.py
- **Fix:** Used `Path("runtime/schema.sql").read_text(encoding="utf-8")` directly — identical content, no functional difference
- **Files modified:** None (fix was in the generation script, not committed source)
- **Verification:** clusters/demo-date-arithmetic/db/schema.sql created successfully; cluster.db seeded correctly
- **Committed in:** 268e40a (Task 2 commit)

**2. [Rule 3 - Blocking] copy_runtime() call path correction**
- **Found during:** Task 2 (cluster artifact generation)
- **Issue:** Plan specified `copy_runtime(base / "runtime")` which produced a nested `clusters/demo-date-arithmetic/runtime/runtime/` double-nesting
- **Fix:** Used `copy_runtime(base)` — the function appends `/runtime/` internally; corrected call produces the expected single-level `clusters/demo-date-arithmetic/runtime/`
- **Files modified:** None (correction in generation script)
- **Verification:** clusters/demo-date-arithmetic/runtime/*.py files at correct path
- **Committed in:** 268e40a (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking)
**Impact on plan:** Both corrections necessary for artifact correctness. No scope changes; all plan outputs delivered as specified.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 Wave 3 complete; demo subcommand and committed artifact both delivered
- 1 remaining xfail stub: test_readme_exists (README.md — Wave 4 scope)
- Phase 6 Plan 04 (artifact validation / CI hardening) is the final plan in this phase
- Full test suite: 128 passed, 1 xfailed, 13 xpassed at 85.78% coverage

## Self-Check: PASSED
