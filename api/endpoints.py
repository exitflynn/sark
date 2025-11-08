"""
HTTP API Endpoints for the Orchestrator.
Provides REST API for worker registration, job management, and monitoring.
"""

from flask import Blueprint, request, jsonify, send_file
import uuid
import csv
import io
import os
import logging
import hashlib
from datetime import datetime
from typing import Tuple, Dict, Any


logger = logging.getLogger(__name__)

# Blueprint for API endpoints
api_bp = Blueprint('api', __name__, url_prefix='/api')


# Global references (will be injected by orchestrator)
store = None
redis_client = None
job_dispatcher = None
health_monitor = None
job_timeout_handler = None


def init_endpoints(inmemory_store, redis_conn, dispatcher=None):
    """Initialize endpoints with store and redis references."""
    global store, redis_client, job_dispatcher, health_monitor, job_timeout_handler
    store = inmemory_store
    redis_client = redis_conn
    job_dispatcher = dispatcher


def get_deterministic_worker_id(device_info: Dict[str, Any]) -> str:
    """
    Generate consistent worker ID based on device UDID.
    Same device always gets same ID, preventing duplicates on restart.
    
    Args:
        device_info: Device information dictionary
        
    Returns:
        Deterministic worker ID
    """
    # Use UDID if available (preferred), fall back to other identifiers
    udid = device_info.get('UDID')
    
    if udid:
        # Hash the UDID to keep ID length reasonable
        hash_obj = hashlib.md5(udid.encode())
        return f"worker-{hash_obj.hexdigest()[:12]}"
    
    # Fallback: Use combination of device identifiers
    device_key = f"{device_info.get('DeviceName', '')}_{device_info.get('Soc', '')}_{device_info.get('Ram', 0)}_{device_info.get('DeviceOs', '')}"
    
    if device_key.strip('_'):  # If we have any data
        hash_obj = hashlib.md5(device_key.encode())
        return f"worker-{hash_obj.hexdigest()[:12]}"
    
    # Last resort: Generate random ID
    return f"worker-{uuid.uuid4().hex[:12]}"


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


@api_bp.route('/reset', methods=['POST'])
def reset_data() -> Tuple[dict, int]:
    """Reset all data (workers, jobs, results, campaigns)."""
    try:
        # Get the storage file path from store
        storage_file = store.storage_file if hasattr(store, 'storage_file') else None
        
        # Clear in-memory data
        store.workers = {}
        store.jobs = {}
        store.results = {}
        store.campaigns = {}
        
        # Delete storage file if it exists
        if storage_file and os.path.exists(storage_file):
            os.remove(storage_file)
            logger.info(f"🔄 Reset complete - deleted storage file: {storage_file}")
        else:
            logger.info("🔄 Reset complete - cleared all in-memory data")
        
        return jsonify({
            'status': 'reset',
            'message': 'All data cleared successfully',
            'workers_cleared': True,
            'jobs_cleared': True,
            'results_cleared': True,
            'campaigns_cleared': True
        }), 200
    
    except Exception as e:
        logger.error(f"Error resetting data: {e}")
        return jsonify({'error': str(e)}), 500


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
    """Register or update a worker with deterministic ID based on device UDID."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['device_name', 'ip_address', 'capabilities', 'device_info']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        # Generate deterministic worker ID from device info (uses UDID if available)
        worker_id = get_deterministic_worker_id(data['device_info'])
        
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
            'udid': data['device_info'].get('UDID', ''),
        }
        
        # Check if worker already exists
        existing = store.get_worker(worker_id)
        
        if existing:
            # Update status to active if was faulty (recovery mechanism)
            if existing.get('status') == 'faulty':
                store.update_worker_status(worker_id, 'active')
                logger.info(f"♻️  Re-registered worker {worker_id} ({data['device_name']}) - status recovered from faulty to active")
            else:
                store.update_worker_status(worker_id, 'active')
                logger.info(f"♻️  Worker {worker_id} ({data['device_name']}) reconnected - updated registration")
            
            return jsonify({
                'worker_id': worker_id,
                'status': 'updated',
                'action': 'recovered' if existing.get('status') == 'faulty' else 'updated'
            }), 200
        else:
            # New worker registration
            store.register_worker(worker_info)
            logger.info(f"✅ Registered new worker {worker_id} ({data['device_name']})")
            logger.info(f"   Capabilities: {', '.join(data['capabilities'])}")
            
            return jsonify({
                'worker_id': worker_id,
                'status': 'registered',
                'action': 'created'
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
        
        # Prepare campaign info with jobs array for tracking
        jobs_array = []
        campaign_info = {
            'campaign_id': campaign_id,
            'model_url': data['model_url'],
            'total_jobs': len(data['jobs']),
            'jobs': jobs_array  # Will be populated below
        }
        
        # Create campaign
        store.create_campaign(campaign_info)
        
        # Create jobs and push to Redis queues
        for i, job_spec in enumerate(data['jobs']):
            job_id = f"{campaign_id}-job-{i}"
            compute_unit = job_spec.get('compute_unit', 'CPU')
            
            job_info = {
                'job_id': job_id,
                'campaign_id': campaign_id,
                'model_url': data['model_url'],
                'compute_unit': compute_unit,
                'worker_id': job_spec.get('worker_id'),
                'num_inference_runs': job_spec.get('num_inference_runs', 10)
            }
            
            # Create job in store
            store.create_job(job_info)
            
            # Add to campaign's job tracking
            jobs_array.append({
                'job_id': job_id,
                'compute_unit': compute_unit,
                'status': 'pending'
            })
            
            # Push to appropriate Redis queue using job dispatcher
            if job_dispatcher:
                job_dispatcher.push_job_to_queues(job_info)
            else:
                # Fallback: push manually
                if job_spec.get('worker_id'):
                    queue_name = f"jobs:{job_spec['worker_id']}"
                else:
                    queue_name = f"jobs:capability:{compute_unit}"
                redis_client.push_job(queue_name, job_id)
                logger.debug(f"Queued job {job_id} to {queue_name}")
        
        logger.info(f"✅ Created campaign {campaign_id} with {len(data['jobs'])} jobs")
        for i, job in enumerate(jobs_array):
            logger.info(f"   Job {i+1}: {job['job_id']} (compute_unit={job['compute_unit']})")
        
        return jsonify({
            'campaign_id': campaign_id,
            'total_jobs': len(data['jobs']),
            'status': 'running',
            'jobs': jobs_array
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
    """Get campaign results as CSV - from file if available, otherwise from memory."""
    try:
        campaign = store.get_campaign(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check if CSV file exists on disk
        csv_file = campaign.get('results_file')
        
        if csv_file and os.path.exists(csv_file):
            # Serve from file
            logger.info(f"Serving campaign results from file: {csv_file}")
            return send_file(
                csv_file,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{campaign_id}_results.csv'
            )
        
        # Fallback: Generate from memory
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


# ========== Phase 3: Health & Monitoring ==========

@api_bp.route('/workers/<worker_id>/health', methods=['GET'])
def get_worker_health(worker_id: str) -> Tuple[dict, int]:
    """Get worker health status."""
    try:
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        health = health_monitor.get_worker_health(worker_id)
        
        if 'error' in health:
            return jsonify(health), 404
        
        return jsonify(health), 200
    
    except Exception as e:
        logger.error(f"Error getting worker health: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/health/workers', methods=['GET'])
def get_all_worker_health() -> Tuple[dict, int]:
    """Get health status for all workers."""
    try:
        if not health_monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        health_statuses = health_monitor.get_all_health()
        healthy_count = sum(1 for h in health_statuses if h.get('is_healthy'))
        
        return jsonify({
            'total': len(health_statuses),
            'healthy': healthy_count,
            'unhealthy': len(health_statuses) - healthy_count,
            'workers': health_statuses
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting all worker health: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/workers/<worker_id>/reset', methods=['PUT'])
def reset_worker(worker_id: str) -> Tuple[dict, int]:
    """Reset faulty worker."""
    try:
        worker = store.get_worker(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404
        
        if worker.get('status') != 'faulty':
            return jsonify({'error': 'Worker is not in faulty state'}), 400
        
        store.update_worker_status(worker_id, 'active')
        
        # Record new heartbeat
        if health_monitor:
            health_monitor.record_heartbeat(worker_id)
        
        logger.info(f"✅ Reset worker {worker_id} from faulty state")
        
        return jsonify({
            'worker_id': worker_id,
            'status': 'active',
            'message': 'Worker reset successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error resetting worker: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/workers/<worker_id>/heartbeat', methods=['POST'])
def worker_heartbeat(worker_id: str) -> Tuple[dict, int]:
    """
    Record worker heartbeat during job execution.
    Workers send periodic heartbeats while executing long-running jobs
    to prevent being marked as faulty by the health monitor.
    
    If worker was marked faulty, recover it back to active status.
    """
    try:
        worker = store.get_worker(worker_id)
        if not worker:
            logger.warning(f"Heartbeat received for unknown worker: {worker_id}")
            return jsonify({'error': 'Worker not found'}), 404
        
        current_status = worker.get('status', 'active')
        
        # Record heartbeat in health monitor (resets the timeout counter)
        if health_monitor:
            health_monitor.record_heartbeat(worker_id)
            logger.debug(f"❤️  Heartbeat recorded for {worker_id}")
        
        # If worker was faulty, recover it to active
        if current_status == 'faulty':
            logger.info(f"♻️  Worker {worker_id} recovered from faulty status (via heartbeat)")
            store.update_worker_status(worker_id, 'active')
            status_action = 'recovered'
        else:
            # Just update last_seen timestamp (keep current status)
            store.update_worker_status(worker_id, current_status)
            status_action = 'updated'
        
        return jsonify({
            'worker_id': worker_id,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'active',
            'previous_status': current_status,
            'action': status_action
        }), 200
    
    except Exception as e:
        logger.error(f"Error recording heartbeat: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500




# ========== Result Files ==========

@api_bp.route('/results/files', methods=['GET'])
def list_result_files() -> Tuple[dict, int]:
    """List all available CSV result files from outputs folder."""
    try:
        files = []
        output_dir = 'outputs'
        
        if os.path.exists(output_dir):
            for filename in os.listdir(output_dir):
                if filename.endswith('_results.csv'):
                    filepath = os.path.join(output_dir, filename)
                    file_size = os.path.getsize(filepath)
                    mod_time = os.path.getmtime(filepath)
                    
                    files.append({
                        'filename': filename,
                        'path': filepath,
                        'size_bytes': file_size,
                        'size_mb': round(file_size / 1024 / 1024, 2),
                        'modified': datetime.fromtimestamp(mod_time).isoformat()
                    })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        logger.debug(f"Listed {len(files)} result files")
        
        return jsonify({
            'count': len(files),
            'files': files
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing result files: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/results/download/<path:filename>', methods=['GET'])
def download_result_file(filename: str) -> Tuple[dict, int]:
    """Download a specific CSV result file from outputs folder."""
    try:
        # Security: validate filename to prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': 'Invalid filename'}), 400
        
        filepath = os.path.join('outputs', filename)
        
        # Verify file exists and ends with .csv
        if not os.path.exists(filepath) or not filename.endswith('_results.csv'):
            return jsonify({'error': 'File not found'}), 404
        
        logger.info(f"Downloading result file: {filepath}")
        
        return send_file(
            filepath,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/monitoring/stats', methods=['GET'])
def get_monitoring_stats() -> Tuple[dict, int]:
    """Get monitoring statistics."""
    try:
        stats = {
            'health_monitor': health_monitor.get_status() if health_monitor else None,
            'timeout_handler': job_timeout_handler.get_timeout_stats() if job_timeout_handler else None,
        }
        
        return jsonify(stats), 200
    
    except Exception as e:
        logger.error(f"Error getting monitoring stats: {e}")
        return jsonify({'error': str(e)}), 500


