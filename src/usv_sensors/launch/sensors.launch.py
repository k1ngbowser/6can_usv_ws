"""B1 보드 launch 파일 — water_quality_node + gps_driver_node + current_sensor_node.

카메라(/camera/surface/image_raw, /camera/underwater/image_raw)는 이제 이 launch 파일이
아니라 별도 컨테이너인 camera_streaming 패키지(camera_node + http_video_server)가 담당한다
(usv_sensors의 camera_node는 그대로 남아있지만 여기서 띄우지 않는다 - 둘 다 띄우면 같은
토픽에 노드 두 개가 중복 발행하게 된다). B1 보드를 통째로 올릴 땐 루트의 start_b1.sh가
usv_sensors와 camera_streaming 컨테이너를 같이 띄운다 (README.md 3항 참고).
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='usv_sensors', executable='water_quality_node', name='water_quality_node'),
        Node(package='usv_sensors', executable='gps_driver_node', name='gps_driver_node'),
        Node(package='usv_sensors', executable='current_sensor_node', name='current_sensor_node'),
    ])
