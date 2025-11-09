import logging
from typing import Dict, Optional, List
from core.redis_client import RedisClient


logger = logging.getLogger(__name__)


class JobDispatcher:
    
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
    
    def determine_queues(self, job_info: Dict) -> List[str]:
        queues = []
        
        worker_id = job_info.get('worker_id')
        compute_unit = job_info.get('compute_unit')
        
        if worker_id:
            queue_name = f"jobs:{worker_id}"
            queues.append(queue_name)
            logger.debug(f"Routing job {job_info.get('job_id')} to worker {worker_id}")
        
        elif compute_unit:
            normalized_unit = compute_unit.lower().replace(' ', '_').replace('(', '').replace(')', '')
            queue_name = f"jobs:capability:{normalized_unit}"
            queues.append(queue_name)
            logger.debug(f"Routing job {job_info.get('job_id')} to capability queue {normalized_unit} (from {compute_unit})")
        
        else:
            logger.warning(f"Job {job_info.get('job_id')} has no worker_id or compute_unit")
        
        return queues
    
    def push_job_to_queues(self, job_info: Dict) -> bool:
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
