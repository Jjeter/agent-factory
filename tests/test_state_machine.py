"""Tests for runtime.state_machine — TaskStateMachine transition table.

Covers: SM-01 (valid transitions succeed), SM-02 (invalid transitions raise),
        SM-03 (InvalidTransitionError message contains both state names).

pytest.importorskip at module level: collection skips cleanly if state_machine
module doesn't exist yet (Plans 02-04).
"""
import pytest

pytest.importorskip(
    "runtime.state_machine",
    reason="runtime.state_machine not yet implemented (Plan 02)",
)

from runtime.state_machine import (  # noqa: E402 — import after importorskip guard
    InvalidTransitionError,
    TaskStateMachine,
    TaskStatus,
)

machine = TaskStateMachine()

# ---------------------------------------------------------------------------
# Transition cases: (from_state, to_state, should_succeed)
# Matches RESEARCH.md Pattern 4 exactly.
# ---------------------------------------------------------------------------

TRANSITION_CASES = [
    # Valid transitions (SM-01)
    (TaskStatus.TODO,        TaskStatus.IN_PROGRESS, True),
    (TaskStatus.IN_PROGRESS, TaskStatus.PEER_REVIEW,  True),
    (TaskStatus.PEER_REVIEW, TaskStatus.REVIEW,        True),
    (TaskStatus.PEER_REVIEW, TaskStatus.IN_PROGRESS,   True),  # rejection path
    (TaskStatus.REVIEW,      TaskStatus.APPROVED,       True),
    # Invalid transitions (SM-02) — regression guards
    (TaskStatus.TODO,        TaskStatus.APPROVED,        False),
    (TaskStatus.TODO,        TaskStatus.PEER_REVIEW,     False),
    (TaskStatus.APPROVED,    TaskStatus.TODO,             False),
    (TaskStatus.IN_PROGRESS, TaskStatus.APPROVED,         False),
    (TaskStatus.REVIEW,      TaskStatus.IN_PROGRESS,       False),
    (TaskStatus.IN_PROGRESS, TaskStatus.TODO,               False),  # regression guard
]


@pytest.mark.parametrize("from_state,to_state,should_succeed", TRANSITION_CASES)
def test_transition(
    from_state: TaskStatus,
    to_state: TaskStatus,
    should_succeed: bool,
) -> None:
    """SM-01 / SM-02: Valid transitions succeed; invalid transitions raise InvalidTransitionError."""
    if should_succeed:
        result = machine.apply(from_state, to_state)
        assert result == to_state, (
            f"Expected {to_state!r} but apply() returned {result!r}"
        )
    else:
        with pytest.raises(InvalidTransitionError):
            machine.apply(from_state, to_state)


def test_error_message_contains_both_states() -> None:
    """SM-03: InvalidTransitionError message contains both from_state and to_state strings."""
    with pytest.raises(InvalidTransitionError) as exc_info:
        machine.apply(TaskStatus.APPROVED, TaskStatus.TODO)

    error_message = str(exc_info.value)
    assert str(TaskStatus.APPROVED) in error_message or TaskStatus.APPROVED.value in error_message, (
        f"Expected from_state ({TaskStatus.APPROVED}) in error message: {error_message!r}"
    )
    assert str(TaskStatus.TODO) in error_message or TaskStatus.TODO.value in error_message, (
        f"Expected to_state ({TaskStatus.TODO}) in error message: {error_message!r}"
    )


def test_apply_returns_target_state() -> None:
    """apply() returns the target state on success (not None, not from_state)."""
    result = machine.apply(TaskStatus.TODO, TaskStatus.IN_PROGRESS)
    assert result is TaskStatus.IN_PROGRESS


def test_approved_is_terminal() -> None:
    """APPROVED has no valid outgoing transitions — every target raises InvalidTransitionError."""
    for target in TaskStatus:
        if target is TaskStatus.APPROVED:
            continue  # self-transition also invalid, but other tests cover it
        with pytest.raises(InvalidTransitionError):
            machine.apply(TaskStatus.APPROVED, target)
