"""
Result Processor - Background thread that processes benchmark results.
Polls Redis results queue, updates store, and tracks campaign progress.
"""

import logging
import threading
import time
from typing import Optional
from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient


logger = logging.getLogger(__name__)


class ResultProcessor:
    """Background thread for processing benchmark results."""
    
    def __init__(self, store: InMemoryStore, redis_client: RedisClient, 
                 poll_timeout: int = 1):
        """
        Initialize result processor.
        
        Args:
            store: InMemoryStore instance
            redis_client: RedisClient instance
            poll_timeout: Timeout for blocking queue operations (seconds)
        """
        self.store = store
        self.redis_client = redis_client
        self.poll_timeout = poll_timeout
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start result processor in background thread."""
        if self.running:
            logger.warning("Result processor already running")
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
            name="ResultProcessor"
        )
        self.thread.start()
        logger.info("✅ Result processor started")
    
    def stop(self) -> None:
        """Stop result processor."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            logger.info("Result processor stopped")
    
    def _process_loop(self) -> None:
        """Main processing loop (runs in background thread)."""
        logger.info("Result processor loop starting")
        
        while self.running:
            try:
                # Poll for result
                result = self.redis_client.pop_result(timeout=self.poll_timeout)
                
                if result:
                    self._process_single_result(result)
            
            except Exception as e:
                logger.error(f"Error in result processor loop: {e}")
                # Continue processing on error
                time.sleep(1)
    
    def _process_single_result(self, result: dict) -> None:
        """
        Process a single result.
        
        Args:
            result: Result dictionary from Redis queue
        """
        try:
            job_id = result.get('job_id')
            campaign_id = result.get('campaign_id')
            status = result.get('status', 'Unknown')
            
            logger.debug(f"Processing result for job {job_id}: {status}")
            
            # Save result to store
            self.store.save_result(result)
            logger.debug(f"Saved result for job {job_id}")
            
            # Update job status
            self.store.update_job_status(job_id, status)
            logger.debug(f"Updated job {job_id} status to {status}")
            
            # Update campaign progress
            if campaign_id:
                if status == 'Complete':
                    self.store.update_campaign_progress(
                        campaign_id,
                        increment_completed=True
                    )
                    logger.debug(f"Incremented completed jobs for campaign {campaign_id}")
                
                elif status == 'Failed':
                    self.store.update_campaign_progress(
                        campaign_id,
                        increment_failed=True
                    )
                    logger.debug(f"Incremented failed jobs for campaign {campaign_id}")
                
                # Check if campaign is complete
                campaign = self.store.get_campaign(campaign_id)
                if campaign:
                    total_completed = campaign.get('completed_jobs', 0) + campaign.get('failed_jobs', 0)
                    total_jobs = campaign.get('total_jobs', 0)
                    
                    if total_completed >= total_jobs and total_jobs > 0:
                        self.store.update_campaign_progress(campaign_id, status='complete')
                        logger.info(f"🎉 Campaign {campaign_id} complete! ({total_completed}/{total_jobs} jobs)")
                        
                        # Force save to disk
                        self.store.force_save()
            
            logger.info(f"✅ Processed result for job {job_id}")
        
        except Exception as e:
            logger.error(f"Error processing result: {e}", exc_info=True)
    
    def get_status(self) -> dict:
        """Get processor status."""
        return {
            'running': self.running,
            'thread_alive': self.thread.is_alive() if self.thread else False
        }

