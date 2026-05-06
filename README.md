# Isaac_Elizarraraz
Overview: Multiprocessing and Shared Memory Integration
The integrated_v5.py system is designed as a high-performance, real-time control architecture for an autonomous vehicle, leveraging Python’s multiprocessing library to bypass the Global Interpreter Lock (GIL). The system operates on a producer-consumer model where four independent background processes (Camera, LIDAR, Lane Detection, and YOLO) continuously update high-speed shared memory buffers and thread-safe multiprocessing.Value objects. This structure ensures that the main control loop always has immediate access to the most recent sensor telemetry without being blocked by computationally expensive tasks like image processing or serial I/O. The core navigation logic uses a vector blending approach, combining repulsion vectors from the LIDAR with steering errors from the lane tracker to calculate a final motor command.

The Background Processes

Camera Capture Worker
The camera worker is responsible for managing the physical hardware interfaces for the dual-camera setup (Left and Right). It utilizes V4L2 backends to pull frames at a tuned resolution of 480x270 at 30 FPS to minimize latency. These frames are written directly into a high-speed shared_memory block, allowing other processes to access the raw BGR pixel data simultaneously without the overhead of copying large arrays between processes.


LIDAR Obstacle Worker
This process maintains a dedicated serial connection to the RPLidar sensor. It continuously parses raw point clouds and groups them into specific spatial sectors: Front-Left (FL), Front (F), and Front-Right (FR). The worker calculates the minimum distance to obstacles in each sector and updates shared Value objects, providing the vehicle with a constant "spatial map" of its immediate surroundings.


Lane Detection & PD Control Worker
The lane worker performs the primary vision pipeline by pulling frames from the shared camera memory. It applies a specialized white mask using HSV, LAB, and YCrCb color spaces to isolate lane markers, then uses a SimpleLineTracker to calculate steering error via a Proportional-Derivative (PD) controller. It is capable of dual-camera tracking for centering or single-camera fallback for handling sharp curves, eventually writing a normalized lane_turn value to shared memory.


YOLO Object Detection Worker
Running the YOLOv8 model, this process identifies critical environmental features such as stop signs and pedestrians. It utilizes pinhole camera geometry to estimate the distance to these objects based on their bounding box height. When an object is detected within a specific threshold (e.g., a stop sign within 5 meters), it triggers a latched "event" in the shared memory to signal the main controller to halt the vehicle.


System Initialization and Setup
Startup is managed through a modular helper called initialize_system, which enforces a SerialPortLock to ensure no other scripts interfere with the TM4C microcontroller. The system sets the spawn multiprocessing method to ensure clean memory allocation on the Jetson platform. Before the vehicle begins moving, the run_integrated function enters a stabilization phase, where it waits up to 10 seconds for the LIDAR and YOLO processes to report valid, non-infinite data, ensuring all sensors are online and calibrated.


Real-Time Vision Telemetry (MJPEG HTTP Server)
To safely monitor the computer vision pipeline without interrupting the vehicle's high-speed control loop, the system implements a lightweight MJPEG HTTP Server. Traditional display methods like OpenCV's cv2.imshow can cause severe blocking issues in multiprocessing environments, so this script handles video streaming entirely in the background. As the Lane Detection worker processes frames, it generates a composite debug image, overlaying lane masks, bounding boxes, and steering calculations. Then it compresses it into a raw JPEG, and pushes it into a MjpegPreviewState object protected by a Manager.Lock(). Meanwhile, a dedicated server thread in the main process constantly reads this locked state and broadcasts the frames as a continuous multipart/x-mixed-replace web stream. This setup allows you to simply open a web browser to localhost:8765 and watch a live, low-latency feed of exactly what the robot "sees" and how it makes its steering decisions, all without slowing down the actual driving logic.

System Teardown and Shutdown
The shutdown protocol is designed to fail-safe the hardware. Upon receiving a termination signal (like Ctrl+C), the system immediately dispatches a forced STOP command to the motors. The main process then terminates all background workers and joins them to prevent "zombie" processes. Crucially, the system unlinks the shared memory blocks and releases the exclusive serial lock. Finally, a kill_port utility is used to clear the MJPEG preview server port, ensuring the system can be restarted immediately without "address already in use" errors.

