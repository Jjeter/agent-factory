"""Pydantic v2 data models for all Agent Factory domain entities.

All models use:
- ConfigDict(use_enum_values=True): status fields serialize to plain str values,
  matching the TEXT values stored in SQLite (e.g., task.status == "todo").
- UUID default_factory: unique id per instance without explicit passing.
- ISO 8601 UTC timestamps via datetime.now(timezone.utc).isoformat().
- model_validate(dict(row)): round-trip from aiosqlite.Row dicts.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums — all are str Enums so comparisons with raw strings work
# ---------------------------------------------------------------------------


class GoalStatus(str, Enum):
    """Lifecycle states for a cluster goal."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    """Task state machine values.

    NOTE: "rejected" is NOT a task status. Rejection is an action recorded
    as a task_comment of type "feedback"; the task returns to "in-progress".
    """

    TODO = "todo"
    IN_PROGRESS = "in-progress"
    PEER_REVIEW = "peer_review"
    REVIEW = "review"
    APPROVED = "approved"


class ReviewStatus(str, Enum):
    """Status of a peer review on a specific task."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentStatusEnum(str, Enum):
    """Current operational state of an agent process."""

    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Helper factory — avoids repeating lambda in every Field()
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Entity models
# ---------------------------------------------------------------------------


class Goal(BaseModel):
    """A cluster's top-level objective."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)
    title: str
    description: str
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = Field(default_factory=_now_iso)


class Task(BaseModel):
    """A unit of work assigned to an agent within a goal."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)
    goal_id: str
    title: str
    description: str
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: int = 50
    model_tier: str = "haiku"
    escalation_count: int = 0
    stuck_since: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class TaskComment(BaseModel):
    """A comment posted to a task by an agent during execution or review."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)
    task_id: str
    agent_id: str
    comment_type: str  # feedback | approval | rejection | progress (extensible)
    content: str
    created_at: str = Field(default_factory=_now_iso)


class TaskReview(BaseModel):
    """A peer review record linking a reviewer to a task."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)
    task_id: str
    reviewer_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: str = Field(default_factory=_now_iso)


class AgentStatus(BaseModel):
    """Live operational state of an agent process, persisted to agent_status table."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)  # agent_id; defaults to UUID if not set explicitly
    agent_role: str
    status: AgentStatusEnum = AgentStatusEnum.IDLE
    last_heartbeat: Optional[str] = None
    current_task: Optional[str] = None  # FK to tasks.id


class Document(BaseModel):
    """An artifact produced by an agent in response to a task."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)
    task_id: Optional[str] = None  # FK to tasks.id; None for standalone documents
    title: str
    content: str
    version: int = 1
    created_by: str
    created_at: str = Field(default_factory=_now_iso)


class ActivityLog(BaseModel):
    """Append-only audit trail of agent actions."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=_uuid)
    agent_id: str
    task_id: Optional[str] = None  # FK to tasks.id; None for goal-level actions
    action: str  # task_claimed | task_submitted | review_approved | review_rejected | ...
    details: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
