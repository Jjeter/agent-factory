"""BossAgent unit tests — Phase 3 TDD.

Groups:
  - Structure (3 tests): sync — no DB needed
  - Promotion (3 tests): async — in-memory DB via _make_db()
  - Decomposition (3 tests): async — mock LLM + DB
  - Re-review UNIQUE constraint (1 test)
  - Stuck detection (5 tests): async — real DB + mock LLM for second intervention
  - Gap-fill / completion (3 tests): async — mock _gap_fill_and_completion_check
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from runtime.config import AgentConfig
from runtime.database import DatabaseManager
from runtime.models import _uuid, _now_iso


def _minutes_ago(n: int) -> str:
    """Return ISO 8601 UTC timestamp n minutes in the past."""
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).isoformat()


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


@pytest.mark.asyncio
async def test_rejection_increments_escalation_count(tmp_path):
    """_reject_back_to_in_progress must increment escalation_count by 1."""
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "peer_review", escalation_count=0)
    await _insert_review(mgr, task_id, "agent-2", "rejected")
    await _insert_review(mgr, task_id, "agent-3", "approved")

    boss = _make_boss(mgr)
    await boss.do_peer_reviews()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT escalation_count FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["escalation_count"] == 1


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


@pytest.mark.asyncio
async def test_gap_fill_runs_every_3_heartbeats(tmp_path):
    mgr = await _make_db(tmp_path)
    boss = _make_boss(mgr)

    with patch.object(boss, "_gap_fill_and_completion_check", new_callable=AsyncMock) as mock_gap:
        # Also patch _detect_stuck_tasks to avoid DB calls for non-existent tasks
        with patch.object(boss, "_detect_stuck_tasks", new_callable=AsyncMock):
            for _ in range(6):
                await boss.do_own_tasks()
    assert mock_gap.call_count == 2  # Called on heartbeat 3 and 6


@pytest.mark.asyncio
async def test_gap_fill_does_not_run_on_heartbeat_1(tmp_path):
    mgr = await _make_db(tmp_path)
    boss = _make_boss(mgr)

    with patch.object(boss, "_gap_fill_and_completion_check", new_callable=AsyncMock) as mock_gap:
        with patch.object(boss, "_detect_stuck_tasks", new_callable=AsyncMock):
            await boss.do_own_tasks()
    assert mock_gap.call_count == 0


@pytest.mark.asyncio
async def test_goal_completion_marks_goal_done(tmp_path):
    from runtime.boss import GoalCompletionResult

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    await _insert_goal(mgr, goal_id, "Build date arithmetic library")

    # Insert 2 approved tasks to simulate completed work
    for i in range(2):
        task_id = _uuid()
        db = await mgr.open_write()
        try:
            await db.execute(
                "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
                "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
                "VALUES (?, ?, ?, 'desc', 'approved', 50, 'haiku', 0, '[]', ?, ?)",
                (task_id, goal_id, f"Task {i}", _now_iso(), _now_iso()),
            )
            await db.commit()
        finally:
            await db.close()

    mock_result = MagicMock()
    mock_result.parsed_output = GoalCompletionResult(is_complete=True, reason="All tasks done")

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", new=AsyncMock(return_value=mock_result)):
        await boss._gap_fill_and_completion_check()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM goals WHERE id = ?", (goal_id,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["status"] == "completed"


# ── Stuck detection ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stuck_task_escalates_model_tier_haiku_to_sonnet(tmp_path):
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)

    # Insert task with updated_at 35 minutes ago — over the 30-min threshold
    db = await mgr.open_write()
    try:
        old_ts = _minutes_ago(35)
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Stuck task', 'Description', 'in-progress', 50, "
            "'haiku', 0, '[]', ?, ?)",
            (task_id, goal_id, old_ts, old_ts),
        )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    await boss.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT model_tier, escalation_count FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["model_tier"] == "sonnet"
    assert row["escalation_count"] == 1


@pytest.mark.asyncio
async def test_stuck_task_escalates_model_tier_sonnet_to_opus(tmp_path):
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)

    db = await mgr.open_write()
    try:
        old_ts = _minutes_ago(35)
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Stuck task', 'Description', 'in-progress', 50, "
            "'sonnet', 1, '[]', ?, ?)",
            (task_id, goal_id, old_ts, old_ts),
        )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    await boss.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT model_tier, escalation_count FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["model_tier"] == "opus"
    assert row["escalation_count"] == 2


@pytest.mark.asyncio
async def test_stuck_task_sets_stuck_since(tmp_path):
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)

    db = await mgr.open_write()
    try:
        old_ts = _minutes_ago(35)
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Stuck task', 'Description', 'in-progress', 50, "
            "'haiku', 0, '[]', ?, ?)",
            (task_id, goal_id, old_ts, old_ts),
        )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    await boss.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT stuck_since FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["stuck_since"] is not None


@pytest.mark.asyncio
async def test_second_intervention_posts_comment(tmp_path):
    from runtime.boss import UnblockingHint

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)

    # Second intervention: model_tier='sonnet' (already escalated), stuck_since 35 min ago
    db = await mgr.open_write()
    try:
        old_ts = _minutes_ago(35)
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, stuck_since, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Stuck task 2', 'Hard description', 'in-progress', 50, "
            "'sonnet', 1, ?, '[]', ?, ?)",
            (task_id, goal_id, old_ts, old_ts, old_ts),
        )
        await db.commit()
    finally:
        await db.close()

    mock_result = MagicMock()
    mock_result.parsed_output = UnblockingHint(hint="Try breaking the task into smaller steps")

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", new=AsyncMock(return_value=mock_result)):
        await boss.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT content, comment_type FROM task_comments WHERE task_id = ?", (task_id,)
        ) as cur:
            comments = await cur.fetchall()
    finally:
        await db.close()
    assert len(comments) >= 1
    assert any("smaller steps" in c["content"] for c in comments)


# ── Activity log ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_escalation_logged_to_activity_log(tmp_path):
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)

    db = await mgr.open_write()
    try:
        old_ts = _minutes_ago(35)
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Stuck task', 'Description', 'in-progress', 50, "
            "'haiku', 0, '[]', ?, ?)",
            (task_id, goal_id, old_ts, old_ts),
        )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    await boss.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT action, details FROM activity_log WHERE task_id = ? AND action = 'task_escalated'",
            (task_id,),
        ) as cur:
            log_rows = await cur.fetchall()
    finally:
        await db.close()
    assert len(log_rows) >= 1
    details = json.loads(log_rows[0]["details"])
    assert "old_tier" in details
    assert "new_tier" in details
    assert "stuck_since" in details


def test_promotion_logged_to_activity_log():
    """Verify promotion to review is logged — covered by test_promote_to_review_when_all_approved."""
    # This is verified in the promotion group above: actions list contains 'task_promoted'
    pass


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


# ── Coverage gap tests (Task 1: 03-04-PLAN.md) ───────────────────────────────


@pytest.mark.asyncio
async def test_stuck_task_opus_stays_opus(tmp_path):
    """opus model_tier stays opus (TIER_ESCALATION maps opus→opus, no KeyError)."""
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)

    db = await mgr.open_write()
    try:
        old_ts = _minutes_ago(35)
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Stuck opus task', 'Description', 'in-progress', 50, "
            "'opus', 2, '[]', ?, ?)",
            (task_id, goal_id, old_ts, old_ts),
        )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    await boss.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT model_tier, escalation_count FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["model_tier"] == "opus"
    assert row["escalation_count"] == 3


@pytest.mark.asyncio
async def test_resolve_reviewer_agents_skips_missing_role(tmp_path):
    """_resolve_reviewer_agents logs warning and skips roles not in agent_status."""
    mgr = await _make_db(tmp_path)

    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
            ("a-1", "researcher"),
        )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    # "missing-role" is not in agent_status — should be skipped with warning
    agents = await boss._resolve_reviewer_agents(
        reviewer_roles=["researcher", "missing-role"],
        assigned_role="writer",
    )
    assert "a-1" in agents
    # missing-role has no matching agent, so it should NOT appear
    assert len(agents) == 1


@pytest.mark.asyncio
async def test_resolve_reviewer_agents_skips_self_role(tmp_path):
    """_resolve_reviewer_agents skips roles that match assigned_role."""
    mgr = await _make_db(tmp_path)

    db = await mgr.open_write()
    try:
        for agent_id, role in [("a-1", "researcher"), ("a-2", "writer")]:
            await db.execute(
                "INSERT INTO agent_status (agent_id, agent_role, status) VALUES (?, ?, 'idle')",
                (agent_id, role),
            )
        await db.commit()
    finally:
        await db.close()

    boss = _make_boss(mgr)
    agents = await boss._resolve_reviewer_agents(
        reviewer_roles=["researcher", "writer"],
        assigned_role="researcher",  # researcher cannot review own work
    )
    assert "a-2" in agents
    assert "a-1" not in agents


@pytest.mark.asyncio
async def test_gap_fill_no_active_goal(tmp_path):
    """_gap_fill_and_completion_check returns early when no active goal exists."""
    mgr = await _make_db(tmp_path)
    boss = _make_boss(mgr)
    # Empty DB — no goals at all — should return early without error
    await boss._gap_fill_and_completion_check()  # Must not raise


@pytest.mark.asyncio
async def test_gap_fill_skips_when_active_tasks_exist(tmp_path):
    """Gap fill does not call decompose_goal when active tasks (cnt > 0) exist."""
    from runtime.boss import GoalCompletionResult

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    await _insert_goal(mgr, goal_id, "Goal with active work")

    # Insert one in-progress task so cnt > 0
    task_id = _uuid()
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
            "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, 'Active task', 'desc', 'in-progress', 50, 'haiku', 0, '[]', ?, ?)",
            (task_id, goal_id, _now_iso(), _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    # LLM says NOT complete — so gap fill branch is reached
    mock_result = MagicMock()
    mock_result.parsed_output = GoalCompletionResult(is_complete=False, reason="Still working")

    boss = _make_boss(mgr)
    with patch.object(boss, "decompose_goal", new_callable=AsyncMock) as mock_decompose:
        with patch.object(boss._llm.messages, "parse", new=AsyncMock(return_value=mock_result)):
            # Need approved tasks for LLM to be called; add one approved task too
            approved_id = _uuid()
            db = await mgr.open_write()
            try:
                await db.execute(
                    "INSERT INTO tasks (id, goal_id, title, description, status, priority, "
                    "model_tier, escalation_count, reviewer_roles, created_at, updated_at) "
                    "VALUES (?, ?, 'Done task', 'desc', 'approved', 50, 'haiku', 0, '[]', ?, ?)",
                    (approved_id, goal_id, _now_iso(), _now_iso()),
                )
                await db.commit()
            finally:
                await db.close()
            await boss._gap_fill_and_completion_check()
    # decompose_goal should NOT be called because cnt > 0 active tasks
    mock_decompose.assert_not_called()


@pytest.mark.asyncio
async def test_check_goal_completion_returns_false_for_empty_summaries(tmp_path):
    """_check_goal_completion returns False immediately when no completed summaries."""
    mgr = await _make_db(tmp_path)
    boss = _make_boss(mgr)
    result = await boss._check_goal_completion("Some goal", [])
    assert result is False


@pytest.mark.asyncio
async def test_check_goal_completion_exception_returns_false(tmp_path):
    """_check_goal_completion returns False (fail-safe) when LLM raises."""
    mgr = await _make_db(tmp_path)
    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", side_effect=RuntimeError("LLM down")):
        result = await boss._check_goal_completion("Some goal", ["Task A done", "Task B done"])
    assert result is False


@pytest.mark.asyncio
async def test_post_unblocking_hint_exception_uses_fallback(tmp_path):
    """_post_unblocking_hint uses fallback hint text when LLM raises."""
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "in-progress")

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", side_effect=RuntimeError("LLM error")):
        # Should NOT raise — fallback hint is used instead
        await boss._post_unblocking_hint(task_id, "Test Task", "Test description")

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT content FROM task_comments WHERE task_id = ?", (task_id,)
        ) as cur:
            comments = await cur.fetchall()
    finally:
        await db.close()
    assert len(comments) >= 1
    # Fallback hint should mention "stuck" or "smaller sub-step"
    assert any("stuck" in c["content"] or "sub-step" in c["content"] for c in comments)


@pytest.mark.asyncio
async def test_decompose_goal_llm_exception_raises(tmp_path):
    """_decompose_goal_llm re-raises LLM exceptions (no silent fallback)."""
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    await _insert_goal(mgr, goal_id)

    boss = _make_boss(mgr)
    with patch.object(boss._llm.messages, "parse", side_effect=RuntimeError("API down")):
        with pytest.raises(RuntimeError, match="API down"):
            await boss.decompose_goal(goal_id, "Test goal description")


@pytest.mark.asyncio
async def test_evaluate_reviews_no_reviews_returns_pending(tmp_path):
    """_evaluate_reviews returns 'pending' when no reviews exist for task."""
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task(mgr, task_id, goal_id, "peer_review")

    boss = _make_boss(mgr)
    status = await boss._evaluate_reviews(task_id)
    assert status == "pending"
