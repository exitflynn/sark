"""
HTTP API Endpoints for the Orchestrator.
Provides REST API for worker registration, campaign management, and monitoring.
"""

from flask import Blueprint, request, jsonify, send_file
import uuid
import csv
import io
import logging
from datetime import datetime
from typing import Tuple


logger = logging.getLogger(__name__)

# Blueprint for API endpoints
api_bp = Blueprint('api', __name__, url_prefix='/api')


# Global references (will be injected by orchestrator)
store = None
redis_client = None


def init_endpoints(inmemory_store, redis_conn):
    """Initialize endpoints with store and redis references."""
    global store, redis_client
    store = inmemory_store
    redis_client = redis_conn


# ========== Health Checks ==========

@api_bp.route('/health', methods=['GET'])
def health_check() -> Tuple[dict, int]:
    """Check orchestrator health."""
    redis_status = redis_client.health_check() if redis_client else {'connected': False}
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'redis': redis_status
    }), 200


# ========== Worker Management ==========

@api_bp.route('/workers', methods=['GET'])
def get_workers() -> Tuple[dict, int]:
    """Get all registered workers."""
    try:
        workers = store.get_all_workers()
        return jsonify({
            'count': len(workers),
            'workers': workers
        }), 200
    except Exception as e:
        logger.error(f"Error getting workers: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/workers/<worker_id>', methods=['GET'])
def get_worker(worker_id: str) -> Tuple[dict, int]:
    """Get specific worker details."""
    try:
        worker = store.get_worker(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404
        return jsonify(worker), 200
    except Exception as e:
        logger.error(f"Error getting worker: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/register', methods=['POST'])
def register_worker() -> Tuple[dict, int]:
    """Register a new worker."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['device_name', 'ip_address', 'capabilities', 'device_info']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        # Generate unique worker ID
        worker_id = f"worker-{uuid.uuid4()}"
        
        worker_info = {
            'worker_id': worker_id,
            'device_name': data['device_name'],
            'ip_address': data['ip_address'],
            'capabilities': data['capabilities'],
            'device_info': data['device_info'],
            # Extract key fields for easier querying
            'soc': data['device_info'].get('Soc', ''),
            'ram_gb': data['device_info'].get('Ram', 0),
            'os': data['device_info'].get('DeviceOs', ''),
            'os_version': data['device_info'].get('DeviceOsVersion', ''),
        }
        
        # Register in store
        store.register_worker(worker_info)
        
        logger.info(f"Registered worker {worker_id} ({data['device_name']})")
        
        return jsonify({
            'worker_id': worker_id,
            'status': 'registered'
        }), 200
    
    except Exception as e:
        logger.error(f"Error registering worker: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/workers/<worker_id>/status', methods=['PUT'])
def update_worker_status(worker_id: str) -> Tuple[dict, int]:
    """Update worker status."""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if status not in ['active', 'busy', 'cleanup', 'faulty']:
            return jsonify({'error': 'Invalid status'}), 400
        
        store.update_worker_status(worker_id, status)
        
        return jsonify({
            'worker_id': worker_id,
            'status': status
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating worker status: {e}")
        return jsonify({'error': str(e)}), 500


# ========== Campaign Management ==========

@api_bp.route('/campaigns', methods=['POST'])
def create_campaign() -> Tuple[dict, int]:
    """Create a new campaign."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'model_url' not in data or 'jobs' not in data:
            return jsonify({'error': 'Missing model_url or jobs'}), 400
        
        # Generate campaign ID
        campaign_id = f"campaign-{int(datetime.utcnow().timestamp())}"
        
        campaign_info = {
            'campaign_id': campaign_id,
            'model_url': data['model_url'],
            'total_jobs': len(data['jobs'])
        }
        
        # Create campaign
        store.create_campaign(campaign_info)
        
        # Create jobs and push to Redis queues
        for i, job_spec in enumerate(data['jobs']):
            job_id = f"{campaign_id}-job-{i}"
            
            job_info = {
                'job_id': job_id,
                'campaign_id': campaign_id,
                'model_url': data['model_url'],
                'compute_unit': job_spec.get('compute_unit'),
                'worker_id': job_spec.get('worker_id'),
                'num_warmups': job_spec.get('num_warmups', 5),
                'num_inference_runs': job_spec.get('num_inference_runs', 10)
            }
            
            # Create job in store
            store.create_job(job_info)
            
            # Push to appropriate Redis queue
            if job_spec.get('worker_id'):
                # Static assignment - push to worker-specific queue
                queue_name = f"jobs:{job_spec['worker_id']}"
            else:
                # Capability-based - push to capability queue
                queue_name = f"jobs:capability:{job_spec.get('compute_unit')}"
            
            redis_client.push_job(queue_name, job_id)
            logger.debug(f"Queued job {job_id} to {queue_name}")
        
        logger.info(f"Created campaign {campaign_id} with {len(data['jobs'])} jobs")
        
        return jsonify({
            'campaign_id': campaign_id,
            'total_jobs': len(data['jobs']),
            'status': 'running'
        }), 200
    
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/campaigns', methods=['GET'])
def get_campaigns() -> Tuple[dict, int]:
    """Get all campaigns."""
    try:
        campaigns = store.get_all_campaigns()
        return jsonify({
            'count': len(campaigns),
            'campaigns': campaigns
        }), 200
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/campaigns/<campaign_id>', methods=['GET'])
def get_campaign(campaign_id: str) -> Tuple[dict, int]:
    """Get campaign status."""
    try:
        campaign = store.get_campaign(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get job status breakdown
        jobs = store.get_jobs_by_campaign(campaign_id)
        status_breakdown = {
            'pending': len([j for j in jobs if j['status'] == 'pending']),
            'running': len([j for j in jobs if j['status'] == 'running']),
            'complete': len([j for j in jobs if j['status'] == 'complete']),
            'failed': len([j for j in jobs if j['status'] == 'failed']),
        }
        
        response = {
            **campaign,
            'job_breakdown': status_breakdown
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        return jsonify({'error': str(e)}), 500


# ========== Results ==========

@api_bp.route('/campaigns/<campaign_id>/results', methods=['GET'])
def get_campaign_results(campaign_id: str) -> Tuple[dict, int]:
    """Get campaign results as CSV."""
    try:
        campaign = store.get_campaign(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Query results
        results = store.query_results_for_csv(campaign_id)
        
        if not results:
            return jsonify({'error': 'No results available yet'}), 404
        
        # Generate CSV
        output = io.StringIO()
        fieldnames = [
            'Status', 'JobId', 'FileName', 'FileSize', 'ComputeUnits',
            'DeviceName', 'DeviceYear', 'Soc', 'Ram', 'DiscreteGpu', 'VRam',
            'DeviceOs', 'DeviceOsVersion',
            'LoadMsMedian', 'LoadMsStdDev', 'LoadMsAverage', 'LoadMsFirst',
            'PeakLoadRamUsage', 'InferenceMsMedian', 'InferenceMsStdDev',
            'InferenceMsAverage', 'InferenceMsFirst', 'PeakInferenceRamUsage'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        
        # Return as file
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{campaign_id}_results.csv'
        )
    
    except Exception as e:
        logger.error(f"Error getting campaign results: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str) -> Tuple[dict, int]:
    """Get job details."""
    try:
        job = store.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        result = store.get_result(job_id)
        
        response = {
            'job': job,
            'result': result
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error getting job: {e}")
        return jsonify({'error': str(e)}), 500


# ========== Queue Status ==========

@api_bp.route('/queue/status', methods=['GET'])
def get_queue_status() -> Tuple[dict, int]:
    """Get status of all job queues."""
    try:
        # Get list of all workers
        workers = store.get_all_workers()
        
        status = {
            'worker_queues': {},
            'capability_queues': {}
        }
        
        # Check worker-specific queues
        for worker in workers:
            worker_id = worker['worker_id']
            queue_name = f"jobs:{worker_id}"
            size = redis_client.get_queue_size(queue_name)
            status['worker_queues'][worker_id] = {
                'device_name': worker['device_name'],
                'queue_size': size
            }
        
        # Check capability queues
        capabilities = set()
        for worker in workers:
            capabilities.update(worker.get('capabilities', []))
        
        for capability in capabilities:
            queue_name = f"jobs:capability:{capability}"
            size = redis_client.get_queue_size(queue_name)
            status['capability_queues'][capability] = size
        
        # Check results queue
        status['results_queue_size'] = redis_client.get_queue_size('results')
        
        return jsonify(status), 200
    
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return jsonify({'error': str(e)}), 500

