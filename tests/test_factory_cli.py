import pytest
from click.testing import CliRunner


@pytest.mark.xfail(reason="CLI-01: not implemented")
def test_create_returns_immediately():
    cli_mod = pytest.importorskip("runtime.cli")
    from unittest.mock import patch
    runner = CliRunner()
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 12345
        result = runner.invoke(cli_mod.factory_cli, ["create", "Build a MTG advisor"])
    assert result.exit_code == 0
    assert "Factory job started" in result.output


@pytest.mark.xfail(reason="CLI-02: not implemented")
def test_status_in_progress():
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["status", "test-cluster"])
    assert "IN PROGRESS" in result.output or result.exit_code == 0


@pytest.mark.xfail(reason="CLI-03: not implemented")
def test_status_complete():
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["status", "test-cluster"])
    assert result.exit_code == 0


@pytest.mark.xfail(reason="CLI-04: not implemented")
def test_list_clusters():
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["list"])
    assert result.exit_code == 0


@pytest.mark.xfail(reason="CLI-05: not implemented")
def test_add_role(tmp_path):
    cli_mod = pytest.importorskip("runtime.cli")
    runner = CliRunner()
    result = runner.invoke(cli_mod.factory_cli, ["add-role", "test-cluster", "A data analyst"])
    assert result.exit_code == 0


@pytest.mark.xfail(reason="CLI-06: not implemented")
def test_name_flag_and_autoslug():
    cli_mod = pytest.importorskip("runtime.cli")
    from unittest.mock import patch
    runner = CliRunner()
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 1
        result = runner.invoke(cli_mod.factory_cli, ["create", "Analyze PDFs"])
    assert "analyze-pdfs" in result.output


@pytest.mark.xfail(reason="CLI-07: not implemented")
def test_collision_policy(tmp_path):
    cli_mod = pytest.importorskip("runtime.cli")
    from unittest.mock import patch
    runner = CliRunner()
    (tmp_path / "clusters" / "my-cluster").mkdir(parents=True)
    with patch("subprocess.Popen"):
        result = runner.invoke(cli_mod.factory_cli, ["create", "My cluster", "--name", "my-cluster"])
    # Must exit non-zero AND output the collision message (not just fail because 'create' is absent)
    assert result.exit_code != 0 and "already exists" in result.output
