"""Structural tests for the committed demo cluster artifact."""

import pytest
from pathlib import Path


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_demo_artifact_docker_compose_exists():
    """clusters/demo-date-arithmetic/docker-compose.yml exists."""
    assert Path("clusters/demo-date-arithmetic/docker-compose.yml").exists()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_demo_artifact_launch_sh_exists():
    """clusters/demo-date-arithmetic/launch.sh exists."""
    assert Path("clusters/demo-date-arithmetic/launch.sh").exists()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_demo_artifact_env_example_exists():
    """clusters/demo-date-arithmetic/.env.example exists."""
    assert Path("clusters/demo-date-arithmetic/.env.example").exists()


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_cluster_db_seeded():
    """clusters/demo-date-arithmetic/db/cluster.db has >= 2 rows in agent_status."""
    import sqlite3

    conn = sqlite3.connect("clusters/demo-date-arithmetic/db/cluster.db")
    count = conn.execute("SELECT count(*) FROM agent_status").fetchone()[0]
    conn.close()
    assert count >= 2


@pytest.mark.xfail(strict=False, reason="not yet implemented")
def test_readme_exists():
    """README.md exists at the project root."""
    assert Path("README.md").exists()
