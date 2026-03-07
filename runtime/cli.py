"""Click CLI entry points for cluster and agent-factory commands."""

import asyncio
import os
import re
import subprocess
import sys
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
    """Agent Factory management."""


# ---------------------------------------------------------------------------
# factory_cli: create / list / status / add-role subcommands (Phase 5)
# ---------------------------------------------------------------------------


def _factory_home() -> Path:
    return Path(os.environ.get("FACTORY_HOME", Path.home() / ".agent-factory"))


def _clusters_base() -> Path:
    """Return the base directory for cluster output dirs.

    Reads FACTORY_CLUSTERS_BASE env var first (for testing), then defaults
    to Path.cwd() / 'clusters' per the project spec.
    """
    env_override = os.environ.get("FACTORY_CLUSTERS_BASE")
    if env_override:
        return Path(env_override)
    return Path.cwd() / "clusters"


def _slugify(goal: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")[:50]


@factory_cli.command(name="create")
@click.argument("goal")
@click.option("--name", default=None, help="Cluster name slug (auto-generated from goal if omitted)")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing cluster directory")
def factory_create(goal: str, name: str | None, force: bool) -> None:
    """Create a new agent cluster from a natural-language goal (fire-and-forget)."""
    asyncio.run(_do_factory_create(goal, name, force))


async def _do_factory_create(goal: str, name: str | None, force: bool) -> None:
    from runtime.database import DatabaseManager
    from runtime.models import _uuid, _now_iso

    cluster_name = name or _slugify(goal)
    factory_home = _factory_home()
    cluster_dir = _clusters_base() / cluster_name

    if cluster_dir.exists() and not force:
        raise click.ClickException(
            f"Cluster '{cluster_name}' already exists at {cluster_dir}. Use --force to overwrite."
        )

    factory_db = factory_home / "factory.db"
    factory_home.mkdir(parents=True, exist_ok=True)

    mgr = DatabaseManager(factory_db)
    await mgr.up()

    goal_id = _uuid()
    db = await mgr.open_write()
    try:
        await db.execute(
            "INSERT INTO goals (id, title, description, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            (goal_id, cluster_name, goal, _now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    cluster_dir.mkdir(parents=True, exist_ok=True)

    subprocess.Popen(
        [sys.executable, "-m", "factory.runner", goal_id, str(factory_db)],
        close_fds=True,
    )

    click.echo(f"Factory job started: {cluster_name}")
    click.echo(f"  Factory DB: {factory_db}")
    click.echo(f"  Track progress: agent-factory status {cluster_name}")
    click.echo(f"  Cluster output: ./clusters/{cluster_name}/ (when complete)")


@factory_cli.command(name="list")
def factory_list() -> None:
    """List all factory cluster jobs."""
    asyncio.run(_do_factory_list())


async def _do_factory_list() -> None:
    from runtime.database import DatabaseManager

    factory_db = _factory_home() / "factory.db"
    if not factory_db.exists():
        click.echo("No factory jobs found.")
        return

    mgr = DatabaseManager(factory_db)
    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT title, status, created_at FROM goals ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()

    if not rows:
        click.echo("No factory jobs found.")
        return

    from tabulate import tabulate

    table = [[r["title"], r["status"], r["created_at"]] for r in rows]
    click.echo(tabulate(table, headers=["Name", "Status", "Created"], tablefmt="simple"))


@factory_cli.command(name="status")
@click.argument("name")
def factory_status(name: str) -> None:
    """Show status of a factory job."""
    asyncio.run(_do_factory_status(name))


async def _do_factory_status(name: str) -> None:
    from runtime.database import DatabaseManager

    factory_db = _factory_home() / "factory.db"
    if not factory_db.exists():
        click.echo(f"Factory job '{name}' not found (no factory DB).")
        return

    mgr = DatabaseManager(factory_db)
    db = await mgr.open_read()
    try:
        async with db.execute(
            "SELECT id, title, status FROM goals WHERE title = ?", (name,)
        ) as cur:
            goal_row = await cur.fetchone()

        if goal_row is None:
            click.echo(f"Factory job '{name}' not found.")
            return

        goal_id = goal_row["id"]
        goal_status = goal_row["status"]

        async with db.execute(
            "SELECT id, title, status, assigned_to FROM tasks WHERE goal_id = ? ORDER BY priority DESC",
            (goal_id,),
        ) as cur:
            task_rows = await cur.fetchall()
    finally:
        await db.close()

    click.echo(f"\nFactory: {name}  [{goal_status.upper()}]\n")

    if task_rows:
        from tabulate import tabulate

        table = [
            [r["id"][:8], r["title"], r["status"], r["assigned_to"] or "\u2014"]
            for r in task_rows
        ]
        headers = ["ID", "Title", "Status", "Assigned To"]
        click.echo(tabulate(table, headers=headers, tablefmt="simple"))

    if goal_status == "completed":
        click.echo(f"\nCluster ready: ./clusters/{name}/")
        click.echo(f"  Launch: cd clusters/{name} && ./launch.sh")


@factory_cli.command(name="add-role")
@click.argument("cluster_name")
@click.argument("role_description")
def factory_add_role(cluster_name: str, role_description: str) -> None:
    """Add a new agent role to an existing cluster."""
    asyncio.run(_do_factory_add_role(cluster_name, role_description))


async def _do_factory_add_role(cluster_name: str, role_description: str) -> None:
    cluster_dir = _clusters_base() / cluster_name
    if not cluster_dir.exists():
        click.echo(f"Cluster '{cluster_name}' not found at {cluster_dir}.")
        return

    from anthropic import AsyncAnthropic
    from factory.pipeline import _enrich_one_role
    from factory.models import RoleSpec
    from factory.generator import render_agent_yaml, render_docker_compose

    llm = AsyncAnthropic()

    role_slug = _slugify(role_description)
    base_role = RoleSpec(
        name=role_slug,
        responsibilities=[role_description],
        personality_system_prompt=f"You are the {role_slug} agent. {role_description}",
        tool_allowlist=[],
    )
    enriched_role = await _enrich_one_role(base_role, llm)

    agents_dir = cluster_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    role_yaml_path = agents_dir / f"{enriched_role.name}.yaml"
    role_yaml_path.write_text(render_agent_yaml(enriched_role), encoding="utf-8")

    # Re-render docker-compose with all existing roles + new role
    existing_roles: list[RoleSpec] = []
    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        if yaml_file.stem not in ("boss", "critic"):
            import yaml as _yaml
            raw = _yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            existing_roles.append(
                RoleSpec(
                    name=raw.get("agent_role", yaml_file.stem),
                    responsibilities=[],
                    personality_system_prompt=raw.get("system_prompt", ""),
                    tool_allowlist=raw.get("tool_allowlist", []),
                )
            )

    compose_path = cluster_dir / "docker-compose.yml"
    compose_path.write_text(
        render_docker_compose(cluster_name, existing_roles), encoding="utf-8"
    )

    click.echo(f"Role '{enriched_role.name}' added to {cluster_name}. Restart with ./launch.sh to activate.")


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
