"""actuator_driver_node — usv_actuators 패키지 (B2 보드).

구독:
  /water_quality/data [std_msgs/msg/String]    B1의 수질 JSON (자동 제어용)
  /actuator/pump_cmd  [std_msgs/msg/Bool]      GCS 수동 명령 — 분수 펌프 on/off
  /actuator/led_cmd   [std_msgs/msg/ColorRGBA] GCS 수동 명령 — RGB LED 색상
  /actuator/auto_mode [std_msgs/msg/Bool]      joy_to_cmd_node가 조이스틱 버튼으로 발행하는
                                                 자동/수동 토글
발행:
  /actuator/pump_state [std_msgs/msg/Bool]      실제로 적용된 펌프 상태 (GCS 표시용)
  /actuator/led_state  [std_msgs/msg/ColorRGBA] 실제로 적용된 LED 색상 (GCS 표시용)

수질에 따라 분수 펌프와 RGB LED를 자동 제어하되, 사람이 GCS에서 버튼을 누르면
그쪽을 우선한다. 자동 입력(/water_quality/data)과 수동 입력(/actuator/*_cmd)이
서로 다른 토픽으로 도착하므로 어느 쪽이 보낸 명령인지 구분할 수 있다.

수동 명령이 오면 pump_manual_hold_s / led_manual_hold_s 동안 자동을 억제하고,
그 시간이 지나면 자동이 다시 판단한다. "단계가 바뀔 때만 개입"으로 하면 물이
계속 나쁠 때 사람이 끄고 잊어버린 펌프가 영영 안 켜지기 때문이다.

자동 제어가 GCS의 마지막 명령을 덮어쓸 수 있어서, /actuator/pump_cmd·led_cmd(명령)만
보면 GCS가 실제 상태를 알 수 없다. 그래서 이 노드가 실제로 적용한 값을
/actuator/pump_state·led_state로 따로 발행한다 (pump_cmd/led_cmd는 여전히 명령 전용).

/actuator/auto_mode는 발행자(joy_to_cmd_node)가 없어도 자동=켬으로 동작하도록
기본값을 안전하게 잡아뒀다.

주의: 여기서 말하는 LED는 B2 보드에 물리적으로 배선된, 분수 펌프 옆의 별도 RGB
LED 조명이다. UNO Q 보드 자체의 내장 상태표시 LED와는 다른 하드웨어다.

배터리 계측 역할은 이 노드에 없다. 전류 센서 4개가 전부 B1 보드에 물려있어서
usv_sensors의 current_sensor_node가 /battery/status로 통합 발행한다.

TODO(하드웨어 확정 필요): 펌프 릴레이/LED 드라이버 배선이 아직 없어서 MCU RPC
메서드 이름(set_pump, set_actuator_led)은 임시로 정한 것이다. Arduino 스케치 쪽에
해당 RPC 핸들러를 구현해야 실제로 동작한다.
"""

import json

import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool
from std_msgs.msg import ColorRGBA
from std_msgs.msg import String

from . import water_policy
from .bridge import Bridge
from .telemetry import bounded_integer


class ActuatorDriverNode(Node):

    def __init__(self):
        super().__init__('actuator_driver_node')

        # 전부 launch 인자로 조정 가능하다. 실제 수조에서 clarity_pct가 어느 범위로
        # 나오는지 보고 코드 수정 없이 튜닝하기 위한 것.
        self.declare_parameter('bad_below', 40.0)
        self.declare_parameter('good_above', 60.0)
        self.declare_parameter('margin', 3.0)
        self.declare_parameter('pump_manual_hold_s', 60.0)
        self.declare_parameter('led_manual_hold_s', 60.0)
        self.declare_parameter('stale_timeout_s', 5.0)

        # 자동 제어 입력 (B1) — 구독만 하므로 B1 쪽은 아무것도 바뀌지 않는다
        self.create_subscription(String, '/water_quality/data', self.on_water_quality, 10)

        # 수동 명령 (GCS) — 토픽 이름·타입 기존 계약 그대로
        self.create_subscription(Bool, '/actuator/pump_cmd', self.on_pump_cmd, 10)
        self.create_subscription(ColorRGBA, '/actuator/led_cmd', self.on_led_cmd, 10)

        # joy_to_cmd_node가 조이스틱 버튼으로 발행. 발행자가 아예 없으면(구버전 GCS 등)
        # 자동=켬으로 동작한다.
        self.create_subscription(Bool, '/actuator/auto_mode', self.on_auto_mode, 10)

        # GCS가 표시용으로 구독하는 실제 적용 상태. 자동 제어가 GCS의 마지막 명령을
        # 덮어쓸 수 있으므로, /actuator/pump_cmd·led_cmd(명령)만으로는 실제로 지금
        # 뭐가 켜져 있는지 GCS가 알 수 없다.
        self.pump_state_pub = self.create_publisher(Bool, '/actuator/pump_state', 10)
        self.led_state_pub = self.create_publisher(ColorRGBA, '/actuator/led_state', 10)

        self.auto_enabled = True
        self.stage = None
        self.applied_pump = None      # MCU에 마지막으로 보낸 값
        self.applied_led = None
        self.pump_hold_until = 0.0    # 이 시각까지는 수동 명령이 우선
        self.led_hold_until = 0.0
        self.last_quality_at = None

        self.create_timer(1.0, self.on_tick)

        self.get_logger().info('Actuator driver node started')

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    # ------------------------------------------------------------------
    # 수동 명령 (GCS)
    # ------------------------------------------------------------------

    def on_pump_cmd(self, msg: Bool):
        hold = self.get_parameter('pump_manual_hold_s').value
        self.pump_hold_until = self.now() + hold
        self.get_logger().info(
            f'수동 펌프 {"ON" if msg.data else "OFF"} ({hold:.0f}초간 자동 억제)')
        self.send_pump(bool(msg.data))

    def on_led_cmd(self, msg: ColorRGBA):
        hold = self.get_parameter('led_manual_hold_s').value
        self.led_hold_until = self.now() + hold
        self.get_logger().info(f'수동 LED 지정 ({hold:.0f}초간 자동 억제)')
        self.send_led(msg.r, msg.g, msg.b)

    def on_auto_mode(self, msg: Bool):
        if bool(msg.data) == self.auto_enabled:
            return

        self.auto_enabled = bool(msg.data)
        # 자동으로 돌아올 때 단계를 초기화한다. 안 하면 수동으로 있는 동안 수질이
        # 바뀌었어도 단계 변수가 그대로라 자동이 개입하지 않는다.
        self.stage = None
        self.get_logger().info(f'{"자동" if msg.data else "수동"} 모드로 전환')

    # ------------------------------------------------------------------
    # 자동 제어 (B1 수질)
    # ------------------------------------------------------------------

    def on_water_quality(self, msg: String):
        try:
            clarity = json.loads(msg.data).get('clarity_pct')
        except (ValueError, TypeError) as error:
            self.get_logger().warning(f'수질 JSON 파싱 실패: {error}')
            return

        if clarity is None:
            return

        self.last_quality_at = self.now()

        if not self.auto_enabled:
            return

        stage = water_policy.classify(
            float(clarity),
            self.stage,
            self.get_parameter('bad_below').value,
            self.get_parameter('good_above').value,
            self.get_parameter('margin').value,
        )

        if stage != self.stage:
            self.get_logger().info(f'수질 {float(clarity):.1f}% → {stage}')
            self.stage = stage

        now = self.now()
        if now >= self.pump_hold_until:
            self.send_pump(water_policy.pump_for(stage))
        if now >= self.led_hold_until:
            self.send_led(*water_policy.color_for(stage))

    def on_tick(self):
        """수질 데이터가 끊기면 펌프를 끈다.

        B1이 죽거나 Wi-Fi가 끊겼는데 펌프가 켜진 채로 방치되면 배터리만 축난다.
        단, 사람이 방금 켠 펌프를 두절 감지가 꺼버리면 안 되므로 수동 억제 중에는
        건드리지 않는다.
        """
        if self.last_quality_at is None or not self.auto_enabled:
            return

        if self.now() < self.pump_hold_until:
            return

        elapsed = self.now() - self.last_quality_at
        if elapsed > self.get_parameter('stale_timeout_s').value and self.applied_pump:
            self.get_logger().warning(f'수질 데이터 {elapsed:.1f}s 두절 — 펌프 정지')
            self.send_pump(False)

    # ------------------------------------------------------------------
    # MCU 전달 — 값이 바뀔 때만 보낸다
    # ------------------------------------------------------------------

    def send_pump(self, on: bool):
        if self.applied_pump == on:
            return

        try:
            # TODO(B2 담당자): 'set_pump'은 임시 RPC 이름. 실제 릴레이 제어 스케치의
            # 핸들러 이름에 맞춰 확인·수정할 것.
            Bridge.notify('set_pump', on)
        except Exception as error:
            self.get_logger().warning(f'Pump Bridge error: {error}')
            return

        self.applied_pump = on
        state_msg = Bool()
        state_msg.data = on
        self.pump_state_pub.publish(state_msg)

    def send_led(self, r, g, b):
        rgb = (
            bounded_integer(round(r * 255), 0, 255),
            bounded_integer(round(g * 255), 0, 255),
            bounded_integer(round(b * 255), 0, 255),
        )

        if self.applied_led == rgb:
            return

        try:
            # TODO(B2 담당자): 'set_actuator_led'는 임시 RPC 이름. 실제 LED 드라이버
            # 배선(공통 애노드/캐소드 등)에 따라 값 반전이 필요할 수 있음.
            Bridge.notify('set_actuator_led', *rgb)
        except Exception as error:
            self.get_logger().warning(f'LED Bridge error: {error}')
            return

        self.applied_led = rgb
        state_msg = ColorRGBA()
        state_msg.r, state_msg.g, state_msg.b = (v / 255.0 for v in rgb)
        state_msg.a = 1.0
        self.led_state_pub.publish(state_msg)


def main(args=None):
    rclpy.init(args=args)
    node = ActuatorDriverNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
