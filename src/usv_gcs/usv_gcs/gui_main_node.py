"""gui_main_node — usv_gcs 패키지 (Raspberry Pi).

구독:
  /water_quality/data [std_msgs/msg/String]         JSON 파싱해서 표시
  /gps/fix             [sensor_msgs/msg/NavSatFix]
  /gps/has_fix         [std_msgs/msg/Bool]           false면 'GPS 신호 없음' 배너
  /battery/status      [std_msgs/msg/String]         JSON 파싱: thruster1, thruster2,
                                                       pump_ctrl, sensor_board 각각
                                                       {current_a, percentage}
  /cmd_vel             [geometry_msgs/msg/Twist]     조이스틱 인디케이터 표시용
  /actuator/pump_cmd   [std_msgs/msg/Bool]           joy_to_cmd_node가 조이스틱 버튼으로
                                                       발행 - 여기선 상태 표시용으로만 구독
  /actuator/pump_state [std_msgs/msg/Bool]           B2가 발행하는 펌프 실제 상태(명령과
                                                       다를 수 있음) - 상태 표시용으로만 구독
  /actuator/led_state  [std_msgs/msg/ColorRGBA]      B2가 발행하는 LED 실제 상태 - 상태
                                                       표시용으로만 구독
  /actuator/auto_mode  [std_msgs/msg/Bool]           joy_to_cmd_node가 조이스틱 버튼으로
                                                       발행 - 여기선 상태 표시용으로만 구독
발행:
  /actuator/led_cmd    [std_msgs/msg/ColorRGBA]

조종은 조이스틱 하나로만 하므로(마우스로 GUI 버튼을 누를 사람이 없음) 펌프와 자동/수동
전환은 joy_to_cmd_node가 조이스틱 버튼으로 발행하고, 이 노드는 그 상태를 /api/state로
보여주기만 한다. LED는 아직 조이스틱에 버튼을 안 배정해서 계속 GUI 쪽 컨트롤(/api/led)로
남겨뒀다.

듀얼 카메라 MJPEG 스트림은 이 노드가 직접 발행하지 않는다. web_video_server를 별도
실행해서 /camera/surface/image_raw, /camera/underwater/image_raw 토픽을 HTTP로 변환해야
하고, 이 노드의 웹 대시보드(dashboard_html.py)는 그 스트림 주소를 <img> 태그로 그대로
표시한다.

전류 센서 4개(추진기1/2, 펌프 제어부, 센서 보드)는 전부 B1 보드에 물려있어서
usv_sensors의 current_sensor_node가 /battery/status 하나로 통합 발행한다. 예전에
usv_actuators가 따로 발행하던 /battery/thruster, /battery/actuator는 삭제되었다.

배터리 경고 기준(BATTERY_WARNING_PCT)은 구체적인 배터리 사양이 아직 정해지지 않아서 20%로
임시 지정했다. 실제 배터리 사양이 정해지면 이 값을 조정해야 한다.
"""

import json
import threading

from ament_index_python.packages import get_package_share_directory

import rclpy
from rclpy.node import Node

from flask import Flask, jsonify, request

from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Bool
from std_msgs.msg import ColorRGBA
from std_msgs.msg import String

from .dashboard_html import INDEX_HTML

# TODO(GCS 담당자): 실제 배터리 사양이 정해지면 경고 기준치를 조정할 것.
BATTERY_WARNING_PCT = 20


class GuiMainNode(Node):

    def __init__(self):
        super().__init__('gui_main_node')

        self.declare_parameter('http_port', 8000)

        self.state_lock = threading.Lock()
        self.state = {
            'water_quality': None,
            'gps_fix': None,
            'gps_has_fix': None,
            'battery_status': None,
            'cmd_vel': None,
            'pump_on': None,
            'pump_state': None,
            'led_state': None,
            'auto_mode': None,
        }

        self.create_subscription(String, '/water_quality/data', self.on_water_quality, 10)
        self.create_subscription(NavSatFix, '/gps/fix', self.on_gps_fix, 10)
        self.create_subscription(Bool, '/gps/has_fix', self.on_gps_has_fix, 10)
        self.create_subscription(String, '/battery/status', self.on_battery_status, 10)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 10)
        self.create_subscription(Bool, '/actuator/pump_cmd', self.on_pump_cmd, 10)
        self.create_subscription(Bool, '/actuator/pump_state', self.on_pump_state, 10)
        self.create_subscription(ColorRGBA, '/actuator/led_state', self.on_led_state, 10)
        self.create_subscription(Bool, '/actuator/auto_mode', self.on_auto_mode, 10)

        self.led_pub = self.create_publisher(ColorRGBA, '/actuator/led_cmd', 10)

        self.get_logger().info('GUI main node started')

    def on_water_quality(self, msg: String):
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError):
            return
        with self.state_lock:
            self.state['water_quality'] = data

    def on_gps_fix(self, msg: NavSatFix):
        with self.state_lock:
            self.state['gps_fix'] = {'latitude': msg.latitude, 'longitude': msg.longitude}

    def on_gps_has_fix(self, msg: Bool):
        with self.state_lock:
            self.state['gps_has_fix'] = msg.data

    def on_battery_status(self, msg: String):
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError):
            return
        with self.state_lock:
            self.state['battery_status'] = data

    def on_cmd_vel(self, msg: Twist):
        with self.state_lock:
            self.state['cmd_vel'] = {'linear_x': msg.linear.x, 'angular_z': msg.angular.z}

    def on_pump_cmd(self, msg: Bool):
        with self.state_lock:
            self.state['pump_on'] = msg.data

    def on_pump_state(self, msg: Bool):
        with self.state_lock:
            self.state['pump_state'] = msg.data

    def on_led_state(self, msg: ColorRGBA):
        with self.state_lock:
            self.state['led_state'] = {'r': msg.r, 'g': msg.g, 'b': msg.b}

    def on_auto_mode(self, msg: Bool):
        with self.state_lock:
            self.state['auto_mode'] = msg.data

    def snapshot(self):
        with self.state_lock:
            return dict(self.state)

    def publish_led(self, r: float, g: float, b: float):
        msg = ColorRGBA()
        msg.r, msg.g, msg.b, msg.a = r, g, b, 1.0
        self.led_pub.publish(msg)


def create_app(node: GuiMainNode) -> Flask:
    # 대시보드(INDEX_HTML)가 참조하는 배/물고기/쓰레기 이미지 에셋은 web/에 설치되어 있고,
    # static_url_path=''라서 "lake.png" 같은 상대 경로 그대로 루트에서 서빙된다.
    web_dir = get_package_share_directory('usv_gcs') + '/web'
    app = Flask(__name__, static_folder=web_dir, static_url_path='')

    @app.get('/')
    def index():
        return INDEX_HTML

    @app.get('/api/state')
    def api_state():
        state = node.snapshot()
        state['battery_warning_pct'] = BATTERY_WARNING_PCT
        return jsonify(state)

    @app.post('/api/led')
    def api_led():
        payload = request.get_json(force=True, silent=True) or {}
        node.publish_led(
            float(payload.get('r', 0.0)),
            float(payload.get('g', 0.0)),
            float(payload.get('b', 0.0)),
        )
        return jsonify({'ok': True})

    return app


def main(args=None):
    rclpy.init(args=args)
    node = GuiMainNode()

    http_port = node.get_parameter('http_port').value
    app = create_app(node)
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=http_port, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
