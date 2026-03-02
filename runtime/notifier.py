"""Notifier protocol and stdout implementation for agent event notifications."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    async def notify_review_ready(self, task_id: str, task_title: str) -> None: ...
    async def notify_escalation(self, task_id: str, reason: str) -> None: ...
    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None: ...


class StdoutNotifier:
    """Stdout implementation of the Notifier protocol — no inheritance, structural typing only."""

    async def notify_review_ready(self, task_id: str, task_title: str) -> None:
        print(f"[REVIEW READY] task={task_id} title={task_title!r}")

    async def notify_escalation(self, task_id: str, reason: str) -> None:
        print(f"[ESCALATION] task={task_id} reason={reason!r}")

    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None:
        print(f"[CLUSTER READY] name={cluster_name!r} path={path!r}")
