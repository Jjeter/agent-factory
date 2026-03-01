"""Notifier protocol and built-in implementations for the Agent Factory runtime.

The Notifier is a pluggable interface: any class that implements the three
async methods satisfies the Protocol without inheritance.

V1 ships StdoutNotifier (prints to console).
Future: DiscordNotifier, SlackNotifier — no changes to this module needed.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    """Pluggable notification interface for agent events.

    Any class implementing these three async methods satisfies this Protocol.
    No inheritance required — structural subtyping via typing.Protocol.

    @runtime_checkable enables isinstance(obj, Notifier) checks at runtime.
    """

    async def notify_review_ready(self, task_id: str, task_title: str) -> None:
        """Called when all peer reviews on a task are approved; task awaits user sign-off."""
        ...

    async def notify_escalation(self, task_id: str, reason: str) -> None:
        """Called when a task's model tier is escalated due to repeated rejections."""
        ...

    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None:
        """Called when the factory has finished generating a new cluster artifact."""
        ...


class StdoutNotifier:
    """V1 notifier: prints event messages to stdout.

    Does NOT inherit from Notifier — satisfies the Protocol structurally.
    This is intentional: external implementations (Discord, Slack) will also
    satisfy the Protocol without modifying this module.
    """

    async def notify_review_ready(self, task_id: str, task_title: str) -> None:
        print(f"[REVIEW READY] Task {task_id!r}: {task_title}")

    async def notify_escalation(self, task_id: str, reason: str) -> None:
        print(f"[ESCALATION] Task {task_id!r}: {reason}")

    async def notify_cluster_ready(self, cluster_name: str, path: str) -> None:
        print(f"[CLUSTER READY] {cluster_name!r} at {path}")
