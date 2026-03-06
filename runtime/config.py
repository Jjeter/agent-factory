"""Agent configuration model loaded from agents/*.yaml config files."""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml


class AgentConfig(BaseModel):
    """Typed configuration for a single agent, parsed from its YAML config file.

    Accepts both ``role`` and ``agent_role`` for the agent's role field, and
    both ``db_path`` (str) and ``state_dir`` (Path) for storage locations.
    This allows test helpers and YAML files to use either naming convention.
    """

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    agent_id: str
    # Primary field name for heartbeat internals; also accepts 'role' via validator
    agent_role: str = Field(default="")
    # Kept for YAML round-trip and test_config.py compatibility
    role: str = Field(default="")
    interval_seconds: float = Field(default=600.0, ge=0.01)
    stagger_offset_seconds: float = Field(default=0.0, ge=0.0)
    jitter_seconds: float = Field(default=30.0, ge=0.0)
    state_dir: Path = Field(default=Path("runtime/state"))
    # Optional DB path for direct construction in tests/heartbeat
    db_path: Optional[str] = Field(default=None)
    # Phase 4: WorkerAgent role-specific fields (populated from role YAML overlay)
    system_prompt: str = Field(default="")
    tool_allowlist: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_role_fields(cls, data: dict) -> dict:
        """Accept 'role' or 'agent_role' interchangeably.

        Whichever is provided, both fields are set to the same value so that
        callers can use either ``config.role`` or ``config.agent_role``.
        """
        if isinstance(data, dict):
            role = data.get("role", "")
            agent_role = data.get("agent_role", "")
            resolved = agent_role or role
            data = {**data, "role": resolved, "agent_role": resolved}
        return data


def load_agent_config(
    path: Path, cluster_config_path: Path | None = None
) -> AgentConfig:
    """Load and validate an AgentConfig from a YAML file.

    When ``cluster_config_path`` is provided the cluster YAML is loaded first as a
    base dict, then the role YAML is merged on top (role values win on conflict).
    This allows shared cluster settings (db_path, interval_seconds, jitter_seconds)
    to be inherited by each role YAML without repetition.

    Args:
        path: Path to the role-specific YAML file (required).
        cluster_config_path: Optional path to the cluster base YAML file.
            When provided, merged as ``{**cluster_raw, **role_raw}`` so role keys
            override cluster keys.

    Raises:
        FileNotFoundError: If path or cluster_config_path does not exist.
        pydantic.ValidationError: If required fields are missing or invalid.
    """
    raw: dict = yaml.safe_load(path.read_text(encoding="utf-8"))
    if cluster_config_path is not None:
        cluster_raw: dict = yaml.safe_load(
            cluster_config_path.read_text(encoding="utf-8")
        )
        merged = {**cluster_raw, **raw}
    else:
        merged = raw
    return AgentConfig.model_validate(merged)
