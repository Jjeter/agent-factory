-- Agent Factory cluster database schema
-- WAL mode preamble: run on every db up
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- goals: one active goal per cluster (V1)
CREATE TABLE IF NOT EXISTS goals (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',   -- active | completed | archived
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- tasks: work items decomposed from the goal
CREATE TABLE IF NOT EXISTS tasks (
    id               TEXT PRIMARY KEY,
    goal_id          TEXT NOT NULL REFERENCES goals(id),
    title            TEXT NOT NULL,
    description      TEXT NOT NULL,
    assigned_to      TEXT,                           -- agent_id; nullable until assigned
    status           TEXT NOT NULL DEFAULT 'todo',   -- todo | in-progress | peer_review | review | approved
    priority         INTEGER NOT NULL DEFAULT 50,
    model_tier       TEXT NOT NULL DEFAULT 'haiku',  -- haiku | sonnet | opus
    escalation_count INTEGER NOT NULL DEFAULT 0,
    stuck_since      TEXT,                           -- ISO 8601; nullable
    reviewer_roles   TEXT,                           -- JSON list e.g. '["researcher","strategist"]'
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- task_comments: progress notes, feedback, approvals, rejections
CREATE TABLE IF NOT EXISTS task_comments (
    id           TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL REFERENCES tasks(id),
    agent_id     TEXT NOT NULL,
    comment_type TEXT NOT NULL,   -- feedback | approval | rejection | progress
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- task_reviews: peer review records (one per reviewer per task)
CREATE TABLE IF NOT EXISTS task_reviews (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    reviewer_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(task_id, reviewer_id)
);

-- agent_status: last known state for each agent in the cluster
CREATE TABLE IF NOT EXISTS agent_status (
    agent_id       TEXT PRIMARY KEY,   -- unique agent identifier
    agent_role     TEXT NOT NULL,      -- boss | researcher | writer | strategist | ...
    status         TEXT NOT NULL DEFAULT 'idle',   -- idle | working | error
    last_heartbeat TEXT,               -- ISO 8601; nullable until first heartbeat
    current_task   TEXT REFERENCES tasks(id)       -- nullable
);

-- documents: output artifacts created by agents for tasks
CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    task_id    TEXT REFERENCES tasks(id),   -- nullable: cluster-level docs have no task
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- activity_log: append-only audit trail of all agent actions
CREATE TABLE IF NOT EXISTS activity_log (
    id         TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL,
    task_id    TEXT REFERENCES tasks(id),   -- nullable: cluster-level actions
    action     TEXT NOT NULL,               -- task_claimed | task_submitted | review_approved | review_rejected | task_escalated | ...
    details    TEXT,                        -- nullable JSON or free-text detail
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for hot query paths
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_goal_id ON tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_agent ON activity_log(agent_id);
