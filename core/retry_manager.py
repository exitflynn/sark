"""
Retry Manager - Implements exponential backoff retry strategy.
Handles job retry logic with configurable backoff and max attempts.
"""

import logging
import time
import math
from typing import Optional, Dict, Callable
from enum import Enum


logger = logging.getLogger(__name__)


class RetryReason(Enum):
    """Reasons for job retry."""
    JOB_TIMEOUT = "job_timeout"
    WORKER_FAULTY = "worker_faulty"
    EXECUTION_ERROR = "execution_error"
    TRANSIENT_ERROR = "transient_error"
    MANUAL_RETRY = "manual_retry"


class RetryPolicy:
    """Defines retry behavior."""
    
    def __init__(self,
                 max_attempts: int = 3,
                 initial_delay: float = 1.0,
                 max_delay: float = 300.0,
                 backoff_multiplier: float = 2.0,
                 jitter: bool = True):
        """
        Initialize retry policy.
        
        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay in seconds (before first retry)
            max_delay: Maximum delay between retries (cap)
            backoff_multiplier: Multiplier for exponential backoff (e.g., 2.0)
            jitter: Whether to add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def should_retry(self, attempt: int) -> bool:
        """
        Check if we should retry given the attempt number.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            True if should retry, False otherwise
        """
        return attempt < self.max_attempts
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry using exponential backoff.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds before next retry
        """
        if attempt == 0:
            delay = self.initial_delay
        else:
            # Exponential backoff: initial_delay * (multiplier ^ attempt)
            delay = self.initial_delay * (self.backoff_multiplier ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter (random 0-25% variation)
        if self.jitter:
            jitter_amount = delay * 0.25 * (time.time() % 1)
            delay = delay + jitter_amount
        
        return delay


class RetryTracker:
    """Tracks retry history for jobs."""
    
    def __init__(self):
        """Initialize retry tracker."""
        self.retry_history: Dict[str, list] = {}
    
    def record_retry(self, job_id: str, reason: RetryReason, attempt: int) -> None:
        """
        Record a retry attempt.
        
        Args:
            job_id: Job ID
            reason: Reason for retry
            attempt: Attempt number
        """
        if job_id not in self.retry_history:
            self.retry_history[job_id] = []
        
        self.retry_history[job_id].append({
            'timestamp': time.time(),
            'reason': reason.value,
            'attempt': attempt
        })
        
        logger.info(f"Recorded retry for job {job_id}: {reason.value} (attempt {attempt})")
    
    def get_retry_history(self, job_id: str) -> list:
        """
        Get retry history for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of retry records
        """
        return self.retry_history.get(job_id, [])
    
    def get_attempt_count(self, job_id: str) -> int:
        """
        Get total attempt count for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Number of attempts (including initial)
        """
        return len(self.retry_history.get(job_id, [])) + 1


class RetryManager:
    """Manages job retries with exponential backoff."""
    
    def __init__(self, policy: Optional[RetryPolicy] = None):
        """
        Initialize retry manager.
        
        Args:
            policy: RetryPolicy instance (uses defaults if None)
        """
        self.policy = policy or RetryPolicy()
        self.tracker = RetryTracker()
    
    def should_retry(self, job_id: str) -> bool:
        """
        Check if job should be retried.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if should retry, False otherwise
        """
        attempt = self.tracker.get_attempt_count(job_id)
        should_retry = self.policy.should_retry(attempt)
        
        if not should_retry:
            logger.warning(f"Job {job_id} max retries reached (attempt {attempt})")
        
        return should_retry
    
    def get_retry_delay(self, job_id: str) -> float:
        """
        Get delay before next retry.
        
        Args:
            job_id: Job ID
            
        Returns:
            Delay in seconds
        """
        attempt = self.tracker.get_attempt_count(job_id)
        # get_delay expects 0-indexed, but attempt_count is 1-indexed
        delay_index = attempt - 1
        delay = self.policy.get_delay(delay_index)
        
        logger.info(f"Retry delay for job {job_id}: {delay:.2f}s (attempt {attempt})")
        
        return delay
    
    def retry_job(self, job_id: str, reason: RetryReason) -> bool:
        """
        Process a job retry.
        
        Args:
            job_id: Job ID
            reason: Reason for retry
            
        Returns:
            True if retry scheduled, False if max retries reached
        """
        if not self.should_retry(job_id):
            return False
        
        attempt = self.tracker.get_attempt_count(job_id)
        self.tracker.record_retry(job_id, reason, attempt)
        
        delay = self.get_retry_delay(job_id)
        logger.info(f"Scheduling retry for job {job_id} (attempt {attempt + 1}) in {delay:.2f}s")
        
        return True
    
    def get_stats(self) -> dict:
        """
        Get retry statistics.
        
        Returns:
            Statistics dictionary
        """
        total_jobs = len(self.retry_history)
        total_retries = sum(len(h) for h in self.retry_history.values())
        
        return {
            'total_jobs_tracked': total_jobs,
            'total_retries': total_retries,
            'policy': {
                'max_attempts': self.policy.max_attempts,
                'initial_delay': self.policy.initial_delay,
                'max_delay': self.policy.max_delay,
                'backoff_multiplier': self.policy.backoff_multiplier,
                'jitter_enabled': self.policy.jitter
            }
        }
    
    @property
    def retry_history(self) -> Dict[str, list]:
        """Get retry history."""
        return self.tracker.retry_history


class ExponentialBackoffCalculator:
    """Utility for calculating exponential backoff."""
    
    @staticmethod
    def calculate_delay(attempt: int,
                       initial_delay: float = 1.0,
                       multiplier: float = 2.0,
                       max_delay: float = 300.0) -> float:
        """
        Calculate delay with exponential backoff.
        
        Formula: delay = min(initial_delay * (multiplier ^ attempt), max_delay)
        
        Args:
            attempt: Attempt number (0-indexed)
            initial_delay: Initial delay value
            multiplier: Backoff multiplier
            max_delay: Maximum delay cap
            
        Returns:
            Calculated delay in seconds
        """
        if attempt == 0:
            return initial_delay
        
        delay = initial_delay * (multiplier ** attempt)
        return min(delay, max_delay)
    
    @staticmethod
    def calculate_delay_with_jitter(attempt: int,
                                   initial_delay: float = 1.0,
                                   multiplier: float = 2.0,
                                   max_delay: float = 300.0,
                                   jitter_factor: float = 0.25) -> float:
        """
        Calculate delay with exponential backoff and jitter.
        
        Jitter helps prevent thundering herd in distributed systems.
        
        Args:
            attempt: Attempt number (0-indexed)
            initial_delay: Initial delay value
            multiplier: Backoff multiplier
            max_delay: Maximum delay cap
            jitter_factor: Jitter as fraction of delay (e.g., 0.25 = ±25%)
            
        Returns:
            Calculated delay in seconds with jitter
        """
        import random
        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt, initial_delay, multiplier, max_delay
        )
        jitter = delay * jitter_factor * random.random()
        return delay + jitter

