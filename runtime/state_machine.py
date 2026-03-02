"""TaskStateMachine — enforces valid state transitions for Task entities.

Exports:
    InvalidTransitionError: raised when an invalid state transition is attempted.
    TaskStateMachine: holds the transition table and apply() method.
    TaskStatus: re-exported from runtime.models for caller convenience.

Design (CONTEXT.md, locked):
    - Transition table is a class-level dict[TaskStatus, set[TaskStatus]].
    - apply() raises InvalidTransitionError for any transition not in the table.
    - APPROVED is terminal: its entry maps to an empty set.
    - "rejected" is NOT a status — rejection is an action recorded as a
      task_comment; PEER_REVIEW → IN_PROGRESS is the transition that implements it.
"""

from runtime.models import TaskStatus

# Re-export TaskStatus so callers can:
#   from runtime.state_machine import TaskStateMachine, InvalidTransitionError, TaskStatus
__all__ = ["InvalidTransitionError", "TaskStateMachine", "TaskStatus"]


class InvalidTransitionError(Exception):
    """Raised when TaskStateMachine.apply() is called with an invalid transition.

    Attributes:
        from_state: The state the machine was in.
        to_state: The state that was requested (but not allowed).

    Message format (CONTEXT.md locked):
        "Cannot transition {from_state} → {to_state}"
        Both state string values appear in the message.
    """

    def __init__(self, from_state: TaskStatus, to_state: TaskStatus) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Cannot transition {from_state} \u2192 {to_state}")


class TaskStateMachine:
    """Enforces the 5-transition state machine for Task lifecycle.

    Valid transitions:
        TODO        → IN_PROGRESS   (agent claims task)
        IN_PROGRESS → PEER_REVIEW   (agent submits work)
        PEER_REVIEW → REVIEW        (boss promotes after all peer reviews pass)
        PEER_REVIEW → IN_PROGRESS   (rejection path — any reviewer rejects)
        REVIEW      → APPROVED      (user approves via CLI)

    APPROVED is terminal: no valid outgoing transitions exist.

    Usage:
        machine = TaskStateMachine()
        new_status = machine.apply(TaskStatus.TODO, TaskStatus.IN_PROGRESS)
        # Returns TaskStatus.IN_PROGRESS

        machine.apply(TaskStatus.APPROVED, TaskStatus.TODO)
        # Raises InvalidTransitionError("Cannot transition approved → todo")
    """

    TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.TODO: {TaskStatus.IN_PROGRESS},
        TaskStatus.IN_PROGRESS: {TaskStatus.PEER_REVIEW},
        TaskStatus.PEER_REVIEW: {TaskStatus.REVIEW, TaskStatus.IN_PROGRESS},
        TaskStatus.REVIEW: {TaskStatus.APPROVED},
        TaskStatus.APPROVED: set(),  # terminal state
    }

    def apply(self, current: TaskStatus, target: TaskStatus) -> TaskStatus:
        """Apply a transition from current to target state.

        Args:
            current: The task's current status.
            target: The desired next status.

        Returns:
            target: The new status (same object passed in).

        Raises:
            InvalidTransitionError: If the transition is not in TRANSITIONS.
        """
        allowed = self.TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidTransitionError(current, target)
        return target
