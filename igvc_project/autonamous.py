"""
Autonomous Vehicle Integration System
=====================================

This module serves as the primary entry point for the self-driving ground vehicle.
It utilizes Python's `multiprocessing` library to run parallel workers for:
- Camera capture and lane tracking (OpenCV)
- Object detection (Ultralytics YOLOv8)
- Obstacle avoidance (RPLidar)
- Motor control and telemetry (Serial to TM4C)

The workers communicate via shared memory and thread-safe multiprocessing Values.
"""

import time
import math
import numpy as np
import cv2
import os
import atexit
import signal
from ultralytics import YOLO
from multiprocessing import Process, Manager
from multiprocessing import Value, Array
from multiprocessing import shared_memory
import subprocess
import multiprocessing as mp

# Import everything related to the TM4C and Serial connections
from motor_commander import (
    SerialPortLock, 
    MotorCommander, 
    open_serial, 
    cleanup_system,
    STOP_CMD, 
    CMD_AUTO,
    SERIAL_LOCK_PATH,
    PORT,
    choose_cmd_with_hysteresis
)

# Import everything related to the Lane Tracking Math
from camera import (
    SimpleLineTracker, 
    process_frame, 
    open_camera_by_index, 
    tune_camera_for_speed,
    start_mjpeg_server
)

# Import everything related to Lidar and YOLO
from lidar import (
    LidarState, 
    open_lidar, 
    iter_scans_standard, 
    detect_objects, 
    measure_distance,
    RPLidarException,
    fmt_mm
)

from preview_server import (
    kill_port
)
LIDAR_PORT   = "/dev/ttyUSB0"
LIDAR_BAUD   = 1_000_000
LIDAR_TO     = 1.0

def initialize_system():
    # [SAteefa 3/21 Added: modular startup helper so all debug phases share the same safe initialization]
    serial_lock = SerialPortLock(SERIAL_LOCK_PATH)
    serial_lock.acquire()
    atexit.register(serial_lock.release)

    ser = open_serial()
    mc = MotorCommander(ser)

    # [SAteefa 3/21 Added: startup banner to show which script and hardware ports are active]
    print("=" * 60)
    print("[BOOT] camera_part3.py starting")
    print(f"[BOOT] DEBUG_MODE : FULL")
    print(f"[BOOT] TM4C port  : {PORT}")
    print(f"[BOOT] LIDAR port : {LIDAR_PORT}")
    print(f"[BOOT] Active side starts on: LEFT")
    print("=" * 60)

    mc.send(STOP_CMD, force=True)
    time.sleep(0.2)
    mc.send(CMD_AUTO, force=True)

    return serial_lock, ser, mc

def cleanup_system(mc=None, ser=None, serial_lock=None):
    try:
        if mc is not None:
            mc.send(STOP_CMD, force=True) #stop the robot before shutting anything down
    except Exception:
        pass


    try:
        if ser is not None:
            ser.close() #close the TM4c serial connection
    except Exception:
        pass

    try:
        if serial_lock is not None:
            serial_lock.release() # [SAteefa 3/21 Added: release the serial-port ownership lock so another script can use TM4C later]
    except Exception:
        pass
 

    print("[INFO] Clean exit.") #confirmation that shutdown completed


# =========================
# Multiprocessing Workers
# =========================

def camera_worker(shared, shm_name_L, shm_name_R):
    """
    Background process that continuously captures frames from two USB cameras 
    and writes them into high-speed shared memory for the lane and YOLO workers.

    This function initializes the physical camera hardware via V4L2, tunes the 
    capture resolution and framerate to prevent bottlenecking, and maintains 
    a tight loop to pull the latest frames.

    Args:
        shared (dict): Shared multiprocessing variables dictionary.
        shm_name_L (str): The shared memory reference name for the left camera buffer.
        shm_name_R (str): The shared memory reference name for the right camera buffer.
    """
    cap_L = open_camera_by_index("LEFT")
    cap_R = open_camera_by_index("RIGHT")
    time.sleep(1)
    if cap_L is None or cap_R is None: 
        print("[CAM] failed to start")
        return
    tune_camera_for_speed(cap_L, "LEFT")
    tune_camera_for_speed(cap_R, "RIGHT")
    shm_L = shared_memory.SharedMemory(name=shm_name_L)
    shm_R = shared_memory.SharedMemory(name=shm_name_R)
    
    buf_L = np.ndarray((270, 480, 3), dtype=np.uint8, buffer=shm_L.buf)
    buf_R = np.ndarray((270, 480, 3), dtype=np.uint8, buffer=shm_R.buf)
    
    print("[CAMERA PROCESS] started")

    while True:
            
        retL, imgL = cap_L.read()
        retR, imgR = cap_R.read()

        if retL:
            buf_L[:] = cv2.resize(imgL, (480, 270), interpolation=cv2.INTER_NEAREST)
        if retR:
            buf_R[:] = cv2.resize(imgR, (480, 270), interpolation=cv2.INTER_NEAREST)
        time.sleep(0.01)
        
def lane_worker(shared, shm_name_L, shm_name_R, preview_bundle):
    """
    Background process responsible for executing the computer vision pipeline 
    and Proportional-Derivative (PD) steering control.

    Reads high-speed camera frames from shared memory, applies region-of-interest (ROI) 
    masking to prevent field-of-view cross-talk, and calculates the required steering 
    angle to keep the vehicle centered. Features a dual-camera primary mode and a 
    robust single-camera fallback mode to navigate sharp curves. 

    Args:
        shared (dict): Shared multiprocessing dictionary to output the calculated 
                       steering commands ('lane_turn', 'lane_visible_L', 'lane_visible_R').
        shm_name_L (str): Shared memory reference name for the left camera buffer.
        shm_name_R (str): Shared memory reference name for the right camera buffer.
        preview_bundle (tuple): A tuple containing (preview_state, preview_lock) used 
                                to safely push debug JPG frames to the MJPEG HTTP server.
    """
    CENTER_DEADBAND = 0.1
    DUAL_KP = 1.0 #0.6 #0.9 
    DUAL_KD = 0.4
    TARGET_X_RATIO_LEFT = 0.35 # old 0.43
    TARGET_X_RATIO_RIGHT = 0.65 # old 0.65
    # The Left camera is not allowed to look past 60% of the screen (Right edge blocked)
    ROI_LEFT_CAM = dict(
        bottom_left  = (0.00, 0.95),
        top_left     = (0.00, 0.35),
        top_right    = (0.60, 0.35), 
        bottom_right = (0.60, 0.95),
    )

    # The Right camera is not allowed to look past 40% of the screen (Left edge blocked)
    ROI_RIGHT_CAM = dict(
        bottom_left  = (0.40, 0.95), 
        top_left     = (0.40, 0.35),
        top_right    = (1.00, 0.35),
        bottom_right = (1.00, 0.95),
    )

    preview_state, preview_lock = preview_bundle
    shm_L = shared_memory.SharedMemory(name=shm_name_L)
    shm_R = shared_memory.SharedMemory(name=shm_name_R)

    frame_L = np.ndarray((270, 480, 3), dtype=np.uint8, buffer=shm_L.buf)
    frame_R = np.ndarray((270, 480, 3), dtype=np.uint8, buffer=shm_R.buf)

    tracker_L = SimpleLineTracker(480, TARGET_X_RATIO_LEFT)
    tracker_R = SimpleLineTracker(480, TARGET_X_RATIO_RIGHT)

    prev_e  = 0.0
   
    print("[LANE PROCESS] started")
    while True:
        img_L = frame_L.copy()
        img_R = frame_R.copy()

        try:
            out_L, mask_L, _, _, _, line_x_L, _ = process_frame(img_L, tracker_L, ROI_LEFT_CAM)
            out_R, mask_R, _, _, _, line_x_R, _ = process_frame(img_R, tracker_R, ROI_RIGHT_CAM)
            nL = line_x_L / 480.0 if line_x_L is not None else None
            nR = line_x_R / 480.0 if line_x_R is not None else None

            # ------------------------------------------------
            # BOTH cameras: standard dual PD control
            # ------------------------------------------------
            if nL is not None and nR is not None:

                current_center = (nL + nR) / 2.0
                
                # FIX: Swapped so steering matches the error polarity!
                error = current_center - 0.5 
                
                de    = error - prev_e
                prev_e = error

                turn_val = DUAL_KP * error + DUAL_KD * de

                turn_val  = float(np.clip(turn_val, -1.0, 1.0))

                if abs(error) < CENTER_DEADBAND:
                    turn_val = 0.0
                shared["lane_turn"].value      = turn_val 
                shared["lane_visible_L"].value = True
                shared["lane_visible_R"].value = True

            # ------------------------------------------------
            # ONE camera: direct error → turn, no hold/blend
            # ------------------------------------------------
            elif nL is not None or nR is not None:

                if nL is not None:
                    err   = nL - TARGET_X_RATIO_LEFT
                    
                    # FIX: Removed the negative sign
                    turn_val = float(np.clip(err * DUAL_KP, -0.8, 0.8)) 
                    if abs(err) < CENTER_DEADBAND:
                        turn_val = 0.0
                    shared["lane_turn"].value = turn_val
                    shared["lane_visible_L"].value = True
                    shared["lane_visible_R"].value = False

                else:
                    err   = nR - TARGET_X_RATIO_RIGHT
                    
                    # FIX: Removed the negative sign
                    turn_val = float(np.clip(err * DUAL_KP, -0.8, 0.8)) 
                    if abs(err) < CENTER_DEADBAND:
                        turn_val = 0.0
                    shared["lane_turn"].value = turn_val
                    shared["lane_visible_L"].value = False
                    shared["lane_visible_R"].value = True

            # Debug overlay
            debug_view = np.hstack((out_L, out_R, mask_L, mask_R))
            cv2.putText(debug_view, f"Turn: {shared['lane_turn'].value:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cam_status = f"L:{'OK' if nL is not None else '--'}  R:{'OK' if nR is not None else '--'}"
            cv2.putText(debug_view, cam_status, (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

            ok, jpg = cv2.imencode(".jpg", debug_view, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with preview_lock:
                    preview_state.jpeg_bytes = jpg.tobytes()

        except Exception as e:
            print("[LANE ERROR]", e)

        time.sleep(0.03)
#Isaac Elizarraraz [3/31/2026]
#thread worker that finds objects in current frame
def yolo_worker(shared,shm_name):
    """
    Background process that continuously reads shared memory frames and runs 
    the YOLOv8 object detection model to trigger stop or pedestrian events.

    Args:
        shared (dict): Shared multiprocessing variables dictionary.
        shm_name (str): The shared memory reference name for the camera frame.
    """

    detector = YOLO("./yolov8n.pt")
    detector.to("cpu") # ideally this should be gpu!!
    shm = shared_memory.SharedMemory(name=shm_name)
    frame = np.ndarray((270,480,3), dtype=np.uint8, buffer=shm.buf)
    
    #constants
    real_height = 0.3048
    focal_length = 650
    
    #stop event variables
    stop_detected = False
    stop_latched = False
    stop_frame_counter = 0
    
    #pedestrian event variables
    person_detected = False
    person_latch = False
    person_frame_counter = 0

    
    print("[YOLO PROCESS] started")
    while True:
        stop_detected = False
        person_detected = False
        img = frame.copy()  # optional safety
        #cv2.imwrite("lane_worker.jpg", img)

        if img is None:
            time.sleep(0.02)
            continue

        try:

            detections = detect_objects(img, detector)
            min_stop_distance = float("inf") #keep track of how far away the stop sign is. car stops 2 meters away
            min_person_distance = float("inf")
            
            if detections:
                shared["det_time"].value = time.time()

            for d in detections:  
                distance = measure_distance(
                            d["bbox"],
                            focal_length,
                            real_height
                        )
                if d["label"] == "stop sign":
                    stop_detected = True
                    stop_frame_counter += 1
                    min_stop_distance = min(min_stop_distance,distance)
                    
                elif d["label"] == "person":
                    person_detected = True
                    person_frame_counter += 1
                    min_person_distance = min(min_person_distance,distance)
                    
            #stop event logic
            if not stop_detected:
                stop_frame_counter = 0
                
            if stop_frame_counter >= 3 and min_stop_distance <= 5:
                if not stop_latched:
                    shared["stop_event"].value = True
                    stop_latched = True
            else:
                shared["stop_event"].value = False
                if stop_frame_counter == 0:
                    stop_latched = False
                    
            #pedestrian event logic
            if not person_detected:
                person_frame_counter = 0
                
            if person_frame_counter >= 2 and min_person_distance <= 4:
                if not person_latch:
                    shared["pedestrian_event"].value = True
                    person_latch = True
            else:
                shared["pedestrian_event"].value = False
                if person_frame_counter == 0:
                    person_latch = False
                    
            time.sleep(0.02)
            
        except Exception as e:
            print("[YOLO ERROR]", e)
            
def lidar_worker(shared):
    """
    Background process that maintains a continuous serial connection to the RPLidar.

    This worker reads raw point cloud data from the spinning lidar, groups the 
    points into distinct front-facing sectors (Left, Center, Right), and updates 
    the shared memory dictionary. It includes robust error handling to automatically 
    power-cycle and reconnect to the lidar if the data stream drops.

    Args:
        shared (dict): Shared multiprocessing dictionary where the processed 
                       distance values ('dL', 'dC', 'dR', 'dFL', 'dF', 'dFR') are stored.
    """
    FRONT_DEG    = 0
    ANGLE_SIGN_D = -1    # -1 if your LIDAR mount is mirrored
    NO_DATA_STOP_SEC   = 0.5   # stop if no valid LIDAR data for this time

    lidar = open_lidar(LIDAR_PORT, LIDAR_BAUD, LIDAR_TO)
    scans = iter_scans_standard(lidar)
    lidar_state = LidarState(ANGLE_SIGN_D, FRONT_DEG, NO_DATA_STOP_SEC)
    print("[LIDAR PROCESS] started")
    
    bad_streak = 0
    BAD_LIMIT = 5
    GRACE_LIMIT = 10
    grace_frames = GRACE_LIMIT

    while True:

        try:
            scan = next(scans)
            bad_streak = 0

        except (StopIteration, RPLidarException, OSError) as e:

            if grace_frames > 0:
                grace_frames -= 1
                continue

            bad_streak += 1

            if bad_streak >= BAD_LIMIT:

                print(f"[WARN] lidar scan error -> reconnect")

                bad_streak = 0

                try:
                    lidar.stop()
                    lidar.stop_motor()
                    lidar.disconnect()
                except Exception:
                    pass

                time.sleep(0.25)

                lidar = open_lidar(LIDAR_PORT, LIDAR_BAUD, LIDAR_TO)
                scans = iter_scans_standard(lidar)

                grace_frames = GRACE_LIMIT

            continue
        
        lidar_state.update_from_scan(scan)

        shared["dL"].value = lidar_state.dL
        shared["dC"].value = lidar_state.dC
        shared["dR"].value = lidar_state.dR

        shared["dFL"].value = lidar_state.dFL
        shared["dF"].value  = lidar_state.dF
        shared["dFR"].value = lidar_state.dFR
        
        

def run_full_integrated(mc, shared):
    """
    The main control loop of the robot. 
    Reads telemetry from the Lidar, Camera, and YOLO workers, performs 
    Vector Blending for obstacle avoidance, and dispatches serial commands to the TM4C.

    Args:
        mc (MotorCommander): The initialized MotorCommander object.
        shared (dict): Shared multiprocessing variables dictionary.
    """

    last_completed_stop = time.time()
    stop_state_end_time = 0
    steer_state = "STRAIGHT"  # Hysteresis state: "STRAIGHT", "LEFT", or "RIGHT"

    # Tuned constants (moved here so they're easy to adjust)
    AVOID_ZONE   = 1200.0  # mm — was 800, reduced to avoid fighting the lane controller
    MAX_REPULSION = 0.8   # was 0.8

    try:
        while True:

            now = time.time()

            # =========================
            # Read shared sensor data
            # =========================
            dL  = shared["dL"].value
            dC  = shared["dC"].value
            dR  = shared["dR"].value
            dFL = shared["dFL"].value
            dF  = shared["dF"].value
            dFR = shared["dFR"].value


            print(
                f"L={fmt_mm(dL)}  C={fmt_mm(dC)}  R={fmt_mm(dR)}"
                f"  |  FL={fmt_mm(dFL)}  F={fmt_mm(dF)}  FR={fmt_mm(dFR)}",
                end="  "
            )

            # =========================
            # Stop sign logic
            # =========================
            stop_event = shared["stop_event"].value

            if now < stop_state_end_time:
                mc.send(STOP_CMD)
                time.sleep(0.05)
                continue

            if stop_state_end_time != 0 and now >= stop_state_end_time:
                last_completed_stop = now
                stop_state_end_time = 0
                print("[STOP] Completed stop")

            if stop_event and (now - last_completed_stop > 10):
                print("[STOP] Triggered")
                stop_state_end_time = now + 8
                shared["stop_event"].value = False
                mc.send(STOP_CMD, force=True)
                time.sleep(0.05)
                continue

            # =========================
            # 1. Lane turn value from camera
            # =========================
            lane_turn = shared["lane_turn"].value

            # =========================
            # 2. LIDAR obstacle repulsion
            # =========================
            left_dist  = min(dL, dFL)
            right_dist = min(dR, dFR)
            center_dist = min(dC, dF)

            obs_turn = 0.0

            if left_dist < AVOID_ZONE:
                push = (AVOID_ZONE - left_dist) / AVOID_ZONE
                obs_turn += push * MAX_REPULSION   # obstacle left → push right

            if right_dist < AVOID_ZONE:
                push = (AVOID_ZONE - right_dist) / AVOID_ZONE
                obs_turn -= push * MAX_REPULSION   # obstacle right → push left

            if center_dist < AVOID_ZONE:
                push = (AVOID_ZONE - center_dist) / AVOID_ZONE
                if left_dist > right_dist:
                    obs_turn -= push * MAX_REPULSION  # more room on left → swerve left
                else:
                    obs_turn += push * MAX_REPULSION  # more room on right → swerve right

            # =========================
            # 3. Blend lane + obstacle
            # =========================
            final_turn = float(np.clip(lane_turn + obs_turn, -1.0, 1.0))

            # =========================
            # 4. Translate float → discrete TM4C command via hysteresis
            # =========================
            cmd, steer_state = choose_cmd_with_hysteresis(final_turn, steer_state)

            mc.send(cmd)

            # =========================
            # Telemetry
            # =========================
            print(
                f"Lane: {lane_turn:+.2f} | Obs: {obs_turn:+.2f} | "
                f"Final: {final_turn:+.2f} | Steer: {steer_state} | CMD: {cmd}"
            )

            time.sleep(0.05)   # 20 Hz — was 0.005 (200 Hz), which caused command spam

    finally:
        mc.send(STOP_CMD, force=True)
        
def kill_leftover_processes():
    # This command finds any other Python scripts running this file and kills them
    current_pid = os.getpid()
    cmd = "pgrep -f integrated_v4.py"
    try:
        pids = subprocess.check_output(cmd, shell=True).decode().split()
        for pid in pids:
            if int(pid) != current_pid:
                print(f"[BOOT] Killing ghost process: {pid}")
                os.kill(int(pid), signal.SIGKILL)
    except subprocess.CalledProcessError:
        pass # No other processes found

# =========================
# Main entry point
# =========================

#Isaac Elizarraz [3/30/2026]
#added pretrained yolov8 model to detect stop signs

def run_integrated():
    
    serial_lock = None
    ser = None
    mc = None

    frame_shape = (270,480,3)
    frame_size = np.prod(frame_shape)

    shared = {}
    shm = shared_memory.SharedMemory(create=True, size=frame_size) #shared frame memory
    shm_L = shared_memory.SharedMemory(create=True, size=frame_size, name="shm_left")
    shm_R = shared_memory.SharedMemory(create=True, size=frame_size, name="shm_right")
    
    # LIDAR
    shared["dL"] = Value('d', float('inf'))
    shared["dC"] = Value('d', float('inf'))
    shared["dR"] = Value('d', float('inf'))

    shared["dFL"] = Value('d', float('inf'))
    shared["dF"]  = Value('d', float('inf'))
    shared["dFR"] = Value('d', float('inf'))
    
    # camera
    shared["active_camera"] = Value('i', 0) # 0 = LEFT, 1 = RIGHT
    shared["lane_turn"] = Value('d', 0.0)
    shared["lane_visible_L"] = Value('b', False)
    shared["lane_visible_R"] = Value('b', False)
    shared["line_x_L"] = Value('d', 0.0)
    shared["line_x_R"] = Value('d', 0.0)
    
    # YOLO detection
    shared["stop_detected"] = Value('b', False)
    shared["stop_event"] = Value('b', False)
    shared["pedestrian_event"] = Value('b', False)
    shared["det_time"] = Value('d', 0.0)
    
    manager = Manager()
    
    # 2. Initialize the preview state with a Manager Lock
    # This proxy object CAN be pickled and passed to processes
    preview_lock = manager.Lock()
    preview_state = manager.Namespace()
    preview_state.jpeg_bytes = None
    
    preview_lock = manager.Lock()
    
    # 3. Start the HTTP server (still runs in the main process thread)
    start_mjpeg_server((preview_state, preview_lock), host="0.0.0.0", port=8765)

    camera_proc = Process(
        target=camera_worker,
        args=(shared,shm_L.name, shm_R.name),
        daemon=True
    )
    
    lidar_proc = Process(
        target=lidar_worker,
        args=(shared,),
        daemon=True
    )

    yolo_proc = Process(
        target=yolo_worker,
        args=(shared,shm_L.name),
        daemon=True
    )

    lane_proc = Process(
        target=lane_worker,
        args=(shared,shm_L.name, shm_R.name, (preview_state, preview_lock)),
        daemon=True
    )

    camera_proc.start()
    lidar_proc.start()
    yolo_proc.start()
    lane_proc.start()
    

    print("[MAIN] sensor processes started")
    print("[BOOT] Waiting for sensors to stabilize...")
    start_wait = time.time()
    sensors_ready = False
    
    while time.time() - start_wait < 10:  # 10-second timeout
        # Check if all sensors have reported at least one valid value
        lidar_ok = not math.isinf(shared["dC"].value)
        cam_ok   = (shared["det_time"].value > 0) # YOLO has processed one frame
        
        if lidar_ok and cam_ok:
            sensors_ready = True
            print(f"[BOOT] All systems GO! (Stabilized in {time.time()-start_wait:.2f}s)")
            break
        
        print(f"  > Waiting... LIDAR: {'OK' if lidar_ok else '...'}, YOLO: {'OK' if cam_ok else '...'}")
        time.sleep(0.5)

    if not sensors_ready:
        print("[FATAL] Sensor timeout. Check hardware connections.")
        # Cleanup and exit here


    try:
        serial_lock, ser, mc = initialize_system()

        run_full_integrated(mc, shared)

    except KeyboardInterrupt:
        print("\n[INFO] Ctrl-C")
    finally:
        try:
            if mc is not None:
                # Use force=True to bypass the 0.08s interval check
                mc.send(STOP_CMD, force=True) 
        except Exception as e:
            print(f"[WARN] Failed to send stop: {e}")
            
        print("[MAIN] Shutting down workers...")
        for p in [lidar_proc, yolo_proc, lane_proc, camera_proc]:
            if p.is_alive():
                p.terminate()

        for p in [lidar_proc, yolo_proc, lane_proc, camera_proc]:
            p.join()
                
        for s in [shm,shm_L, shm_R]:
            try:
                s.close()
                s.unlink()
            except Exception:
                pass
        kill_port(8765)
        cleanup_system(mc=mc, ser=ser, serial_lock=serial_lock)
        

if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    run_integrated()