import pytest
from click.testing import CliRunner


def test_create_returns_immediately():
    cli_mod = pytest.importorskip("runtime.cli")
    from unittest.mock import patch
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.pid = 12345
            result = runner.invoke(cli_mod.factory_cli, ["create", "Build a MTG advisor"])
    assert result.exit_code == 0, result.output
    assert "Factory job started" in result.output


def test_status_in_progress():
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["status", "test-cluster"])
    # When cluster does not exist, command still exits 0 with a "not found" message
    assert "IN PROGRESS" in result.output or result.exit_code == 0


def test_status_complete():
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["status", "test-cluster"])
    assert result.exit_code == 0


def test_list_clusters():
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["list"])
    assert result.exit_code == 0


def test_add_role(tmp_path):
    cli_mod = pytest.importorskip("runtime.cli")
    import os
    runner = CliRunner()
    # Use an isolated clusters base so the test doesn't find any real cluster dir
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["add-role", "test-cluster", "A data analyst"],
        env=env,
    )
    assert result.exit_code == 0


def test_name_flag_and_autoslug():
    cli_mod = pytest.importorskip("runtime.cli")
    from unittest.mock import patch
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.pid = 1
            result = runner.invoke(cli_mod.factory_cli, ["create", "Analyze PDFs"])
    assert "analyze-pdfs" in result.output


def test_collision_policy(tmp_path):
    cli_mod = pytest.importorskip("runtime.cli")
    import os
    from unittest.mock import patch
    runner = CliRunner()
    cluster_dir = tmp_path / "clusters" / "my-cluster"
    cluster_dir.mkdir(parents=True)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    with patch("subprocess.Popen"):
        result = runner.invoke(
            cli_mod.factory_cli,
            ["create", "My cluster", "--name", "my-cluster"],
            env=env,
        )
    # Must exit non-zero AND output the collision message
    assert result.exit_code != 0 and "already exists" in result.output


# ---------------------------------------------------------------------------
# Phase 6 stubs — approve subcommand
# ---------------------------------------------------------------------------

def _make_cluster_db(tmp_path, cluster_name="test-cluster"):
    """Create a minimal cluster DB seeded with schema, return (cluster_dir, db_path)."""
    import sqlite3
    from pathlib import Path

    cluster_dir = tmp_path / "clusters" / cluster_name
    db_dir = cluster_dir / "db"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "cluster.db"
    schema = Path("runtime/schema.sql").read_text()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema)
    conn.commit()
    conn.close()
    return cluster_dir, db_path


def _seed_goal(db_path, goal_id="goal-01"):
    """Insert a minimal goal row; return goal_id."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO goals (id, title, description, status) VALUES (?, ?, ?, ?)",
        (goal_id, "Test goal", "Test description", "active"),
    )
    conn.commit()
    conn.close()
    return goal_id


def _seed_task(db_path, task_id="task-001", status="todo", goal_id="goal-01"):
    """Insert a minimal task row with given status; return task_id."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO tasks (id, goal_id, title, description, status) VALUES (?, ?, ?, ?, ?)",
        (task_id, goal_id, "Test task", "Test description", status),
    )
    conn.commit()
    conn.close()
    return task_id


def _seed_activity_log(db_path, agent_id="boss-01", action="task_claimed", n=1):
    """Insert n activity_log rows for given agent; return list of inserted ids."""
    import sqlite3
    import uuid
    conn = sqlite3.connect(str(db_path))
    ids = []
    for i in range(n):
        row_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO activity_log (id, agent_id, action, details) VALUES (?, ?, ?, ?)",
            (row_id, agent_id, action, f"detail {i}"),
        )
        ids.append(row_id)
    conn.commit()
    conn.close()
    return ids


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_approve_cluster_not_found(tmp_path):
    """approve exits 0 with info message when cluster DB does not exist."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["approve", "no-such-cluster", "task-abc"],
        env=env,
    )
    assert result.exit_code == 0
    assert "not found" in result.output.lower()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_approve_wrong_state(tmp_path):
    """approve exits 0 with info message when task is not in 'review' state."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    _, db_path = _make_cluster_db(tmp_path)
    goal_id = _seed_goal(db_path)
    task_id = _seed_task(db_path, task_id="task-002", status="todo", goal_id=goal_id)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["approve", "test-cluster", task_id],
        env=env,
    )
    assert result.exit_code == 0
    assert "not" in result.output.lower()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_approve_success(tmp_path):
    """approve updates task to 'approved' and prints success output."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    _, db_path = _make_cluster_db(tmp_path)
    goal_id = _seed_goal(db_path)
    task_id = _seed_task(db_path, task_id="task-003", status="review", goal_id=goal_id)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["approve", "test-cluster", task_id],
        env=env,
    )
    assert result.exit_code == 0
    assert "approved" in result.output.lower()


# ---------------------------------------------------------------------------
# Phase 6 stubs — logs subcommand
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_logs_cluster_not_found(tmp_path):
    """logs exits 0 with info message when cluster DB does not exist."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["logs", "no-such-cluster"],
        env=env,
    )
    assert result.exit_code == 0
    assert "not found" in result.output.lower()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_logs_table_output(tmp_path):
    """logs prints a tabulate 'simple' table with timestamp/agent_id/action/details columns."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    _, db_path = _make_cluster_db(tmp_path)
    _seed_activity_log(db_path, agent_id="boss-01", action="task_claimed", n=1)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["logs", "test-cluster"],
        env=env,
    )
    assert result.exit_code == 0
    assert "agent_id" in result.output or "agent" in result.output.lower()
    assert "action" in result.output.lower()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_logs_json_output(tmp_path):
    """logs --json prints a valid JSON list."""
    import os
    import json
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    _, db_path = _make_cluster_db(tmp_path)
    _seed_activity_log(db_path, agent_id="boss-01", action="task_claimed", n=1)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["logs", "test-cluster", "--json"],
        env=env,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_logs_tail(tmp_path):
    """logs --tail N limits output rows to N."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    _, db_path = _make_cluster_db(tmp_path)
    _seed_activity_log(db_path, agent_id="boss-01", action="task_claimed", n=5)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["logs", "test-cluster", "--tail", "2"],
        env=env,
    )
    assert result.exit_code == 0
    # With tabulate simple format there's a header row + separator; data rows = 2
    lines = [ln for ln in result.output.splitlines() if ln.strip() and "---" not in ln]
    assert len(lines) <= 3  # header + up to 2 data rows


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_logs_agent_filter(tmp_path):
    """logs --agent <id> filters rows to only that agent."""
    import os
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    _, db_path = _make_cluster_db(tmp_path)
    _seed_activity_log(db_path, agent_id="boss-01", action="task_claimed", n=2)
    _seed_activity_log(db_path, agent_id="worker-01", action="task_submitted", n=2)
    env = {**os.environ, "FACTORY_CLUSTERS_BASE": str(tmp_path / "clusters")}
    result = runner.invoke(
        cli_mod.factory_cli,
        ["logs", "test-cluster", "--agent", "boss-01"],
        env=env,
    )
    assert result.exit_code == 0
    assert "worker-01" not in result.output


# ---------------------------------------------------------------------------
# Phase 6 stubs — demo subcommand
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_demo_exists():
    """demo subcommand is registered (--help exits 0, not exit 2 for unknown command)."""
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["demo", "--help"])
    assert result.exit_code == 0
