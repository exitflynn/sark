"""
Centralized constants for the Orchestrator (SARK).
Ensures consistency across backend, frontend, and worker communication.
"""

# ========== Worker Status Constants ==========
WORKER_STATUS_ACTIVE = 'active'
WORKER_STATUS_BUSY = 'busy'
WORKER_STATUS_CLEANUP = 'cleanup'
WORKER_STATUS_FAULTY = 'faulty'

WORKER_STATUS_VALUES = [
    WORKER_STATUS_ACTIVE,
    WORKER_STATUS_BUSY,
    WORKER_STATUS_CLEANUP,
    WORKER_STATUS_FAULTY
]

# ========== Job Status Constants ==========
JOB_STATUS_PENDING = 'pending'
JOB_STATUS_RUNNING = 'running'
JOB_STATUS_COMPLETE = 'Complete'
JOB_STATUS_FAILED = 'Failed'
JOB_STATUS_CANCELLED = 'cancelled'

JOB_STATUS_VALUES = [
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETE,
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCELLED
]

# ========== Campaign Status Constants ==========
CAMPAIGN_STATUS_RUNNING = 'running'
CAMPAIGN_STATUS_COMPLETED = 'completed'
CAMPAIGN_STATUS_PARTIAL = 'partial'
CAMPAIGN_STATUS_FAILED = 'failed'

CAMPAIGN_STATUS_VALUES = [
    CAMPAIGN_STATUS_RUNNING,
    CAMPAIGN_STATUS_COMPLETED,
    CAMPAIGN_STATUS_PARTIAL,
    CAMPAIGN_STATUS_FAILED
]

# ========== Compute Unit Constants ==========
COMPUTE_UNIT_CPU_ONNX = 'CPU (ONNX)'
COMPUTE_UNIT_GPU_ONNX = 'GPU (ONNX)'
COMPUTE_UNIT_DIRECTML_ONNX = 'DirectML (ONNX)'
COMPUTE_UNIT_OPENVINO_ONNX = 'OpenVINO (ONNX)'
COMPUTE_UNIT_GPU_COREML = 'GPU (CoreML)'
COMPUTE_UNIT_NEURAL_ENGINE_COREML = 'Neural Engine (CoreML)'

COMPUTE_UNIT_VALUES = [
    COMPUTE_UNIT_CPU_ONNX,
    COMPUTE_UNIT_GPU_ONNX,
    COMPUTE_UNIT_DIRECTML_ONNX,
    COMPUTE_UNIT_OPENVINO_ONNX,
    COMPUTE_UNIT_GPU_COREML,
    COMPUTE_UNIT_NEURAL_ENGINE_COREML
]

# Restricted compute units (only these are allowed)
ALLOWED_COMPUTE_UNITS = [
    COMPUTE_UNIT_CPU_ONNX,
    COMPUTE_UNIT_GPU_ONNX,
    COMPUTE_UNIT_GPU_COREML,
    COMPUTE_UNIT_NEURAL_ENGINE_COREML
]

# ========== Queue Name Constants ==========
QUEUE_PREFIX_JOBS = 'jobs:capability'
QUEUE_PREFIX_RESULTS = 'results:queue'
QUEUE_PREFIX_HEARTBEAT = 'heartbeat'

# ========== Result Status Constants ==========
RESULT_STATUS_COMPLETE = 'Complete'
RESULT_STATUS_FAILED = 'Failed'

# ========== Heartbeat Constants ==========
HEARTBEAT_INTERVAL = 10  # seconds
HEARTBEAT_TIMEOUT = 60  # seconds
HEARTBEAT_WARNING_THRESHOLD = 45  # seconds

# ========== Timeout Constants ==========
DEFAULT_JOB_TIMEOUT = 3600  # seconds (1 hour)
TIMEOUT_CHECK_INTERVAL = 5  # seconds

# ========== Retry Constants ==========
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 300.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0
