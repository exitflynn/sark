## API Documentation

### Base URL
```
http://localhost:5000/api
```

<details>
<summary> Health & System</summary>

#### Health Check
```
GET /health
```
Check orchestrator and Redis connection status.

**Response**: `{ "status": "healthy", "timestamp": "...", "redis": {...} }`

#### Reset All Data
```
POST /reset
```
Clear all workers, campaigns, jobs, and results.

**Response**: `{ "status": "reset", "message": "...", "workers_cleared": true, ... }`

</details>

<details>
<summary> Workers</summary>

#### Register Worker
```
POST /register
```
Register or reconnect a worker device.

**Request**:
```json
{
  "device_name": "MacBook Pro",
  "ip_address": "192.168.1.100",
  "capabilities": ["CPU (ONNX)", "GPU (CoreML)"],
  "device_info": {
    "Soc": "Apple M2 Pro",
    "Ram": "16",
    "DeviceOs": "Darwin",
    "UDID": "unique-device-id"
  }
}
```

**Response**: `{ "worker_id": "worker-abc123", "status": "registered", "action": "created" }`

#### List All Workers
```
GET /workers
```
Get all registered workers with their status and capabilities.

**Response**: `{ "count": 2, "workers": [...] }`

#### Get Worker Details
```
GET /workers/{worker_id}
```
Get detailed info for a specific worker.

**Response**: Worker object with device info, capabilities, status

#### Update Worker Status
```
PUT /workers/{worker_id}/status
```
Update worker status (active/busy/cleanup/faulty).

**Request**: `{ "status": "active" }`

**Response**: `{ "worker_id": "...", "status": "active" }`

#### Worker Heartbeat
```
POST /workers/{worker_id}/heartbeat
```
Record periodic heartbeat (prevents marking as faulty). Called by worker during job execution.

**Response**: `{ "worker_id": "...", "status": "active", "action": "updated" }`

#### Get Worker Health
```
GET /workers/{worker_id}/health
```
Get health status and last heartbeat time.

**Response**: `{ "worker_id": "...", "is_healthy": true, "last_heartbeat": "...", "seconds_since_heartbeat": 5 }`

#### Get All Workers Health
```
GET /health/workers
```
Get health status for all workers.

**Response**: `{ "total": 2, "healthy": 2, "unhealthy": 0, "workers": [...] }`

#### Reset Faulty Worker
```
PUT /workers/{worker_id}/reset
```
Manually recover a faulty worker back to active state.

**Response**: `{ "worker_id": "...", "status": "active", "message": "..." }`

</details>

<details>
<summary> Campaigns</summary>

#### Create Campaign
```
POST /campaigns
```
Create new benchmarking campaign with model and jobs.

**Request**:
```json
{
  "model_url": "https://github.com/onnx/models/raw/refs/heads/main/validated/vision/object_detection_segmentation/tiny-yolov2/model/tinyyolov2-7.onnx",
  "jobs": [
    {
      "compute_unit": "CPU (ONNX)",
      "num_inference_runs": 10
    },
    {
      "compute_unit": "GPU (CoreML)",
      "num_inference_runs": 10
    }
  ]
}
```

**Supported Compute Units**:
- `CPU (ONNX)` - CPU inference via ONNX Runtime
- `GPU (ONNX)` - GPU inference via ONNX Runtime (CUDA/ROCm)
- `GPU (CoreML)` - GPU inference via CoreML (Metal)
- `Neural Engine (CoreML)` - Apple Neural Engine

**Response**:
```json
{
  "campaign_id": "campaign-1234567890",
  "total_jobs": 2,
  "status": "running",
  "jobs": [
    { "job_id": "campaign-1234567890-job-0", "compute_unit": "CPU (ONNX)", "status": "pending" },
    { "job_id": "campaign-1234567890-job-1", "compute_unit": "GPU (CoreML)", "status": "pending" }
  ]
}
```

#### List All Campaigns
```
GET /campaigns
```
Get all campaigns with status and job breakdown.

**Response**: `{ "count": 3, "campaigns": [...] }`

#### Get Campaign Details
```
GET /campaigns/{campaign_id}
```
Get status and job breakdown for specific campaign.

**Response**:
```json
{
  "campaign_id": "campaign-1234567890",
  "model_url": "https://...",
  "status": "completed",
  "total_jobs": 2,
  "completed_jobs": 2,
  "job_breakdown": {
    "pending": 0,
    "running": 0,
    "complete": 2,
    "failed": 0
  }
}
```

#### Get Campaign Results (CSV)
```
GET /campaigns/{campaign_id}/results
```
Download benchmark results as CSV file.

**Response**: CSV file with columns:
- Status, JobId, FileName, FileSize, ComputeUnits
- DeviceName, Soc, Ram, DeviceOs
- LoadMsMedian, LoadMsAverage, LoadMsStdDev, PeakLoadRamUsage
- InferenceMsMedian, InferenceMsAverage, InferenceMsStdDev, PeakInferenceRamUsage

</details>

<details>
<summary> Jobs</summary>

#### Get Job Details
```
GET /jobs/{job_id}
```
Get job and associated result details.

**Response**:
```json
{
  "job": {
    "job_id": "campaign-1234567890-job-0",
    "campaign_id": "campaign-1234567890",
    "compute_unit": "CPU (ONNX)",
    "status": "complete"
  },
  "result": {
    "status": "Complete",
    "LoadMsMedian": 45.23,
    "InferenceMsMedian": 12.50,
    "PeakInferenceRamUsage": 256.5
  }
}
```

</details>

<details>
<summary> Queue Management</summary>

#### Get Queue Status
```
GET /queue/status
```
Get current job queue sizes and processing status.

**Response**:
```json
{
  "worker_queues": {
    "worker-abc123": { "device_name": "MacBook", "queue_size": 3 }
  },
  "capability_queues": {
    "CPU (ONNX)": 5,
    "GPU (CoreML)": 2
  },
  "results_queue_size": 1
}
```

</details>

<details>
<summary> Results Files</summary>

#### List Result Files
```
GET /results/files
```
List all generated CSV result files in outputs folder.

**Response**:
```json
{
  "count": 2,
  "files": [
    {
      "filename": "campaign-1234567890_20250109_143022_results.csv",
      "size_mb": 0.05,
      "modified": "2025-01-09T14:30:22"
    }
  ]
}
```

#### Download Result File
```
GET /results/download/{filename}
```
Download a specific CSV result file.

**Response**: CSV file

</details>

<details>
<summary> Monitoring</summary>

#### Get Monitoring Stats
```
GET /monitoring/stats
```
Get monitoring system statistics and health check info.

**Response**: Health monitor and timeout handler statistics

</details>

---

## CSV Output Format

Each campaign generates a CSV file with benchmark results:

| Column | Description |
|--------|-------------|
| Status | Complete, Failed, Cancelled |
| JobId | Unique job identifier |
| FileName | Model filename |
| ComputeUnits | Compute unit used (CPU (ONNX), etc.) |
| DeviceName | Device/worker name |
| Soc | CPU/SOC model |
| Ram | RAM in GB |
| LoadMsMedian | Model load time (median, ms) |
| LoadMsAverage | Model load time (average, ms) |
| LoadMsStdDev | Model load time (std dev, ms) |
| PeakLoadRamUsage | Peak RAM during load (MB) |
| InferenceMsMedian | Inference time (median, ms) |
| InferenceMsAverage | Inference time (average, ms) |
| InferenceMsStdDev | Inference time (std dev, ms) |
| PeakInferenceRamUsage | Peak RAM during inference (MB) |

---