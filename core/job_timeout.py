"""
Job Timeout Handler - Monitors and handles job timeouts.
Detects jobs that exceed execution time limits and triggers recovery with retry.
"""

import logging
import threading
import time
from typing import Optional, Dict, List
from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient
from core.retry_manager import RetryManager, RetryReason


logger = logging.getLogger(__name__)


class JobTimeoutHandler:
    """Monitors jobs for timeouts and handles recovery."""
    
    def __init__(self, store: InMemoryStore, redis_client: RedisClient,
                 default_timeout: int = 3600,
                 check_interval: int = 5,
                 retry_manager: Optional[RetryManager] = None):
        """
        Initialize job timeout handler.
        
        Args:
            store: InMemoryStore instance
            redis_client: RedisClient instance
            default_timeout: Default job timeout in seconds
            check_interval: Interval between timeout checks (seconds)
            retry_manager: RetryManager for handling retries (uses default if None)
        """
        self.store = store
        self.redis_client = redis_client
        self.default_timeout = default_timeout
        self.check_interval = check_interval
        self.retry_manager = retry_manager or RetryManager()
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start timeout handler in background thread."""
        if self.running:
            logger.warning("Timeout handler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="JobTimeoutHandler"
        )
        self.thread.start()
        logger.info("✅ Job timeout handler started")
    
    def stop(self) -> None:
        """Stop timeout handler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Job timeout handler stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop (runs in background thread)."""
        logger.info("Job timeout handler loop starting")
        
        while self.running:
            try:
                self._check_job_timeouts()
                time.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Error in timeout handler: {e}", exc_info=True)
                time.sleep(1)
    
    def _check_job_timeouts(self) -> None:
        """Check all active jobs for timeouts."""
        current_time = time.time()
        
        # Get all jobs with 'running' status
        running_jobs = self.store.get_jobs_by_status('running')
        
        for job in running_jobs:
            job_id = job['job_id']
            started_at = job.get('started_at')
            
            if not started_at:
                logger.debug(f"Job {job_id} has no start time")
                continue
            
            # Get timeout (from job or use default)
            timeout_seconds = job.get('timeout_seconds', self.default_timeout)
            execution_time = current_time - started_at
            
            # Check for timeout
            if execution_time > timeout_seconds:
                logger.warning(
                    f"Job {job_id} timed out "
                    f"({execution_time:.1f}s > {timeout_seconds}s)"
                )
                self._handle_job_timeout(job)
    
    def _handle_job_timeout(self, job: Dict) -> None:
        """
        Handle a timed-out job with retry logic.
        
        Args:
            job: Job dictionary
        """
        job_id = job['job_id']
        campaign_id = job.get('campaign_id')
        worker_id = job.get('worker_id')
        compute_unit = job.get('compute_unit')
        
        try:
            # Mark job as timed-out
            self.store.update_job_status(job_id, 'timed_out')
            logger.error(f"⏱️  Job {job_id} timed out")
            
            # Mark worker as faulty
            if worker_id:
                self.store.update_worker_status(worker_id, 'faulty')
                logger.error(f"❌ Marked worker {worker_id} as faulty (job timeout)")
            
            # Use retry manager to decide if we should retry
            if self.retry_manager.retry_job(job_id, RetryReason.JOB_TIMEOUT):
                # Get retry delay
                retry_delay = self.retry_manager.get_retry_delay(job_id)
                attempt = self.retry_manager.tracker.get_attempt_count(job_id)
                
                # Requeue job
                new_job = {
                    'job_id': job_id,
                    'campaign_id': campaign_id,
                    'model_url': job.get('model_url'),
                    'compute_unit': compute_unit,
                    'worker_id': None,  # Clear worker assignment
                    'status': 'pending',
                    'retry_after': time.time() + retry_delay,
                    'num_warmups': job.get('num_warmups'),
                    'num_inference_runs': job.get('num_inference_runs'),
                    'submitted_at': job.get('submitted_at'),
                }
                
                # Push back to capability queue
                if compute_unit:
                    queue_name = f"jobs:capability:{compute_unit}"
                    self.redis_client.push_job(queue_name, job_id)
                    logger.info(
                        f"♻️  Requeued job {job_id} (attempt {attempt}) "
                        f"with {retry_delay:.1f}s backoff"
                    )
            else:
                # Max retries reached
                self.store.update_job_status(job_id, 'failed')
                attempt = self.retry_manager.tracker.get_attempt_count(job_id)
                
                # Update campaign
                if campaign_id:
                    self.store.update_campaign_progress(
                        campaign_id,
                        increment_failed=True
                    )
                
                logger.error(f"❌ Job {job_id} failed after {attempt} attempts")
        
        except Exception as e:
            logger.error(f"Error handling timeout for job {job_id}: {e}", exc_info=True)
    
    def get_timeout_stats(self) -> Dict:
        """Get timeout statistics."""
        all_jobs = self.store.jobs.values()
        
        timed_out = [j for j in all_jobs if j.get('status') == 'timed_out']
        failed = [j for j in all_jobs if j.get('status') == 'failed']
        
        return {
            'total_jobs': len(all_jobs),
            'timed_out_jobs': len(timed_out),
            'failed_jobs': len(failed),
            'default_timeout': self.default_timeout
        }
    
    def get_status(self) -> dict:
        """Get handler status."""
        return {
            'running': self.running,
            'thread_alive': self.thread.is_alive() if self.thread else False,
            'default_timeout': self.default_timeout,
            'check_interval': self.check_interval,
            'retry_stats': self.retry_manager.get_stats()
        }

