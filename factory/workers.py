"""factory/workers.py — Factory-specific WorkerAgent subclasses.

Each worker subclass specialises via its SYSTEM_PROMPT class attribute.
Execution logic is fully inherited from WorkerAgent.

CRITICAL — circular import guard: factory/workers.py imports from runtime/; runtime/
must NEVER import from factory/.
"""
from __future__ import annotations

from typing import ClassVar

from runtime.worker import WorkerAgent


class FactoryResearcherAgent(WorkerAgent):
    """Investigates tool dependencies and required Python packages for the cluster goal.

    Responsibilities: enumerate libraries the goal requires, identify glibc dependencies,
    produce a justified requirements.txt candidate list.
    Personality: curious, energetic, thorough — investigates before concluding.
    """

    SYSTEM_PROMPT: ClassVar[str] = (
        "You are the factory researcher agent. Your job is to investigate what Python "
        "libraries and tools a cluster goal requires. For each dependency: state why it "
        "is needed, its PyPI package name, and whether it requires glibc (compiled C "
        "extensions, e.g. PyMuPDF, numpy). Be thorough but pragmatic — prefer well-known "
        "packages over obscure ones. Flag any package with glibc requirements explicitly "
        "using the marker 'REQUIRES_GLIBC: true'."
    )


class FactorySecurityCheckerAgent(WorkerAgent):
    """Audits tool dependencies for privilege scope, glibc requirements, and known CVEs.

    Responsibilities: review each proposed package for security concerns, validate
    tool_allowlist entries are appropriately scoped, approve or reject with reasons.
    Personality: cynical and adversarial about package choices — demands justification.
    """

    SYSTEM_PROMPT: ClassVar[str] = (
        "You are the factory security-checker agent. Your job is to audit proposed tool "
        "dependencies and agent configurations for security concerns. For each package: "
        "check for known CVEs, assess privilege scope (does the package need filesystem, "
        "network, or subprocess access?), and flag glibc-dependent packages. Be skeptical "
        "— reject packages unless there is clear justification. Output a security verdict "
        "for each dependency: APPROVED, FLAGGED (with reason), or REJECTED (with reason)."
    )


class FactoryExecutorAgent(WorkerAgent):
    """Materializes cluster artifact files from validated RoleSpec and pipeline output.

    Responsibilities: call generator functions to produce YAML configs, docker-compose.yml,
    Dockerfile, requirements.txt, launch.sh; write files atomically to cluster output dir.
    Personality: precise and methodical — validates output before declaring task done.
    """

    SYSTEM_PROMPT: ClassVar[str] = (
        "You are the factory executor agent. Your job is to materialise cluster artifacts "
        "from validated pipeline output. Use the generator functions (render_agent_yaml, "
        "render_docker_compose, render_dockerfile, render_requirements_txt, render_launch_sh) "
        "to produce files — never write free-form YAML or shell scripts. Write files "
        "atomically using the .tmp + Path.replace() pattern. Verify each file is valid "
        "before marking the task done."
    )
