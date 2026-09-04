#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from std_msgs.msg import Header


class JoyToCmdNode(Node):
    def __init__(self):
        super().__init__('joy_to_cmd_node')

        # --- Parameters (팀 논의 후 조정) ---
        self.declare_parameter('linear_axis', 1)      # 전후진 축 번호
        self.declare_parameter('angular_axis', 0)     # 좌우 회전 축 번호
        self.declare_parameter('linear_scale', 1.0)    # m/s
        self.declare_parameter('angular_scale', 1.0)   # rad/s
        self.declare_parameter('deadzone', 0.05)
        # 펌프/워터캐논 작동 버튼 번호. 조종은 조이스틱 하나로만 하므로(마우스로 GUI
        # 버튼을 누를 사람이 없음) 여기서 발행한다. 0번(Xbox 계열 컨트롤러 기준 A 버튼)으로
        # 확정. 실제 조이스틱에서 다르게 나오면 코드는 그대로 두고 pump_button 인자만
        # 바꾸면 됨.
        self.declare_parameter('pump_button', 0)
        # 자동/수동 제어 토글 버튼 번호. 마우스로 GUI 체크박스를 누를 사람이 없으므로
        # pump_button과 동일한 패턴으로 여기서 토글 발행한다. 실제 버튼 배정은 팀 논의 후
        # 확정 필요 - 임시로 1번(Xbox 계열 기준 B 버튼) 지정.
        self.declare_parameter('auto_button', 1)
        self.declare_parameter('enable_heartbeat', False)   # /gcs/heartbeat 발행 여부 - 설계 미확정, 팀 논의 후 True로 전환
        self.declare_parameter('heartbeat_period_sec', 0.5)  # watchdog timeout보다 충분히 짧게 설정 필요

        self.linear_axis = self.get_parameter('linear_axis').value
        self.angular_axis = self.get_parameter('angular_axis').value
        self.linear_scale = self.get_parameter('linear_scale').value
        self.angular_scale = self.get_parameter('angular_scale').value
        self.deadzone = self.get_parameter('deadzone').value
        self.pump_button = self.get_parameter('pump_button').value
        self.auto_button = self.get_parameter('auto_button').value
        self.enable_heartbeat = self.get_parameter('enable_heartbeat').value
        self.heartbeat_period_sec = self.get_parameter('heartbeat_period_sec').value

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.joy_sub = self.create_subscription(Joy, '/joy', self.joy_callback, qos)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', qos)
        # gui_main_node도 이 토픽을 구독해서 대시보드에 펌프 상태를 표시만 한다 (발행 X).
        self.pump_pub = self.create_publisher(Bool, '/actuator/pump_cmd', qos)
        # gui_main_node/B2 둘 다 이 토픽을 구독. gui_main_node는 표시만, B2는 이 값으로
        # 자동/수동을 나눈다 (발행 X, 여기서만 발행).
        self.auto_mode_pub = self.create_publisher(Bool, '/actuator/auto_mode', qos)

        self._last_joy_time = None

        # heartbeat: joy -> cmd_vel 경로가 살아있다는 신호. 발행 주체/주기는 아직 미확정이라
        # enable_heartbeat 파라미터로 켜고 끌 수 있게만 해둠 (기본 off).
        self.heartbeat_pub = None
        if self.enable_heartbeat:
            self.heartbeat_pub = self.create_publisher(Header, '/gcs/heartbeat', qos)
            self.heartbeat_timer = self.create_timer(
                self.heartbeat_period_sec, self.heartbeat_callback
            )

        self.get_logger().info('joy_to_cmd_node started')
        self.prev_pump_state = False # 이전 펌프 상태를 저장하여 버튼 상태 변화 감지용
        self.prev_auto_button_state = False  # 버튼 눌림 자체의 변화 감지용 (edge trigger)
        self.auto_mode = True  # 기본값: 자동 제어 켜짐

        # B2가 노드 시작 직후 켜져도 기본값을 바로 알 수 있도록 시작 시 한 번 발행.
        # (버튼을 누르기 전까지는 /joy 콜백이 안 돌아서 값이 안 나감)
        auto_msg = Bool()
        auto_msg.data = self.auto_mode
        self.auto_mode_pub.publish(auto_msg)

    def joy_callback(self, msg: Joy):
        self._last_joy_time = self.get_clock().now()

        twist = Twist()
        linear = msg.axes[self.linear_axis] if len(msg.axes) > self.linear_axis else 0.0
        angular = msg.axes[self.angular_axis] if len(msg.axes) > self.angular_axis else 0.0

        if abs(linear) < self.deadzone:
            linear = 0.0
        if abs(angular) < self.deadzone:
            angular = 0.0

        twist.linear.x = linear * self.linear_scale
        twist.angular.z = angular * self.angular_scale

        self.cmd_pub.publish(twist)

        if len(msg.buttons) > self.pump_button:
            new_state = bool(msg.buttons[self.pump_button])
            if new_state != self.prev_pump_state:
                pump_msg = Bool()
                pump_msg.data = new_state
                self.pump_pub.publish(pump_msg)
                self.prev_pump_state = new_state

        if len(msg.buttons) > self.auto_button:
            button_pressed = bool(msg.buttons[self.auto_button])
            if button_pressed and not self.prev_auto_button_state:
                # 버튼을 누르는 순간(edge)에만 토글 - 누르고 있는 동안 계속 뒤집히지 않게
                self.auto_mode = not self.auto_mode
                auto_msg = Bool()
                auto_msg.data = self.auto_mode
                self.auto_mode_pub.publish(auto_msg)
            self.prev_auto_button_state = button_pressed

    def heartbeat_callback(self):
        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = 'joy_to_cmd_node'
        self.heartbeat_pub.publish(header)


def main(args=None):
    rclpy.init(args=args)
    node = JoyToCmdNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
