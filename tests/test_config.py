"""TDD stub tests for Phase 2 — AgentConfig and load_agent_config.

Covers HB-01 (interval_seconds >= 0.01 constraint) and HB-02 (YAML round-trip).

All tests use pytest.importorskip inside the test body so pytest can collect this
file before runtime/config.py exists. Tests skip cleanly when the module is absent.
"""
import pytest


def test_interval_ge_constraint():
    """HB-01: AgentConfig rejects interval_seconds below 0.01, accepts 0.01."""
    config_mod = pytest.importorskip("runtime.config")
    AgentConfig = config_mod.AgentConfig
    import pydantic

    # Values below minimum should raise ValidationError
    with pytest.raises(pydantic.ValidationError):
        AgentConfig(
            agent_id="a",
            role="worker",
            interval_seconds=0.005,
        )

    # Minimum boundary value should succeed
    cfg = AgentConfig(
        agent_id="a",
        role="worker",
        interval_seconds=0.01,
    )
    assert cfg.interval_seconds == 0.01


def test_load_agent_config(tmp_path):
    """HB-02: load_agent_config reads a YAML file and returns an AgentConfig."""
    config_mod = pytest.importorskip("runtime.config")
    AgentConfig = config_mod.AgentConfig
    load_agent_config = config_mod.load_agent_config

    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text(
        "agent_id: test-agent\nrole: worker\n"
    )

    result = load_agent_config(yaml_file)

    assert isinstance(result, AgentConfig)
    assert result.agent_id == "test-agent"
    assert result.role == "worker"


def test_agent_config_system_prompt_and_tool_allowlist():
    """W-02: AgentConfig accepts system_prompt (str) and tool_allowlist (list[str]) fields."""
    config_mod = pytest.importorskip("runtime.config")
    AgentConfig = config_mod.AgentConfig

    cfg = AgentConfig(
        agent_id="researcher-1",
        role="researcher",
        system_prompt="You are a researcher. Produce detailed findings.",
        tool_allowlist=["tool_a", "tool_b"],
    )
    assert cfg.system_prompt == "You are a researcher. Produce detailed findings."
    assert cfg.tool_allowlist == ["tool_a", "tool_b"]


@pytest.mark.xfail(reason="load_agent_config merge signature not implemented until Plan 04-01")
def test_load_agent_config_merge(tmp_path):
    """W-02 / W-03: load_agent_config merges cluster.yaml base with role YAML overlay."""
    config_mod = pytest.importorskip("runtime.config")
    load_agent_config = config_mod.load_agent_config

    cluster_path = tmp_path / "cluster.yaml"
    cluster_path.write_text(
        "db_path: /shared/cluster.db\ninterval_seconds: 300.0\njitter_seconds: 15.0\n"
    )
    role_path = tmp_path / "researcher.yaml"
    role_path.write_text(
        "agent_id: researcher-1\nagent_role: researcher\n"
        "system_prompt: You are a researcher.\n"
        "tool_allowlist: []\n"
    )

    cfg = load_agent_config(role_path, cluster_config_path=cluster_path)

    # Role fields take priority
    assert cfg.agent_id == "researcher-1"
    assert cfg.system_prompt == "You are a researcher."
    # Cluster defaults merged in
    assert cfg.db_path == "/shared/cluster.db"
    assert cfg.interval_seconds == 300.0
