"""Pydantic models for the factory role decomposition pipeline."""
from __future__ import annotations

import pydantic


class RoleSpec(pydantic.BaseModel):
    """One agent role in a generated cluster."""

    name: str
    responsibilities: list[str]
    personality_system_prompt: str
    tool_allowlist: list[str]
    requires_glibc: bool = False


class RolesResult(pydantic.BaseModel):
    """Output of the role decomposition step."""

    roles: list[RoleSpec]


class FitCheckResult(pydantic.BaseModel):
    """Output of the fit-check evaluation step."""

    passed: bool
    failing_role: str | None = None
    reason: str | None = None
