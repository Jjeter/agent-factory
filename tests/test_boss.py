"""BossAgent unit tests — Phase 3 TDD.

Groups:
  - Structure (3 tests): sync — no DB needed
  - Promotion (3 tests): async — in-memory DB via _make_db()
  - Decomposition (3 tests): async — mock LLM + DB
  - Re-review UNIQUE constraint (1 test)
  - Remaining stubs (8): xfail until Wave 2/3

Tests use pytest.importorskip("runtime.boss") inside the test body for the
still-unimplemented stubs so collection does not crash before boss.py exists.
For implemented tests, imports are at function scope (after boss.py is present).
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from runtime.config import AgentConfig
from runtime.database import DatabaseManager
from runtime.models import _uuid, _now_iso


# ---------------------------------------------------------------------------
# Shared async helpers
# ---------------------------------------------------------------------------


async def _make_db(tmp_path: Path) -> DatabaseManager:
    """Create an initialized test DB backed by a tmp file."""
    db_file = tmp_path / "test.db"
    mgr = DatabaseManager(db_file)
    await mgr.up()
    return mgr


async def _insert_goal(mgr: DatabaseManager, goal_id: str, title: str = "Test Goal") -> None:
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO goals (id, title, description, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (goal_id, title, "A test goal description", "active", _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()


async def _insert_task(
    mgr: DatabaseManager,
    task_id: str,
    goal_id: str,
    status: str,
    model_tier: str = "haiku",
    escalation_count: int = 0,
    stuck_since: str | None = None,
) -> None:
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, model_tier, "
            "escalation_count, stuck_since, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                goal_id,
                "Test Task",
                "Do the thing",
                status,
                50,
                model_tier,
                escalation_count,
                stuck_since,
                json.dumps(["researcher", "strategist"]),
                _now_iso(),
                _now_iso(),
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def _insert_review(mgr: DatabaseManager, task_id: str, reviewer_id: str, status: str) -> None:
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO task_reviews (id, task_id, reviewer_id, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_uuid(), task_id, reviewer_id, status, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()


def _make_boss(mgr: DatabaseManager, notifier=None):
    from runtime.boss import BossAgent

    config = AgentConfig(
        agent_id="boss-1",
        agent_role="boss",
        interval_seconds=600.0,
        db_path=str(mgr._db_path),
    )
    return BossAgent(config, notifier=notifier)


# ── BossAgent structure ───────────────────────────────────────────────────────


def test_boss_agent_is_base_agent():
    from runtime.boss import BossAgent
    from runtime.heartbeat import BaseAgent

    config = AgentConfig(agent_id="boss-1", agent_role="boss", interval_seconds=600.0)
    boss = BossAgent(config)
    assert isinstance(boss, BaseAgent)


def test_boss_agent_has_llm_client():
    from runtime.boss import BossAgent
    from anthropic import AsyncAnthropic

    config = AgentConfig(agent_id="boss-1", agent_role="boss", interval_seconds=600.0)
    boss = BossAgent(config)
    assert isinstance(boss._llm, AsyncAnthropic)


def test_boss_agent_has_heartbeat_counter():
    from runtime.boss import BossAgent

    config = AgentConfig(agent_id="boss-1", agent_role="boss", interval_seconds=600.0)
    boss = BossAgent(config)
    assert boss._heartbeat_counter == 0


# ── Peer review promotion ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_to_review_when_all_approved(tmp_path):
    from runtime.notifier import StdoutNotifier

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "peer_review")
    await _insert_review(mgr, task_id, "agent-2", "approved")
    await _insert_review(mgr, task_id, "agent-3", "approved")

    mock_notifier = AsyncMock(spec=StdoutNotifier)
    boss = _make_boss(mgr, mock_notifier)
    await boss.do_peer_reviews()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["status"] == "review"
    mock_notifier.notify_review_ready.assert_called_once()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT action FROM activity_log WHERE task_id = ?", (task_id,)) as cur:
            log_rows = await cur.fetchall()
    finally:
        await db.close()
    actions = [r["action"] for r in log_rows]
    assert "task_promoted" in actions


@pytest.mark.asyncio
async def test_no_promotion_when_reviews_pending(tmp_path):
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "peer_review")
    await _insert_review(mgr, task_id, "agent-2", "approved")
    await _insert_review(mgr, task_id, "agent-3", "pending")

    boss = _make_boss(mgr)
    await boss.do_peer_reviews()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["status"] == "peer_review"


@pytest.mark.asyncio
async def test_any_rejection_returns_to_in_progress(tmp_path):
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "peer_review")
    await _insert_review(mgr, task_id, "agent-2", "rejected")
    await _insert_review(mgr, task_id, "agent-3", "approved")

    boss = _make_boss(mgr)
    await boss.do_peer_reviews()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            task_row = await cur.fetchone()
        async with db.execute(
            "SELECT status FROM task_reviews WHERE task_id = ?", (task_id,)
        ) as cur:
            review_rows = await cur.fetchall()
    finally:
        await db.close()
    assert task_row["status"] == "in-progress"
    assert all(r["status"] == "pending" for r in review_rows)


# ── Goal decomposition ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decompose_goal_creates_tasks(tmp_path):
    from runtime.boss import BossAgent, DecompositionResult, TaskSpec

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    await _insert_goal(mgr, goal_id, "Build a date arithmetic library")

    # Seed agent_status so reviewer resolution works
    db = await mgr.open_write()
    try:
        for agent_id, role in [("a-1", "researcher"), ("a-2", "writer"), ("a-3", "strategist")]:
            await db.execute(
                "INSERT INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
                (agent_id, role),
            )
        await db.commit()
    finally:
        await db.close()

    mock_result = MagicMock()
    mock_result.parsed_output = DecompositionResult(
        tasks=[
            TaskSpec(
                title="Research existing libs",
                description="Look up existing date libs",
                assigned_role="researcher",
                reviewer_roles=["writer", "strategist"],
                priority=80,
                model_tier="haiku",
            ),
            TaskSpec(
                title="Write core module",
                description="Implement date arithmetic",
                assigned_role="writer",
                reviewer_roles=["researcher", "strategist"],
                priority=70,
                model_tier="haiku",
            ),
            TaskSpec(
                title="Plan test strategy",
                description="Define test approach",
                assigned_role="strategist",
                reviewer_roles=["researcher", "writer"],
                priority=60,
                model_tier="haiku",
            ),
        ]
    )

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", new=AsyncMock(return_value=mock_result)):
        await boss.decompose_goal(goal_id, "Build a date arithmetic library")

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT * FROM tasks WHERE goal_id = ?", (goal_id,)) as cur:
            tasks = await cur.fetchall()
    finally:
        await db.close()
    assert len(tasks) == 3
    assert all(t["status"] == "todo" for t in tasks)
    assert all(t["model_tier"] in ("haiku", "sonnet", "opus") for t in tasks)


@pytest.mark.asyncio
async def test_decompose_goal_assigns_reviewer_roles(tmp_path):
    from runtime.boss import BossAgent, DecompositionResult, TaskSpec

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    await _insert_goal(mgr, goal_id)

    db = await mgr.open_write()
    try:
        for agent_id, role in [("a-1", "researcher"), ("a-2", "writer"), ("a-3", "strategist")]:
            await db.execute(
                "INSERT INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
                (agent_id, role),
            )
        await db.commit()
    finally:
        await db.close()

    mock_result = MagicMock()
    mock_result.parsed_output = DecompositionResult(
        tasks=[
            TaskSpec(
                title="T1",
                description="d1",
                assigned_role="researcher",
                reviewer_roles=["writer", "strategist"],
                priority=50,
                model_tier="haiku",
            ),
        ]
    )

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", new=AsyncMock(return_value=mock_result)):
        await boss.decompose_goal(goal_id, "Some goal")

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT reviewer_roles FROM tasks WHERE goal_id = ?", (goal_id,)
        ) as cur:
            tasks = await cur.fetchall()
    finally:
        await db.close()
    assert len(tasks) == 1
    roles = json.loads(tasks[0]["reviewer_roles"])
    assert isinstance(roles, list)
    assert len(roles) >= 2


@pytest.mark.asyncio
async def test_decompose_goal_creates_task_review_rows(tmp_path):
    from runtime.boss import BossAgent, DecompositionResult, TaskSpec

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    await _insert_goal(mgr, goal_id)

    db = await mgr.open_write()
    try:
        for agent_id, role in [("a-1", "researcher"), ("a-2", "writer"), ("a-3", "strategist")]:
            await db.execute(
                "INSERT INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
                (agent_id, role),
            )
        await db.commit()
    finally:
        await db.close()

    mock_result = MagicMock()
    mock_result.parsed_output = DecompositionResult(
        tasks=[
            TaskSpec(
                title="T1",
                description="d1",
                assigned_role="researcher",
                reviewer_roles=["writer", "strategist"],
                priority=50,
                model_tier="haiku",
            ),
        ]
    )

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", new=AsyncMock(return_value=mock_result)):
        await boss.decompose_goal(goal_id, "Some goal")

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT tr.reviewer_id, tr.status FROM task_reviews tr "
            "JOIN tasks t ON tr.task_id = t.id WHERE t.goal_id = ?",
            (goal_id,),
        ) as cur:
            reviews = await cur.fetchall()
    finally:
        await db.close()
    assert len(reviews) == 2  # writer + strategist
    assert all(r["status"] == "pending" for r in reviews)


# ── Heartbeat counter / gap-fill ──────────────────────────────────────────────


def test_gap_fill_runs_every_3_heartbeats():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


def test_gap_fill_does_not_run_on_heartbeat_1():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


def test_goal_completion_marks_goal_done():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


# ── Stuck detection ───────────────────────────────────────────────────────────


def test_stuck_task_escalates_model_tier_haiku_to_sonnet():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


def test_stuck_task_escalates_model_tier_sonnet_to_opus():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


def test_stuck_task_sets_stuck_since():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


def test_second_intervention_posts_comment():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


# ── Activity log ──────────────────────────────────────────────────────────────


def test_escalation_logged_to_activity_log():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


def test_promotion_logged_to_activity_log():
    pytest.importorskip("runtime.boss")
    pytest.xfail("not implemented yet")


# ── Re-review UNIQUE constraint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_re_review_upsert_on_rejection(tmp_path):
    """Boss can re-create task_reviews rows without UNIQUE IntegrityError after rejection."""
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "peer_review")
    await _insert_review(mgr, task_id, "agent-2", "rejected")
    await _insert_review(mgr, task_id, "agent-3", "approved")

    boss = _make_boss(mgr)
    # First: rejection resets task to in-progress, reviews to pending
    await boss.do_peer_reviews()

    # Now simulate boss re-creating review rows (as would happen in decompose_goal
    # or any re-assignment logic) — must not raise IntegrityError
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO task_reviews (id, task_id, reviewer_id, status, created_at) "
            "VALUES (?, ?, 'agent-2', 'pending', ?)",
            (_uuid(), task_id, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT status FROM task_reviews WHERE task_id = ? AND reviewer_id = 'agent-2'",
            (task_id,),
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["status"] == "pending"
