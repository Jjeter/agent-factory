"""Security test stubs for Phase 7 — TDD RED gate.

Covers SEC-01 (tool allowlist enforcement) and SEC-02 (cross-cluster DB isolation).
Both stubs use xfail(strict=False) consistent with Phases 3-6 pattern.
"""
import pytest
from pathlib import Path


# ── SEC-01: Tool allowlist enforcement ───────────────────────────────────────


@pytest.mark.xfail(strict=False, reason="Tool allowlist enforcement not yet implemented")
@pytest.mark.asyncio
async def test_tool_allowlist_blocks_disallowed_call(tmp_path):
    """WorkerAgent must NOT forward a disallowed tool call from the LLM."""
    pytest.importorskip("runtime.worker")
    # Setup: create WorkerAgent with tool_allowlist=["allowed_tool"]
    # Mock _llm.messages.create to return a response with tool_use block for "disallowed_tool"
    # Assert: WorkerAgent either raises DisallowedToolCallError or logs+skips (does NOT call the tool)
    # The test body is a stub — just have it xfail at pytest.xfail() call
    pytest.xfail("SEC-01 not yet implemented")


# ── SEC-02: Cross-cluster DB isolation ───────────────────────────────────────


@pytest.mark.xfail(strict=False, reason="Cross-cluster DB isolation test not yet implemented")
@pytest.mark.asyncio
async def test_cross_cluster_db_isolation(tmp_path):
    """Two DatabaseManager instances pointing to different paths cannot see each other's data."""
    pytest.importorskip("runtime.database")
    # This test will be GREEN once implemented — path-based isolation is structural
    # Stub: just xfail to establish the contract
    pytest.xfail("SEC-02 stub — implementation in Wave 2")
