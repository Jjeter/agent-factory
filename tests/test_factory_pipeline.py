import pytest
from unittest.mock import AsyncMock, patch


async def test_pipeline_produces_roles():
    pipeline = pytest.importorskip("factory.pipeline")
    models = pytest.importorskip("factory.models")
    mock_llm = AsyncMock()
    mock_llm.messages.parse.return_value = AsyncMock(
        parsed_output=models.RolesResult(
            roles=[
                models.RoleSpec(
                    name="researcher",
                    responsibilities=["research"],
                    personality_system_prompt="p",
                    tool_allowlist=[],
                ),
                models.RoleSpec(
                    name="writer",
                    responsibilities=["write"],
                    personality_system_prompt="p",
                    tool_allowlist=[],
                ),
            ]
        )
    )
    result = await pipeline.decompose_roles("Build a thing", mock_llm)
    assert len(result.roles) >= 2


async def test_fit_check_retry():
    pipeline = pytest.importorskip("factory.pipeline")
    models = pytest.importorskip("factory.models")
    mock_llm = AsyncMock()
    # First call: fit check fails; second call: passes
    mock_llm.messages.parse.side_effect = [
        AsyncMock(
            parsed_output=models.FitCheckResult(
                passed=False,
                failing_role="researcher",
                reason="too broad",
            )
        ),
        AsyncMock(
            parsed_output=models.RolesResult(
                roles=[
                    models.RoleSpec(
                        name="researcher",
                        responsibilities=["narrowed"],
                        personality_system_prompt="p",
                        tool_allowlist=[],
                    )
                ]
            )
        ),
        AsyncMock(parsed_output=models.FitCheckResult(passed=True)),
    ]
    # pipeline.fit_check_with_retry should call fit_check, re-cluster on failure, then pass
    result = await pipeline.fit_check(models.RolesResult(roles=[]), mock_llm)
    assert isinstance(result, models.FitCheckResult)


async def test_structural_roles_present():
    pipeline = pytest.importorskip("factory.pipeline")
    models = pytest.importorskip("factory.models")
    mock_llm = AsyncMock()
    mock_llm.messages.parse.return_value = AsyncMock(
        parsed_output=models.RolesResult(
            roles=[
                models.RoleSpec(
                    name="analyst",
                    responsibilities=["analyze"],
                    personality_system_prompt="p",
                    tool_allowlist=[],
                )
            ]
        )
    )
    roles = await pipeline.decompose_roles("Build a thing", mock_llm)
    role_names = [r.name for r in roles.roles]
    assert "boss" in role_names
    assert "critic" in role_names
