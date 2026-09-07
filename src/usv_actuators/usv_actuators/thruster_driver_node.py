#!/usr/bin/env python3
"""thruster_driver_node — usv_actuators 패키지 (B2 보드).

구독: /cmd_vel [geometry_msgs/msg/Twist]
Direct Bridge RPC 호출 방식으로 MCU 스케치('set_thruster_pwm') 직접 제어.
"""

import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

from .bridge import Bridge
from .telemetry import bounded_integer

NEUTRAL_PWM = 1487
DEADBAND = 35
MAX_DELTA = 10
STEP_US = 150
REVERSE_PAUSE = 0.3


class ThrusterDriverNode(Node):

    def __init__(self):
        super().__init__('thruster_driver_node')

        self.cmd_sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.on_cmd_vel,
            10
        )

        self.cur_left = NEUTRAL_PWM
        self.cur_right = NEUTRAL_PWM
        self.hold_until = 0.0

        self.target_left = NEUTRAL_PWM
        self.target_right = NEUTRAL_PWM

        # 20Hz (0.05초) 타이머로 Ramp 및 self.get_logger().info(f'SEND L={self.cur_left} R={self.cur_right}')
        self.timer = self.create_timer(0.05, self.control_loop)

        self.get_logger().info('Thruster Driver Node Started (Direct Bridge RPC Mode)')

    def on_cmd_vel(self, msg: Twist):
        linear = max(-1.0, min(1.0, msg.linear.x))
        angular = max(-1.0, min(1.0, msg.angular.z))

        left_raw = linear - angular
        right_raw = linear + angular

        scale = max(1.0, abs(left_raw), abs(right_raw))
        left_norm = left_raw / scale
        right_norm = right_raw / scale

        self.target_left = self.calc_pwm(left_norm)
        self.target_right = self.calc_pwm(right_norm)
        self.get_logger().info(f'linear={linear} angular={angular} tL={self.target_left} tR={self.target_right}')

    def calc_pwm(self, val: float) -> int:
        if abs(val) < 0.01:
            return NEUTRAL_PWM

        delta = bounded_integer(round(val * MAX_DELTA), -MAX_DELTA, MAX_DELTA)

        if delta > 0:
            return NEUTRAL_PWM + DEADBAND + delta
        elif delta < 0:
            return NEUTRAL_PWM - DEADBAND + delta
        else:
            return NEUTRAL_PWM

    @staticmethod
    def sign(v: int) -> int:
        if v > NEUTRAL_PWM: return 1
        if v < NEUTRAL_PWM: return -1
        return 0

    def ramp(self, cur: int, target: int) -> int:
        if abs(target - NEUTRAL_PWM) <= abs(cur - NEUTRAL_PWM):
            return target
        if target > cur:
            return min(target, cur + STEP_US)
        else:
            return max(target, cur - STEP_US)

    def control_loop(self):
        now = time.time()

        if (self.sign(self.target_left) * self.sign(self.cur_left) < 0 or
                self.sign(self.target_right) * self.sign(self.cur_right) < 0):
            if self.hold_until < now:
                self.hold_until = now + REVERSE_PAUSE
            self.cur_left = NEUTRAL_PWM
            self.cur_right = NEUTRAL_PWM
        elif self.hold_until > now:
            self.cur_left = NEUTRAL_PWM
            self.cur_right = NEUTRAL_PWM
        else:
            self.cur_left = self.ramp(self.cur_left, self.target_left)
            self.cur_right = self.ramp(self.cur_right, self.target_right)

        try:
            self.get_logger().info(f'SEND L={self.cur_left} R={self.cur_right}')
            Bridge.notify('set_thruster_pwm', self.cur_left, self.cur_right)
        except Exception as error:
            self.get_logger().warning(f'Thruster Bridge RPC error: {error}')


def main(args=None):
    rclpy.init(args=args)
    node = ThrusterDriverNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            self.get_logger().info(f'SEND L={self.cur_left} R={self.cur_right}')
            Bridge.notify('set_thruster_pwm', NEUTRAL_PWM, NEUTRAL_PWM)
        except Exception:
            pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
