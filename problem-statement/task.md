You'll
be working on implementing a performance utility for ML models that will showcase performance, device utilisation 


The Challenge

We're providing you with some sample CVs across different formats, i.e. ONNX/coreML/pytorch-based, for which:

Make a central system that distributes them to multiple device targets
Perform relevant analysis 
Collect results from these targets and report them back.
The model inference engine frameworks, i.e., ONNX/CoreML versions, should be easily changeable for the consumer.

Your mission: The system must be scalable to support multiple targets and efficiently manage dependencies and error handling, keeping everything headless.


Evaluation:
Ability for the central system to delegate model jobs for speed benchmarking, RAM utilisation, and CPU utilisation to target devices.
Ability for the central system to communicate with a few devices, starting from the parent machine.
Ability for the central system to generate CSV-based reports for all the data points.




Deliverables
A GitHub repo with the implementation
A working demo with the ability for the central system to connect to foreign devices.
A brief write-up explaining your approach, challenges faced, and results

