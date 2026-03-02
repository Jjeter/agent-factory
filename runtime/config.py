"""Agent configuration model loaded from agents/*.yaml config files."""
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
import yaml


class AgentConfig(BaseModel):
    """Typed configuration for a single agent, parsed from its YAML config file."""

    model_config = ConfigDict(use_enum_values=True)

    agent_id: str
    agent_role: str
    db_path: str
    interval_seconds: float = Field(default=600.0, ge=0.01)
    stagger_offset_seconds: float = Field(default=0.0, ge=0.0)


def load_agent_config(path: Path) -> AgentConfig:
    """Load and validate an AgentConfig from a YAML file.

    Raises:
        FileNotFoundError: If path does not exist (from Path.read_text).
        pydantic.ValidationError: If required fields are missing or invalid.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AgentConfig.model_validate(raw)
