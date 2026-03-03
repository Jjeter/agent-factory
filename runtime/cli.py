"""Click CLI entry points for cluster and agent-factory commands."""

import asyncio
from pathlib import Path

import click


@click.group()
def cluster_cli() -> None:
    """Cluster runtime management."""


@cluster_cli.group(name="db")
def db_group() -> None:
    """Database lifecycle commands."""


@db_group.command(name="up")
@click.option(
    "--db-path",
    default="cluster.db",
    envvar="CLUSTER_DB_PATH",
    show_default=True,
    help="Path to the SQLite database file.",
)
def db_up(db_path: str) -> None:
    """Initialize the cluster database schema (idempotent)."""
    asyncio.run(_do_up(Path(db_path)))
    click.echo(f"Database initialized: {db_path}")


async def _do_up(path: Path) -> None:
    from runtime.database import DatabaseManager

    mgr = DatabaseManager(path)
    await mgr.up()


@db_group.command(name="reset")
@click.option(
    "--db-path",
    default="cluster.db",
    envvar="CLUSTER_DB_PATH",
    show_default=True,
    help="Path to the SQLite database file.",
)
def db_reset(db_path: str) -> None:
    """Drop all tables and recreate schema. DESTRUCTIVE."""
    asyncio.run(_do_reset(Path(db_path)))
    click.echo(f"Database reset: {db_path}")


async def _do_reset(path: Path) -> None:
    from runtime.database import DatabaseManager

    mgr = DatabaseManager(path)
    await mgr.reset()


@click.group()
def factory_cli() -> None:
    """Agent Factory management. (Full implementation in Phase 5.)"""


# ---------------------------------------------------------------------------
# cluster goal subcommands (Phase 3)
# ---------------------------------------------------------------------------


@cluster_cli.group(name="goal")
def goal_group() -> None:
    """Goal management commands."""


@goal_group.command(name="set")
@click.argument("description")
@click.option(
    "--db-path",
    default="cluster.db",
    envvar="CLUSTER_DB_PATH",
    show_default=True,
    help="Path to the SQLite database file.",
)
def goal_set(description: str, db_path: str) -> None:
    """Set or update the active goal. Archives any existing active goal."""
    asyncio.run(_do_goal_set(Path(db_path), description))
    click.echo("Goal set. Boss will decompose into tasks on next heartbeat.")


async def _do_goal_set(db_path: Path, description: str) -> None:
    from runtime.database import DatabaseManager
    from runtime.models import _uuid, _now_iso

    mgr = DatabaseManager(db_path)
    # Archive any existing active goal
    db = await mgr.open_write()
    try:
        await db.execute(
            "UPDATE goals SET status = 'archived' WHERE status = 'active'"
        )
        await db.commit()
    finally:
        await db.close()

    goal_id = _uuid()
    title = description[:80] + ("..." if len(description) > 80 else "")
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO goals (id, title, description, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            (goal_id, title, description, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    # Trigger immediate decomposition via BossAgent
    from runtime.config import AgentConfig
    from runtime.boss import BossAgent

    config = AgentConfig(agent_id="boss-cli", agent_role="boss", db_path=str(db_path))
    boss = BossAgent(config)
    await boss.decompose_goal(goal_id, description)


# ---------------------------------------------------------------------------
# cluster tasks subcommands (Phase 3)
# ---------------------------------------------------------------------------


@cluster_cli.group(name="tasks")
def tasks_group() -> None:
    """Task management commands."""


@tasks_group.command(name="list")
@click.option("--status", default=None, help="Filter by task status.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON array.")
@click.option(
    "--db-path",
    default="cluster.db",
    envvar="CLUSTER_DB_PATH",
    show_default=True,
    help="Path to the SQLite database file.",
)
def tasks_list(status: str | None, as_json: bool, db_path: str) -> None:
    """List tasks with optional status filter."""
    rows = asyncio.run(_fetch_tasks_rows(Path(db_path), status))
    if as_json:
        import json as _json

        click.echo(_json.dumps(rows, indent=2))
    else:
        from tabulate import tabulate

        table_rows = [
            [r["id"], r["title"], r["status"], r["assigned_to"], r["model_tier"], r["priority"]]
            for r in rows
        ]
        headers = ["ID", "Title", "Status", "Assigned To", "Tier", "Priority"]
        click.echo(tabulate(table_rows, headers=headers, tablefmt="simple"))


async def _fetch_tasks_rows(db_path: Path, status: str | None) -> list[dict]:
    from runtime.database import DatabaseManager

    mgr = DatabaseManager(db_path)
    db = await mgr.open_read()
    try:
        sql = (
            "SELECT id, title, status, assigned_to, model_tier, priority "
            "FROM tasks"
        )
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY priority DESC"
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [
            {
                "id": r["id"][:8],
                "title": r["title"],
                "status": r["status"],
                "assigned_to": r["assigned_to"] or "\u2014",
                "model_tier": r["model_tier"],
                "priority": r["priority"],
            }
            for r in rows
        ]
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# cluster agents subcommands (Phase 3)
# ---------------------------------------------------------------------------


@cluster_cli.group(name="agents")
def agents_group() -> None:
    """Agent status commands."""


@agents_group.command(name="status")
@click.option(
    "--db-path",
    default="cluster.db",
    envvar="CLUSTER_DB_PATH",
    show_default=True,
    help="Path to the SQLite database file.",
)
def agents_status(db_path: str) -> None:
    """Show all agents and their last heartbeat."""
    rows = asyncio.run(_fetch_agents_rows(Path(db_path)))
    from tabulate import tabulate

    headers = ["Agent ID", "Role", "Status", "Last Heartbeat", "Current Task"]
    click.echo(tabulate(rows, headers=headers, tablefmt="simple"))


async def _fetch_agents_rows(db_path: Path) -> list[list]:
    from runtime.database import DatabaseManager

    mgr = DatabaseManager(db_path)
    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT agent_id, agent_role, status, last_heartbeat, current_task FROM agent_status"
        ) as cur:
            rows = await cur.fetchall()
        return [
            [
                r["agent_id"],
                r["agent_role"],
                r["status"],
                r["last_heartbeat"] or "\u2014",
                r["current_task"] or "\u2014",
            ]
            for r in rows
        ]
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# cluster approve command (Phase 3)
# ---------------------------------------------------------------------------


@cluster_cli.command(name="approve")
@click.argument("task_id")
@click.option(
    "--db-path",
    default="cluster.db",
    envvar="CLUSTER_DB_PATH",
    show_default=True,
    help="Path to the SQLite database file.",
)
def approve_task(task_id: str, db_path: str) -> None:
    """Approve a task that is in 'review' state."""
    try:
        asyncio.run(_do_approve(Path(db_path), task_id))
        click.echo(f"Task {task_id[:8]} approved.")
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)


async def _do_approve(db_path: Path, task_id: str) -> None:
    from runtime.database import DatabaseManager
    from runtime.models import _now_iso, TaskStatus
    from runtime.state_machine import TaskStateMachine, InvalidTransitionError

    mgr = DatabaseManager(db_path)
    db = await mgr.open_read()
    try:
        async with db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()

    if row is None:
        raise ValueError(f"Task {task_id!r} not found")

    # Validate transition using TaskStateMachine — raises InvalidTransitionError if not in 'review'
    machine = TaskStateMachine()
    machine.apply(TaskStatus(row["status"]), TaskStatus.APPROVED)

    db = await mgr.open_write()
    try:
        await db.execute(
            "UPDATE tasks SET status = 'approved', updated_at = ? WHERE id = ?",
            (_now_iso(), task_id),
        )
        await db.commit()
    finally:
        await db.close()
