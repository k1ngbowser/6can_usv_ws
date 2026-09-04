"""B2 보드 launch 파일 — thruster_driver_node + actuator_driver_node.

모터 드라이버 PWM 범위를 확정한 뒤에는 코드를 고치지 말고 인자로 넘기면 된다:

    ros2 launch usv_actuators actuators.launch.py max_pwm:=180

수질 자동 제어 임계값도 마찬가지다. 실제 수조에서 clarity_pct가 어느 범위로
나오는지 보고 코드 수정 없이 조정한다:

    ros2 launch usv_actuators actuators.launch.py bad_below:=35.0 good_above:=55.0

수동 조작 우선 시간(초)도 인자다. 사람이 GCS에서 버튼을 누르면 이 시간 동안
자동 제어가 억제된다:

    ros2 launch usv_actuators actuators.launch.py pump_manual_hold_s:=120.0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _float_arg(name, default, description):
    return DeclareLaunchArgument(name, default_value=default, description=description)


def generate_launch_description():
    max_pwm_arg = DeclareLaunchArgument(
        'max_pwm', default_value='255',
        description='추진기 PWM 최대값 (B2 담당자가 실제 모터 드라이버 사양에 맞춰 확정)',
    )

    policy_args = [
        _float_arg('bad_below', '40.0', 'clarity_pct가 이 값 미만이면 나쁨 (펌프 ON, LED 빨강)'),
        _float_arg('good_above', '60.0', 'clarity_pct가 이 값 이상이면 좋음 (LED 초록)'),
        _float_arg('margin', '3.0', '히스테리시스 폭 — 경계에서 펌프가 떠는 것을 막는다'),
        _float_arg('pump_manual_hold_s', '60.0', 'GCS 수동 펌프 조작이 자동보다 우선하는 시간(초)'),
        _float_arg('led_manual_hold_s', '60.0', 'GCS 수동 LED 조작이 자동보다 우선하는 시간(초)'),
        _float_arg('stale_timeout_s', '5.0', '수질 데이터가 이 시간 이상 끊기면 펌프 정지'),
    ]

    def as_float(name):
        return ParameterValue(LaunchConfiguration(name), value_type=float)

    return LaunchDescription([
        max_pwm_arg,
        *policy_args,
        Node(
            package='usv_actuators', executable='thruster_driver_node', name='thruster_driver_node',
            parameters=[{'max_pwm': ParameterValue(LaunchConfiguration('max_pwm'), value_type=int)}],
        ),
        Node(
            package='usv_actuators', executable='actuator_driver_node', name='actuator_driver_node',
            parameters=[{
                'bad_below': as_float('bad_below'),
                'good_above': as_float('good_above'),
                'margin': as_float('margin'),
                'pump_manual_hold_s': as_float('pump_manual_hold_s'),
                'led_manual_hold_s': as_float('led_manual_hold_s'),
                'stale_timeout_s': as_float('stale_timeout_s'),
            }],
        ),
    ])
