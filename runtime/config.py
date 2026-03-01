"""Agent configuration model for the Agent Factory runtime.

Loaded from agents/<role>.yaml using yaml.safe_load() at agent startup.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AgentConfig(BaseModel, frozen=True):
    """Typed configuration for a single agent, parsed from its YAML config file.

    All fields are immutable after construction (frozen=True matches Phase 1 pattern).
    """

    agent_id: str
    role: str
    interval_seconds: float = Field(default=600.0, ge=0.01)
    stagger_offset_seconds: float = Field(default=0.0, ge=0.0)
    jitter_seconds: float = Field(default=30.0, ge=0.0)
    state_dir: Path = Field(default=Path("runtime/state"))


def load_agent_config(yaml_path: Path) -> AgentConfig:
    """Load and validate an AgentConfig from a YAML file.

    Uses yaml.safe_load() exclusively — never yaml.load() — to prevent
    arbitrary Python object deserialization from agent YAML files.

    Raises:
        FileNotFoundError: If yaml_path does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        pydantic.ValidationError: If required fields are missing or invalid.
    """
    raw: object = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping at {yaml_path}, got {type(raw).__name__}")
    return AgentConfig.model_validate(raw)
