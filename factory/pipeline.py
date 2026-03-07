"""factory/pipeline.py — Multi-step role decomposition pipeline.

Three async pipeline stages:
  1. decompose_roles  — LLM call to enumerate responsibilities and cluster into roles.
                        Always injects structural "boss" and "critic" roles after LLM response.
  2. fit_check        — Single-shot LLM quality evaluation of a roles result.
                        Caller is responsible for retry logic (max 2 retries).
  3. enrich_roles     — Per-role enrichment in parallel via asyncio.gather.

All LLM calls use the messages.parse() pattern with Pydantic output_format — same
pattern as runtime/boss.py decompose_goal.
"""
from __future__ import annotations

import asyncio

import yaml
from anthropic import AsyncAnthropic

from factory.models import FitCheckResult, RoleSpec, RolesResult

# Haiku is fast and sufficient for structured decomposition; boss can escalate if needed.
_PIPELINE_MODEL = "claude-haiku-4-5-20251001"


async def decompose_roles(goal: str, llm: AsyncAnthropic) -> RolesResult:
    """Stage 1: LLM decomposes a cluster goal into named roles.

    After the LLM response, structural roles "boss" and "critic" are always
    injected if not already present — they are never left to LLM discretion.
    """
    parsed = await llm.messages.parse(
        model=_PIPELINE_MODEL,
        max_tokens=2048,
        system=(
            "You are a factory agent. Given a cluster goal, enumerate all agent "
            "responsibilities and group them into distinct roles. Avoid role overlap. "
            "Each role should have a clear, bounded responsibility set."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Goal: {goal}\n\n"
                    "Decompose into roles. Each role needs a slug name, list of "
                    "responsibilities, and a distinctive personality system prompt. "
                    "Return roles array."
                ),
            }
        ],
        output_format=RolesResult,
    )
    result: RolesResult = parsed.parsed_output

    # Always inject structural roles — boss and critic are mandatory in every cluster.
    role_names = {r.name for r in result.roles}
    if "boss" not in role_names:
        result.roles.insert(
            0,
            RoleSpec(
                name="boss",
                responsibilities=[
                    "coordinate workers",
                    "decompose tasks",
                    "review progress",
                ],
                personality_system_prompt=(
                    f"You are the boss agent for this cluster. Goal: {goal}. "
                    "Coordinate workers, decompose tasks, and review progress."
                ),
                tool_allowlist=[],
            ),
        )
    if "critic" not in role_names:
        result.roles.append(
            RoleSpec(
                name="critic",
                responsibilities=[
                    "peer review all deliverables",
                    "identify weaknesses",
                    "require evidence before approving",
                ],
                personality_system_prompt=(
                    f"You are the critic for this cluster. Goal context: {goal}. "
                    "Your personality: cynical, skeptical, adversarial. You poke holes "
                    "in every deliverable. Find weaknesses, edge cases, and missing "
                    "assumptions. Never rubber-stamp work. Require specific evidence "
                    "before approving."
                ),
                tool_allowlist=[],
            ),
        )
    return result


async def fit_check(roles_result: RolesResult, llm: AsyncAnthropic) -> FitCheckResult:
    """Stage 2: Single-shot quality evaluation of a roles result.

    Returns FitCheckResult with passed=True/False.
    Caller is responsible for retry logic (max 2 retries) — this function is single-shot.
    """
    roles_yaml = yaml.dump(
        [r.model_dump() for r in roles_result.roles],
        default_flow_style=False,
        allow_unicode=True,
    )
    parsed = await llm.messages.parse(
        model=_PIPELINE_MODEL,
        max_tokens=1024,
        system=(
            "You are a quality evaluator. Evaluate whether these agent roles for a "
            "cluster are well-defined. Check: responsibility cohesion (each role's "
            "responsibilities belong together), privilege scope (roles have appropriate "
            "access scope), name clarity (role name clearly describes function)."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Roles to evaluate:\n{roles_yaml}\n\n"
                    "Does this role set pass quality review? Return passed=true/false. "
                    "If false, identify the failing_role and reason."
                ),
            }
        ],
        output_format=FitCheckResult,
    )
    return parsed.parsed_output


async def _enrich_one_role(role: RoleSpec, llm: AsyncAnthropic) -> RoleSpec:
    """Enrich a single role with richer personality and tool_allowlist recommendations."""
    parsed = await llm.messages.parse(
        model=_PIPELINE_MODEL,
        max_tokens=1024,
        system=(
            "You are a role enrichment specialist. Given an agent role specification, "
            "enhance its personality system prompt to be more vivid and directive. "
            "Also recommend specific tool allowlist entries (Python stdlib or PyPI "
            "package names) this role would need. Return the enriched role."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Role to enrich:\n"
                    f"Name: {role.name}\n"
                    f"Responsibilities: {role.responsibilities}\n"
                    f"Current personality: {role.personality_system_prompt}\n\n"
                    "Return an enriched RoleSpec with improved personality_system_prompt "
                    "and appropriate tool_allowlist entries."
                ),
            }
        ],
        output_format=RoleSpec,
    )
    return parsed.parsed_output


async def enrich_roles(roles_result: RolesResult, llm: AsyncAnthropic) -> list[RoleSpec]:
    """Stage 3: Per-role enrichment in parallel using asyncio.gather.

    Each role gets a separate LLM call to enrich its personality and tool allowlist.
    All calls run concurrently.
    """
    return list(
        await asyncio.gather(*[_enrich_one_role(r, llm) for r in roles_result.roles])
    )
