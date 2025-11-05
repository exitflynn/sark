"""
Job Dispatcher - Routes jobs to Redis queues based on assignment strategy.
Implements hybrid queuing: static assignment + capability-based routing.
"""

import logging
from typing import Dict, Optional, List
from core.redis_client import RedisClient


logger = logging.getLogger(__name__)


class JobDispatcher:
    """Routes jobs to appropriate Redis queues."""
    
    def __init__(self, redis_client: RedisClient):
        """
        Initialize job dispatcher.
        
        Args:
            redis_client: RedisClient instance for queue operations
        """
        self.redis_client = redis_client
    
    def determine_queues(self, job_info: Dict) -> List[str]:
        """
        Determine which queue(s) a job should be pushed to.
        
        Returns hybrid routing:
        - If job has worker_id: static assignment to jobs:{worker_id}
        - Else if job has compute_unit: capability-based to jobs:capability:{unit}
        
        Args:
            job_info: Job information dictionary
            
        Returns:
            List of queue names (usually 1, rarely 2)
        """
        queues = []
        
        worker_id = job_info.get('worker_id')
        compute_unit = job_info.get('compute_unit')
        
        if worker_id:
            # Static assignment - push to worker-specific queue
            queue_name = f"jobs:{worker_id}"
            queues.append(queue_name)
            logger.debug(f"Routing job {job_info.get('job_id')} to worker {worker_id}")
        
        elif compute_unit:
            # Capability-based assignment - push to capability queue
            queue_name = f"jobs:capability:{compute_unit}"
            queues.append(queue_name)
            logger.debug(f"Routing job {job_info.get('job_id')} to capability queue {compute_unit}")
        
        else:
            logger.warning(f"Job {job_info.get('job_id')} has no worker_id or compute_unit")
        
        return queues
    
    def push_job_to_queues(self, job_info: Dict) -> bool:
        """
        Push job to appropriate queue(s).
        
        Args:
            job_info: Job information
            
        Returns:
            True if successful, False otherwise
        """
        queues = self.determine_queues(job_info)
        
        if not queues:
            logger.error(f"No queues determined for job {job_info.get('job_id')}")
            return False
        
        job_id = job_info['job_id']
        success = True
        
        for queue_name in queues:
            if not self.redis_client.push_job(queue_name, job_id):
                logger.error(f"Failed to push job {job_id} to queue {queue_name}")
                success = False
            else:
                logger.info(f"Queued job {job_id} to {queue_name}")
        
        return success
    
    def push_jobs_from_campaign(self, redis_client, store, campaign_id: str) -> int:
        """
        Push all pending jobs from a campaign to appropriate queues.
        
        Args:
            redis_client: RedisClient instance
            store: InMemoryStore instance
            campaign_id: Campaign ID
            
        Returns:
            Number of jobs successfully queued
        """
        jobs = store.get_jobs_by_campaign(campaign_id)
        pending_jobs = [j for j in jobs if j['status'] == 'pending']
        
        queued_count = 0
        
        for job in pending_jobs:
            if self.push_job_to_queues(job):
                queued_count += 1
            else:
                logger.warning(f"Failed to queue job {job['job_id']}")
        
        logger.info(f"Queued {queued_count}/{len(pending_jobs)} jobs from campaign {campaign_id}")
        
        return queued_count
    
    @staticmethod
    def get_worker_queue_priority(worker_id: str, capabilities: List[str]) -> List[str]:
        """
        Get queue names in priority order for a worker to poll.
        
        Workers should check queues in this priority:
        1. Personal queue (highest priority)
        2. Capability queues (in order)
        
        Args:
            worker_id: Worker ID
            capabilities: List of compute units worker supports
            
        Returns:
            List of queue names to poll in order
        """
        queues = [f"jobs:{worker_id}"]  # Personal queue first
        
        for capability in capabilities:
            queues.append(f"jobs:capability:{capability}")
        
        return queues

