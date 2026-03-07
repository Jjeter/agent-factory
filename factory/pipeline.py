from factory.models import FitCheckResult, RoleSpec, RolesResult


async def decompose_roles(goal: str, llm) -> RolesResult:
    raise NotImplementedError


async def fit_check(roles_result: RolesResult, llm) -> FitCheckResult:
    raise NotImplementedError


async def enrich_roles(roles_result: RolesResult, llm) -> list[RoleSpec]:
    raise NotImplementedError
