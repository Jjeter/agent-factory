"""WorkerAgent unit tests — Phase 4 TDD RED stubs.

All 18 tests are guarded by pytest.importorskip("runtime.worker") inside the test
body so pytest can collect this file before runtime/worker.py exists. Tests skip
cleanly when the module is absent (the module does not exist yet in Wave 0).

Groups:
  - W-01: Structure (subclass check)
  - W-02: Config fields (system_prompt + tool_allowlist — covered in test_config.py)
  - W-03: Config merge (cluster.yaml base + role overlay)
  - W-04: Schema migration (assigned_role column idempotent)
  - W-05: Resume-first claiming
  - W-06: Role-based claim query
  - W-07: Atomic claim guard
  - W-08: First execution prompt (title + description only)
  - W-09: Re-execution prompt (includes prior doc + feedback)
  - W-10: Full execution cycle (doc inserted, comment posted, peer_review status)
  - W-11: Document version increments on re-submission
  - W-12: _fetch_pending_reviews filters by reviewer and status
  - W-13: Peer review always uses sonnet tier
  - W-14: ReviewDecision parsed from messages.parse() via parsed_output
  - W-15: After review: task_comment inserted + task_reviews row updated
  - W-16: Peer review prompt excludes prior reviewer comments
  - W-17: Review skips gracefully when task has no document
  - W-18: No tasks available: do_own_tasks returns without error
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from runtime.config import AgentConfig
from runtime.database import DatabaseManager
from runtime.models import _uuid, _now_iso


# ---------------------------------------------------------------------------
# Shared async helpers (mirrors test_boss.py pattern)
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
    assigned_to: str | None = None,
) -> None:
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, model_tier, "
            "escalation_count, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                goal_id,
                "Test Task",
                "Do the thing",
                status,
                50,
                model_tier,
                0,
                json.dumps(["writer", "strategist"]),
                _now_iso(),
                _now_iso(),
            ),
        )
        if assigned_to is not None:
            await db.execute(
                "UPDATE tasks SET assigned_to = ? WHERE id = ?",
                (assigned_to, task_id),
            )
        await db.commit()
    finally:
        await db.close()


async def _insert_task_with_role(
    mgr: DatabaseManager,
    task_id: str,
    goal_id: str,
    status: str,
    assigned_role: str,
    assigned_to: str | None = None,
    model_tier: str = "haiku",
) -> None:
    """Insert a task with assigned_role set (required for role-based claiming tests)."""
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO tasks (id, goal_id, title, description, status, priority, model_tier, "
            "escalation_count, assigned_role, reviewer_roles, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                goal_id,
                "Role Task",
                "Do the role thing",
                status,
                50,
                model_tier,
                0,
                assigned_role,
                json.dumps(["writer", "strategist"]),
                _now_iso(),
                _now_iso(),
            ),
        )
        if assigned_to is not None:
            await db.execute(
                "UPDATE tasks SET assigned_to = ? WHERE id = ?",
                (assigned_to, task_id),
            )
        await db.commit()
    finally:
        await db.close()


async def _insert_review(
    mgr: DatabaseManager, task_id: str, reviewer_id: str, status: str = "pending"
) -> None:
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


async def _insert_document(
    mgr: DatabaseManager,
    task_id: str,
    content: str,
    version: int = 1,
    created_by: str = "worker-1",
) -> str:
    """Insert a document row for a task. Returns the document id."""
    doc_id = _uuid()
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO documents (id, task_id, title, content, version, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, task_id, "Task Output", content, version, created_by, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()
    return doc_id


def _make_worker(mgr: DatabaseManager, agent_id: str = "worker-1", agent_role: str = "researcher"):
    worker_mod = pytest.importorskip("runtime.worker")
    WorkerAgent = worker_mod.WorkerAgent
    config = AgentConfig(
        agent_id=agent_id,
        agent_role=agent_role,
        interval_seconds=600.0,
        db_path=str(mgr._db_path),
    )
    return WorkerAgent(config)


# ---------------------------------------------------------------------------
# W-01: WorkerAgent subclasses BaseAgent
# ---------------------------------------------------------------------------


def test_worker_agent_is_base_agent():
    """W-01: WorkerAgent subclasses BaseAgent and exposes do_peer_reviews + do_own_tasks."""
    pytest.importorskip("runtime.worker")
    from runtime.worker import WorkerAgent
    from runtime.heartbeat import BaseAgent

    config = AgentConfig(agent_id="worker-1", agent_role="researcher", interval_seconds=600.0)
    worker = WorkerAgent(config)
    assert isinstance(worker, BaseAgent)
    assert hasattr(worker, "do_peer_reviews")
    assert hasattr(worker, "do_own_tasks")


# ---------------------------------------------------------------------------
# W-02: AgentConfig has system_prompt and tool_allowlist fields
# ---------------------------------------------------------------------------


def test_agent_config_has_system_prompt_and_tool_allowlist_fields():
    """W-02: AgentConfig exposes system_prompt (str) and tool_allowlist (list[str]) fields."""
    pytest.importorskip("runtime.worker")
    config = AgentConfig(
        agent_id="researcher-1",
        agent_role="researcher",
        interval_seconds=600.0,
        system_prompt="You are a researcher.",
        tool_allowlist=["search", "read_file"],
    )
    assert config.system_prompt == "You are a researcher."
    assert config.tool_allowlist == ["search", "read_file"]


# ---------------------------------------------------------------------------
# W-03: load_agent_config merges cluster.yaml + role YAML
# ---------------------------------------------------------------------------


def test_load_agent_config_role_wins_on_conflict(tmp_path):
    """W-03: Role YAML overrides cluster.yaml on conflicting fields."""
    pytest.importorskip("runtime.worker")
    from runtime.config import load_agent_config

    cluster_yaml = tmp_path / "cluster.yaml"
    cluster_yaml.write_text(
        "db_path: /shared/cluster.db\ninterval_seconds: 300.0\njitter_seconds: 10.0\n"
    )
    role_yaml = tmp_path / "researcher.yaml"
    role_yaml.write_text(
        "agent_id: researcher-1\nagent_role: researcher\n"
        "stagger_offset_seconds: 5.0\n"
        "system_prompt: You are a researcher.\n"
        "tool_allowlist: []\n"
    )
    cfg = load_agent_config(role_yaml, cluster_config_path=cluster_yaml)
    # Role fields present
    assert cfg.agent_id == "researcher-1"
    assert cfg.agent_role == "researcher"
    # Cluster defaults merged in
    assert cfg.db_path == "/shared/cluster.db"
    assert cfg.interval_seconds == 300.0
    # Role-specific fields preserved
    assert cfg.system_prompt == "You are a researcher."


# ---------------------------------------------------------------------------
# W-04: DatabaseManager.up() adds assigned_role column idempotently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_up_assigned_role_idempotent(tmp_path):
    """W-04: Calling mgr.up() twice does not raise; assigned_role column exists."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    # Second call must not raise
    await mgr.up()
    db = await mgr.open_read()
    try:
        async with db.execute("PRAGMA table_info(tasks)") as cur:
            cols = await cur.fetchall()
    finally:
        await db.close()
    col_names = [c["name"] for c in cols]
    assert "assigned_role" in col_names


@pytest.mark.asyncio
async def test_schema_migration_idempotent(tmp_path):
    """W-04: DatabaseManager.up() is idempotent; assigned_role column survives two calls.

    This test does NOT require runtime.worker — it only tests runtime.database and
    runtime.schema.sql changes from Plan 04-01.
    """
    db_mod = pytest.importorskip("runtime.database")
    DatabaseManager = db_mod.DatabaseManager

    db_path = tmp_path / "migration_test.db"
    mgr = DatabaseManager(db_path)

    # First call creates schema + adds assigned_role column
    await mgr.up()
    # Second call must not raise (idempotent ALTER TABLE)
    await mgr.up()

    # Verify assigned_role column exists
    db = await mgr.open_read()
    try:
        async with db.execute("PRAGMA table_info(tasks)") as cur:
            cols = await cur.fetchall()
    finally:
        await db.close()

    col_names = [c["name"] for c in cols]
    assert "assigned_role" in col_names, (
        f"assigned_role column missing from tasks table. Columns: {col_names}"
    )


# ---------------------------------------------------------------------------
# W-05: Resume-first: existing in-progress task claimed before todo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_do_own_tasks_resumes_in_progress_task(tmp_path):
    """W-05: do_own_tasks picks up own in-progress task before claiming from todo."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    in_progress_id = _uuid()
    todo_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(
        mgr, in_progress_id, goal_id, "in-progress", "researcher", assigned_to="worker-1"
    )
    await _insert_task_with_role(mgr, todo_id, goal_id, "todo", "researcher")

    worker = _make_worker(mgr)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Research findings here.")]

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await worker.do_own_tasks()

    # The in-progress task should be submitted (peer_review), not the todo task
    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (in_progress_id,)) as cur:
            row = await cur.fetchone()
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (todo_id,)) as cur:
            todo_row = await cur.fetchone()
    finally:
        await db.close()
    assert row["status"] == "peer_review"
    assert todo_row["status"] == "todo"


# ---------------------------------------------------------------------------
# W-06: Claim query filters by assigned_role (not agent_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_filters_by_assigned_role(tmp_path):
    """W-06: Worker only claims tasks whose assigned_role matches the worker's role."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    researcher_task_id = _uuid()
    writer_task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, researcher_task_id, goal_id, "todo", "researcher")
    await _insert_task_with_role(mgr, writer_task_id, goal_id, "todo", "writer")

    worker = _make_worker(mgr, agent_role="researcher")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Research done.")]

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await worker.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (researcher_task_id,)) as cur:
            res_row = await cur.fetchone()
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (writer_task_id,)) as cur:
            writer_row = await cur.fetchone()
    finally:
        await db.close()
    # Researcher task should have been claimed and submitted
    assert res_row["status"] == "peer_review"
    # Writer task must remain untouched
    assert writer_row["status"] == "todo"


# ---------------------------------------------------------------------------
# W-07: Atomic claim guard prevents double-claim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_atomic_claim_guard_rowcount_zero_returns(tmp_path):
    """W-07: If UPDATE rowcount=0 (lost race), do_own_tasks returns without error."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "todo", "researcher")

    worker = _make_worker(mgr)

    # Simulate a lost race by marking task in-progress by another agent between SELECT and UPDATE
    async def steal_task(*args, **kwargs):
        db = await mgr.open_write()
        try:
            await db.execute(
                "UPDATE tasks SET status = 'in-progress', assigned_to = 'other-worker' WHERE id = ?",
                (task_id,),
            )
            await db.commit()
        finally:
            await db.close()
        return MagicMock(rowcount=0)

    with patch.object(worker, "_try_claim_task", new_callable=AsyncMock) as mock_claim:
        mock_claim.return_value = None  # None = lost race, no task claimed
        # Should return gracefully without error
        await worker.do_own_tasks()

    mock_claim.assert_called_once()


# ---------------------------------------------------------------------------
# W-08: First execution prompt contains only title + description
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_execution_prompt_no_prior_doc(tmp_path):
    """W-08: LLM prompt for first execution contains task title + description only."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "todo", "researcher")

    worker = _make_worker(mgr)
    captured_messages = []

    async def capture_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        resp = MagicMock()
        resp.content = [MagicMock(text="Initial research findings.")]
        return resp

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = capture_create
        await worker.do_own_tasks()

    assert len(captured_messages) >= 1
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m, dict) else str(m)
        for m in captured_messages[0]
    )
    # Title and description present
    assert "Role Task" in prompt_text or "Do the role thing" in prompt_text
    # No "Prior output" or "feedback" section
    assert "Prior output" not in prompt_text
    assert "feedback" not in prompt_text.lower()


# ---------------------------------------------------------------------------
# W-09: Re-execution prompt includes prior doc + feedback comments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_re_execution_prompt_includes_prior_doc_and_feedback(tmp_path):
    """W-09: Re-execution LLM prompt includes prior document content + feedback."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(
        mgr, task_id, goal_id, "in-progress", "researcher", assigned_to="worker-1"
    )
    await _insert_document(mgr, task_id, "Draft research content here.", version=1)

    # Insert a feedback comment
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO task_comments (id, task_id, agent_id, comment_type, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid(), task_id, "reviewer-1", "feedback", "Needs more citations.", _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    worker = _make_worker(mgr)
    captured_messages = []

    async def capture_create(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        resp = MagicMock()
        resp.content = [MagicMock(text="Revised research with citations.")]
        return resp

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = capture_create
        await worker.do_own_tasks()

    assert len(captured_messages) >= 1
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m, dict) else str(m)
        for m in captured_messages[0]
    )
    assert "Draft research content here." in prompt_text
    assert "Needs more citations." in prompt_text


# ---------------------------------------------------------------------------
# W-10: Full execution cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_execution_cycle(tmp_path):
    """W-10: Document inserted, progress comment posted, task moves to peer_review."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "todo", "researcher")
    await _insert_review(mgr, task_id, "writer-1", "pending")
    await _insert_review(mgr, task_id, "strategist-1", "pending")

    worker = _make_worker(mgr)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Complete research output.")]

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await worker.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            task_row = await cur.fetchone()
        async with db.execute(
            "SELECT content FROM documents WHERE task_id = ?", (task_id,)
        ) as cur:
            docs = await cur.fetchall()
        async with db.execute(
            "SELECT comment_type FROM task_comments WHERE task_id = ?", (task_id,)
        ) as cur:
            comments = await cur.fetchall()
    finally:
        await db.close()

    assert task_row["status"] == "peer_review"
    assert len(docs) >= 1
    assert any(c["comment_type"] == "progress" for c in comments)


# ---------------------------------------------------------------------------
# W-11: Document version increments on re-submission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_version_increments_on_resubmission(tmp_path):
    """W-11: Version = MAX(prior) + 1 on each re-submission."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(
        mgr, task_id, goal_id, "in-progress", "researcher", assigned_to="worker-1"
    )
    # Prior document at version 1
    await _insert_document(mgr, task_id, "Version 1 content.", version=1)

    worker = _make_worker(mgr)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Version 2 improved content.")]

    with patch.object(worker._llm.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await worker.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT version FROM documents WHERE task_id = ? ORDER BY version DESC", (task_id,)
        ) as cur:
            docs = await cur.fetchall()
    finally:
        await db.close()

    versions = [d["version"] for d in docs]
    assert 2 in versions
    assert 1 in versions


# ---------------------------------------------------------------------------
# W-12: _fetch_pending_reviews returns correct task_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_pending_reviews_filters_by_reviewer_and_status(tmp_path):
    """W-12: _fetch_pending_reviews returns tasks where this agent is pending reviewer."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_a = _uuid()
    task_b = _uuid()
    task_c = _uuid()
    await _insert_goal(mgr, goal_id)
    # task_a: worker-1 is pending reviewer, in peer_review
    await _insert_task_with_role(mgr, task_a, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_a, "worker-1", "pending")
    # task_b: worker-1 has already approved — should not appear
    await _insert_task_with_role(mgr, task_b, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_b, "worker-1", "approved")
    # task_c: worker-1 is not a reviewer at all
    await _insert_task_with_role(mgr, task_c, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_c, "other-worker", "pending")

    worker = _make_worker(mgr)
    task_ids = await worker._fetch_pending_reviews()

    assert task_a in task_ids
    assert task_b not in task_ids
    assert task_c not in task_ids


# ---------------------------------------------------------------------------
# W-13: Peer review always uses claude-sonnet-4-6 (regardless of agent tier)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_peer_review_uses_sonnet_model(tmp_path):
    """W-13: Review LLM call always uses claude-sonnet-4-6 regardless of agent config."""
    pytest.importorskip("runtime.worker")
    from runtime.worker import ReviewDecision

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_id, "worker-1", "pending")
    await _insert_document(mgr, task_id, "The document to review.", version=1)

    # Worker configured as haiku tier — review must still use sonnet
    worker = _make_worker(mgr, agent_id="worker-1", agent_role="researcher")
    mock_result = MagicMock()
    mock_result.parsed_output = ReviewDecision(
        decision="approve", feedback="Well researched and clearly written."
    )

    captured_models = []

    async def capture_parse(**kwargs):
        captured_models.append(kwargs.get("model", ""))
        return mock_result

    with patch.object(worker._llm.messages, "parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.side_effect = capture_parse
        await worker.do_peer_reviews()

    assert len(captured_models) >= 1
    assert all("sonnet" in m for m in captured_models)


# ---------------------------------------------------------------------------
# W-14: ReviewDecision parsed via messages.parse() parsed_output attribute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_decision_via_parsed_output(tmp_path):
    """W-14: ReviewDecision is extracted from messages.parse() result.parsed_output."""
    pytest.importorskip("runtime.worker")
    from runtime.worker import ReviewDecision

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_id, "worker-1", "pending")
    await _insert_document(mgr, task_id, "Solid document for review.", version=1)

    worker = _make_worker(mgr)
    mock_result = MagicMock()
    mock_result.parsed_output = ReviewDecision(
        decision="reject",
        feedback="Missing key citations. Required: add at least 3 primary sources.",
        required_changes="Add 3 primary source citations in the findings section.",
    )

    with patch.object(worker._llm.messages, "parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_result
        await worker.do_peer_reviews()

    # Verify parse was called with output_format=ReviewDecision
    mock_parse.assert_called_once()
    call_kwargs = mock_parse.call_args.kwargs
    assert call_kwargs.get("output_format") is ReviewDecision


# ---------------------------------------------------------------------------
# W-15: After review: task_comment inserted + task_reviews row updated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_posts_comment_and_updates_review_row(tmp_path):
    """W-15: Feedback task_comment inserted AND task_reviews row updated to decision."""
    pytest.importorskip("runtime.worker")
    from runtime.worker import ReviewDecision

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_id, "worker-1", "pending")
    await _insert_document(mgr, task_id, "The document content to review.", version=1)

    worker = _make_worker(mgr)
    mock_result = MagicMock()
    mock_result.parsed_output = ReviewDecision(
        decision="approve",
        feedback="Clear, thorough, and well-structured. No changes needed.",
    )

    with patch.object(worker._llm.messages, "parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_result
        await worker.do_peer_reviews()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT comment_type, content FROM task_comments WHERE task_id = ?", (task_id,)
        ) as cur:
            comments = await cur.fetchall()
        async with db.execute(
            "SELECT status FROM task_reviews WHERE task_id = ? AND reviewer_id = 'worker-1'",
            (task_id,),
        ) as cur:
            review_row = await cur.fetchone()
    finally:
        await db.close()

    assert any(c["comment_type"] == "feedback" for c in comments)
    assert review_row["status"] == "approved"


# ---------------------------------------------------------------------------
# W-16: Peer review prompt does NOT include prior reviewer comments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_peer_review_prompt_excludes_prior_reviewer_comments(tmp_path):
    """W-16: Review prompt contains task + doc only — no prior reviewer comments."""
    pytest.importorskip("runtime.worker")
    from runtime.worker import ReviewDecision

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_id, "worker-1", "pending")
    await _insert_document(mgr, task_id, "Document being reviewed.", version=1)

    # Add a prior reviewer comment that must NOT appear in the new review prompt
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO task_comments (id, task_id, agent_id, comment_type, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                _uuid(),
                task_id,
                "other-reviewer",
                "feedback",
                "PRIOR REVIEWER COMMENT: should not appear",
                _now_iso(),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    worker = _make_worker(mgr)
    captured_messages = []

    async def capture_parse(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        mock_result = MagicMock()
        mock_result.parsed_output = ReviewDecision(
            decision="approve", feedback="Good work, independent evaluation."
        )
        return mock_result

    with patch.object(worker._llm.messages, "parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.side_effect = capture_parse
        await worker.do_peer_reviews()

    assert len(captured_messages) >= 1
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m, dict) else str(m)
        for m in captured_messages[0]
    )
    assert "PRIOR REVIEWER COMMENT" not in prompt_text


# ---------------------------------------------------------------------------
# W-17: Review skips gracefully when task has no document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_skips_when_no_document(tmp_path):
    """W-17: do_peer_reviews logs warning and skips tasks without a document (no crash)."""
    pytest.importorskip("runtime.worker")

    mgr = await _make_db(tmp_path)
    goal_id = _uuid()
    task_id = _uuid()
    await _insert_goal(mgr, goal_id)
    await _insert_task_with_role(mgr, task_id, goal_id, "peer_review", "writer")
    await _insert_review(mgr, task_id, "worker-1", "pending")
    # No document inserted — task has no document yet

    worker = _make_worker(mgr)
    # Should complete without raising
    await worker.do_peer_reviews()

    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT status FROM task_reviews WHERE task_id = ? AND reviewer_id = 'worker-1'",
            (task_id,),
        ) as cur:
            review_row = await cur.fetchone()
    finally:
        await db.close()
    # Review row must remain pending (no decision made without a document)
    assert review_row["status"] == "pending"


# ---------------------------------------------------------------------------
# W-18: No tasks available — do_own_tasks returns without error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_tasks_available_returns_cleanly(tmp_path):
    """W-18: do_own_tasks with empty todo queue returns without error or claims."""
    pytest.importorskip("runtime.worker")
    mgr = await _make_db(tmp_path)
    # Empty DB — no goals, no tasks

    worker = _make_worker(mgr)
    # Must not raise
    await worker.do_own_tasks()

    db = await mgr.open_read()
    try:
        async with db.execute("SELECT COUNT(*) AS cnt FROM tasks") as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    assert row["cnt"] == 0
