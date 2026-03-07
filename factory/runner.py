import asyncio
import sys


async def run_factory(goal_id: str, db_path: str) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(run_factory(sys.argv[1], sys.argv[2]))
