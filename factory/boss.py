"""factory/boss.py — FactoryBossAgent: boss for cluster-creation goals.

FactoryBossAgent overrides decompose_goal with a deterministic factory task set.
No LLM call is made in decompose_goal — the workflow for cluster creation is fixed
and well-known. The pipeline (factory/pipeline.py) handles all LLM role decomposition.

Task set covers the complete cluster artifact generation workflow:
  1. Research tool dependencies
  2. Design agent roles via decomposition pipeline
  3. Generate agent YAML configs
  4. Write docker-compose.yml
  5. Write Dockerfile and requirements.txt
  6. Seed cluster database
  7. Write launch.sh and .env.example

CRITICAL — circular import guard: factory/boss.py imports from runtime/; runtime/
must NEVER import from factory/.
"""
from __future__ import annotations

from runtime.boss import BossAgent

# ---------------------------------------------------------------------------
# Factory task set — deterministic, no LLM call
# ---------------------------------------------------------------------------

_FACTORY_TASKS: list[dict] = [
    {
        "title": "Research tool dependencies",
        "description": (
            "Investigate what Python libraries and tools the goal requires. "
            "Produce a requirements.txt list with justification for each dependency. "
            "Flag any glibc-dependent packages."
        ),
        "priority": 80,
        "model_tier": "haiku",
        "assigned_role": "researcher",
        "reviewer_roles": ["critic"],
    },
    {
        "title": "Design agent roles via decomposition pipeline",
        "description": (
            "Run the role decomposition pipeline: enumerate responsibilities, cluster "
            "into roles, fit-check (max 2 retries), enrich with personality and tool "
            "allowlists. Produce a validated RoleSpec list."
        ),
        "priority": 90,
        "model_tier": "sonnet",
        "assigned_role": "executor",
        "reviewer_roles": ["critic"],
    },
    {
        "title": "Generate agent YAML configs",
        "description": (
            "Using the validated RoleSpec list, generate agents/*.yaml files for each "
            "role including boss and critic. Use generator.render_agent_yaml() — no "
            "free-form YAML."
        ),
        "priority": 70,
        "model_tier": "haiku",
        "assigned_role": "executor",
        "reviewer_roles": ["critic"],
    },
    {
        "title": "Write docker-compose.yml",
        "description": (
            "Generate the cluster docker-compose.yml with one service per role, shared "
            "cluster-data volume, computed stagger offsets. Use "
            "generator.render_docker_compose()."
        ),
        "priority": 70,
        "model_tier": "haiku",
        "assigned_role": "executor",
        "reviewer_roles": ["critic"],
    },
    {
        "title": "Write Dockerfile and requirements.txt",
        "description": (
            "Generate Dockerfile (python:3.12-slim base, or ubuntu:22.04 if "
            "security-checker flagged glibc dependencies) and requirements.txt. "
            "Use generator.render_dockerfile() and generator.render_requirements_txt()."
        ),
        "priority": 70,
        "model_tier": "haiku",
        "assigned_role": "executor",
        "reviewer_roles": ["critic"],
    },
    {
        "title": "Seed cluster database",
        "description": (
            "Initialize the cluster SQLite database with the goal using "
            "DatabaseManager.up() and INSERT INTO goals. Insert agent_status rows "
            "for each generated agent. Verify schema is correct."
        ),
        "priority": 60,
        "model_tier": "haiku",
        "assigned_role": "executor",
        "reviewer_roles": ["critic"],
    },
    {
        "title": "Write launch.sh and .env.example",
        "description": (
            "Generate launch.sh with ANTHROPIC_API_KEY validation guard and docker "
            "compose build+up. Generate .env.example with placeholder values. "
            "Use generator.render_launch_sh()."
        ),
        "priority": 60,
        "model_tier": "haiku",
        "assigned_role": "executor",
        "reviewer_roles": ["critic"],
    },
]


class FactoryBossAgent(BossAgent):
    """Factory-specific boss: decomposes cluster-creation goals into artifact-generation tasks.

    Overrides decompose_goal with a deterministic task set — no LLM call.
    The pipeline (factory/pipeline.py) handles all LLM role decomposition work.
    """

    async def decompose_goal(self, goal_id: str, goal_description: str) -> None:
        """Emit the fixed factory task set for any cluster-creation goal.

        Does NOT call the LLM — the task set is deterministic because the
        cluster artifact generation workflow is fixed and well-known.
        """
        from runtime.boss import TaskSpec
        from runtime.models import _uuid

        for spec_dict in _FACTORY_TASKS:
            task_id = _uuid()
            spec = TaskSpec(
                title=spec_dict["title"],
                description=f"{spec_dict['description']}\n\nCluster goal: {goal_description}",
                priority=spec_dict["priority"],
                model_tier=spec_dict["model_tier"],
                assigned_role=spec_dict["assigned_role"],
                reviewer_roles=spec_dict["reviewer_roles"],
            )
            await self._insert_task(
                goal_id,
                task_id,
                spec,
                reviewer_agents=["factory-critic-01"],
            )
