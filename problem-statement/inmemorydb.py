# for eventual orchestrator.py - In-memory state with periodic persistence

import json
import threading
import time
from datetime import datetime

class InMemoryStore:
    def __init__(self, persistence_file='orchestrator_state.json'):
        self.persistence_file = persistence_file
        self.lock = threading.Lock()
        
        # In-memory structures (replace database tables)
        self.workers = {}      # worker_id -> worker_info
        self.campaigns = {}    # campaign_id -> campaign_info
        self.jobs = {}         # job_id -> job_info
        self.results = {}      # job_id -> result_info
        
        # Load from disk if exists
        self._load_from_disk()
        
        # Start background persistence thread
        self._start_persistence_thread()
    
    def _load_from_disk(self):
        """Load state from JSON file on startup"""
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
    
    def _save_to_disk(self):
        """Persist state to JSON file"""
        with self.lock:
            data = {
                'workers': self.workers,
                'campaigns': self.campaigns,
                'jobs': self.jobs,
                'results': self.results,
                'last_saved': datetime.utcnow().isoformat()
            }
            
            # Atomic write (write to temp, then rename)
            temp_file = f"{self.persistence_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, self.persistence_file)
    
    def _persistence_thread(self):
        """Save to disk every 30 seconds"""
        while True:
            time.sleep(30)
            self._save_to_disk()
    
    def _start_persistence_thread(self):
        t = threading.Thread(target=self._persistence_thread, daemon=True)
        t.start()
    
    # ========== Worker Operations ==========
    
    def register_worker(self, worker_info):
        with self.lock:
            worker_id = worker_info['worker_id']
            worker_info['registered_at'] = time.time()
            worker_info['status'] = 'active'
            self.workers[worker_id] = worker_info
            return worker_id
    
    def get_worker(self, worker_id):
        return self.workers.get(worker_id)
    
    def get_active_workers(self):
        return [w for w in self.workers.values() if w['status'] == 'active']
    
    def update_worker_status(self, worker_id, status):
        with self.lock:
            if worker_id in self.workers:
                self.workers[worker_id]['status'] = status
                self.workers[worker_id]['last_seen'] = time.time()
    
    def get_workers_by_capability(self, compute_unit):
        return [
            w for w in self.workers.values() 
            if compute_unit in w.get('capabilities', []) 
            and w['status'] == 'active'
        ]
    
    # ========== Campaign Operations ==========
    
    def create_campaign(self, campaign_info):
        with self.lock:
            campaign_id = campaign_info['campaign_id']
            campaign_info['created_at'] = time.time()
            campaign_info['status'] = 'running'
            campaign_info['completed_jobs'] = 0
            campaign_info['failed_jobs'] = 0
            self.campaigns[campaign_id] = campaign_info
            return campaign_id
    
    def get_campaign(self, campaign_id):
        return self.campaigns.get(campaign_id)
    
    def update_campaign_progress(self, campaign_id, status=None, increment_completed=False, increment_failed=False):
        with self.lock:
            if campaign_id in self.campaigns:
                if increment_completed:
                    self.campaigns[campaign_id]['completed_jobs'] += 1
                if increment_failed:
                    self.campaigns[campaign_id]['failed_jobs'] += 1
                if status:
                    self.campaigns[campaign_id]['status'] = status
    
    # ========== Job Operations ==========
    
    def create_job(self, job_info):
        with self.lock:
            job_id = job_info['job_id']
            job_info['submitted_at'] = time.time()
            job_info['status'] = 'pending'
            job_info['retry_count'] = 0
            self.jobs[job_id] = job_info
            return job_id
    
    def get_job(self, job_id):
        return self.jobs.get(job_id)
    
    def update_job_status(self, job_id, status, worker_id=None):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = status
                if status == 'running':
                    self.jobs[job_id]['started_at'] = time.time()
                    self.jobs[job_id]['worker_id'] = worker_id
                elif status in ['complete', 'failed', 'cancelled']:
                    self.jobs[job_id]['completed_at'] = time.time()
    
    def get_jobs_by_campaign(self, campaign_id):
        return [j for j in self.jobs.values() if j['campaign_id'] == campaign_id]
    
    def get_jobs_by_status(self, status):
        return [j for j in self.jobs.values() if j['status'] == status]
    
    # ========== Result Operations ==========
    
    def save_result(self, result_info):
        with self.lock:
            job_id = result_info['job_id']
            result_info['saved_at'] = time.time()
            self.results[job_id] = result_info
    
    def get_result(self, job_id):
        return self.results.get(job_id)
    
    def get_results_by_campaign(self, campaign_id):
        """Get all results for a campaign (for CSV generation)"""
        campaign_job_ids = [j['job_id'] for j in self.jobs.values() if j['campaign_id'] == campaign_id]
        return [self.results[job_id] for job_id in campaign_job_ids if job_id in self.results]
    
    # ========== Query Operations (like SQL queries) ==========
    
    def query_results_for_csv(self, campaign_id):
        """Mimic a SQL JOIN for CSV generation"""
        results = []
        
        for job_id, result in self.results.items():
            job = self.jobs.get(job_id)
            if job and job['campaign_id'] == campaign_id:
                worker = self.workers.get(job['worker_id'])
                
                # Combine data from multiple "tables"
                row = {
                    # From job
                    'job_id': job_id,
                    'compute_unit': job['compute_unit'],
                    'submitted_at': job['submitted_at'],
                    
                    # From worker
                    'device_name': worker.get('device_name', 'Unknown') if worker else 'Unknown',
                    'soc': worker.get('soc', '') if worker else '',
                    'ram_gb': worker.get('ram_gb', 0) if worker else 0,
                    'os': worker.get('os', '') if worker else '',
                    
                    # From result
                    'status': result['status'],
                    'load_ms_median': result.get('load_ms_median'),
                    'inference_ms_median': result.get('inference_ms_median'),
                    'peak_load_ram_mb': result.get('peak_load_ram_mb'),
                    'peak_inference_ram_mb': result.get('peak_inference_ram_mb'),
                    # ... all other metrics
                }
                results.append(row)
        
        return results

# ========== Usage in Orchestrator ==========

store = InMemoryStore('orchestrator_state.json')

# Worker registration endpoint
@app.route('/api/register', methods=['POST'])
def register_worker():
    worker_info = request.json
    worker_id = f"{worker_info['device_name']}-{uuid.uuid4()}"
    worker_info['worker_id'] = worker_id
    worker_info['ip_address'] = request.remote_addr
    
    store.register_worker(worker_info)
    
    # Also cache IP in Redis for fast lookup
    r.hset(f'worker:{worker_id}', 'ip_address', request.remote_addr)
    
    return jsonify({'worker_id': worker_id}), 200

# Campaign submission
def create_campaign(model_url, device_compute_matrix):
    campaign_id = f"campaign-{int(time.time())}"
    
    campaign_info = {
        'campaign_id': campaign_id,
        'model_url': model_url,
        'total_jobs': len(device_compute_matrix)
    }
    store.create_campaign(campaign_info)
    
    # Create jobs
    for device_id, compute_unit in device_compute_matrix:
        job_id = f"{campaign_id}-{device_id}-{compute_unit}"
        job_info = {
            'job_id': job_id,
            'campaign_id': campaign_id,
            'model_url': model_url,
            'compute_unit': compute_unit,
        }
        store.create_job(job_info)
        
        # Push to Redis queue
        r.lpush(f'jobs:{device_id}', job_id)
    
    return campaign_id

# Result processing
def process_result_from_redis():
    """Background thread consuming results from Redis"""
    while True:
        result_json = r.brpop('results', timeout=1)
        if result_json:
            result = json.loads(result_json[1])
            
            # Save result
            store.save_result(result)
            
            # Update job status
            store.update_job_status(result['job_id'], result['status'])
            
            # Update campaign progress
            campaign_id = result['campaign_id']
            store.update_campaign_progress(
                campaign_id,
                increment_completed=True if result['status'] == 'complete' else False,
                increment_failed=True if result['status'] == 'failed' else False
            )
            
            # Check if campaign is complete
            campaign = store.get_campaign(campaign_id)
            if campaign['completed_jobs'] + campaign['failed_jobs'] >= campaign['total_jobs']:
                generate_csv_report(campaign_id)

# CSV generation
def generate_csv_report(campaign_id):
    results = store.query_results_for_csv(campaign_id)
    
    df = pd.DataFrame(results)
    output_path = f'reports/{campaign_id}.csv'
    df.to_csv(output_path, index=False)
    
    store.update_campaign_progress(campaign_id, status='complete')
    print(f"✅ CSV report generated: {output_path}")