"""Tests for runtime/models.py — Pydantic v2 entity models and enums.

Test IDs (from plan):
  MDL-01: All 7 models construct with minimal required fields
  MDL-02: TaskStatus has exactly 5 values; "rejected" is absent
  MDL-03: Invalid status string raises ValidationError
  MDL-04: isinstance(model.status, str) is True (use_enum_values)
  MDL-05: model_validate() round-trips from dict correctly
  MDL-06: GoalStatus, ReviewStatus, AgentStatusEnum values match SQLite TEXT
  MDL-07: Default fields are auto-generated (id, created_at)
"""

import pytest
from pydantic import ValidationError

from runtime.models import (
    ActivityLog,
    AgentStatus,
    AgentStatusEnum,
    Document,
    Goal,
    GoalStatus,
    ReviewStatus,
    Task,
    TaskComment,
    TaskReview,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# MDL-02: TaskStatus enum shape
# ---------------------------------------------------------------------------


class TestTaskStatusEnum:
    def test_task_status_has_exactly_five_values(self):
        values = [s.value for s in TaskStatus]
        assert len(values) == 5

    def test_task_status_does_not_include_rejected(self):
        values = [s.value for s in TaskStatus]
        assert "rejected" not in values

    def test_task_status_expected_values(self):
        assert TaskStatus.TODO == "todo"
        assert TaskStatus.IN_PROGRESS == "in-progress"
        assert TaskStatus.PEER_REVIEW == "peer_review"
        assert TaskStatus.REVIEW == "review"
        assert TaskStatus.APPROVED == "approved"


class TestGoalStatusEnum:
    def test_goal_status_expected_values(self):
        assert GoalStatus.ACTIVE == "active"
        assert GoalStatus.COMPLETED == "completed"
        assert GoalStatus.ARCHIVED == "archived"


class TestReviewStatusEnum:
    def test_review_status_expected_values(self):
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"


class TestAgentStatusEnum:
    def test_agent_status_enum_expected_values(self):
        assert AgentStatusEnum.IDLE == "idle"
        assert AgentStatusEnum.WORKING == "working"
        assert AgentStatusEnum.ERROR == "error"


# ---------------------------------------------------------------------------
# MDL-01: All 7 models construct with minimal required fields
# ---------------------------------------------------------------------------


class TestGoalModel:
    def test_goal_constructs_with_required_fields(self):
        g = Goal(title="Test Goal", description="Goal description")
        assert g.title == "Test Goal"
        assert g.description == "Goal description"

    def test_goal_has_auto_id(self):
        g = Goal(title="T", description="D")
        assert g.id is not None
        assert len(g.id) == 36  # UUID4 format

    def test_goal_has_auto_created_at(self):
        g = Goal(title="T", description="D")
        assert g.created_at is not None
        assert "T" in g.created_at or "+" in g.created_at  # ISO 8601

    def test_goal_default_status_is_active(self):
        g = Goal(title="T", description="D")
        assert g.status == "active"

    def test_goal_ids_are_unique(self):
        g1 = Goal(title="T", description="D")
        g2 = Goal(title="T", description="D")
        assert g1.id != g2.id


class TestTaskModel:
    def test_task_constructs_with_required_fields(self):
        t = Task(goal_id="some-goal-id", title="Test Task", description="Task description")
        assert t.goal_id == "some-goal-id"
        assert t.title == "Test Task"
        assert t.description == "Task description"

    def test_task_default_status_is_todo(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.status == "todo"

    def test_task_default_priority_is_50(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.priority == 50

    def test_task_default_model_tier_is_haiku(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.model_tier == "haiku"

    def test_task_default_escalation_count_is_zero(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.escalation_count == 0

    def test_task_assigned_to_defaults_to_none(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.assigned_to is None

    def test_task_stuck_since_defaults_to_none(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.stuck_since is None

    def test_task_accepts_valid_status_string(self):
        t = Task(goal_id="g", title="T", description="D", status="todo")
        assert t.status == "todo"

    def test_task_has_auto_id(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.id is not None
        assert len(t.id) == 36


class TestTaskCommentModel:
    def test_task_comment_constructs_with_required_fields(self):
        tc = TaskComment(
            task_id="task-id",
            agent_id="agent-id",
            comment_type="feedback",
            content="Great work!",
        )
        assert tc.task_id == "task-id"
        assert tc.agent_id == "agent-id"
        assert tc.comment_type == "feedback"
        assert tc.content == "Great work!"

    def test_task_comment_has_auto_id(self):
        tc = TaskComment(
            task_id="t", agent_id="a", comment_type="feedback", content="c"
        )
        assert tc.id is not None


class TestTaskReviewModel:
    def test_task_review_constructs_with_required_fields(self):
        tr = TaskReview(task_id="task-id", reviewer_id="reviewer-id")
        assert tr.task_id == "task-id"
        assert tr.reviewer_id == "reviewer-id"

    def test_task_review_default_status_is_pending(self):
        tr = TaskReview(task_id="t", reviewer_id="r")
        assert tr.status == "pending"

    def test_task_review_has_auto_id(self):
        tr = TaskReview(task_id="t", reviewer_id="r")
        assert tr.id is not None


class TestAgentStatusModel:
    def test_agent_status_constructs_with_required_fields(self):
        a = AgentStatus(id="boss", agent_role="boss")
        assert a.id == "boss"
        assert a.agent_role == "boss"

    def test_agent_status_default_status_is_idle(self):
        a = AgentStatus(id="boss", agent_role="boss")
        assert a.status == "idle"

    def test_agent_status_last_heartbeat_defaults_to_none(self):
        a = AgentStatus(id="boss", agent_role="boss")
        assert a.last_heartbeat is None

    def test_agent_status_current_task_defaults_to_none(self):
        a = AgentStatus(id="boss", agent_role="boss")
        assert a.current_task is None


class TestDocumentModel:
    def test_document_constructs_with_required_fields(self):
        d = Document(title="My Doc", content="Some text", created_by="agent1")
        assert d.title == "My Doc"
        assert d.content == "Some text"
        assert d.created_by == "agent1"

    def test_document_task_id_defaults_to_none(self):
        d = Document(title="doc", content="text", created_by="a")
        assert d.task_id is None

    def test_document_version_defaults_to_one(self):
        d = Document(title="doc", content="text", created_by="a")
        assert d.version == 1

    def test_document_has_auto_id(self):
        d = Document(title="doc", content="text", created_by="a")
        assert d.id is not None


class TestActivityLogModel:
    def test_activity_log_constructs_with_required_fields(self):
        al = ActivityLog(agent_id="agent1", action="task_claimed")
        assert al.agent_id == "agent1"
        assert al.action == "task_claimed"

    def test_activity_log_task_id_defaults_to_none(self):
        al = ActivityLog(agent_id="a", action="task_claimed")
        assert al.task_id is None

    def test_activity_log_details_defaults_to_none(self):
        al = ActivityLog(agent_id="a", action="task_claimed")
        assert al.details is None

    def test_activity_log_has_auto_id(self):
        al = ActivityLog(agent_id="a", action="task_claimed")
        assert al.id is not None


# ---------------------------------------------------------------------------
# MDL-03: Invalid status raises ValidationError
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_invalid_task_status_raises_validation_error(self):
        with pytest.raises(ValidationError):
            Task(goal_id="g", title="t", description="d", status="invalid")

    def test_rejected_not_valid_task_status(self):
        with pytest.raises(ValidationError):
            Task(goal_id="g", title="t", description="d", status="rejected")

    def test_invalid_goal_status_raises_validation_error(self):
        with pytest.raises(ValidationError):
            Goal(title="t", description="d", status="bad_status")

    def test_invalid_review_status_raises_validation_error(self):
        with pytest.raises(ValidationError):
            TaskReview(task_id="t", reviewer_id="r", status="bad_status")

    def test_invalid_agent_status_raises_validation_error(self):
        with pytest.raises(ValidationError):
            AgentStatus(id="a", agent_role="boss", status="bad_status")


# ---------------------------------------------------------------------------
# MDL-04: use_enum_values=True — status fields are plain strings
# ---------------------------------------------------------------------------


class TestStrEnumBehavior:
    def test_task_status_is_str_instance(self):
        t = Task(goal_id="g", title="T", description="D")
        assert isinstance(t.status, str)

    def test_goal_status_is_str_instance(self):
        g = Goal(title="T", description="D")
        assert isinstance(g.status, str)

    def test_task_review_status_is_str_instance(self):
        tr = TaskReview(task_id="t", reviewer_id="r")
        assert isinstance(tr.status, str)

    def test_agent_status_status_is_str_instance(self):
        a = AgentStatus(id="a", agent_role="boss")
        assert isinstance(a.status, str)

    def test_task_status_equals_string_literal(self):
        t = Task(goal_id="g", title="T", description="D")
        assert t.status == "todo"  # not TaskStatus.TODO

    def test_goal_status_equals_string_literal(self):
        g = Goal(title="T", description="D")
        assert g.status == "active"


# ---------------------------------------------------------------------------
# MDL-05: model_validate round-trip
# ---------------------------------------------------------------------------


class TestModelValidate:
    def test_goal_round_trips_from_dict(self):
        data = {
            "id": "some-uuid",
            "title": "My Goal",
            "description": "Do something",
            "status": "active",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        g = Goal.model_validate(data)
        assert g.id == "some-uuid"
        assert g.title == "My Goal"
        assert g.status == "active"

    def test_task_round_trips_from_dict(self):
        data = {
            "id": "task-uuid",
            "goal_id": "goal-uuid",
            "title": "My Task",
            "description": "Do this",
            "assigned_to": None,
            "status": "in-progress",
            "priority": 75,
            "model_tier": "sonnet",
            "escalation_count": 1,
            "stuck_since": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        t = Task.model_validate(data)
        assert t.id == "task-uuid"
        assert t.status == "in-progress"
        assert t.priority == 75

    def test_agent_status_round_trips_from_dict(self):
        data = {
            "id": "boss",
            "agent_role": "boss",
            "status": "working",
            "last_heartbeat": "2026-01-01T00:00:00+00:00",
            "current_task": None,
        }
        a = AgentStatus.model_validate(data)
        assert a.id == "boss"
        assert a.status == "working"

    def test_model_dump_returns_plain_strings(self):
        t = Task(goal_id="g", title="T", description="D")
        d = t.model_dump()
        assert isinstance(d["status"], str)
        assert d["status"] == "todo"
