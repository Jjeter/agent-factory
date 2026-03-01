"""Tests for runtime.notifier — Notifier Protocol and StdoutNotifier.

HB-07: Notifier Protocol satisfied by StdoutNotifier at runtime.
HB-08: StdoutNotifier.notify_review_ready() prints correct output.
HB-09: StdoutNotifier.notify_escalation() prints correct output.
"""
import pytest


class TestNotifierProtocol:
    def test_stdout_notifier_satisfies_protocol(self):
        """HB-07: isinstance(StdoutNotifier(), Notifier) is True at runtime."""
        from runtime.notifier import Notifier, StdoutNotifier

        notifier = StdoutNotifier()
        assert isinstance(notifier, Notifier)


class TestStdoutNotifier:
    async def test_stdout_notifier_review_ready(self, capsys):
        """HB-08: notify_review_ready() prints task_id and task_title to stdout."""
        from runtime.notifier import StdoutNotifier

        notifier = StdoutNotifier()
        await notifier.notify_review_ready("task-123", "Write design doc")

        captured = capsys.readouterr()
        assert "task-123" in captured.out
        assert "Write design doc" in captured.out

    async def test_stdout_notifier_escalation(self, capsys):
        """HB-09: notify_escalation() prints task_id and reason to stdout."""
        from runtime.notifier import StdoutNotifier

        notifier = StdoutNotifier()
        await notifier.notify_escalation("task-456", "2 peer rejections")

        captured = capsys.readouterr()
        assert "task-456" in captured.out
        assert "2 peer rejections" in captured.out
