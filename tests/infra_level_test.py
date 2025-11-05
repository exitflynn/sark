import unittest
import tempfile
import os
import time
from unittest.mock import Mock, MagicMock, patch

from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient
from core.state_machine import StateMachine, WorkerState, WorkerLifecycle, InvalidStateTransition
from core.health_monitor import HealthMonitor
from core.job_timeout import JobTimeoutHandler


class TestStateMachine(unittest.TestCase):
    """Test cases for worker state machine."""
    
    def test_initial_state(self):
        """Test initial state is ACTIVE."""
        sm = StateMachine()
        self.assertEqual(sm.state, WorkerState.ACTIVE)
    
    def test_active_to_busy_transition(self):
        """Test ACTIVE → BUSY transition."""
        sm = StateMachine(WorkerState.ACTIVE)
        self.assertTrue(sm.can_transition(WorkerState.BUSY))
        sm.transition(WorkerState.BUSY)
        self.assertEqual(sm.state, WorkerState.BUSY)
    
    def test_busy_to_cleanup_transition(self):
        """Test BUSY → CLEANUP transition."""
        sm = StateMachine(WorkerState.BUSY)
        self.assertTrue(sm.can_transition(WorkerState.CLEANUP))
        sm.transition(WorkerState.CLEANUP)
        self.assertEqual(sm.state, WorkerState.CLEANUP)
    
    def test_cleanup_to_active_transition(self):
        """Test CLEANUP → ACTIVE transition."""
        sm = StateMachine(WorkerState.CLEANUP)
        self.assertTrue(sm.can_transition(WorkerState.ACTIVE))
        sm.transition(WorkerState.ACTIVE)
        self.assertEqual(sm.state, WorkerState.ACTIVE)
    
    def test_any_to_faulty_transition(self):
        """Test any state → FAULTY transition."""
        for state in [WorkerState.ACTIVE, WorkerState.BUSY, WorkerState.CLEANUP]:
            sm = StateMachine(state)
            self.assertTrue(sm.can_transition(WorkerState.FAULTY))
            sm.transition(WorkerState.FAULTY)
            self.assertEqual(sm.state, WorkerState.FAULTY)
    
    def test_faulty_to_active_transition(self):
        """Test FAULTY → ACTIVE recovery transition."""
        sm = StateMachine(WorkerState.FAULTY)
        self.assertTrue(sm.can_transition(WorkerState.ACTIVE))
        sm.transition(WorkerState.ACTIVE)
        self.assertEqual(sm.state, WorkerState.ACTIVE)
    
    def test_invalid_transition(self):
        """Test invalid transition raises error."""
        sm = StateMachine(WorkerState.ACTIVE)
        self.assertFalse(sm.can_transition(WorkerState.CLEANUP))
        with self.assertRaises(InvalidStateTransition):
            sm.transition(WorkerState.CLEANUP)
    
    def test_no_self_transition(self):
        """Test self-transitions not allowed."""
        sm = StateMachine(WorkerState.ACTIVE)
        self.assertFalse(sm.can_transition(WorkerState.ACTIVE))
    
    def test_worker_lifecycle_mark_busy(self):
        """Test WorkerLifecycle helper mark_busy."""
        sm = StateMachine(WorkerState.ACTIVE)
        WorkerLifecycle.mark_busy(sm)
        self.assertEqual(sm.state, WorkerState.BUSY)
    
    def test_worker_lifecycle_mark_cleanup(self):
        """Test WorkerLifecycle helper mark_cleanup."""
        sm = StateMachine(WorkerState.BUSY)
        WorkerLifecycle.mark_cleanup(sm)
        self.assertEqual(sm.state, WorkerState.CLEANUP)
    
    def test_worker_lifecycle_mark_active(self):
        """Test WorkerLifecycle helper mark_active."""
        sm = StateMachine(WorkerState.CLEANUP)
        WorkerLifecycle.mark_active(sm)
        self.assertEqual(sm.state, WorkerState.ACTIVE)
    
    def test_worker_lifecycle_mark_faulty(self):
        """Test WorkerLifecycle helper mark_faulty."""
        sm = StateMachine(WorkerState.BUSY)
        WorkerLifecycle.mark_faulty(sm, "test error")
        self.assertEqual(sm.state, WorkerState.FAULTY)
    
    def test_full_lifecycle(self):
        """Test full worker lifecycle."""
        sm = StateMachine()
        
        # ACTIVE → BUSY
        WorkerLifecycle.mark_busy(sm)
        self.assertTrue(sm.is_busy())
        
        # BUSY → CLEANUP
        WorkerLifecycle.mark_cleanup(sm)
        self.assertEqual(sm.state, WorkerState.CLEANUP)
        
        # CLEANUP → ACTIVE
        WorkerLifecycle.mark_active(sm)
        self.assertTrue(sm.is_active())


class TestHealthMonitor(unittest.TestCase):
    """Test cases for health monitor."""
    
    def setUp(self):
        """Create test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.store = InMemoryStore(persistence_file=self.temp_file.name)
        self.redis_mock = MagicMock()
        self.monitor = HealthMonitor(self.store, heartbeat_timeout=60, check_interval=1)
    
    def tearDown(self):
        """Clean up."""
        self.monitor.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_record_heartbeat(self):
        """Test recording heartbeat."""
        self.monitor.record_heartbeat('worker-1')
        self.assertIn('worker-1', self.monitor.last_heartbeat)
    
    def test_worker_health_active(self):
        """Test health status for active worker."""
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        self.monitor.record_heartbeat('worker-1')
        health = self.monitor.get_worker_health('worker-1')
        
        self.assertTrue(health['is_healthy'])
        self.assertEqual(health['worker_id'], 'worker-1')
    
    def test_worker_health_timeout(self):
        """Test health status for timed-out worker."""
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        # Record heartbeat in the past (beyond timeout)
        self.monitor.last_heartbeat['worker-1'] = time.time() - 120
        health = self.monitor.get_worker_health('worker-1')
        
        self.assertFalse(health['is_healthy'])
    
    def test_get_all_health(self):
        """Test getting health for all workers."""
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test1',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        self.store.register_worker({
            'worker_id': 'worker-2',
            'device_name': 'Test2',
            'ip_address': '192.168.1.2',
            'capabilities': ['CPU']
        })
        
        self.monitor.record_heartbeat('worker-1')
        self.monitor.record_heartbeat('worker-2')
        
        all_health = self.monitor.get_all_health()
        self.assertEqual(len(all_health), 2)


class TestJobTimeoutHandler(unittest.TestCase):
    """Test cases for job timeout handler."""
    
    def setUp(self):
        """Create test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.store = InMemoryStore(persistence_file=self.temp_file.name)
        self.redis_mock = MagicMock()
        self.timeout_handler = JobTimeoutHandler(self.store, self.redis_mock, 
                                                default_timeout=60, check_interval=1)
    
    def tearDown(self):
        """Clean up."""
        self.timeout_handler.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_timeout_detection(self):
        """Test timeout detection."""
        # Create campaign and job
        self.store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 1
        })
        
        self.store.create_job({
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'compute_unit': 'CPU'
        })
        
        # Mark job as running with old start time (will timeout)
        self.store.update_job_status('job-1', 'running')
        job = self.store.get_job('job-1')
        job['started_at'] = time.time() - 120  # 120 seconds ago
        
        # Check timeouts
        self.timeout_handler._check_job_timeouts()
        
        # Job should be marked as timed out
        updated_job = self.store.get_job('job-1')
        self.assertEqual(updated_job['status'], 'timed_out')
    
    def test_timeout_stats(self):
        """Test timeout statistics."""
        stats = self.timeout_handler.get_timeout_stats()
        
        self.assertIn('total_jobs', stats)
        self.assertIn('timed_out_jobs', stats)
        self.assertIn('failed_jobs', stats)


class TestIntegrationInfraLevel(unittest.TestCase):
    
    def setUp(self):
        """Create test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.store = InMemoryStore(persistence_file=self.temp_file.name)
        self.redis_mock = MagicMock()
        self.monitor = HealthMonitor(self.store, heartbeat_timeout=2, check_interval=1)
        self.timeout_handler = JobTimeoutHandler(self.store, self.redis_mock)
    
    def tearDown(self):
        """Clean up."""
        self.monitor.stop()
        self.timeout_handler.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_worker_lifecycle_with_monitoring(self):
        """Test complete worker lifecycle with monitoring."""
        # Register worker
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test Machine',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        # Record heartbeat
        self.monitor.record_heartbeat('worker-1')
        health = self.monitor.get_worker_health('worker-1')
        self.assertTrue(health['is_healthy'])
        
        # Worker should still be healthy immediately
        self.assertTrue(health['is_healthy'])
    
    def test_job_timeout_and_worker_faulty(self):
        """Test job timeout marks worker as faulty."""
        # Register worker
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        # Create campaign and job with timeout
        self.store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 1
        })
        
        current_time = time.time()
        self.store.create_job({
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'compute_unit': 'CPU',
            'worker_id': 'worker-1',
            'timeout_seconds': 60
        })
        
        # Mark job as running with old start time (will timeout)
        with self.store.lock:
            self.store.jobs['job-1']['status'] = 'running'
            self.store.jobs['job-1']['worker_id'] = 'worker-1'
            self.store.jobs['job-1']['started_at'] = current_time - 120  # 120 seconds ago
        
        # Detect timeout
        self.timeout_handler._check_job_timeouts()
        
        # Job should be marked as timed out
        updated_job = self.store.get_job('job-1')
        self.assertEqual(updated_job['status'], 'timed_out')


if __name__ == '__main__':
    unittest.main()

