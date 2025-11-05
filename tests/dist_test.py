import unittest
import tempfile
import os
import json
import time
from unittest.mock import Mock, patch, MagicMock

from core.inmemory_store import InMemoryStore
from core.redis_client import RedisClient
from core.job_dispatcher import JobDispatcher
from core.result_processor import ResultProcessor


class TestJobDispatcher(unittest.TestCase):
    """Test cases for JobDispatcher."""
    
    def setUp(self):
        """Create mock Redis client."""
        self.redis_mock = MagicMock()
        self.dispatcher = JobDispatcher(self.redis_mock)
    
    def test_determine_queues_static_assignment(self):
        """Test routing with static worker assignment."""
        job = {
            'job_id': 'job-1',
            'worker_id': 'worker-1',
            'compute_unit': 'CPU'
        }
        
        queues = self.dispatcher.determine_queues(job)
        
        self.assertEqual(len(queues), 1)
        self.assertEqual(queues[0], 'jobs:worker-1')
    
    def test_determine_queues_capability_based(self):
        """Test routing with capability-based assignment."""
        job = {
            'job_id': 'job-1',
            'compute_unit': 'DML'
        }
        
        queues = self.dispatcher.determine_queues(job)
        
        self.assertEqual(len(queues), 1)
        self.assertEqual(queues[0], 'jobs:capability:DML')
    
    def test_determine_queues_no_routing_info(self):
        """Test handling of job with no routing information."""
        job = {
            'job_id': 'job-1'
        }
        
        queues = self.dispatcher.determine_queues(job)
        
        self.assertEqual(len(queues), 0)
    
    def test_push_job_to_queues_success(self):
        """Test successful job push to queue."""
        self.redis_mock.push_job.return_value = True
        
        job = {
            'job_id': 'job-1',
            'worker_id': 'worker-1',
            'compute_unit': 'CPU'
        }
        
        success = self.dispatcher.push_job_to_queues(job)
        
        self.assertTrue(success)
        self.redis_mock.push_job.assert_called_once()
    
    def test_get_worker_queue_priority(self):
        """Test worker queue priority ordering."""
        queues = JobDispatcher.get_worker_queue_priority(
            'worker-1',
            ['CPU', 'DML', 'OpenVINO;GPU']
        )
        
        # Personal queue should be first
        self.assertEqual(queues[0], 'jobs:worker-1')
        # Capability queues should follow
        self.assertIn('jobs:capability:CPU', queues)
        self.assertIn('jobs:capability:DML', queues)
        self.assertIn('jobs:capability:OpenVINO;GPU', queues)
    
    def test_push_jobs_from_campaign(self):
        """Test pushing all jobs from a campaign."""
        self.redis_mock.push_job.return_value = True
        
        # Create store with data
        store = InMemoryStore(persistence_file=tempfile.mktemp())
        
        # Create campaign and jobs
        store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 3
        })
        
        for i in range(3):
            store.create_job({
                'job_id': f'campaign-1-job-{i}',
                'campaign_id': 'campaign-1',
                'model_url': 'https://example.com/model.onnx',
                'compute_unit': 'CPU',
                'worker_id': f'worker-{i}'
            })
        
        # Push jobs
        queued_count = self.dispatcher.push_jobs_from_campaign(
            self.redis_mock, store, 'campaign-1'
        )
        
        self.assertEqual(queued_count, 3)
        self.assertEqual(self.redis_mock.push_job.call_count, 3)


class TestResultProcessor(unittest.TestCase):
    """Test cases for ResultProcessor."""
    
    def setUp(self):
        """Create test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.store = InMemoryStore(persistence_file=self.temp_file.name)
        self.redis_mock = MagicMock()
        self.processor = ResultProcessor(self.store, self.redis_mock)
    
    def tearDown(self):
        """Clean up."""
        self.processor.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_process_single_result_success(self):
        """Test processing a successful result."""
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
        
        # Process result
        result = {
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'status': 'Complete',
            'LoadMsMedian': 100.0,
            'InferenceMsMedian': 200.0
        }
        
        self.processor._process_single_result(result)
        
        # Verify result was saved
        saved_result = self.store.get_result('job-1')
        self.assertIsNotNone(saved_result)
        self.assertEqual(saved_result['status'], 'Complete')
        
        # Verify campaign progress updated
        campaign = self.store.get_campaign('campaign-1')
        self.assertEqual(campaign['completed_jobs'], 1)
    
    def test_process_single_result_failure(self):
        """Test processing a failed result."""
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
        
        # Process failed result
        result = {
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'status': 'Failed',
            'remark': 'Model not found'
        }
        
        self.processor._process_single_result(result)
        
        # Verify campaign progress updated
        campaign = self.store.get_campaign('campaign-1')
        self.assertEqual(campaign['failed_jobs'], 1)
    
    def test_campaign_completion_detection(self):
        """Test detection of campaign completion."""
        # Create campaign with 2 jobs
        self.store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 2
        })
        
        self.store.create_job({
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'compute_unit': 'CPU'
        })
        
        self.store.create_job({
            'job_id': 'job-2',
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'compute_unit': 'DML'
        })
        
        # Process first result
        self.processor._process_single_result({
            'job_id': 'job-1',
            'campaign_id': 'campaign-1',
            'status': 'Complete'
        })
        
        campaign = self.store.get_campaign('campaign-1')
        self.assertEqual(campaign['status'], 'running')  # Still running
        
        # Process second result
        self.processor._process_single_result({
            'job_id': 'job-2',
            'campaign_id': 'campaign-1',
            'status': 'Complete'
        })
        
        campaign = self.store.get_campaign('campaign-1')
        self.assertEqual(campaign['status'], 'complete')  # Now complete
    
    def test_get_status(self):
        """Test processor status reporting."""
        status = self.processor.get_status()
        
        self.assertIn('running', status)
        self.assertIn('thread_alive', status)


class TestIntegrationPhase2(unittest.TestCase):
    """Integration tests for Phase 2."""
    
    def setUp(self):
        """Create test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.store = InMemoryStore(persistence_file=self.temp_file.name)
        self.redis_mock = MagicMock()
        self.dispatcher = JobDispatcher(self.redis_mock)
        self.processor = ResultProcessor(self.store, self.redis_mock)
    
    def tearDown(self):
        """Clean up."""
        self.processor.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_campaign_to_job_distribution(self):
        """Test complete flow: campaign creation to job distribution."""
        # Register workers
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Machine 1',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU', 'DML']
        })
        
        self.store.register_worker({
            'worker_id': 'worker-2',
            'device_name': 'Machine 2',
            'ip_address': '192.168.1.2',
            'capabilities': ['CPU']
        })
        
        # Create campaign
        self.store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 3
        })
        
        # Create jobs with different routing strategies
        jobs = [
            {
                'job_id': 'campaign-1-job-0',
                'campaign_id': 'campaign-1',
                'model_url': 'https://example.com/model.onnx',
                'compute_unit': 'CPU',
                'worker_id': 'worker-1'  # Static assignment
            },
            {
                'job_id': 'campaign-1-job-1',
                'campaign_id': 'campaign-1',
                'model_url': 'https://example.com/model.onnx',
                'compute_unit': 'DML',
                # No worker_id -> capability-based
            },
            {
                'job_id': 'campaign-1-job-2',
                'campaign_id': 'campaign-1',
                'model_url': 'https://example.com/model.onnx',
                'compute_unit': 'CPU',
                # No worker_id -> capability-based
            }
        ]
        
        for job in jobs:
            self.store.create_job(job)
            self.dispatcher.push_job_to_queues(job)
        
        # Verify all jobs were queued
        self.assertEqual(self.redis_mock.push_job.call_count, 3)
    
    def test_end_to_end_campaign_flow(self):
        """Test complete campaign flow with results."""
        # Register worker
        self.store.register_worker({
            'worker_id': 'worker-1',
            'device_name': 'Test Machine',
            'ip_address': '192.168.1.1',
            'capabilities': ['CPU']
        })
        
        # Create campaign with 2 jobs
        self.store.create_campaign({
            'campaign_id': 'campaign-1',
            'model_url': 'https://example.com/model.onnx',
            'total_jobs': 2
        })
        
        for i in range(2):
            self.store.create_job({
                'job_id': f'campaign-1-job-{i}',
                'campaign_id': 'campaign-1',
                'model_url': 'https://example.com/model.onnx',
                'compute_unit': 'CPU'
            })
        
        # Simulate job execution and results
        for i in range(2):
            result = {
                'job_id': f'campaign-1-job-{i}',
                'campaign_id': 'campaign-1',
                'worker_id': 'worker-1',
                'status': 'Complete',
                'LoadMsMedian': 100.0 + i,
                'InferenceMsMedian': 200.0 + i,
                'FileName': f'model-{i}.onnx',
                'FileSize': 1000,
                'ComputeUnits': 'CPU'
            }
            
            self.processor._process_single_result(result)
        
        # Verify campaign is complete
        campaign = self.store.get_campaign('campaign-1')
        self.assertEqual(campaign['status'], 'complete')
        self.assertEqual(campaign['completed_jobs'], 2)
        
        # Verify results can be queried for CSV
        results = self.store.query_results_for_csv('campaign-1')
        self.assertEqual(len(results), 2)
        
        # Verify CSV contains expected fields
        for result_row in results:
            self.assertIn('LoadMsMedian', result_row)
            self.assertIn('InferenceMsMedian', result_row)
            self.assertIn('DeviceName', result_row)


if __name__ == '__main__':
    unittest.main()

