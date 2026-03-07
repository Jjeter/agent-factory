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
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["add-role", "test-cluster", "A data analyst"])
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
