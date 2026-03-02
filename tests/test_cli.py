"""Tests for runtime.cli — Click CLI entry points for cluster commands."""

from click.testing import CliRunner
from runtime.cli import cluster_cli, factory_cli


def test_cluster_db_help() -> None:
    """cluster db --help shows up and reset subcommands."""
    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["db", "--help"])
    assert result.exit_code == 0
    assert "up" in result.output
    assert "reset" in result.output


def test_cluster_db_up_creates_database(tmp_path) -> None:
    """cluster db up initializes the database at the given path."""
    db_file = tmp_path / "test_cluster.db"
    runner = CliRunner()
    result = runner.invoke(cluster_cli, ["db", "up", "--db-path", str(db_file)])
    assert result.exit_code == 0, result.output
    assert "Database initialized" in result.output
    assert db_file.exists()


def test_cluster_db_up_is_idempotent(tmp_path) -> None:
    """cluster db up can be called twice without error."""
    db_file = tmp_path / "idempotent.db"
    runner = CliRunner()
    result1 = runner.invoke(cluster_cli, ["db", "up", "--db-path", str(db_file)])
    result2 = runner.invoke(cluster_cli, ["db", "up", "--db-path", str(db_file)])
    assert result1.exit_code == 0
    assert result2.exit_code == 0


def test_cluster_db_reset(tmp_path) -> None:
    """cluster db reset drops and recreates all tables."""
    db_file = tmp_path / "reset_test.db"
    runner = CliRunner()
    # First bring the DB up
    runner.invoke(cluster_cli, ["db", "up", "--db-path", str(db_file)])
    # Then reset it
    result = runner.invoke(cluster_cli, ["db", "reset", "--db-path", str(db_file)])
    assert result.exit_code == 0, result.output
    assert "Database reset" in result.output


def test_cluster_db_up_uses_envvar(tmp_path) -> None:
    """cluster db up respects the CLUSTER_DB_PATH environment variable."""
    db_file = tmp_path / "envvar_test.db"
    runner = CliRunner()
    result = runner.invoke(
        cluster_cli,
        ["db", "up"],
        env={"CLUSTER_DB_PATH": str(db_file)},
    )
    assert result.exit_code == 0, result.output
    assert db_file.exists()


def test_factory_cli_help() -> None:
    """factory_cli --help exits 0 (stub group resolves correctly)."""
    runner = CliRunner()
    result = runner.invoke(factory_cli, ["--help"])
    assert result.exit_code == 0
    assert "Phase 5" in result.output or "management" in result.output.lower()
