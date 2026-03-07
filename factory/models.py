import pydantic


class RoleSpec(pydantic.BaseModel):
    name: str
    responsibilities: list[str]
    personality_system_prompt: str
    tool_allowlist: list[str]
    requires_glibc: bool = False


class RolesResult(pydantic.BaseModel):
    roles: list[RoleSpec]


class FitCheckResult(pydantic.BaseModel):
    passed: bool
    failing_role: str | None = None
    reason: str | None = None
