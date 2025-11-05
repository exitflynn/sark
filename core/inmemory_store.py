"""
In-Memory State Store with Periodic Persistence.
Thread-safe store for workers, campaigns, jobs, and results.
"""

import json
import threading
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


class InMemoryStore:
    """In-memory storage with JSON persistence."""
    
    def __init__(self, persistence_file: str = 'orchestrator_state.json'):
        """
        Initialize the in-memory store.
        
        Args:
            persistence_file: Path to JSON file for persistence
        """
        self.persistence_file = persistence_file
        self.lock = threading.Lock()
        
        # In-memory structures (replacing database tables)
        self.workers: Dict[str, Dict[str, Any]] = {}      # worker_id -> worker_info
        self.campaigns: Dict[str, Dict[str, Any]] = {}    # campaign_id -> campaign_info
        self.jobs: Dict[str, Dict[str, Any]] = {}         # job_id -> job_info
        self.results: Dict[str, Dict[str, Any]] = {}      # job_id -> result_info
        
        # Load from disk if exists
        self._load_from_disk()
        
        # Start background persistence thread
        self._start_persistence_thread()
    
    def _load_from_disk(self) -> None:
        """Load state from JSON file on startup."""
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
                self.workers = data.get('workers', {})
                self.campaigns = data.get('campaigns', {})
                self.jobs = data.get('jobs', {})
                self.results = data.get('results', {})
            print(f"✅ Loaded state from {self.persistence_file}")
        except FileNotFoundError:
            print(f"No existing state file, starting fresh")
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse state file: {e}, starting fresh")
    
    def _save_to_disk(self) -> None:
        """Persist state to JSON file."""
        with self.lock:
            data = {
                'workers': self.workers,
                'campaigns': self.campaigns,
                'jobs': self.jobs,
                'results': self.results,
                'last_saved': datetime.utcnow().isoformat()
            }
            
            try:
                # Atomic write (write to temp, then rename)
                temp_file = f"{self.persistence_file}.tmp"
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                os.replace(temp_file, self.persistence_file)
            except Exception as e:
                print(f"⚠️  Failed to save state: {e}")
    
    def _persistence_thread(self) -> None:
        """Background thread that saves to disk every 30 seconds."""
        while True:
            time.sleep(30)
            self._save_to_disk()
    
    def _start_persistence_thread(self) -> None:
        """Start background persistence thread."""
        t = threading.Thread(target=self._persistence_thread, daemon=True)
        t.start()
    
    # ========== Worker Operations ==========
    
    def register_worker(self, worker_info: Dict[str, Any]) -> str:
        """
        Register a new worker.
        
        Args:
            worker_info: Worker information dictionary
            
        Returns:
            worker_id
        """
        with self.lock:
            worker_id = worker_info['worker_id']
            worker_info['registered_at'] = time.time()
            worker_info['status'] = 'active'
            worker_info['last_seen'] = time.time()
            self.workers[worker_id] = worker_info
            return worker_id
    
    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get worker by ID."""
        return self.workers.get(worker_id)
    
    def get_all_workers(self) -> List[Dict[str, Any]]:
        """Get all workers."""
        with self.lock:
            return list(self.workers.values())
    
    def get_active_workers(self) -> List[Dict[str, Any]]:
        """Get all active workers."""
        with self.lock:
            return [w for w in self.workers.values() if w['status'] == 'active']
    
    def update_worker_status(self, worker_id: str, status: str) -> None:
        """Update worker status."""
        with self.lock:
            if worker_id in self.workers:
                self.workers[worker_id]['status'] = status
                self.workers[worker_id]['last_seen'] = time.time()
    
    def get_workers_by_capability(self, compute_unit: str) -> List[Dict[str, Any]]:
        """Get workers that support a specific compute unit."""
        with self.lock:
            return [
                w for w in self.workers.values()
                if compute_unit in w.get('capabilities', [])
                and w['status'] == 'active'
            ]
    
    # ========== Campaign Operations ==========
    
    def create_campaign(self, campaign_info: Dict[str, Any]) -> str:
        """
        Create a new campaign.
        
        Args:
            campaign_info: Campaign information dictionary
            
        Returns:
            campaign_id
        """
        with self.lock:
            campaign_id = campaign_info['campaign_id']
            campaign_info['created_at'] = time.time()
            campaign_info['status'] = 'running'
            campaign_info['completed_jobs'] = 0
            campaign_info['failed_jobs'] = 0
            self.campaigns[campaign_id] = campaign_info
            return campaign_id
    
    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get campaign by ID."""
        return self.campaigns.get(campaign_id)
    
    def get_all_campaigns(self) -> List[Dict[str, Any]]:
        """Get all campaigns."""
        with self.lock:
            return list(self.campaigns.values())
    
    def update_campaign_progress(self, campaign_id: str, status: Optional[str] = None,
                                increment_completed: bool = False,
                                increment_failed: bool = False) -> None:
        """Update campaign progress."""
        with self.lock:
            if campaign_id in self.campaigns:
                if increment_completed:
                    self.campaigns[campaign_id]['completed_jobs'] += 1
                if increment_failed:
                    self.campaigns[campaign_id]['failed_jobs'] += 1
                if status:
                    self.campaigns[campaign_id]['status'] = status
    
    # ========== Job Operations ==========
    
    def create_job(self, job_info: Dict[str, Any]) -> str:
        """
        Create a new job.
        
        Args:
            job_info: Job information dictionary
            
        Returns:
            job_id
        """
        with self.lock:
            job_id = job_info['job_id']
            job_info['submitted_at'] = time.time()
            job_info['status'] = 'pending'
            job_info['retry_count'] = 0
            self.jobs[job_id] = job_info
            return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, worker_id: Optional[str] = None) -> None:
        """Update job status."""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = status
                if status == 'running':
                    self.jobs[job_id]['started_at'] = time.time()
                    if worker_id:
                        self.jobs[job_id]['worker_id'] = worker_id
                elif status in ['complete', 'failed', 'cancelled']:
                    self.jobs[job_id]['completed_at'] = time.time()
    
    def get_jobs_by_campaign(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get all jobs for a campaign."""
        with self.lock:
            return [j for j in self.jobs.values() if j['campaign_id'] == campaign_id]
    
    def get_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all jobs with a specific status."""
        with self.lock:
            return [j for j in self.jobs.values() if j['status'] == status]
    
    def increment_job_retry(self, job_id: str) -> int:
        """Increment job retry count and return new count."""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['retry_count'] += 1
                return self.jobs[job_id]['retry_count']
            return 0
    
    # ========== Result Operations ==========
    
    def save_result(self, result_info: Dict[str, Any]) -> None:
        """Save a result."""
        with self.lock:
            job_id = result_info['job_id']
            result_info['saved_at'] = time.time()
            self.results[job_id] = result_info
    
    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get result by job ID."""
        return self.results.get(job_id)
    
    def get_results_by_campaign(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get all results for a campaign."""
        with self.lock:
            campaign_job_ids = [j['job_id'] for j in self.jobs.values() 
                               if j['campaign_id'] == campaign_id]
            return [self.results[job_id] for job_id in campaign_job_ids 
                   if job_id in self.results]
    
    # ========== Query Operations (like SQL queries) ==========
    
    def query_results_for_csv(self, campaign_id: str) -> List[Dict[str, Any]]:
        """
        Query results for CSV generation (joins jobs, workers, results).
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            List of result rows with joined data
        """
        with self.lock:
            results = []
            
            for job_id, result in self.results.items():
                job = self.jobs.get(job_id)
                if job and job['campaign_id'] == campaign_id:
                    worker = self.workers.get(job.get('worker_id', ''))
                    
                    # Combine data from multiple "tables"
                    row = {
                        # From result
                        'Status': result.get('status', 'Unknown'),
                        'JobId': job_id,
                        'FileName': result.get('FileName', ''),
                        'FileSize': result.get('FileSize', 0),
                        'ComputeUnits': result.get('ComputeUnits', ''),
                        
                        # From worker
                        'DeviceName': worker.get('device_name', 'Unknown') if worker else 'Unknown',
                        'DeviceYear': worker.get('device_year', '') if worker else '',
                        'Soc': worker.get('soc', '') if worker else '',
                        'Ram': worker.get('ram_gb', 0) if worker else 0,
                        'DiscreteGpu': worker.get('discrete_gpu', '') if worker else '',
                        'VRam': worker.get('vram', '') if worker else '',
                        'DeviceOs': worker.get('os', '') if worker else '',
                        'DeviceOsVersion': worker.get('os_version', '') if worker else '',
                        
                        # From result - benchmark metrics
                        'LoadMsMedian': result.get('LoadMsMedian', ''),
                        'LoadMsStdDev': result.get('LoadMsStdDev', ''),
                        'LoadMsAverage': result.get('LoadMsAverage', ''),
                        'LoadMsFirst': result.get('LoadMsFirst', ''),
                        'PeakLoadRamUsage': result.get('PeakLoadRamUsage', ''),
                        'InferenceMsMedian': result.get('InferenceMsMedian', ''),
                        'InferenceMsStdDev': result.get('InferenceMsStdDev', ''),
                        'InferenceMsAverage': result.get('InferenceMsAverage', ''),
                        'InferenceMsFirst': result.get('InferenceMsFirst', ''),
                        'PeakInferenceRamUsage': result.get('PeakInferenceRamUsage', ''),
                    }
                    results.append(row)
            
            return results
    
    def force_save(self) -> None:
        """Force immediate save to disk."""
        self._save_to_disk()

