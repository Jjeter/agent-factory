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
            agent_role="worker",
            db_path="/tmp/x.db",
            interval_seconds=0.005,
        )

    # Minimum boundary value should succeed
    cfg = AgentConfig(
        agent_id="a",
        agent_role="worker",
        db_path="/tmp/x.db",
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
        "agent_id: test-agent\nagent_role: worker\ndb_path: /tmp/test.db\n"
    )

    result = load_agent_config(yaml_file)

    assert isinstance(result, AgentConfig)
    assert result.agent_id == "test-agent"
    assert result.agent_role == "worker"
