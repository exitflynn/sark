# SARK - Distributed ML Model Benchmarking System

Orchestrates [Dumont](https://github.com/exitflynn/dumont) nodes to make for a distributed system for benchmarking on-device inference for ML models across multiple (Windows, MacOS and Linux-based) devices. Collects performance metrics (speed, RAM, CPU, GPU utilization) and generates comprehensive CSV reports. Built with a scale of around 30-50 devices in mind.

## Quick Start

### Prerequisites
- Python 3.11+
- Redis 6.x
- Docker (optional)

### Installation

```bash
# Orchestrator (sark)
pip install -r requirements.txt
python orchestrator.py

# Worker (dumont) - on separate device or terminal
pip install git+https://github.com/exitflynn/dumont.git
dumont start --host $ORCHESTRATOR_HOST
```

> **Note:** Replace `$ORCHESTRATOR_HOST` with the orchestrator's IP address or hostname, e.g., `http://192.168.1.100:5000`.

### First Campaign

```bash
# Create a campaign with ONNX model
curl -X POST $ORCHESTRATOR_HOST/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "model_url": "https://github.com/onnx/models/raw/refs/heads/main/validated/vision/object_detection_segmentation/tiny-yolov2/model/tinyyolov2-7.onnx",
    "jobs": [
      {
        "compute_unit": "CPU (ONNX)",
        "num_inference_runs": 10
      }
    ]
  }'
```

Wait for campaign to complete, then download CSV:
```bash
# List available results
curl $ORCHESTRATOR_HOST/api/results/files

# Download specific campaign results
curl $ORCHESTRATOR_HOST/api/campaigns/{campaign-id}/results > results.csv
```

<details>
<summary> Example Runs</summary>

### Create campaign with 3 different compute units
```
curl -X POST $ORCHESTRATOR_HOST/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "model_url": "https://github.com/onnx/models/raw/refs/heads/main/validated/vision/object_detection_segmentation/tiny-yolov2/model/tinyyolov2-7.onnx",
    "jobs": [
      { "compute_unit": "CPU (ONNX)", "num_inference_runs": 10 },
      { "compute_unit": "GPU (ONNX)", "num_inference_runs": 10 }
    ]
  }'
```

### Get campaign ID from response, then monitor progress
curl $ORCHESTRATOR_HOST/api/campaigns/campaign-xyz123

### Download results when complete
curl $ORCHESTRATOR_HOST/api/campaigns/campaign-xyz123/results > results.csv
```

</details>

### Multi-Device Distribution
```bash
# Register multiple workers (from different machines)
curl -X POST $ORCHESTRATOR_HOST/api/register -d '{...}'

# Create campaign with many jobs (auto-distributed)
curl -X POST $ORCHESTRATOR_HOST/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "model_url": "...",
    "jobs": [
      { "compute_unit": "CPU (ONNX)" },
      { "compute_unit": "CPU (ONNX)" },
      { "compute_unit": "GPU (CoreML)" },
      { "compute_unit": "GPU (CoreML)" }
    ]
  }'

# Jobs distributed across workers based on capabilities
```

### Test Model (ONNX)

Here's a small pre-trained model from the ONNX Model Zoo for quick validation:
```
https://github.com/onnx/models/raw/refs/heads/main/validated/vision/object_detection_segmentation/tiny-yolov2/model/tinyyolov2-7.onnx
```

---

## Supported Frameworks

- **ONNX Runtime** - CPU, GPU (CUDA), DirectML (Windows)
- **CoreML** - GPU (Metal), Neural Engine (Apple Silicon)
- Extensible architecture for adding PyTorch, OpenVINO etc.
