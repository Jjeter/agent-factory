"""Tests for runtime.models — Pydantic entity models and enums.

Covers: MDL-01 (Goal round-trip), MDL-02 (Task rejects invalid status),
        MDL-03 (all 7 models construct), SM-04 (rejected not in TaskStatus values).

pytest.importorskip("runtime.models") at module level: if the module does not
exist yet, the entire file is skipped cleanly (no ImportError on collection).
"""
import pytest

pytest.importorskip("runtime.models", reason="runtime.models not yet implemented (Plan 03)")

from runtime.models import (  # noqa: E402 — import after importorskip guard
    ActivityLog,
    AgentStatus,
    Document,
    Goal,
    Task,
    TaskComment,
    TaskReview,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# SM-04: rejected is not a TaskStatus value
# ---------------------------------------------------------------------------


def test_task_status_no_rejected_value() -> None:
    """SM-04: 'rejected' must not appear as a TaskStatus enum value."""
    values = [s.value for s in TaskStatus]
    assert "rejected" not in values, (
        f"'rejected' must not be a TaskStatus value; found: {values}"
    )


def test_task_status_has_five_values() -> None:
    """TaskStatus has exactly 5 values: todo, in-progress, peer_review, review, approved."""
    values = [s.value for s in TaskStatus]
    assert len(values) == 5
    assert set(values) == {"todo", "in-progress", "peer_review", "review", "approved"}


# ---------------------------------------------------------------------------
# MDL-01: Goal model round-trips id, title, description, status, created_at
# ---------------------------------------------------------------------------


def test_goal_model_roundtrip() -> None:
    """MDL-01: Goal round-trips via model_dump / model_validate."""
    goal = Goal(title="Alpha", description="First goal")
    assert goal.title == "Alpha"
    assert goal.description == "First goal"
    assert goal.status == "active"

    data = goal.model_dump()
    goal2 = Goal.model_validate(data)
    assert goal2.id == goal.id
    assert goal2.status == goal.status


# ---------------------------------------------------------------------------
# MDL-02: Task rejects invalid status string
# ---------------------------------------------------------------------------


def test_task_rejects_invalid_status() -> None:
    """MDL-02: Task raises ValidationError for status='rejected' (not a valid value)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Task(
            goal_id="some-goal-id",
            title="Bad task",
            description="Task with bad status",
            status="rejected",
        )


def test_task_rejects_arbitrary_invalid_status() -> None:
    """Task raises ValidationError for any unknown status string."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Task(
            goal_id="g",
            title="T",
            description="D",
            status="not-a-real-state",
        )


# ---------------------------------------------------------------------------
# MDL-03: All 7 Pydantic models construct without error
# ---------------------------------------------------------------------------


def test_all_models_construct() -> None:
    """MDL-03: All 7 models instantiate with minimal required fields."""
    import uuid

    goal_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    goal = Goal(title="G", description="Desc")
    assert goal.id

    task = Task(goal_id=goal_id, title="T", description="D")
    assert task.id

    comment = TaskComment(
        task_id=task_id,
        agent_id=agent_id,
        comment_type="progress",
        content="Working on it",
    )
    assert comment.id

    review = TaskReview(task_id=task_id, reviewer_id=agent_id)
    assert review.id

    agent_status = AgentStatus(agent_role="boss")
    assert agent_status.id

    doc = Document(
        title="Doc",
        content="Content",
        created_by=agent_id,
    )
    assert doc.id

    log = ActivityLog(agent_id=agent_id, action="task_claimed")
    assert log.id


def test_goal_defaults() -> None:
    """Goal has correct defaults: status=active, auto id and created_at."""
    g = Goal(title="T", description="D")
    assert g.status == "active"
    assert g.id is not None
    assert g.created_at is not None


def test_task_defaults() -> None:
    """Task has correct defaults: status=todo, priority=50, model_tier=haiku, escalation_count=0."""
    t = Task(goal_id="g", title="T", description="D")
    assert t.status == "todo"
    assert t.priority == 50
    assert t.model_tier == "haiku"
    assert t.escalation_count == 0
    assert t.assigned_to is None
    assert t.stuck_since is None


def test_task_review_defaults() -> None:
    """TaskReview default status is pending."""
    tr = TaskReview(task_id="t", reviewer_id="r")
    assert tr.status == "pending"


def test_agent_status_defaults() -> None:
    """AgentStatus defaults: status=idle, last_heartbeat=None, current_task=None."""
    a = AgentStatus(agent_role="boss")
    assert a.status == "idle"
    assert a.last_heartbeat is None
    assert a.current_task is None


def test_document_defaults() -> None:
    """Document defaults: version=1, task_id=None."""
    d = Document(title="doc", content="text", created_by="agent")
    assert d.version == 1
    assert d.task_id is None


def test_activity_log_defaults() -> None:
    """ActivityLog defaults: task_id=None, details=None."""
    al = ActivityLog(agent_id="agent", action="task_claimed")
    assert al.task_id is None
    assert al.details is None


def test_str_enum_status_is_string() -> None:
    """str, Enum pattern: task.status is an instance of str (serializes to TEXT)."""
    t = Task(goal_id="g", title="T", description="D")
    assert isinstance(t.status, str)
    assert t.status == "todo"
