#!/usr/bin/env python3
import io
import logging
import socketserver
from http import server
from threading import Condition, Thread
import time

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform

# ==================== CONFIGURATION ====================
RESOLUTION = (1280, 720)      # Conservative but usable (change to 1024x576 if needed)
FRAMERATE = 12                # Conservative FPS for Pi Zero 2W
PORT = 7123
# =======================================================

PAGE = """\
<!DOCTYPE html>
<html>
<head>
    <title>PrinterCam</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            margin: 0;
            background: #000;
            display: flex;
            flex-direction: column;
            height: 100vh;
            font-family: Arial, sans-serif;
        }
        h1 {
            color: #aaa;
            margin: 8px 0;
            font-size: 1.1em;
            text-align: center;
            flex-shrink: 0;
        }
        .stream-container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        img {
            max-width: 100%;
            max-height: 100%;
            width: auto;
            height: auto;
            object-fit: contain;
        }
    </style>
</head>
<body>
    <h1>PrinterCam</h1>
    <div class="stream-container">
        <img src="/stream.mjpg" />
    </div>
</body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

# ==================== MAIN ====================
logging.basicConfig(level=logging.INFO)

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"size": RESOLUTION},
    controls={"FrameRate": FRAMERATE},
    transform=Transform(vflip=1)   # Flip vertically — change to hflip=1 if needed
))

output = StreamingOutput()
picam2.start_recording(MJPEGEncoder(), FileOutput(output))

try:
    address = ('', PORT)
    server = StreamingServer(address, StreamingHandler)
    logging.info(f"Starting server on port {PORT}")
    server.serve_forever()
finally:
    picam2.stop_recording()
