"""
Health Monitor - Tracks worker health via heartbeats.
Detects worker failures and marks workers as faulty when unresponsive.
"""

import logging
import threading
import time
from typing import Dict, Optional
from core.inmemory_store import InMemoryStore
from core.state_machine import WorkerState, WorkerLifecycle


logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors worker health via heartbeats."""
    
    def __init__(self, store: InMemoryStore, 
                 heartbeat_timeout: int = 60,
                 check_interval: int = 10):
        """
        Initialize health monitor.
        
        Args:
            store: InMemoryStore instance
            heartbeat_timeout: Seconds without heartbeat before marking faulty
            check_interval: Interval between health checks (seconds)
        """
        self.store = store
        self.heartbeat_timeout = heartbeat_timeout
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_heartbeat: Dict[str, float] = {}
    
    def start(self) -> None:
        """Start health monitor in background thread."""
        if self.running:
            logger.warning("Health monitor already running")
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="HealthMonitor"
        )
        self.thread.start()
        logger.info("✅ Health monitor started")
    
    def stop(self) -> None:
        """Stop health monitor."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Health monitor stopped")
    
    def record_heartbeat(self, worker_id: str) -> None:
        """
        Record heartbeat from worker.
        
        Args:
            worker_id: Worker ID
        """
        self.last_heartbeat[worker_id] = time.time()
        logger.debug(f"Heartbeat from {worker_id}")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop (runs in background thread)."""
        logger.info("Health monitor loop starting")
        
        while self.running:
            try:
                self._check_heartbeats()
                time.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Error in health monitor: {e}", exc_info=True)
                time.sleep(1)
    
    def _check_heartbeats(self) -> None:
        """Check all workers for heartbeat timeouts."""
        current_time = time.time()
        workers = self.store.get_all_workers()
        
        for worker in workers:
            worker_id = worker['worker_id']
            
            # Skip already faulty workers
            if worker.get('status') == 'faulty':
                continue
            
            # Get last heartbeat time
            last_beat = self.last_heartbeat.get(worker_id)
            
            # If no heartbeat recorded yet, record current time
            if last_beat is None:
                self.last_heartbeat[worker_id] = current_time
                continue
            
            # Check for timeout
            time_since_heartbeat = current_time - last_beat
            
            if time_since_heartbeat > self.heartbeat_timeout:
                logger.warning(
                    f"Worker {worker_id} heartbeat timeout "
                    f"({time_since_heartbeat:.1f}s > {self.heartbeat_timeout}s)"
                )
                self._mark_worker_faulty(worker_id, "heartbeat_timeout")
    
    def _mark_worker_faulty(self, worker_id: str, reason: str) -> None:
        """
        Mark worker as faulty.
        
        Args:
            worker_id: Worker ID
            reason: Reason for marking as faulty
        """
        try:
            self.store.update_worker_status(worker_id, 'faulty')
            logger.error(f"❌ Marked worker {worker_id} as faulty: {reason}")
        
        except Exception as e:
            logger.error(f"Failed to mark worker {worker_id} as faulty: {e}")
    
    def get_worker_health(self, worker_id: str) -> Dict:
        """
        Get health status for a worker.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            Health status dictionary
        """
        worker = self.store.get_worker(worker_id)
        if not worker:
            return {'error': 'Worker not found'}
        
        last_beat = self.last_heartbeat.get(worker_id)
        current_time = time.time()
        
        if last_beat is None:
            time_since_beat = None
            is_healthy = True
        else:
            time_since_beat = current_time - last_beat
            is_healthy = time_since_beat < self.heartbeat_timeout
        
        return {
            'worker_id': worker_id,
            'status': worker.get('status', 'unknown'),
            'is_healthy': is_healthy,
            'last_heartbeat': last_beat,
            'time_since_heartbeat': time_since_beat,
            'heartbeat_timeout': self.heartbeat_timeout
        }
    
    def get_all_health(self) -> list:
        """Get health status for all workers."""
        workers = self.store.get_all_workers()
        return [self.get_worker_health(w['worker_id']) for w in workers]
    
    def get_status(self) -> dict:
        """Get monitor status."""
        return {
            'running': self.running,
            'thread_alive': self.thread.is_alive() if self.thread else False,
            'heartbeat_timeout': self.heartbeat_timeout,
            'check_interval': self.check_interval
        }

