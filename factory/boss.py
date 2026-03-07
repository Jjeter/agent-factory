from runtime.boss import BossAgent


class FactoryBossAgent(BossAgent):
    """Factory-specific boss: decomposes cluster-creation goals into artifact-generation tasks."""

    async def decompose_goal(self, goal_id: str, goal_description: str) -> None:
        raise NotImplementedError
