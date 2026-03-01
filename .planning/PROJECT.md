# Agent Factory

## What This Is

An open-source, self-hosted Python system that creates and deploys independent, domain-specialized AI agent clusters. The user hands a goal to a "factory" cluster, which produces a fully self-contained cluster artifact (its own boss, database, agents, and Docker Compose environment) specialized for that domain — whether that's software engineering, Magic: The Gathering deck building, PR campaign management, or any other workflow.

## Core Value

Given a goal, the system produces a running, independent agent cluster that works autonomously until completion — with no further setup required from the user.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Boss agent decomposes goals into tasks and assigns them to worker agents
- [ ] Worker agents execute tasks asynchronously via staggered ~10-minute heartbeats
- [ ] Peer review gate: all assigned reviewers must approve before a task advances
- [ ] Task state machine: todo → in-progress → peer_review → review → approved
- [ ] Boss has exclusive authority to create tasks, promote to review, reassign, and reprioritize
- [ ] Model escalation: tasks start at Haiku, auto-escalate on peer review rejection, boss can override
- [ ] SQLite WAL database per cluster (portable, zero-setup)
- [ ] CLI interface for submitting goals and checking status; pluggable Notifier for future messaging
- [ ] Factory cluster outputs a Docker Compose project (self-contained, deployable anywhere)
- [ ] Created clusters run fully independently with their own boss, DB, and agents

### Out of Scope

- Messaging platform integration (WhatsApp, Telegram, etc.) in v1 — CLI first; add as pluggable Notifier later
- Web UI dashboard — CLI sufficient for v1
- Cloud deployment automation — user runs `docker compose up` manually
- Shared infrastructure between clusters — each cluster is fully isolated

## Context

- Inspired by OpenClaw/Moltbot architecture (messaging-native autonomous agent) but designed from scratch with security, isolation, and programmatic cluster generation as first-class concerns
- OpenClaw's key security failures (plaintext secrets, no auth by default, malicious skill marketplace, cross-session leakage) explicitly avoided by design
- User is the "executive": submits goals, approves reviewed tasks, receives escalations from boss
- Boss is the "team lead": manages task lifecycle, coordinates agents, escalates blockers
- Workers are the "team": researcher, strategist, writer (roles configurable per cluster)
- Heartbeats are staggered so agents never access the database simultaneously

## Constraints

- **Tech stack**: Python (asyncio), Claude API (Anthropic SDK), SQLite WAL, Docker Compose
- **LLM**: Sonnet 4.6 for boss, Haiku 4.5 for workers by default; Opus 4.6 available for escalation
- **Security**: No plaintext secrets (env vars only), no shared credentials between clusters, per-agent tool allowlists
- **Isolation**: Each cluster has its own DB file, agent workspace, and Docker network

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python over TypeScript | Best AI ecosystem, asyncio maps directly to heartbeat/cron model | — Pending |
| SQLite WAL over Postgres | Portable file = portable cluster; WAL handles ≤10-agent concurrency | — Pending |
| Docker Compose per cluster | Factory output is self-contained, deployable anywhere with `docker compose up` | — Pending |
| CLI-first with pluggable Notifier | Simple, auditable, secure; Discord/Slack can be added without touching core logic | — Pending |
| All agents review all tasks | Boss assigns reviewers at creation; simpler and more flexible than role-based rules | — Pending |
| Factory cluster built first | It IS the primary product; demo cluster validates the runtime during factory dev | — Pending |

---
*Last updated: 2026-02-28 after initialization*
