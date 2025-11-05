import unittest
import time
from core.retry_manager import (
    RetryPolicy, RetryTracker, RetryManager, RetryReason,
    ExponentialBackoffCalculator
)


class TestRetryPolicy(unittest.TestCase):
    """Test cases for retry policy."""
    
    def test_default_policy(self):
        """Test default retry policy creation."""
        policy = RetryPolicy()
        self.assertEqual(policy.max_attempts, 3)
        self.assertEqual(policy.initial_delay, 1.0)
        self.assertEqual(policy.max_delay, 300.0)
        self.assertEqual(policy.backoff_multiplier, 2.0)
        self.assertTrue(policy.jitter)
    
    def test_custom_policy(self):
        """Test custom retry policy."""
        policy = RetryPolicy(
            max_attempts=5,
            initial_delay=2.0,
            max_delay=600.0,
            backoff_multiplier=3.0,
            jitter=False
        )
        self.assertEqual(policy.max_attempts, 5)
        self.assertEqual(policy.initial_delay, 2.0)
        self.assertEqual(policy.max_delay, 600.0)
        self.assertEqual(policy.backoff_multiplier, 3.0)
        self.assertFalse(policy.jitter)
    
    def test_should_retry_within_limit(self):
        """Test should_retry returns True within limit."""
        policy = RetryPolicy(max_attempts=3)
        self.assertTrue(policy.should_retry(0))
        self.assertTrue(policy.should_retry(1))
        self.assertTrue(policy.should_retry(2))
    
    def test_should_retry_at_limit(self):
        """Test should_retry returns False at limit."""
        policy = RetryPolicy(max_attempts=3)
        self.assertFalse(policy.should_retry(3))
        self.assertFalse(policy.should_retry(4))
    
    def test_get_delay_first_attempt(self):
        """Test delay for first attempt."""
        policy = RetryPolicy(initial_delay=1.0, jitter=False)
        delay = policy.get_delay(0)
        self.assertEqual(delay, 1.0)
    
    def test_get_delay_exponential_backoff(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(
            initial_delay=1.0,
            backoff_multiplier=2.0,
            jitter=False
        )
        self.assertEqual(policy.get_delay(0), 1.0)
        self.assertEqual(policy.get_delay(1), 2.0)
        self.assertEqual(policy.get_delay(2), 4.0)
        self.assertEqual(policy.get_delay(3), 8.0)
    
    def test_get_delay_max_cap(self):
        """Test delay respects max_delay cap."""
        policy = RetryPolicy(
            initial_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=10.0,
            jitter=False
        )
        self.assertEqual(policy.get_delay(0), 1.0)
        self.assertEqual(policy.get_delay(1), 2.0)
        self.assertEqual(policy.get_delay(2), 4.0)
        self.assertEqual(policy.get_delay(3), 8.0)
        self.assertEqual(policy.get_delay(4), 10.0)  # Capped
        self.assertEqual(policy.get_delay(5), 10.0)  # Still capped


class TestRetryTracker(unittest.TestCase):
    """Test cases for retry tracker."""
    
    def test_record_retry(self):
        """Test recording retry attempts."""
        tracker = RetryTracker()
        tracker.record_retry('job-1', RetryReason.JOB_TIMEOUT, 1)
        
        history = tracker.get_retry_history('job-1')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['reason'], 'job_timeout')
        self.assertEqual(history[0]['attempt'], 1)
    
    def test_get_attempt_count(self):
        """Test attempt count."""
        tracker = RetryTracker()
        self.assertEqual(tracker.get_attempt_count('job-1'), 1)
        
        tracker.record_retry('job-1', RetryReason.JOB_TIMEOUT, 1)
        self.assertEqual(tracker.get_attempt_count('job-1'), 2)
        
        tracker.record_retry('job-1', RetryReason.JOB_TIMEOUT, 2)
        self.assertEqual(tracker.get_attempt_count('job-1'), 3)
    
    def test_multiple_jobs(self):
        """Test tracking multiple jobs."""
        tracker = RetryTracker()
        tracker.record_retry('job-1', RetryReason.JOB_TIMEOUT, 1)
        tracker.record_retry('job-2', RetryReason.EXECUTION_ERROR, 1)
        
        self.assertEqual(tracker.get_attempt_count('job-1'), 2)
        self.assertEqual(tracker.get_attempt_count('job-2'), 2)


class TestRetryManager(unittest.TestCase):
    """Test cases for retry manager."""
    
    def test_default_manager(self):
        """Test default retry manager."""
        manager = RetryManager()
        self.assertIsNotNone(manager.policy)
        self.assertIsNotNone(manager.tracker)
    
    def test_should_retry_within_limit(self):
        """Test should_retry within limit."""
        manager = RetryManager(RetryPolicy(max_attempts=4))  # Allow up to 4 attempts
        # Before any retries - attempt count is 1, should retry (< 4)
        self.assertTrue(manager.should_retry('job-1'))
        # After 1st retry - count is 2, should still retry (< 4)
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        self.assertTrue(manager.should_retry('job-1'))
        # After 2nd retry - count is 3, should still retry (< 4)
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        self.assertTrue(manager.should_retry('job-1'))
    
    def test_should_retry_at_limit(self):
        """Test should_retry at limit."""
        manager = RetryManager(RetryPolicy(max_attempts=2))
        # Attempt 1 - should retry (attempt < max_attempts)
        self.assertTrue(manager.should_retry('job-1'))
        # Attempt 2 - should retry (attempt < max_attempts) 
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        # NOTE: After retry_job, the next check should fail because attempt count is now 2
        # which equals max_attempts, so should_retry should return False
        self.assertFalse(manager.should_retry('job-1'))
    
    def test_retry_job_success(self):
        """Test successful retry_job."""
        manager = RetryManager(RetryPolicy(max_attempts=3, jitter=False))
        result = manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        self.assertTrue(result)
    
    def test_retry_job_failure(self):
        """Test retry_job at limit."""
        manager = RetryManager(RetryPolicy(max_attempts=1))
        manager.tracker.record_retry('job-1', RetryReason.JOB_TIMEOUT, 1)
        result = manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        self.assertFalse(result)
    
    def test_get_retry_delay(self):
        """Test getting retry delay."""
        manager = RetryManager(
            RetryPolicy(
                initial_delay=1.0,
                backoff_multiplier=2.0,
                jitter=False
            )
        )
        
        # Initial delay (before any retries, attempt count = 1)
        delay1 = manager.get_retry_delay('job-1')
        self.assertEqual(delay1, 1.0)
        
        # After first retry (attempt count = 2)
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        delay2 = manager.get_retry_delay('job-1')
        self.assertEqual(delay2, 2.0)
        
        # After second retry (attempt count = 3)
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        delay3 = manager.get_retry_delay('job-1')
        self.assertEqual(delay3, 4.0)
    
    def test_get_stats(self):
        """Test getting retry statistics."""
        manager = RetryManager()
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        manager.retry_job('job-2', RetryReason.EXECUTION_ERROR)
        
        stats = manager.get_stats()
        self.assertEqual(stats['total_jobs_tracked'], 2)
        self.assertEqual(stats['total_retries'], 2)
        self.assertEqual(stats['policy']['max_attempts'], 3)


class TestExponentialBackoffCalculator(unittest.TestCase):
    """Test cases for exponential backoff calculator."""
    
    def test_calculate_delay_first_attempt(self):
        """Test delay calculation for first attempt."""
        delay = ExponentialBackoffCalculator.calculate_delay(0)
        self.assertEqual(delay, 1.0)
    
    def test_calculate_delay_exponential(self):
        """Test exponential delay calculation."""
        self.assertEqual(ExponentialBackoffCalculator.calculate_delay(0), 1.0)
        self.assertEqual(ExponentialBackoffCalculator.calculate_delay(1), 2.0)
        self.assertEqual(ExponentialBackoffCalculator.calculate_delay(2), 4.0)
        self.assertEqual(ExponentialBackoffCalculator.calculate_delay(3), 8.0)
    
    def test_calculate_delay_custom_params(self):
        """Test delay with custom parameters."""
        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt=2,
            initial_delay=2.0,
            multiplier=3.0
        )
        self.assertEqual(delay, 18.0)  # 2.0 * (3.0 ^ 2)
    
    def test_calculate_delay_with_jitter(self):
        """Test delay with jitter."""
        delay1 = ExponentialBackoffCalculator.calculate_delay_with_jitter(1)
        delay2 = ExponentialBackoffCalculator.calculate_delay_with_jitter(1)
        
        # Both should be around 2.0 with jitter
        self.assertGreater(delay1, 1.5)
        self.assertLess(delay1, 2.5)
        self.assertGreater(delay2, 1.5)
        self.assertLess(delay2, 2.5)
        
        # Very unlikely to be identical (different random jitter)
        # But we can't assert they're different due to random chance
    
    def test_calculate_delay_max_cap(self):
        """Test delay respects max cap."""
        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt=10,
            initial_delay=1.0,
            multiplier=2.0,
            max_delay=100.0
        )
        self.assertEqual(delay, 100.0)


class TestRetryReasons(unittest.TestCase):
    """Test cases for retry reasons."""
    
    def test_retry_reasons_exist(self):
        """Test all retry reasons exist."""
        reasons = [
            RetryReason.JOB_TIMEOUT,
            RetryReason.WORKER_FAULTY,
            RetryReason.EXECUTION_ERROR,
            RetryReason.TRANSIENT_ERROR,
            RetryReason.MANUAL_RETRY,
        ]
        self.assertEqual(len(reasons), 5)
    
    def test_retry_reason_values(self):
        """Test retry reason values."""
        self.assertEqual(RetryReason.JOB_TIMEOUT.value, "job_timeout")
        self.assertEqual(RetryReason.WORKER_FAULTY.value, "worker_faulty")
        self.assertEqual(RetryReason.EXECUTION_ERROR.value, "execution_error")
        self.assertEqual(RetryReason.TRANSIENT_ERROR.value, "transient_error")
        self.assertEqual(RetryReason.MANUAL_RETRY.value, "manual_retry")


class TestRetryIntegration(unittest.TestCase):
    """Integration tests for retry functionality."""
    
    def test_full_retry_workflow(self):
        """Test complete retry workflow."""
        policy = RetryPolicy(
            max_attempts=4,
            initial_delay=0.1,
            backoff_multiplier=2.0,
            jitter=False
        )
        manager = RetryManager(policy=policy)
        
        job_id = 'test-job-1'
        
        # Attempt 1: retry_job returns True (records retry)
        self.assertTrue(manager.retry_job(job_id, RetryReason.JOB_TIMEOUT))
        # After 1st retry: attempt_count = 2, delay_index = 1, delay = 0.1 * 2^1 = 0.2
        delay1 = manager.get_retry_delay(job_id)
        self.assertEqual(delay1, 0.2)
        
        # Attempt 2
        self.assertTrue(manager.retry_job(job_id, RetryReason.JOB_TIMEOUT))
        # After 2nd retry: attempt_count = 3, delay_index = 2, delay = 0.1 * 2^2 = 0.4
        delay2 = manager.get_retry_delay(job_id)
        self.assertEqual(delay2, 0.4)
        
        # Attempt 3
        self.assertTrue(manager.retry_job(job_id, RetryReason.JOB_TIMEOUT))
        # After 3rd retry: attempt_count = 4, delay_index = 3, delay = 0.1 * 2^3 = 0.8
        delay3 = manager.get_retry_delay(job_id)
        self.assertEqual(delay3, 0.8)
        
        # No more retries (attempt count = 4, which is not < max_attempts)
        self.assertFalse(manager.retry_job(job_id, RetryReason.JOB_TIMEOUT))
    
    def test_multiple_jobs_independent_retries(self):
        """Test retries for multiple jobs are independent."""
        manager = RetryManager(
            RetryPolicy(
                max_attempts=3,  # Allow 3 attempts
                initial_delay=1.0,
                backoff_multiplier=2.0,
                jitter=False
            )
        )
        
        # Job-1: One retry attempt (attempt count becomes 2)
        manager.retry_job('job-1', RetryReason.JOB_TIMEOUT)
        # Should still be retryable (2 < 3)
        self.assertTrue(manager.should_retry('job-1'))
        
        # Job-2: Two retry attempts (attempt count becomes 3)
        manager.retry_job('job-2', RetryReason.JOB_TIMEOUT)
        manager.retry_job('job-2', RetryReason.JOB_TIMEOUT)
        # Should NOT be retryable (3 >= 3)
        self.assertFalse(manager.should_retry('job-2'))


if __name__ == '__main__':
    unittest.main()

