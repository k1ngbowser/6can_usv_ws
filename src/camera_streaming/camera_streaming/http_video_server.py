#!/usr/bin/env python3
"""Minimal replacement for web_video_server: subscribes to the camera image
topics and re-serves them over HTTP as MJPEG, without depending on the
heavy ros-jazzy-web-video-server package (boost/ffmpeg dev libs).

Endpoints:
  GET /                       -> index page with links
  GET /snapshot?topic=<topic> -> single JPEG frame
  GET /stream?topic=<topic>   -> multipart/x-mixed-replace MJPEG stream
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

BOUNDARY = 'camstream'
TOPICS = [
    '/camera/surface/image_raw',
    '/camera/underwater/image_raw',
]


class FrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg = {}

    def update(self, topic, jpeg_bytes):
        with self._lock:
            self._jpeg[topic] = jpeg_bytes

    def get(self, topic):
        with self._lock:
            return self._jpeg.get(topic)


store = FrameStore()


def image_msg_to_bgr(msg: Image):
    arr = np.frombuffer(msg.data, dtype=np.uint8)
    if msg.encoding in ('bgr8', 'rgb8'):
        frame = arr.reshape((msg.height, msg.width, 3))
        if msg.encoding == 'rgb8':
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame
    if msg.encoding == 'mono8':
        return cv2.cvtColor(arr.reshape((msg.height, msg.width)), cv2.COLOR_GRAY2BGR)
    raise ValueError(f'unsupported encoding: {msg.encoding}')


def make_callback(topic):
    def callback(msg):
        try:
            frame = image_msg_to_bgr(msg)
        except ValueError:
            return
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            store.update(topic, buf.tobytes())
    return callback


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        topic = qs.get('topic', [None])[0]

        if parsed.path == '/':
            self._send_index()
        elif parsed.path == '/snapshot':
            self._send_snapshot(topic)
        elif parsed.path == '/stream':
            self._send_stream(topic)
        else:
            self.send_error(404)

    def _send_index(self):
        items = ''.join(
            f'<li>{t} — <a href="/stream?topic={t}">stream</a> | '
            f'<a href="/snapshot?topic={t}">snapshot</a></li>' for t in TOPICS
        )
        body = f'<html><body><h1>camera_streaming</h1><ul>{items}</ul></body></html>'
        body = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_snapshot(self, topic):
        jpeg = store.get(topic) if topic else None
        if jpeg is None:
            self.send_error(404, 'no frame yet for topic')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(jpeg)))
        self.end_headers()
        self.wfile.write(jpeg)

    def _send_stream(self, topic):
        if topic not in TOPICS:
            self.send_error(404, 'unknown topic')
            return
        self.send_response(200)
        self.send_header('Content-Type', f'multipart/x-mixed-replace; boundary={BOUNDARY}')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            last = None
            while True:
                jpeg = store.get(topic)
                if jpeg is not None and jpeg is not last:
                    last = jpeg
                    self.wfile.write(f'--{BOUNDARY}\r\n'.encode())
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode())
                    self.wfile.write(jpeg)
                    self.wfile.write(b'\r\n')
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    rclpy.init()
    node = Node('http_video_server')
    node.declare_parameter('port', 8000)
    port = node.get_parameter('port').value

    for topic in TOPICS:
        node.create_subscription(Image, topic, make_callback(topic), 10)

    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    node.get_logger().info(f'http_video_server listening on :{port}')
    try:
        server.serve_forever()
    finally:
        server.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
