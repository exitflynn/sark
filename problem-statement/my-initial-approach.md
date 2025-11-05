Secret Task RFC (of sorts)
Here’s how I plan to approach the task:

1. The Orchestration:

For the host device to assign and run jobs on the target devices, there should be a queue (instead of polling based mechanisms). 
I plan to use Redis queues for this (Celery was a good option but has limited support on Windows and I personally think something like RabbitMQ is comparatively overkill to setup/maintain for this scale).

For distributing models, we’ll send a raw URL from the orchestrator which the worker/agent can download on-device. The orchestrator publishes jobs on a `jobs` topic and the workers listen and pick the one that fits them and publish results on the `results` topic. (Stretch-goals: cancelling a running job, worker-side timeout implementation).

Any `job` published on the channel will have the following info with it
{
	‘job_id’ str, ‘model_url’ str, ‘device_udid’ str, ‘compute_unit’ str
}

And a `result` would have
{
	‘job_id’ str, ‘status’ str, ‘remark’ str, …<data_points>
}

The results would have a status field (for ’failed’ or ‘successful’), a remark field for optional (error or otherwise) messages and the data points (at higher scale we’d just upload to cloud storage from the devices and pass the url for the .csv file).

There should also be state management for each worker device between ‘active’, ‘busy’, ‘cleanup’, ‘faulty’ stages which will also involve communication via the redis queue, we can also have health checks here for the devices via heartbeats.
This information about states would be available at the orchestrator and the device allocation logic would be at the orchestrator only.

2. The Benchmarking:

There’ll be a pre-run stage where we can run generic preprocessing steps before running all models (like normalising inputs etc. if needed) and also a post-run stage where we perform cleanup after inference.

Would use psutil for RAM metrics, pynvml for GPU and time.perf_counter() for measuring time.

Number of runs for the aggregate data like the number of warmups: this number could be something unique to each hardware and we can dynamically generate during enrollment after looking when it starts to converge and then store it for the device for the future, for now I’ll start with 5.
