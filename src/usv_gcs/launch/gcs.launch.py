"""GCS(Raspberry Pi) launch 파일 — joy_node + joy_to_cmd_node + gui_main_node.

조이스틱 축/버튼 번호를 확정한 뒤에는 코드를 고치지 말고 인자로 넘기면 된다:

    ros2 launch usv_gcs gcs.launch.py linear_axis:=1 angular_axis:=0 pump_button:=0 auto_button:=1

카메라 스트림은 GCS가 아니라 B1 보드 위 camera_streaming 패키지(http_video_server, 고정
포트 8000)가 직접 서빙한다 (web_video_server는 그래서 이 launch 파일에 없다). GCS는 B1의
IP를 알 방법이 없으므로 camera_host 인자로 반드시 넘겨야 한다:

    ros2 launch usv_gcs gcs.launch.py camera_host:=<B1_보드_IP>
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    http_port_arg = DeclareLaunchArgument(
        'http_port', default_value='8000',
        description='gui_main_node 웹 대시보드 포트',
    )
    linear_axis_arg = DeclareLaunchArgument(
        'linear_axis', default_value='1',
        description='조이스틱 전진/후진 축 번호 (GCS 담당자가 실제 조이스틱 기준으로 확정)',
    )
    angular_axis_arg = DeclareLaunchArgument(
        'angular_axis', default_value='0',
        description='조이스틱 좌/우 회전 축 번호',
    )
    linear_scale_arg = DeclareLaunchArgument('linear_scale', default_value='1.0')
    angular_scale_arg = DeclareLaunchArgument('angular_scale', default_value='1.0')
    pump_button_arg = DeclareLaunchArgument(
        'pump_button', default_value='0',
        description='펌프/워터캐논 작동 버튼 번호 (GCS 담당자가 실제 조이스틱 기준으로 확정)',
    )
    auto_button_arg = DeclareLaunchArgument(
        'auto_button', default_value='1',
        description='자동/수동 제어 토글 버튼 번호 (GCS 담당자가 실제 조이스틱 기준으로 확정)',
    )
    camera_host_arg = DeclareLaunchArgument(
        'camera_host', default_value='',
        description='B1 보드의 IP - camera_streaming 패키지(http_video_server, 포트 8000)가 '
                     '그 보드 위에서 카메라 스트림을 직접 서빙하므로 GCS는 이 값을 알아야 한다.',
    )

    return LaunchDescription([
        http_port_arg,
        linear_axis_arg,
        angular_axis_arg,
        linear_scale_arg,
        angular_scale_arg,
        pump_button_arg,
        auto_button_arg,
        camera_host_arg,
        Node(package='joy', executable='joy_node', name='joy_node'),
        Node(
            package='usv_gcs', executable='joy_to_cmd_node', name='joy_to_cmd_node',
            parameters=[{
                'linear_axis': ParameterValue(LaunchConfiguration('linear_axis'), value_type=int),
                'angular_axis': ParameterValue(LaunchConfiguration('angular_axis'), value_type=int),
                'linear_scale': ParameterValue(LaunchConfiguration('linear_scale'), value_type=float),
                'angular_scale': ParameterValue(LaunchConfiguration('angular_scale'), value_type=float),
                'pump_button': ParameterValue(LaunchConfiguration('pump_button'), value_type=int),
                'auto_button': ParameterValue(LaunchConfiguration('auto_button'), value_type=int),
            }],
        ),
        Node(
            package='usv_gcs', executable='gui_main_node', name='gui_main_node',
            parameters=[{
                'http_port': ParameterValue(LaunchConfiguration('http_port'), value_type=int),
                'camera_host': LaunchConfiguration('camera_host'),
            }],
        ),
    ])
