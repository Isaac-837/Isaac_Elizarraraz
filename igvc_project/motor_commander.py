import time
import serial
import os
import fcntl

CMD_UP     = "Forward Half"
CMD_DOWN   = "Backward Half"
CMD_LEFT   = "Left Half"
CMD_RIGHT  = "Right Half"
CMD_AUTO   = "Auto"
CMD_MANUAL = "Manual"
STOP_CMD   = "Stop"

CHAR_DELAY = 0.005
SERIAL_LOCK_PATH = "/tmp/tm4c_serial.lock" # DEBUG Phase 1: [SAteefa 3/21: added to enforce one-way pathway and prevent interleaving]
PORT = "/dev/ttyACM0"   # change if needed
BAUD = 19200
DTR = True
RTS = True
BOOT_WAIT = 2.0         # wait after opening serial for TM4C boot

# [SAteefa 3/22 Added: TM4C command sender]
# Sends commands while:
#   - suppressing exact duplicates
#   - reducing rapid serial spam/jitter
#   - allowing force=True for critical commands like STOP and AUTO
class MotorCommander:
    """
    Manages high-level motor commands to the TM4C. 
    Prevents serial spam by suppressing exact duplicates and enforcing a minimum send interval.

    Attributes:
        ser (serial.Serial): The serial connection object.
        min_cmd_interval (float): Minimum seconds between identical commands.
    """
    def __init__(self,ser,min_cmd_interval=0.08):
        self.ser = ser              #serial connection to TM4C
        self.last_cmd = None        #remembers the last command sent
        self.last_send_time = 0.0   # [SAteefa 3/21 added: remembers when the last command was sent]
        self.min_cmd_interval = min_cmd_interval # [SAteefa 3/21 added: minimum delay between non-forced command sends]
    def send(self, cmd:str, force:bool=False):
        """
        Evaluates and sends a command to the motors.

        Args:
            cmd (str): The movement command string.
            force (bool): If True, bypasses timing restrictions and sends immediately.
        """
        now = time.time()

        same_cmd = (cmd == self.last_cmd)
        too_soon = (now - self.last_send_time) < self.min_cmd_interval

        # send immediately if forced
        if force:
            send_line_typewriter(self.ser, cmd)
            self.last_cmd = cmd
            self.last_send_time = now
            return

        # send if command changed, or if same command but refresh interval has passed
        if (not same_cmd) or (not too_soon):
            send_line_typewriter(self.ser, cmd)
            self.last_cmd = cmd
            self.last_send_time = now


# [SAteefa 3/22 Added: hysteresis-based discrete steering decision]
# Keeps the controller from flipping between LEFT and FORWARD on tiny frame-to-frame noise.
def choose_cmd_with_hysteresis(turn, steer_state):
    """
    Translates a fractional turn value into a discrete TM4C hardware command.
    Applies hysteresis thresholds to prevent the robot from wiggling on straightaways.

    Args:
        turn (float): Normalized turn desire (-1.0 to 1.0).
        steer_state (str): The current driving state ("LEFT", "RIGHT", "STRAIGHT").

    Returns:
        tuple: (The specific string command, The new state)
    """
    LEFT_ENTER_THRESH  = -0.05
    LEFT_EXIT_THRESH   = -0.02

    RIGHT_ENTER_THRESH =  0.05
    RIGHT_EXIT_THRESH  =  0.02

    if steer_state == "LEFT":
        if turn > LEFT_EXIT_THRESH:
            steer_state = "STRAIGHT"
    elif steer_state == "RIGHT":
        if turn < RIGHT_EXIT_THRESH:
            steer_state = "STRAIGHT"
    else:
        if turn < LEFT_ENTER_THRESH:
            steer_state = "LEFT"
        elif turn > RIGHT_ENTER_THRESH:
            steer_state = "RIGHT"

    if steer_state == "LEFT":
        return CMD_LEFT, steer_state
    elif steer_state == "RIGHT":
        return CMD_RIGHT, steer_state
    else:
        return CMD_UP, steer_state


def send_line_typewriter(ser: serial.Serial, text: str):
    """
    Sends a string command over serial, character by character, to avoid buffer overflow.

    Args:
        ser (serial.Serial): The active serial connection.
        text (str): The command string to send (e.g., 'Forward Half').
    """
    EOL = "\r" 
    data = (text + EOL).encode("ascii", errors="ignore")
    print("TX:", repr(text + EOL), list(data))
    for b in data:
        ser.write(bytes([b]))
        ser.flush()
        time.sleep(CHAR_DELAY)
        
        

# =========================
# Serial helpers
# =========================

# DEBUG Phase 1: [SAteefa 3.21] Helper function for open_serial

#[SAteefa 3/21 Added: lock-file helper to ensure only one script owns the TM4c serial port at a time]
# Prevents multiple scripts from writing to TM4C at the same time by using an exclusive lock file
class SerialPortLock:
    def __init__(self, lock_path):
        self.lock_path = lock_path   #path to the lock file used to cooredinate port ownership
        self.fd = None              #file descriptor for the lock file
    def acquire(self):
        #[SAteefa 3/21 Added: open lock file in a+ mode so we can both write our PID and read existing owner's PID]
        #Using "w" would erase contents and would not let us read back the current owner properly
        self.fd = open(self.lock_path, "a+")
        try:
            #[SAteefa 3/21 Added: request a non-blocking exclusive lock]
            # If this succeeds, this script becomes the only allowed owner of the TM4c serial resource
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            #[SAteefa 3/21 Added: clear old contents, then store this process ID in the lock file]
            # This helps identify which process currently owns the serial port.
            self.fd.seek(0)
            self.fd.truncate()
            self.fd.write(str(os.getpid()))
            self.fd.flush()


            print(f"[LOCK] Acquired TM4C serial lock: {self.lock_path}")
        except BlockingIOError:
            # [SAteefa 3/21 Added: if another process already owns the lock, read its PID for a clearer error message]
            self.fd.seek(0)
            owner = self.fd.read().strip()


            raise RuntimeError(
                f"TM4c serial port is already owned by another process"
                f"{' (PID ' + owner + ')' if owner else ''}. "
                f"Stop the other script before running this one."
            )
    def release(self):
        if self.fd is not None:
            try:
                #[SAteefa 3/21 ADDED: clear the stored PID and release the exclusive lock during shutdown.]
                #This prevents ownership from being left behind after the script exits
                self.fd.seek(0)
                self.fd.truncate()
                fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
                print(f"[LOCK] Released TM4C serial lock : {self.lock_path}")
            except Exception:
                pass
            try:
                #close the lock-file handle after unlocking
                self.fd.close()
            except Exception:
                pass
            self.fd = None


def open_serial():
    """
    Initializes and opens the serial connection to the TM4C microcontroller.

    Returns:
        serial.Serial: The active serial connection object.
    """
    print("Opening serial:", PORT, "@", BAUD)
    ser = serial.Serial(
        PORT, BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.5,
        write_timeout=1.0,
        rtscts=False,
        dsrdtr=False,
        xonxoff=False,
    )
    ser.setDTR(DTR)
    ser.setRTS(RTS)
    time.sleep(BOOT_WAIT)
    return ser

