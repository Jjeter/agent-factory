# Agent Factory

## What it is

Agent Factory is a Python system that accepts a natural-language goal and generates a self-contained AI agent cluster. Each cluster has its own boss, worker agents, peer review pipeline, and Docker Compose environment. The factory itself runs as an agentic cluster that decomposes your goal into agent roles and outputs a ready-to-launch project directory.

## Quick Start

```bash
pip install -e .
export ANTHROPIC_API_KEY=sk-...

# Run the live demo (real LLM calls — takes a few minutes)
agent-factory demo

# Once a task reaches 'review', approve it
agent-factory approve demo-date-arithmetic <task-id>

# Check what was built
sqlite3 clusters/demo-date-arithmetic/db/cluster.db \
  "SELECT title, status FROM tasks WHERE status='approved'"
```

## How it works

```
you
 |
 v
agent-factory create "your goal"
 |
 v
Factory Cluster  ─────────────────────────────────────
│  FactoryBossAgent   (decomposes goal → agent roles) │
│  FactoryResearcher  (identifies tool dependencies)   │
│  FactoryExecutor    (writes artifact files)          │
└─────────────────────────────────────────────────────
 |
 v
clusters/<name>/          ← self-contained project
├── docker-compose.yml
├── config/agents/*.yaml  ← per-agent system prompts + tool allowlists
├── db/cluster.db         ← seeded SQLite WAL database
└── launch.sh             ← docker compose up + env validation
 |
 v
./launch.sh               ← starts your cluster
 |
 v
Running Cluster  ─────────────────────────────────────
│  BossAgent      (heartbeat: decompose → assign → promote)  │
│  WorkerAgents   (heartbeat: execute → peer review)          │
│  Peer Review    (todo → in-progress → peer_review → review)  │
└─────────────────────────────────────────────────────
 |
 v
agent-factory approve <cluster> <task-id>  ← user sign-off
```

### Demo walkthrough

Run `agent-factory demo` to see the system in action. The demo creates a `demo-date-arithmetic` cluster with a pre-seeded goal — implementing a date arithmetic module — and starts the boss and coder agents against it.

What you will see:
- A live status line that updates in place, showing `todo / in-progress / peer_review / review / approved` task counts as they change
- The boss agent decomposing the goal into concrete coding tasks and assigning them to the coder
- The coder agent executing each task and submitting output for peer review
- The boss promoting approved tasks through the review pipeline

Once a task reaches `review` status, use `agent-factory approve demo-date-arithmetic <task-id>` to give final sign-off. The demo exits automatically when the first task is approved.

Run `agent-factory approve --help`, `agent-factory logs --help`, and `agent-factory demo --help` for the full subcommand reference.
