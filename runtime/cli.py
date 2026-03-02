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
