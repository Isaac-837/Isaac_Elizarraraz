from rplidar import RPLidar, RPLidarException
import time
import math


def wrap180(a):
    """Normalizes an angle to be within -180 and +180 degrees."""
    return (a + 180) % 360 - 180

def rel_to_front(a_abs, angle_sign, front_deg):
    """Calculates the relative angle of a LIDAR point based on the physical mount orientation."""
    return angle_sign * wrap180(a_abs - front_deg)

def fmt_mm(x):
    """Formats a millimeter distance for console printing, hiding infinite values."""
    PRINT_INF_AS = -1
    
    return int(x) if x < math.inf else PRINT_INF_AS

def open_lidar(port, baud, timeout):
    """
    Connects to the RPLidar sensor and clears its initial buffers.

    Args:
        port (str): The USB port (e.g., '/dev/ttyUSB0').
        baud (int): Baudrate for the lidar connection.
        timeout (float): Connection timeout in seconds.

    Returns:
        RPLidar: The initialized Lidar object.
    """
    lid = RPLidar(port, baudrate=baud, timeout=timeout)
    time.sleep(0.1)
    try:
        lid.start_motor()
    except Exception:
        pass

    # drain garbage
    try:
        if hasattr(lid, 'clean_input'):
            lid.clean_input()
        elif hasattr(lid, 'clear_input'):
            lid.clear_input()
        else:
            try:
                _ = lid._serial.read(4096)
            except Exception:
                pass
    except Exception:
        pass

    try:
        _ = lid.get_info()
    except Exception:
        pass
    try:
        _ = lid.get_health()
    except Exception:
        pass
    return lid


def iter_scans_standard(lidar):
    """Generator that yields standard scans from the RPLidar."""
    for scan in lidar.iter_scans(max_buf_meas=8192, min_len=40):
        yield scan

def bins_from_scan(scan, angle_sign, front_deg):
    """Groups lidar points into direct angles (-50, 0, 50 degrees)."""
    LOOK_ANGLES  = [-50, 0, +50]
    ANG_TOL      = 10
    
    bins = {a: math.inf for a in LOOK_ANGLES}
    for q, ang, dist in scan:
        if dist <= 0:
            continue
        rel = rel_to_front(ang, angle_sign, front_deg)
        for tgt in LOOK_ANGLES:
            if abs(rel - tgt) <= ANG_TOL and dist < bins[tgt]:
                bins[tgt] = dist
    return bins

def sectors_from_scan(scan, angle_sign, front_deg):
    """Groups lidar points into wide frontal sectors for object avoidance."""
    FORWARD_SECTORS = {
    'FR': (-60.0, -10.0),
    'F' : (-15.0, +15.0),
    'FL': (+10.0, +60.0),
    }
    
    sectors = {name: math.inf for name in FORWARD_SECTORS}
    for q, ang, dist in scan:
        if dist <= 0:
            continue
        rel = rel_to_front(ang, angle_sign, front_deg)
        for name, (lo, hi) in FORWARD_SECTORS.items():
            if lo <= rel <= hi and dist < sectors[name]:
                sectors[name] = dist
    return sectors

def combine_min(*vals):
    """Returns the minimum value from a list, ignoring mathematical infinity."""
    finite = [v for v in vals if not math.isinf(v)]
    return min(finite) if finite else math.inf

class LidarState:
    """Maintains the current spatial state of the vehicle's surroundings using Lidar data."""
    def __init__(self, angle_sign, front_deg, no_data_stop_sec):
        self.angle_sign = angle_sign
        self.front_deg  = front_deg
        self.no_data_stop_sec = no_data_stop_sec

        self.last_valid_time = time.time()
        self.dL = self.dC = self.dR = math.inf
        self.dFL = self.dF = self.dFR = math.inf

    def update_from_scan(self, scan):
        bins = bins_from_scan(scan, self.angle_sign, self.front_deg)
        dR_raw, dC_raw, dL_raw = bins[-50], bins[0], bins[+50]

        sectors = sectors_from_scan(scan, self.angle_sign, self.front_deg)
        dFR = sectors['FR']
        dF  = sectors['F']
        dFL = sectors['FL']

        dR = combine_min(dR_raw, dFR)
        dC = combine_min(dC_raw, dF)
        dL = combine_min(dL_raw, dFL)

        now = time.time()
        have_any = not (math.isinf(dL) and math.isinf(dC) and math.isinf(dR))
        if have_any:
            self.last_valid_time = now

        self.dL, self.dC, self.dR = dL, dC, dR
        self.dFL, self.dF, self.dFR = dFL, dF, dFR
        return have_any

    def no_data_too_long(self):
        return (time.time() - self.last_valid_time) > self.no_data_stop_sec
    