"""Publish surface/underwater camera feeds and expose them over HTTP.

camera_node captures both cameras with OpenCV and publishes sensor_msgs/Image
on /camera/surface/image_raw and /camera/underwater/image_raw.
http_video_server subscribes to those topics and re-serves them as MJPEG over
HTTP on `port` (default 8000), e.g.
http://<board-ip>:8000/stream?topic=/camera/surface/image_raw
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    surface_device = LaunchConfiguration('surface_device')
    underwater_device = LaunchConfiguration('underwater_device')
    port = LaunchConfiguration('port')

    return LaunchDescription([
        DeclareLaunchArgument(
            'surface_device', default_value='/dev/video2',
            description='V4L2 device path for the surface camera'),
        DeclareLaunchArgument(
            'underwater_device', default_value='/dev/video3',
            description='V4L2 device path for the underwater camera'),
        DeclareLaunchArgument(
            'port', default_value='8000',
            description='HTTP port the video server listens on'),

        Node(
            package='camera_streaming',
            executable='camera_node',
            name='camera_node',
            parameters=[{
                'surface_device': surface_device,
                'underwater_device': underwater_device,
                # 320x240: at 640x480 the two UVC cameras exceed the shared
                # USB hub's isochronous bandwidth ("Not enough bandwidth for
                # altsetting") when both stream at once, even MJPG-compressed.
                'width': 320,
                'height': 240,
                'fps': 15.0,
            }],
        ),

        Node(
            package='camera_streaming',
            executable='http_video_server',
            name='http_video_server',
            parameters=[{'port': port}],
        ),
    ])
