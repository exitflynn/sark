"""
Worker State Machine - Manages worker lifecycle states.
Defines valid state transitions for worker objects.
"""

from enum import Enum
from typing import Optional
import logging


logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """Worker states in the lifecycle."""
    ACTIVE = "active"      # Ready to accept jobs
    BUSY = "busy"          # Currently executing a job
    CLEANUP = "cleanup"    # Cleaning up after job
    FAULTY = "faulty"      # Error state


class InvalidStateTransition(Exception):
    """Raised when attempting an invalid state transition."""
    pass


class StateMachine:
    """Worker state machine with valid transitions."""
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        WorkerState.ACTIVE: [WorkerState.BUSY, WorkerState.FAULTY],
        WorkerState.BUSY: [WorkerState.CLEANUP, WorkerState.FAULTY],
        WorkerState.CLEANUP: [WorkerState.ACTIVE, WorkerState.FAULTY],
        WorkerState.FAULTY: [WorkerState.ACTIVE],  # Recovery only path
    }
    
    def __init__(self, initial_state: WorkerState = WorkerState.ACTIVE):
        """
        Initialize state machine.
        
        Args:
            initial_state: Starting state (default: ACTIVE)
        """
        self.state = initial_state
        self.transition_history = [(initial_state, "initialized")]
    
    def can_transition(self, target_state: WorkerState) -> bool:
        """
        Check if transition is valid.
        
        Args:
            target_state: Target state
            
        Returns:
            True if transition is valid
        """
        if self.state == target_state:
            return False  # No self-transitions
        
        return target_state in self.VALID_TRANSITIONS.get(self.state, [])
    
    def transition(self, target_state: WorkerState, reason: str = "") -> None:
        """
        Transition to new state.
        
        Args:
            target_state: Target state
            reason: Reason for transition (for logging)
            
        Raises:
            InvalidStateTransition: If transition is invalid
        """
        if not self.can_transition(target_state):
            msg = f"Invalid transition from {self.state.value} to {target_state.value}"
            if reason:
                msg += f": {reason}"
            logger.error(msg)
            raise InvalidStateTransition(msg)
        
        old_state = self.state
        self.state = target_state
        self.transition_history.append((target_state, reason or "manual"))
        
        logger.info(f"State transition: {old_state.value} → {target_state.value}" +
                   (f" ({reason})" if reason else ""))
    
    def is_active(self) -> bool:
        """Check if worker is ready for jobs."""
        return self.state == WorkerState.ACTIVE
    
    def is_busy(self) -> bool:
        """Check if worker is executing a job."""
        return self.state == WorkerState.BUSY
    
    def is_faulty(self) -> bool:
        """Check if worker is in faulty state."""
        return self.state == WorkerState.FAULTY
    
    def __str__(self) -> str:
        """String representation."""
        return self.state.value
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return f"StateMachine(state={self.state.value})"


class WorkerLifecycle:
    """Helper for managing worker lifecycle transitions."""
    
    @staticmethod
    def mark_busy(state_machine: StateMachine) -> None:
        """Mark worker as busy (job started)."""
        if not state_machine.is_active():
            raise InvalidStateTransition(
                f"Cannot mark busy from {state_machine.state.value} state"
            )
        state_machine.transition(WorkerState.BUSY, "job_started")
    
    @staticmethod
    def mark_cleanup(state_machine: StateMachine) -> None:
        """Mark worker as cleaning up (job completed)."""
        if not state_machine.is_busy():
            raise InvalidStateTransition(
                f"Cannot mark cleanup from {state_machine.state.value} state"
            )
        state_machine.transition(WorkerState.CLEANUP, "job_completed")
    
    @staticmethod
    def mark_active(state_machine: StateMachine) -> None:
        """Mark worker as active (cleanup finished)."""
        if state_machine.state not in [WorkerState.CLEANUP, WorkerState.FAULTY]:
            raise InvalidStateTransition(
                f"Cannot mark active from {state_machine.state.value} state"
            )
        state_machine.transition(WorkerState.ACTIVE, "ready_for_jobs")
    
    @staticmethod
    def mark_faulty(state_machine: StateMachine, reason: str = "") -> None:
        """Mark worker as faulty (error occurred)."""
        state_machine.transition(
            WorkerState.FAULTY,
            f"faulty: {reason}" if reason else "faulty"
        )
    
    @staticmethod
    def recover(state_machine: StateMachine) -> None:
        """Attempt to recover faulty worker."""
        if not state_machine.is_faulty():
            raise InvalidStateTransition(
                f"Cannot recover from {state_machine.state.value} state"
            )
        state_machine.transition(WorkerState.ACTIVE, "recovered")

