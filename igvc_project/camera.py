
import time
import numpy as np
import cv2


LEFT_CAM_INDEX = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.1.1:1.0-video-index0"
RIGHT_CAM_INDEX = "/dev/v4l/by-path/platform-3610000.usb-usb-0:1.2:1.0-video-index0"
CAM_BACKEND     = cv2.CAP_V4L2   # or cv2.CAP_ANY



def process_frame(frame_bgr, tracker: SimpleLineTracker, roi_dict):
    LANE_COLOR   = (255, 255, 255)
    TARGET_COLOR = (0, 255, 0)
    MIN_AREA             = 80 #old: 80
    MIN_HEIGHT           = 15 #old: 15
    MIN_WIDTH            = 2
    MIN_ASPECT_H_OVER_W  = 1 #old: 0.6,1.0


    h, w = frame_bgr.shape[:2]
    y_bottom = h - 1
    y_top    = int(h * roi_dict['top_left'][1]) # Use roi_dict here

    roi = region_selection(frame_bgr, roi_dict)
    mask_white = white_mask(roi)
    mask_white = morph_clean(mask_white)

    contours, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_rect = None
    best_score = -1e9

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_AREA:
            continue
        rect = cv2.minAreaRect(cnt)
        (cx, cy), (rw, rh), _ = rect
        height = max(rw, rh); width = min(rw, rh)
        if height < MIN_HEIGHT or width < MIN_WIDTH:
            continue
        aspect = height / max(1.0, width)
        if aspect < MIN_ASPECT_H_OVER_W:
            continue
        
        score = score_component(rect)
        if score > best_score:
            best_score = score
            best_rect = rect

    out = frame_bgr.copy()
    mask_debug = cv2.cvtColor(mask_white, cv2.COLOR_GRAY2BGR)

    line_x_bottom = None
    angle_deg = None

    if best_rect is not None:
        box = cv2.boxPoints(best_rect).astype(np.int32)
        cv2.drawContours(out, [box], 0, LANE_COLOR, 2)
        cv2.drawContours(mask_debug, [box], 0, (0, 255, 255), 2)


        # best_rect format is: ((cx, cy), (width, height), angle)
        (cx, cy) = best_rect[0]
        
        # We still call it line_x_bottom for variable compatibility, 
        # but it is now tracking the center of the line!
        line_x_bottom = float(cx) 
        
        # Draw the red dot in the center of the bounding box so you can see it working!
        cv2.circle(out, (int(cx), int(cy)), 5, (0,0,255), -1)
        cv2.circle(mask_debug, (int(cx), int(cy)), 5, (0,0,255), -1)
        
        angle_deg = rect_angle_from_vertical(best_rect)

    cv2.line(out, (0, y_top), (w-1, y_top), (255, 0, 0), 1, cv2.LINE_AA)
    cv2.line(mask_debug, (0, y_top), (w-1, y_top), (255, 0, 0), 1, cv2.LINE_AA)

    target_x = int(tracker.target_x_ratio * w)
    cv2.line(out, (target_x, y_top), (target_x, y_bottom), TARGET_COLOR, 2, cv2.LINE_AA)
    cv2.line(mask_debug, (target_x, y_top), (target_x, y_bottom), TARGET_COLOR, 2, cv2.LINE_AA)

    u, err_norm = tracker.control_from_x(line_x_bottom)
    forward, turn = apply_steering(u)

    print(f"[TELEM] LineX={line_x_bottom}  ErrNorm={err_norm:+.2f}  AngleAbsDeg={angle_deg}")
    

    return out, mask_debug, forward, turn, (angle_deg if angle_deg is not None else 0.0), line_x_bottom, err_norm

def open_camera_by_index(label: str):
    path = LEFT_CAM_INDEX if label == "LEFT" else RIGHT_CAM_INDEX
    print(f"[CAM] Trying to open {label} camera at index {path}...")
    cap = cv2.VideoCapture(path, CAM_BACKEND)
    time.sleep(0.3)
    if not cap.isOpened():
        print(f"[CAM] Failed to open {label} camera at index {path}")
        cap.release()
        return None
    ret, frame = cap.read()
    if not ret:
        print(f"[CAM] {label} opened but could not read frame")
        cap.release()
        return None
    print(f"[CAM] Using {label} camera at index {path}")
    return cap

def tune_camera_for_speed(cap, label: str):
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  480) #previous 960
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 270) #previous 540
    cap.set(cv2.CAP_PROP_FPS, 30)

    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[CAM] {label} tuned to ~{w:.0f}x{h:.0f} @ {fps:.1f} FPS")


# Add roi_dict as the second parameter
def region_selection(image, roi_dict):
    mask = np.zeros_like(image)
    h, w = image.shape[:2]
    
    # Use the passed dictionary instead of the hardcoded global
    bl = (int(w*roi_dict['bottom_left'][0]),  int(h*roi_dict['bottom_left'][1]))
    tl = (int(w*roi_dict['top_left'][0]),     int(h*roi_dict['top_left'][1]))
    tr = (int(w*roi_dict['top_right'][0]),    int(h*roi_dict['top_right'][1]))
    br = (int(w*roi_dict['bottom_right'][0]), int(h*roi_dict['bottom_right'][1]))
    
    pts = np.array([[bl, tl, tr, br]], dtype=np.int32)
    color = 255 if len(image.shape) == 2 else (255,) * image.shape[2]
    cv2.fillPoly(mask, pts, color)
    return cv2.bitwise_and(image, mask)

def white_mask(bgr):
    HSV_S_MAX = 70
    HSV_V_MIN = 200
    HSV_H_ANY = (0, 180)
    LAB_A_ABS_MAX = 20
    LAB_B_ABS_MAX = 20
    Y_MIN = 210
    CR_ABS_MAX = 14
    CB_ABS_MAX = 14

    hsv  = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab  = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab)
    ycc  = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)

    h, s, v   = cv2.split(hsv)
    L, a, b   = cv2.split(lab)
    Y, Cr, Cb = cv2.split(ycc)

    m_hsv = (s <= HSV_S_MAX) & (v >= HSV_V_MIN)
    m_hsv &= (h >= HSV_H_ANY[0]) & (h <= HSV_H_ANY[1])

    m_lab = (np.abs(a.astype(np.int16)-128) <= LAB_A_ABS_MAX) & \
            (np.abs(b.astype(np.int16)-128) <= LAB_B_ABS_MAX)

    m_y   = (Y >= Y_MIN)
    m_cr  = (np.abs(Cr.astype(np.int16)-128) <= CR_ABS_MAX)
    m_cb  = (np.abs(Cb.astype(np.int16)-128) <= CB_ABS_MAX)
    m_ycc = (m_y & m_cr & m_cb)

    mask = (m_hsv & m_lab & m_ycc).astype(np.uint8) * 255

    return mask

def morph_clean(mask):
    OPEN_K  = (3, 3)
    CLOSE_K = (11, 11)

    open_k  = cv2.getStructuringElement(cv2.MORPH_RECT, OPEN_K)
    close_k = cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE_K)
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_k)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, close_k)
    return m

def rect_angle_from_vertical(rect):
    box = cv2.boxPoints(rect)
    box = np.array(box, dtype=np.float32)
    edges = []
    for i in range(4):
        p0 = box[i]; p1 = box[(i+1) % 4]
        v = p1 - p0
        edges.append((np.linalg.norm(v), v))
    edges.sort(key=lambda t: t[0], reverse=True)
    vx, vy = np.abs(edges[0][1][0]), np.abs(edges[0][1][1])
    if vx == 0 and vy == 0:
        return 90.0
    ang_deg = np.degrees(np.arctan2(vx, vy))
    return float(ang_deg)

def score_component(rect):
    (cx, cy), (w, h), _ = rect
    area = max(1.0, w*h)
    height_bonus = max(w, h)**2
    bottom_bias = cy
    return area + 0.3*height_bonus + 0.8*bottom_bias

class SimpleLineTracker:
    """
    A Proportional-Derivative (PD) controller that calculates steering error 
    based on a lane line's position on the screen.
    """
    def __init__(self, w, target_x_ratio: float):
        self.w = w
        self.target_x_ratio = target_x_ratio
        self.prev_err = 0.0

    def control_from_x(self, line_x_bottom):
        """
        Calculates the steering output needed to center the line.

        Args:
            line_x_bottom (float): The current X coordinate of the tracked line.

        Returns:
            tuple: (Steering output command, Normalized Error)
        """
        # PD gains
        KP = 0.9
        KD = 0.2
        target_x = self.target_x_ratio * self.w

        if line_x_bottom is None:
            err_norm = 0.0
        else:
            err_px = line_x_bottom - target_x
            err_norm = float(np.clip(err_px / (self.w/2), -1.0, 1.0))

        d = err_norm - self.prev_err
        self.prev_err = err_norm
        u = KP * err_norm + KD * d
        u = float(np.clip(u, -1.0, 1.0))
        return u, err_norm

def apply_steering(norm_error):
    turn_scale = 1.0
    turn = float(np.clip(norm_error, -1.0, 1.0)) * turn_scale
    forward = 0.6 * (1 - 0.5*abs(turn))
    print(f"[CTRL] forward={forward:.2f} turn={turn:.2f}")
    return forward, turn