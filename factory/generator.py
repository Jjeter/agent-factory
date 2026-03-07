"""Deterministic artifact generators for factory cluster output.

All functions are pure Python — no LLM calls, no side effects except copy_runtime.
"""
from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import yaml

from factory.models import RoleSpec

# Baseline runtime packages always included in generated requirements.txt
_BASELINE_PACKAGES = [
    "anthropic",
    "aiosqlite",
    "click",
    "pydantic",
    "tabulate",
]


def render_agent_yaml(
    role: RoleSpec,
    cluster_config: dict | None = None,
    stagger_offset_seconds: float = 0.0,
) -> str:
    """Return YAML string for a single agent config file.

    cluster_config is accepted for backwards compatibility but ignored for stagger
    calculation — pass stagger_offset_seconds explicitly.
    """
    data = {
        "agent_id": f"{role.name}-01",
        "agent_role": role.name,
        "stagger_offset_seconds": stagger_offset_seconds,
        "system_prompt": role.personality_system_prompt,
        "tool_allowlist": role.tool_allowlist,
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def render_docker_compose(
    cluster_name: str,
    roles: list[RoleSpec],
    interval_seconds: float = 600.0,
) -> str:
    """Return docker-compose.yml YAML string.

    Always includes boss and critic as structural services.
    Each service uses the cluster-data named volume at /data.
    """
    total_count = len(roles) + 2  # boss + critic always added

    services: dict = {}

    # Boss is always index 0
    services["boss"] = {
        "build": ".",
        "command": "python -m runtime.cli run-agent --role boss",
        "volumes": ["cluster-data:/data"],
        "env_file": ".env",
    }

    # Critic is always index 1
    services["critic"] = {
        "build": ".",
        "command": "python -m runtime.cli run-agent --role critic",
        "volumes": ["cluster-data:/data"],
        "env_file": ".env",
    }

    # Worker roles start at index 2
    for idx, role in enumerate(roles, start=2):
        services[role.name] = {
            "build": ".",
            "command": f"python -m runtime.cli run-agent --role {role.name}",
            "volumes": ["cluster-data:/data"],
            "env_file": ".env",
        }

    data = {
        "services": services,
        "volumes": {"cluster-data": None},
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def render_cluster_yaml(
    cluster_name: str,
    goal: str,
    roles: list[RoleSpec],
    db_path: str = "/data/cluster.db",
) -> str:
    """Return cluster.yaml YAML string with cluster metadata."""
    data = {
        "cluster_name": cluster_name,
        "goal": goal,
        "db_path": db_path,
        "interval_seconds": 600.0,
        "jitter_seconds": 30.0,
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def render_launch_sh(cluster_name: str) -> str:
    """Return launch.sh shell script content.

    Script checks for ANTHROPIC_API_KEY and exits 1 if not set.
    """
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        if [[ -z "${{ANTHROPIC_API_KEY:-}}" ]]; then
          echo "ERROR: ANTHROPIC_API_KEY is not set. Export it before running launch.sh." >&2
          exit 1
        fi
        docker compose build
        docker compose up -d
        echo "Cluster {cluster_name} started. Use 'cluster tasks list' to track progress."
        """
    )


def render_dockerfile(roles: list[RoleSpec]) -> str:
    """Return Dockerfile content.

    Uses python:3.12-slim base by default.
    Uses ubuntu:22.04 base if any role has requires_glibc=True.
    """
    needs_glibc = any(r.requires_glibc for r in roles)

    if needs_glibc:
        return textwrap.dedent(
            """\
            FROM ubuntu:22.04
            RUN apt-get update && apt-get install -y python3.12 python3-pip && rm -rf /var/lib/apt/lists/*
            WORKDIR /app
            COPY requirements.txt .
            RUN pip3 install --no-cache-dir -r requirements.txt
            COPY runtime/ runtime/
            COPY config/ config/
            CMD ["python3", "-m", "runtime.cli", "run-agent"]
            """
        )
    else:
        return textwrap.dedent(
            """\
            FROM python:3.12-slim
            WORKDIR /app
            COPY requirements.txt .
            RUN pip install --no-cache-dir -r requirements.txt
            COPY runtime/ runtime/
            COPY config/ config/
            CMD ["python", "-m", "runtime.cli", "run-agent"]
            """
        )


def render_requirements_txt(roles: list[RoleSpec]) -> str:
    """Return requirements.txt content.

    Always includes baseline runtime packages.
    Adds deduplicated, sorted tool_allowlist entries from all roles.
    """
    extra: set[str] = set()
    for role in roles:
        for pkg in role.tool_allowlist:
            extra.add(pkg)

    all_packages = sorted(set(_BASELINE_PACKAGES) | extra)
    return "\n".join(all_packages) + "\n"


def copy_runtime(dest_dir: Path) -> None:
    """Copy the runtime/ package into dest_dir/runtime/.

    Uses shutil.copytree with dirs_exist_ok=True for idempotency.
    """
    src = Path(__file__).parent.parent / "runtime"
    shutil.copytree(src, dest_dir / "runtime", dirs_exist_ok=True)
