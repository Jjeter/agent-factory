import pytest


@pytest.mark.xfail(reason="GEN-01: not implemented")
def test_render_agent_yaml():
    gen = pytest.importorskip("factory.generator")
    models = pytest.importorskip("factory.models")
    role = models.RoleSpec(
        name="researcher",
        responsibilities=["research"],
        personality_system_prompt="You research.",
        tool_allowlist=[],
    )
    result = gen.render_agent_yaml(role, {"db_path": "/data/cluster.db"})
    assert "agent_id" in result
    assert "researcher" in result


@pytest.mark.xfail(reason="GEN-02: not implemented")
def test_render_docker_compose():
    gen = pytest.importorskip("factory.generator")
    models = pytest.importorskip("factory.models")
    roles = [
        models.RoleSpec(
            name="writer",
            responsibilities=["write"],
            personality_system_prompt="You write.",
            tool_allowlist=[],
        )
    ]
    result = gen.render_docker_compose("test-cluster", roles)
    assert "services:" in result
    assert "writer" in result


@pytest.mark.xfail(reason="GEN-03: not implemented")
def test_render_cluster_yaml():
    gen = pytest.importorskip("factory.generator")
    models = pytest.importorskip("factory.models")
    result = gen.render_cluster_yaml("test-cluster", "Build a thing", [])
    import yaml
    loaded = yaml.safe_load(result)
    assert loaded["cluster_name"] == "test-cluster"


@pytest.mark.xfail(reason="GEN-04: not implemented")
def test_launch_sh_fails_without_key():
    import subprocess, textwrap
    gen = pytest.importorskip("factory.generator")
    script = gen.render_launch_sh("test-cluster")
    assert "ANTHROPIC_API_KEY" in script
    assert "exit 1" in script


@pytest.mark.xfail(reason="GEN-05: not implemented")
def test_copy_runtime(tmp_path):
    gen = pytest.importorskip("factory.generator")
    gen.copy_runtime(tmp_path)
    assert (tmp_path / "runtime" / "__init__.py").exists()
