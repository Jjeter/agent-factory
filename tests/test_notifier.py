"""TDD stub tests for Phase 2 — Notifier protocol and StdoutNotifier.

Covers HB-03 (StdoutNotifier satisfies Notifier protocol, all methods async).

Uses pytest.importorskip inside the test body so pytest can collect this file
before runtime/notifier.py exists. Test skips cleanly when the module is absent.
"""
import pytest


async def test_stdout_notifier(capsys):
    """HB-03: StdoutNotifier satisfies Notifier protocol with async methods."""
    notifier_mod = pytest.importorskip("runtime.notifier")
    StdoutNotifier = notifier_mod.StdoutNotifier

    notifier = StdoutNotifier()

    # All three protocol methods must exist
    assert hasattr(notifier, "notify_review_ready")
    assert hasattr(notifier, "notify_escalation")
    assert hasattr(notifier, "notify_cluster_ready")

    # Each method must be awaitable and not raise
    await notifier.notify_review_ready(task_id="t-1", task_title="Test task")
    out1 = capsys.readouterr().out
    assert out1.strip(), "notify_review_ready must print non-empty output"

    await notifier.notify_escalation(task_id="t-1", reason="2 rejections")
    out2 = capsys.readouterr().out
    assert out2.strip(), "notify_escalation must print non-empty output"

    await notifier.notify_cluster_ready(cluster_name="demo", path="/tmp/demo")
    out3 = capsys.readouterr().out
    assert out3.strip(), "notify_cluster_ready must print non-empty output"
