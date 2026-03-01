"""Tests for runtime.config — AgentConfig model and load_agent_config().

HB-10: AgentConfig loads from valid YAML file.
HB-11: AgentConfig raises on missing required fields.
"""
import pytest
from pathlib import Path


class TestAgentConfigLoad:
    def test_load_agent_config_valid(self, tmp_path: Path):
        """HB-10: load_agent_config() parses a valid YAML file into AgentConfig."""
        from runtime.config import AgentConfig, load_agent_config

        yaml_content = """
agent_id: researcher-1
role: researcher
interval_seconds: 600.0
stagger_offset_seconds: 150.0
jitter_seconds: 30.0
"""
        config_path = tmp_path / "researcher.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        config = load_agent_config(config_path)

        assert isinstance(config, AgentConfig)
        assert config.agent_id == "researcher-1"
        assert config.role == "researcher"
        assert config.interval_seconds == 600.0
        assert config.stagger_offset_seconds == 150.0
        assert config.jitter_seconds == 30.0

    def test_load_agent_config_invalid(self, tmp_path: Path):
        """HB-11: load_agent_config() raises ValidationError when required fields are missing."""
        from runtime.config import load_agent_config
        from pydantic import ValidationError

        # Missing required 'agent_id' and 'role'
        yaml_content = "interval_seconds: 600.0\n"
        config_path = tmp_path / "bad.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ValidationError):
            load_agent_config(config_path)
