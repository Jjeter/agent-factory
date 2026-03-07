from pathlib import Path

from factory.models import RoleSpec


def render_agent_yaml(
    role: RoleSpec,
    cluster_config: dict | None = None,
    stagger_offset_seconds: float = 0.0,
) -> str:
    raise NotImplementedError


def render_docker_compose(
    cluster_name: str,
    roles: list[RoleSpec],
    interval_seconds: float = 600.0,
) -> str:
    raise NotImplementedError


def render_cluster_yaml(
    cluster_name: str,
    goal: str,
    roles: list[RoleSpec],
    db_path: str = "/data/cluster.db",
) -> str:
    raise NotImplementedError


def render_launch_sh(cluster_name: str) -> str:
    raise NotImplementedError


def render_dockerfile(roles: list[RoleSpec]) -> str:
    raise NotImplementedError


def render_requirements_txt(roles: list[RoleSpec]) -> str:
    raise NotImplementedError


def copy_runtime(dest_dir: Path) -> None:
    raise NotImplementedError
