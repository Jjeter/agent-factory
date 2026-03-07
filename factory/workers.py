from runtime.worker import WorkerAgent


class FactoryResearcherAgent(WorkerAgent):
    """Investigates tool dependencies and required Python packages."""
    pass


class FactorySecurityCheckerAgent(WorkerAgent):
    """Audits tool dependencies for privilege scope, glibc requirements, and known CVEs."""
    pass


class FactoryExecutorAgent(WorkerAgent):
    """Materializes cluster artifact files from validated RoleSpec and pipeline output."""
    pass
