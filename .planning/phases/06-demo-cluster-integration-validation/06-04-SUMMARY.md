---
phase: 06-demo-cluster-integration-validation
plan: 04
subsystem: infra
tags: [github-actions, ci, yaml, readme, docker-compose, sqlite3]

requires:
  - phase: 06-03
    provides: clusters/demo-date-arithmetic/ artifact with pre-seeded cluster.db, agent-factory demo subcommand

provides:
  - .github/workflows/smoke-test.yml CI workflow: build + start cluster containers + sqlite3 health check on every push/PR
  - README.md at project root: What it is, Quick Start, How it works with ASCII architecture diagram

affects: [ci, release-readiness]

tech-stack:
  added: []
  patterns:
    - "GitHub Actions smoke test: docker compose build + up -d + sleep 15 + sqlite3 row count check + docker compose down --volumes (if: always)"
    - "README structure: What it is (2-3 sentences) + Quick Start (bash block) + How it works (ASCII diagram + demo walkthrough prose)"
    - "No fabricated terminal output in README — descriptive prose only until real demo run captured"

key-files:
  created:
    - .github/workflows/smoke-test.yml
    - README.md
  modified: []

key-decisions:
  - "actions/checkout@v4 not v2/v3 — both deprecated on ubuntu-latest as of 2024"
  - "docker compose (space, v2 syntax) not docker-compose (hyphen, v1 removed from ubuntu-latest 2024)"
  - "sqlite3 availability check step before DB query — cheap insurance against 'sqlite3 not found' edge case"
  - "if: always() on teardown — ensures containers stop even when earlier steps fail"
  - "No real ANTHROPIC_API_KEY in CI — placeholder .env copied from .env.example; agents don't make LLM calls within 15s window"
  - "No fabricated task IDs in README walkthrough — descriptive prose about what demo shows, trace added after real demo run"
  - "on: key parsed as Python True by PyYAML (known quirk) — GitHub Actions reads YAML correctly regardless"

patterns-established:
  - "CI smoke test pattern: docker compose build (validates artifact build) + sqlite3 row count (validates pre-seeded DB) — no LLM calls in CI"

requirements-completed: [ci-smoke-test, project-readme]

duration: 4min
completed: 2026-03-08
---

# Phase 6 Plan 04: CI Smoke Test + README Summary

**GitHub Actions smoke-test.yml (CI for every push/PR) and project README.md with Quick Start + ASCII architecture diagram delivered as Phase 6 final artifacts**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-08T13:25:31Z
- **Completed:** 2026-03-08T13:30:44Z
- **Tasks:** 3 of 3 complete (checkpoint:human-verify approved)
- **Files modified:** 2

## Accomplishments
- `.github/workflows/smoke-test.yml` created: triggers on push to `main` and all PRs; builds demo cluster containers, starts them detached, waits 15s, verifies >= 2 `agent_status` rows in the pre-seeded `cluster.db`, tears down with `if: always()`
- `README.md` created at project root: three sections (What it is / Quick Start / How it works), ASCII architecture diagram showing factory → cluster artifact → running cluster flow, demo walkthrough prose with no fabricated terminal output
- `test_readme_exists` stub xpassed — full suite now 128 passed, 14 xpassed at 85.78% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Create .github/workflows/smoke-test.yml** - `876d4c1` (feat)
2. **Task 2: Write root-level README.md** - `2ec8ad2` (feat)
3. **Task 3: checkpoint:human-verify** - approved (128 tests passing, 85.78% coverage, artifact structure verified)

## Files Created/Modified
- `.github/workflows/smoke-test.yml` - CI smoke test workflow (40 lines): checkout, .env setup, sqlite3 version check, docker compose build/up, wait, DB row count assertion, docker compose down
- `README.md` - Project README (72 lines): What it is, Quick Start bash block, How it works ASCII diagram + demo walkthrough

## Decisions Made
- `on:` in YAML is parsed as Python boolean `True` by PyYAML — this is a known quirk; GitHub Actions reads the YAML correctly. Plan verification check (`assert 'smoke-test' in data['jobs']`) passes.
- No fabricated task IDs or fake terminal output in README — descriptive prose only. After a real `agent-factory demo` run the trace can be added with actual output.
- `actions/checkout@v4` used (v2/v3 deprecated); `docker compose` space-separated (v1 `docker-compose` removed from ubuntu-latest 2024).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 Plan 04 fully complete; checkpoint:human-verify approved by user (all checks passed)
- Full test suite GREEN: 128 passed + 14 xpassed at 85.78% coverage (above 80% threshold)
- Phase 6 (Demo Cluster + Integration Validation) is complete; Phase 7 (hardening + v0.1.0 release) is next

## Self-Check: PASSED
- `.github/workflows/smoke-test.yml` exists: confirmed
- `README.md` exists: confirmed
- Commits `876d4c1` and `2ec8ad2` verified in git log
- Checkpoint task approved: 128 tests GREEN, 85.78% coverage, demo artifact structure verified
</content>
</invoke>