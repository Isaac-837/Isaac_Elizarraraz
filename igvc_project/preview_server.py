import time
import os
import signal
import subprocess
from http.server import BaseHTTPRequestHandler
import threading
import socketserver
from typing import Optional


class MjpegPreviewState:
    def __init__(self, lock):
        self.lock = lock  # This will be a Manager.Lock()
        self.jpeg_bytes = None

    def set_jpeg(self, data: bytes):
        with self.lock:
            self.jpeg_bytes = data

    def get_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.jpeg_bytes

def make_mjpeg_handler(preview_bundle):
    preview_state, preview_lock = preview_bundle
    boundary = b"--jpgboundary"
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/view"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><img src='/stream' style='width:100%'></body></html>")
                return
            if self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=jpgboundary")
                self.end_headers()
                while True:
                    with preview_lock:
                        jpg = preview_state.jpeg_bytes

                    if jpg is None:
                        time.sleep(0.1)
                        continue
                    try:
                        self.wfile.write(boundary + b"\r\nContent-Type: image/jpeg\r\n" +
                                b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" +
                                    jpg + b"\r\n")
                        self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        break
                    time.sleep(0.05) # Cap at ~20 FPS to save CPU
        def log_message(self, format, *log_args): pass
    return Handler

def start_mjpeg_server(preview, host="0.0.0.0", port=8765):
    server = socketserver.ThreadingTCPServer((host, port), make_mjpeg_handler(preview))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[HTTP] Preview live at http://localhost:{port}")
    
def kill_port(port=8765):
    """Kill any process still holding the preview server port from a previous run."""
    try:
        result = subprocess.check_output(
            f"fuser {port}/tcp 2>/dev/null", shell=True
        ).decode().strip()
        if result:
            for pid in result.split():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"[BOOT] Killed stale process {pid} holding port {port}")
                except Exception:
                    pass
            time.sleep(0.5)  # give OS a moment to release the port
    except subprocess.CalledProcessError:
        pass  # fuser returns non-zero if nothing is holding the port — that's fine