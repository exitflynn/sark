"""
Result Processor - Background thread that processes benchmark results.
Polls Redis results queue, updates store, and tracks campaign progress.
Generates CSV files for completed campaigns.
"""

import logging
import threading
import time
import csv
import os
from datetime import datetime
from typing import Optional, List, Dict
from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient


logger = logging.getLogger(__name__)


class ResultProcessor:
    """Background thread for processing benchmark results."""
    
    def __init__(self, store: InMemoryStore, redis_client: RedisClient, 
                 poll_timeout: int = 1, output_dir: str = 'outputs'):
        """
        Initialize result processor.
        
        Args:
            store: InMemoryStore instance
            redis_client: RedisClient instance
            poll_timeout: Timeout for blocking queue operations (seconds)
            output_dir: Directory for CSV output files
        """
        self.store = store
        self.redis_client = redis_client
        self.poll_timeout = poll_timeout
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        self._ensure_output_directory()
    
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
    
    def _ensure_output_directory(self) -> None:
        """Create output directory if it doesn't exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"✅ Created output directory: {self.output_dir}")
    
    def _generate_csv_file(self, campaign_id: str, results: List[Dict]) -> Optional[str]:
        """
        Generate CSV file from results.
        
        Args:
            campaign_id: Campaign ID
            results: List of result dictionaries
            
        Returns:
            Path to generated CSV file, or None if failed
        """
        if not results:
            logger.warning(f"No results to save for campaign {campaign_id}")
            return None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{campaign_id}_{timestamp}_results.csv'
            filepath = os.path.join(self.output_dir, filename)
            
            fieldnames = [
                'CreatedUtc', 'Status', 'UploadId', 'FileName', 'FileSize',
                'DeviceName', 'DeviceYear', 'Soc', 'Ram', 'DiscreteGpu', 'VRam',
                'DeviceOs', 'DeviceOsVersion',
                'ComputeUnits', 'LoadMsMedian', 'LoadMsStdDev', 'LoadMsAverage',
                'LoadMsFirst', 'PeakLoadRamUsage', 'InferenceMsMedian', 'InferenceMsStdDev',
                'InferenceMsAverage', 'InferenceMsFirst', 'PeakInferenceRamUsage', 'JobId'
            ]
            
            # Write CSV file
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, restval='')
                writer.writeheader()
                writer.writerows(results)
            
            logger.info(f"✅ Generated CSV: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Failed to generate CSV for {campaign_id}: {e}")
            return None
    
    
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
            
            logger.info(f"Processing result for job {job_id}: status={status}, DeviceName={result.get('DeviceName')}, Soc={result.get('Soc')}, Ram={result.get('Ram')}")
            logger.debug(f"Processing result for job {job_id}: {status}")
            
            # Save result to store
            self.store.save_result(result)
            
            # Update job status
            self.store.update_job_status(job_id, status)
            
            # Update campaign progress
            if campaign_id:
                if status == 'Complete':
                    self.store.update_campaign_progress(
                        campaign_id,
                        increment_completed=True
                    )
                
                elif status == 'Failed':
                    self.store.update_campaign_progress(
                        campaign_id,
                        increment_failed=True
                    )
                
                # Check if campaign is complete
                campaign = self.store.get_campaign(campaign_id)
                if campaign:
                    total_completed = campaign.get('completed_jobs', 0) + campaign.get('failed_jobs', 0)
                    total_jobs = campaign.get('total_jobs', 0)
                    
                    if total_completed >= total_jobs and total_jobs > 0:
                        logger.info(f"Campaign {campaign_id} complete! ({total_completed}/{total_jobs} jobs)")
                        
                        # Update status to 'completed' (normalized value for frontend)
                        self.store.update_campaign_progress(campaign_id, status='completed')
                        
                        # Generate CSV file with results
                        try:
                            logger.debug(f"Generating CSV for campaign {campaign_id}")
                            campaign_results = self.store.query_results_for_csv(campaign_id)
                            
                            csv_path = self._generate_csv_file(campaign_id, campaign_results)
                            
                            if csv_path:
                                # Store file path in campaign metadata
                                campaign['results_file'] = csv_path
                                logger.info(f"CSV generated: {csv_path}")
                            else:
                                logger.warning(f"CSV generation failed for campaign {campaign_id}")
                        except Exception as e:
                            logger.error(f"Failed to generate CSV for campaign {campaign_id}: {e}", exc_info=True)
                        
                        # Force save to disk
                        self.store.force_save()
            
        except Exception as e:
            logger.error(f"Error processing result: {e}", exc_info=True)
    
    def get_status(self) -> dict:
        """Get processor status."""
        return {
            'running': self.running,
            'thread_alive': self.thread.is_alive() if self.thread else False
        }

