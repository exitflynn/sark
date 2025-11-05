import unittest
import tempfile
import os
import json
import time
from unittest.mock import Mock, patch

from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient


class TestInMemoryStore(unittest.TestCase):
    """Test cases for InMemoryStore."""
    
    def setUp(self):
        """Create temporary store file for testing."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.store_path = self.temp_file.name
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        if os.path.exists(f"{self.store_path}.tmp"):
            os.unlink(f"{self.store_path}.tmp")
    
    def test_worker_registration(self):
        """Test worker registration."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        worker_info = {
            'worker_id': 'worker-1',
            'device_name': 'MacBook Pro',
            'ip_address': '192.168.1.100',
            'capabilities': ['CPU', 'DML'],
            'soc': 'Apple M1',
            'ram_gb': 16,
            'os': 'Darwin'
        }
        
        worker_id = store.register_worker(worker_info)
        
        self.assertEqual(worker_id, 'worker-1')
        self.assertEqual(store.get_worker('worker-1')['device_name'], 'MacBook Pro')
        self.assertEqual(store.get_worker('worker-1')['status'], 'active')
    
    def test_campaign_creation(self):
        """Test campaign creation."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        campaign_info = {
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 5
        }
        
        campaign_id = store.create_campaign(campaign_info)
        
        self.assertEqual(campaign_id, 'campaign-1')
        campaign = store.get_campaign('campaign-1')
        self.assertEqual(campaign['status'], 'running')
        self.assertEqual(campaign['completed_jobs'], 0)
    
    def test_job_creation(self):
        """Test job creation."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        job_info = {
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'compute_unit': 'CPU'
        }
        
        job_id = store.create_job(job_info)
        
        self.assertEqual(job_id, 'job-1')
        job = store.get_job('job-1')
        self.assertEqual(job['status'], 'pending')
    
    def test_job_status_update(self):
        """Test job status updates."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        job_info = {
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'compute_unit': 'CPU'
        }
        
        store.create_job(job_info)
        store.update_job_status('job-1', 'running', worker_id='worker-1')
        
        job = store.get_job('job-1')
        self.assertEqual(job['status'], 'running')
        self.assertEqual(job['worker_id'], 'worker-1')
    
    def test_result_saving(self):
        """Test result saving."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        result_info = {
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'status': 'Complete',
            'LoadMsMedian': 123.45,
            'InferenceMsMedian': 234.56
        }
        
        store.save_result(result_info)
        
        result = store.get_result('job-1')
        self.assertEqual(result['LoadMsMedian'], 123.45)
    
    def test_persistence(self):
        """Test persistence to disk."""
        # Create store and add data
        store1 = InMemoryStore(persistence_file=self.store_path)
        
        worker_info = {
            'worker_id': 'worker-1',
            'device_name': 'Test',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        }
        store1.register_worker(worker_info)
        
        # Force save
        store1.force_save()
        
        # Create new store and verify data is loaded
        store2 = InMemoryStore(persistence_file=self.store_path)
        
        self.assertEqual(len(store2.get_all_workers()), 1)
        self.assertEqual(store2.get_worker('worker-1')['device_name'], 'Test')
    
    def test_capability_filtering(self):
        """Test querying workers by capability."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        # Register workers with different capabilities
        store.register_worker({
            'worker_id': 'worker-cpu',
            'device_name': 'CPU Machine',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        store.register_worker({
            'worker_id': 'worker-gpu',
            'device_name': 'GPU Machine',
            'ip_address': '192.168.1.2',
            'capabilities': ['DML', 'OpenVINO;GPU']
        })
        
        # Query by capability
        cpu_workers = store.get_workers_by_capability('CPU')
        self.assertEqual(len(cpu_workers), 1)
        self.assertEqual(cpu_workers[0]['worker_id'], 'worker-cpu')
        
        gpu_workers = store.get_workers_by_capability('DML')
        self.assertEqual(len(gpu_workers), 1)
        self.assertEqual(gpu_workers[0]['worker_id'], 'worker-gpu')
    
    def test_campaign_progress_tracking(self):
        """Test campaign progress tracking."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 5
        })
        
        store.update_campaign_progress('campaign-1', increment_completed=True)
        store.update_campaign_progress('campaign-1', increment_completed=True)
        store.update_campaign_progress('campaign-1', increment_failed=True)
        
        campaign = store.get_campaign('campaign-1')
        self.assertEqual(campaign['completed_jobs'], 2)
        self.assertEqual(campaign['failed_jobs'], 1)
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        store = InMemoryStore(persistence_file=self.store_path)
        import threading
        
        def register_workers():
            for i in range(10):
                store.register_worker({
                    'worker_id': f'worker-{i}',
                    'device_name': f'Machine {i}',
                    'ip_address': f'192.168.1.{i}',
                    'capabilities': ['CPU']
                })
        
        threads = [threading.Thread(target=register_workers) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have registered workers without errors
        workers = store.get_all_workers()
        self.assertGreater(len(workers), 0)


class TestRedisClient(unittest.TestCase):
    """Test cases for RedisClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock Redis client
        self.redis_mock = Mock()
    
    def test_redis_health_check_format(self):
        """Test health check response format."""
        client = RedisClient(host='localhost', port=6379)
        health = client.health_check()
        
        self.assertIn('connected', health)
        self.assertIn('host', health)
        self.assertIn('port', health)
        self.assertIn('timestamp', health)


class TestIntegration(unittest.TestCase):
    """Integration tests for Phase 1."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.store_path = self.temp_file.name
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
    
    def test_end_to_end_workflow(self):
        """Test complete workflow: register worker -> create campaign -> create jobs."""
        store = InMemoryStore(persistence_file=self.store_path)
        
        # 1. Register worker
        store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test Machine',
            'ip_address': '192.168.1.100',
            'capabilities': ['CPU', 'DML']
        })
        
        # 2. Create campaign
        store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 3
        })
        
        # 3. Create jobs
        for i in range(3):
            store.create_job({
                'job_id': f'campaign-1-job-{i}',
                'campaign_id': 'campaign-1',
                'model_url': 'https://example.com/model.onnx',
                'compute_unit': 'CPU' if i % 2 == 0 else 'DML'
            })
        
        # 4. Execute jobs (simulate)
        jobs = store.get_jobs_by_campaign('campaign-1')
        self.assertEqual(len(jobs), 3)
        
        for job in jobs:
            store.update_job_status(job['job_id'], 'running', 'worker-1')
        
        # 5. Save results
        for job in jobs:
            store.save_result({
                'job_id': job['job_id'],
                'campaign_id': 'campaign-1',
                'status': 'Complete',
                'LoadMsMedian': 100.0,
                'InferenceMsMedian': 200.0,
                'ComputeUnits': job['compute_unit']
            })
            store.update_job_status(job['job_id'], 'complete')
        
        # 6. Update campaign progress
        store.update_campaign_progress('campaign-1', increment_completed=True)
        store.update_campaign_progress('campaign-1', increment_completed=True)
        store.update_campaign_progress('campaign-1', increment_completed=True)
        store.update_campaign_progress('campaign-1', status='complete')
        
        # 7. Verify results
        campaign = store.get_campaign('campaign-1')
        self.assertEqual(campaign['status'], 'complete')
        self.assertEqual(campaign['completed_jobs'], 3)
        
        results = store.query_results_for_csv('campaign-1')
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['DeviceName'], 'Test Machine')


if __name__ == '__main__':
    unittest.main()

