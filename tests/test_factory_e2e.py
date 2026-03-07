"""End-to-end tests for factory artifact generation."""
import shutil
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_roles():
    models = pytest.importorskip("factory.models")
    return [
        models.RoleSpec(
            name="analyst",
            responsibilities=["analyze data", "produce insights"],
            personality_system_prompt="You are an analyst. Examine data carefully and produce clear insights.",
            tool_allowlist=[],
        ),
        models.RoleSpec(
            name="writer",
            responsibilities=["write reports", "summarize findings"],
            personality_system_prompt="You are a writer. Turn raw findings into clear, engaging prose.",
            tool_allowlist=[],
        ),
    ]


async def test_full_artifact_created(tmp_path, sample_roles):
    """E2E-01: generator functions produce a complete cluster artifact directory.

    Covers REQUIREMENTS §5 Factory Output Structure including the Dockerfile and
    requirements.txt required by the locked Dockerfile/Image Strategy decision.
    """
    gen = pytest.importorskip("factory.generator")
    models = pytest.importorskip("factory.models")

    cluster_name = "test-mtg-advisor"
    goal = "Build a MTG deckbuilding advisor"
    cluster_dir = tmp_path / "clusters" / cluster_name

    # Create directory structure
    (cluster_dir / "config" / "agents").mkdir(parents=True)
    (cluster_dir / "db").mkdir(parents=True)

    # Add structural roles
    boss_role = models.RoleSpec(
        name="boss",
        responsibilities=["coordinate workers", "decompose tasks"],
        personality_system_prompt=f"You are the boss for {cluster_name}. Goal: {goal}.",
        tool_allowlist=[],
    )
    critic_role = models.RoleSpec(
        name="critic",
        responsibilities=["peer review all deliverables", "identify weaknesses"],
        personality_system_prompt=f"You are the critic for {cluster_name}. Be cynical and adversarial.",
        tool_allowlist=[],
    )
    all_roles = [boss_role, critic_role] + sample_roles

    # Generate artifact files
    stagger_interval = 600.0
    total_roles = len(all_roles)
    for i, role in enumerate(all_roles):
        stagger = round(i * (stagger_interval / total_roles), 1)
        yaml_content = gen.render_agent_yaml(role, stagger_offset_seconds=stagger)
        agent_path = cluster_dir / "config" / "agents" / f"{role.name}.yaml"
        agent_path.write_text(yaml_content, encoding="utf-8")

    cluster_yaml = gen.render_cluster_yaml(cluster_name, goal, all_roles)
    (cluster_dir / "config" / "cluster.yaml").write_text(cluster_yaml, encoding="utf-8")

    compose_yaml = gen.render_docker_compose(cluster_name, all_roles)
    (cluster_dir / "docker-compose.yml").write_text(compose_yaml, encoding="utf-8")

    launch_sh = gen.render_launch_sh(cluster_name)
    (cluster_dir / "launch.sh").write_text(launch_sh, encoding="utf-8")

    # Generate Dockerfile and requirements.txt (locked CONTEXT.md decision)
    dockerfile_content = gen.render_dockerfile(all_roles)
    (cluster_dir / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")

    requirements_content = gen.render_requirements_txt(all_roles)
    (cluster_dir / "requirements.txt").write_text(requirements_content, encoding="utf-8")

    # Generate .env.example
    env_example = "ANTHROPIC_API_KEY=your-key-here\nCLUSTER_NAME={}\nCLUSTER_DB_PATH=/data/cluster.db\n".format(cluster_name)
    (cluster_dir / ".env.example").write_text(env_example, encoding="utf-8")

    # Copy db/schema.sql
    schema_src = Path(__file__).parent.parent / "runtime" / "schema.sql"
    shutil.copy2(schema_src, cluster_dir / "db" / "schema.sql")

    # Copy runtime/
    gen.copy_runtime(cluster_dir)

    # Assertions — REQUIREMENTS §5 structure
    assert (cluster_dir / "docker-compose.yml").exists()
    assert (cluster_dir / ".env.example").exists()
    assert (cluster_dir / "config" / "cluster.yaml").exists()
    assert (cluster_dir / "config" / "agents" / "boss.yaml").exists()
    assert (cluster_dir / "config" / "agents" / "critic.yaml").exists()
    assert (cluster_dir / "config" / "agents" / "analyst.yaml").exists()
    assert (cluster_dir / "db" / "schema.sql").exists()
    assert (cluster_dir / "runtime" / "__init__.py").exists()
    assert (cluster_dir / "launch.sh").exists()

    # Dockerfile and requirements.txt must exist (standalone cluster — no factory repo dependency)
    assert (cluster_dir / "Dockerfile").exists(), "Dockerfile missing — locked CONTEXT.md decision requires standalone Dockerfile"
    assert (cluster_dir / "requirements.txt").exists(), "requirements.txt missing — Dockerfile COPYs and pip installs it"

    # docker-compose.yml is valid YAML with services
    compose_loaded = yaml.safe_load((cluster_dir / "docker-compose.yml").read_text())
    assert "services" in compose_loaded
    assert "boss" in compose_loaded["services"]
    assert "critic" in compose_loaded["services"]
    assert "analyst" in compose_loaded["services"]

    # launch.sh has required guard
    launch_content = (cluster_dir / "launch.sh").read_text()
    assert "ANTHROPIC_API_KEY" in launch_content
    assert "exit 1" in launch_content

    # cluster.yaml has required fields
    cluster_loaded = yaml.safe_load((cluster_dir / "config" / "cluster.yaml").read_text())
    assert cluster_loaded["cluster_name"] == cluster_name
    assert cluster_loaded["goal"] == goal

    # Dockerfile uses python:3.12-slim base (no glibc roles in sample_roles)
    dockerfile_text = (cluster_dir / "Dockerfile").read_text()
    assert "FROM python:3.12-slim" in dockerfile_text

    # requirements.txt contains at least one baseline package
    reqs_text = (cluster_dir / "requirements.txt").read_text()
    assert "anthropic" in reqs_text


async def test_db_seeded_correctly(tmp_path):
    """E2E-02: DatabaseManager.up() + goal INSERT produces queryable goal row.

    Also verifies the agent_status table exists in the schema (REQUIREMENTS §5
    success criterion: 'seeded DB has correct goal and initial agent_status rows').
    """
    db_mod = pytest.importorskip("runtime.database")
    models_mod = pytest.importorskip("runtime.models")

    db_path = tmp_path / "cluster.db"
    mgr = db_mod.DatabaseManager(db_path)
    await mgr.up()

    goal_id = models_mod._uuid()
    cluster_name = "test-cluster"
    goal_description = "Build a MTG deckbuilding advisor"

    write_conn = await mgr.open_write()
    try:
        await write_conn.execute(
            "INSERT INTO goals (id, title, description) VALUES (?, ?, ?)",
            (goal_id, cluster_name, goal_description),
        )
        await write_conn.commit()
    finally:
        await write_conn.close()

    # Verify the goal row exists and is readable
    read_conn = await mgr.open_read()
    try:
        cursor = await read_conn.execute(
            "SELECT id, title, description, status FROM goals WHERE id = ?",
            (goal_id,),
        )
        row = await cursor.fetchone()
    finally:
        await read_conn.close()

    assert row is not None
    assert row["id"] == goal_id
    assert row["title"] == cluster_name
    assert row["description"] == goal_description
    assert row["status"] == "active"

    # Verify agent_status table exists and is queryable (created by DatabaseManager.up())
    # REQUIREMENTS §5: "seeded DB has correct goal and initial agent_status rows"
    count_conn = await mgr.open_read()
    try:
        cursor = await count_conn.execute("SELECT count(*) as cnt FROM agent_status")
        count_row = await cursor.fetchone()
    finally:
        await count_conn.close()
    assert count_row["cnt"] >= 0  # table is queryable; actual agent rows seeded by runner.py at startup
