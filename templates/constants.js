/**
 * Frontend Constants - Shared with backend
 * These must match the Python constants for consistency
 */

// ========== Worker Status Constants ==========
const WORKER_STATUS_ACTIVE = 'active';
const WORKER_STATUS_BUSY = 'busy';
const WORKER_STATUS_CLEANUP = 'cleanup';
const WORKER_STATUS_FAULTY = 'faulty';

const WORKER_STATUSES = {
    ACTIVE: WORKER_STATUS_ACTIVE,
    BUSY: WORKER_STATUS_BUSY,
    CLEANUP: WORKER_STATUS_CLEANUP,
    FAULTY: WORKER_STATUS_FAULTY
};

// ========== Campaign Status Constants ==========
const CAMPAIGN_STATUS_RUNNING = 'running';
const CAMPAIGN_STATUS_COMPLETED = 'completed';
const CAMPAIGN_STATUS_PARTIAL = 'partial';

const CAMPAIGN_STATUSES = {
    RUNNING: CAMPAIGN_STATUS_RUNNING,
    COMPLETED: CAMPAIGN_STATUS_COMPLETED,
    PARTIAL: CAMPAIGN_STATUS_PARTIAL
};

// ========== Compute Unit Constants ==========
const COMPUTE_UNIT_CPU_ONNX = 'CPU (ONNX)';
const COMPUTE_UNIT_GPU_ONNX = 'GPU (ONNX)';
const COMPUTE_UNIT_GPU_COREML = 'GPU (CoreML)';
const COMPUTE_UNIT_NEURAL_ENGINE_COREML = 'Neural Engine (CoreML)';

const COMPUTE_UNITS = [
    COMPUTE_UNIT_CPU_ONNX,
    COMPUTE_UNIT_GPU_ONNX,
    COMPUTE_UNIT_GPU_COREML,
    COMPUTE_UNIT_NEURAL_ENGINE_COREML
];

// ========== Status Display ==========
function getWorkerStatusBadgeClass(status) {
    const normalizedStatus = status?.toLowerCase() || 'unknown';
    switch (normalizedStatus) {
        case WORKER_STATUS_ACTIVE:
            return 'status-healthy';
        case WORKER_STATUS_BUSY:
            return 'status-warning';
        case WORKER_STATUS_FAULTY:
        case WORKER_STATUS_CLEANUP:
            return 'status-error';
        default:
            return 'status-error';
    }
}

function getCampaignIsCompleted(status) {
    return [CAMPAIGN_STATUS_COMPLETED, CAMPAIGN_STATUS_PARTIAL].includes(status);
}
