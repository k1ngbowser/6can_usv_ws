#!/usr/bin/env python3
"""Publish surface/underwater USB camera frames as ROS 2 image topics.

Captures frames with OpenCV (no usb_cam dependency) and publishes them as
sensor_msgs/Image on /camera/surface/image_raw and
/camera/underwater/image_raw. If a camera is not connected yet, this keeps
retrying to open it instead of crashing.
"""

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class CameraPublisher:
    def __init__(self, node: Node, name: str, device, topic: str,
                 width: int, height: int, fps: float):
        self.node = node
        self.name = name
        self.device = device
        self.frame_id = f'{name}_camera'
        self.pub = node.create_publisher(Image, topic, 10)
        self.cap = None
        self._open(width, height)
        period = 1.0 / fps if fps > 0 else 0.1
        node.create_timer(period, self._tick)

    def _open(self, width, height):
        cap = cv2.VideoCapture(self.device)
        # Request MJPG (compressed) instead of the default uncompressed
        # format: two UVC cameras sharing one USB hub can exceed the hub's
        # isochronous bandwidth ("Not enough bandwidth for altsetting")
        # unless each stream is compressed.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        if width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if cap.isOpened():
            self.cap = cap
            self.node.get_logger().info(f'[{self.name}] opened {self.device}')
        else:
            cap.release()
            self.cap = None
            self.node.get_logger().warn(
                f'[{self.name}] could not open {self.device}, will retry')

    def _tick(self):
        if self.cap is None:
            self._open(0, 0)
            return
        ok, frame = self.cap.read()
        if not ok:
            self.node.get_logger().warn(
                f'[{self.name}] read failed on {self.device}, reopening')
            self.cap.release()
            self.cap = None
            return
        msg = Image()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.height, msg.width = frame.shape[0], frame.shape[1]
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = msg.width * 3
        msg.data = frame.tobytes()
        self.pub.publish(msg)

    def release(self):
        if self.cap is not None:
            self.cap.release()


def main():
    rclpy.init()
    node = Node('camera_node')
    node.declare_parameter('surface_device', '/dev/video2')
    node.declare_parameter('underwater_device', '/dev/video3')
    node.declare_parameter('width', 640)
    node.declare_parameter('height', 480)
    node.declare_parameter('fps', 15.0)

    surface_device = node.get_parameter('surface_device').value
    underwater_device = node.get_parameter('underwater_device').value
    width = node.get_parameter('width').value
    height = node.get_parameter('height').value
    fps = node.get_parameter('fps').value

    cameras = [
        CameraPublisher(node, 'surface', surface_device,
                         '/camera/surface/image_raw', width, height, fps),
        CameraPublisher(node, 'underwater', underwater_device,
                         '/camera/underwater/image_raw', width, height, fps),
    ]

    try:
        rclpy.spin(node)
    finally:
        for cam in cameras:
            cam.release()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
