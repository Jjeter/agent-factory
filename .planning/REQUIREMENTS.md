# Agent Factory — Requirements

*Last updated: 2026-02-28*

## Overview

The Agent Factory is a Python system that runs as a "factory cluster" and produces independent, self-contained AI agent clusters. Each produced cluster has its own boss, database, agents, and Docker Compose environment tailored to a specific domain goal.

---

## 1. Task State Machine

Every task in a cluster follows a strict linear state machine:

```
todo → in-progress → peer_review → review → approved
                         ↓
                    (rejected) → in-progress (re-assigned or re-worked)
```

| State | Who Sets It | Meaning |
|-------|-------------|---------|
| `todo` | Boss | Task created, awaiting assignment |
| `in-progress` | Assigned agent | Agent has claimed and started work |
| `peer_review` | Assigned agent | Agent submitted work for peer review |
| `review` | Boss | All peer reviews approved; awaiting user sign-off |
| `approved` | User (via CLI) | User accepted the output |
| `rejected` | Reviewer agent | Substantive peer rejection; returns to `in-progress` |

**Rules:**
- Only the boss may transition tasks from `peer_review` → `review`.
- Only the user may transition `review` → `approved`.
- Rejection by any assigned reviewer sends the task back to `in-progress`.
- A rejection increments `escalation_count`; at threshold, the boss escalates model tier.

---

## 2. Agent Heartbeat Model

All agents (boss and workers) run on independent heartbeat loops, staggered so no two agents access the database simultaneously.

### Worker Heartbeat (~10 minutes, staggered offsets)

1. **Authenticate**: Verify agent identity; write `status = 'working'` to `agent_status`.
2. **Peer review gate (priority)**: Fetch all tasks in `peer_review` where this agent is an assigned reviewer and their review is `pending`. For each:
   - Generate substantive feedback (minimum 2 sentences).
   - Post a `task_comment` of type `feedback`.
   - Set review status to `approved` or `rejected`.
   - If rejected, include a specific reason and required changes.
3. **Own tasks**: Fetch tasks assigned to this agent in `todo` or `in-progress`.
   - Move `todo` → `in-progress`.
   - Execute work (LLM call, tool use, document creation).
   - Save output as a `document` linked to the task.
   - Post a `task_comment` of type `progress`.
   - Move task to `peer_review`.
4. **Log activity**: Write an entry to `activity_log` with action and summary.
5. **Save local state**: Write heartbeat timestamp and current task IDs to a local state file.

### Boss Heartbeat (special authorities, ~10 minutes, offset 0)

In addition to worker steps, boss performs:

1. **Promote to review**: For each task in `peer_review`, check if all assigned reviewers have status `approved`. If yes, move task → `review`, notify user via Notifier.
2. **Detect blocked tasks**: If a task has been `in-progress` for > N minutes without a `task_comment`, mark it stuck. Investigate by reading the last comments. If still blocked, reassign to another agent or escalate to user.
3. **Goal analysis**: On a cron schedule (e.g., every 3 heartbeats), fetch the active goal and all completed tasks. Determine if new tasks are needed to achieve the goal. Create tasks with priorities and reviewer assignments.
4. **Escalation handling**: If a task's `escalation_count` exceeds the threshold, update `model_tier` to the next level (haiku → sonnet → opus).
5. **Priority adjustment**: Re-order task priorities based on goal progress.

### Heartbeat Stagger Configuration

```yaml
# Example stagger for 3 workers + 1 boss
boss:   offset: 0 min
agent1: offset: 2.5 min
agent2: offset: 5 min
agent3: offset: 7.5 min
```

---

## 3. Model Escalation

| Tier | Model | Default Use |
|------|-------|-------------|
| `haiku` | claude-haiku-4-5-20251001 | All worker tasks by default |
| `sonnet` | claude-sonnet-4-6 | Boss; worker tasks escalated after 1 rejection |
| `opus` | claude-opus-4-6 | Critical escalations; boss explicit override |

**Escalation rules:**
- Boss sets initial `model_tier` per task at creation time.
- Any peer review rejection increments `escalation_count`.
- When `escalation_count` reaches the configured threshold (default: 2), the boss upgrades `model_tier` for the next attempt.
- Escalation is logged in `activity_log` with reason.

---

## 4. Database Schema (SQLite WAL)

WAL mode is mandatory. Each cluster has exactly one database file.

### `goals`
```sql
CREATE TABLE goals (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',  -- active | completed | archived
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### `tasks`
```sql
CREATE TABLE tasks (
    id               TEXT PRIMARY KEY,
    goal_id          TEXT NOT NULL REFERENCES goals(id),
    title            TEXT NOT NULL,
    description      TEXT NOT NULL,
    assigned_to      TEXT,                  -- agent_id
    status           TEXT NOT NULL DEFAULT 'todo',
    priority         INTEGER NOT NULL DEFAULT 50,
    model_tier       TEXT NOT NULL DEFAULT 'haiku',
    escalation_count INTEGER NOT NULL DEFAULT 0,
    stuck_since      TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### `task_comments`
```sql
CREATE TABLE task_comments (
    id           TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL REFERENCES tasks(id),
    agent_id     TEXT NOT NULL,
    comment_type TEXT NOT NULL,  -- feedback | approval | rejection | progress
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### `task_reviews`
```sql
CREATE TABLE task_reviews (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    reviewer_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(task_id, reviewer_id)
);
```

### `agent_status`
```sql
CREATE TABLE agent_status (
    id             TEXT PRIMARY KEY,  -- agent_id
    agent_role     TEXT NOT NULL,     -- boss | researcher | writer | strategist | ...
    status         TEXT NOT NULL DEFAULT 'idle',  -- idle | working | error
    last_heartbeat TEXT,
    current_task   TEXT REFERENCES tasks(id)
);
```

### `documents`
```sql
CREATE TABLE documents (
    id         TEXT PRIMARY KEY,
    task_id    TEXT REFERENCES tasks(id),
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### `activity_log`
```sql
CREATE TABLE activity_log (
    id         TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL,
    task_id    TEXT REFERENCES tasks(id),
    action     TEXT NOT NULL,  -- task_claimed | task_submitted | review_approved | review_rejected | task_escalated | ...
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

---

## 5. Factory Output Structure

When the factory cluster creates a new cluster, it outputs a self-contained project directory:

```
clusters/<cluster-name>/
├── docker-compose.yml          # All services: boss, agent-N, shared volume
├── .env.example                # Required env vars (ANTHROPIC_API_KEY, CLUSTER_NAME, etc.)
├── config/
│   ├── cluster.yaml            # domain, goal, agent roles, heartbeat offsets
│   └── agents/
│       ├── boss.yaml           # system prompt template, tool allowlist, authorities
│       ├── researcher.yaml
│       ├── writer.yaml
│       └── strategist.yaml     # (role set is goal-dependent)
├── db/
│   └── schema.sql              # Canonical schema for this cluster
├── runtime/                    # Agent runtime Python package (copied from factory)
│   ├── __init__.py
│   ├── heartbeat.py
│   ├── database.py
│   ├── models.py
│   ├── notifier.py
│   └── cli.py
└── launch.sh                   # docker compose up -d with env validation
```

**Factory requirements:**
- Factory reads a natural-language goal and domain description.
- Factory's boss decomposes the goal into the required agent roles.
- Factory generates `cluster.yaml`, all `agents/*.yaml` configs, and `docker-compose.yml`.
- Factory copies the shared runtime into the output directory.
- Factory seeds the cluster DB with the initial goal.
- Output cluster is runnable with `./launch.sh` on any Docker-capable host.

---

## 6. CLI Interface

### Factory CLI (manages factory cluster)

```
agent-factory create <goal>          # Submit a goal to the factory; creates a new cluster
agent-factory list                   # List all created clusters with status
agent-factory status <cluster-name>  # Show cluster's goal, task counts, agent status
agent-factory approve <cluster-name> <task-id>  # Approve a task in review state
agent-factory logs <cluster-name> [--agent <id>]  # Tail activity logs
```

### Cluster CLI (bundled into each cluster's runtime)

```
cluster goal set "<description>"     # Seed or update the active goal
cluster tasks list [--status <s>]    # List tasks with optional status filter
cluster tasks show <task-id>         # Show task details, comments, and review status
cluster approve <task-id>            # Approve task in 'review' state
cluster agents status                # Show all agents and last heartbeat
cluster logs [--tail N]              # Recent activity log entries
```

---

## 7. Notifier Interface

The Notifier is a pluggable interface. V1 ships with a CLI (stdout) implementation only.

```python
class Notifier(Protocol):
    async def notify_review_ready(self, task_id: str, task_title: str) -> None: ...
    async def notify_escalation(self, task_id: str, reason: str) -> None: ...
    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None: ...
```

**Implementations:**
- `StdoutNotifier` — prints to console (V1 default)
- `DiscordNotifier` — sends to configured webhook (future)
- `SlackNotifier` — sends to Slack webhook (future)

---

## 8. Security Requirements

- **No plaintext secrets**: All API keys and credentials are loaded from environment variables only; `.env` files are gitignored.
- **Per-cluster isolation**: Each cluster has its own DB file and Docker network; no shared credentials.
- **Per-agent tool allowlists**: Each agent's `yaml` config lists exactly which tools it may call.
- **No cross-cluster access**: Agents cannot read or write to another cluster's database.
- **No remote code execution via config**: Cluster YAML files are data-only; no eval or shell injection vectors.
- **Secrets rotation**: Factory never stores API keys; they are injected at launch time via env vars.

---

## 9. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Heartbeat jitter | ±30 seconds random to prevent thundering herd |
| SQLite WAL timeout | 5 seconds (raises error, agent retries next heartbeat) |
| Max concurrent DB writers | 1 (enforced by stagger design) |
| Task stuck threshold | 30 minutes without a comment |
| Escalation threshold | 2 peer rejections |
| Cluster creation time | < 60 seconds end-to-end |
| Supported Python version | 3.12+ |

---

## 10. Out of Scope (V1)

- Web UI dashboard
- Messaging platform integration (WhatsApp, Telegram)
- Cloud deployment automation
- Shared infrastructure between clusters
- Agent memory / vector store
- Multi-goal clusters (one active goal per cluster in V1)
