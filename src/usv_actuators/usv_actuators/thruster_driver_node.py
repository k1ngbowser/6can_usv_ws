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


# ============================================================
# Thruster 설정
# ============================================================

NEUTRAL_PWM = 1487

# ESC deadband
DEADBAND = 35

# 최대 출력 변화량
MAX_DELTA = 50

# PWM ramp
STEP_US = 150

# 정/역방향 전환 시 중립 유지 시간
REVERSE_PAUSE = 0.3

# /cmd_vel timeout
CMD_TIMEOUT = 0.5


# ============================================================
# 추진기 방향 설정
#
# 중요:
# LEFT  = CCW 추진기
# RIGHT = CW 추진기
#
# 현재 문제 해결을 위해:
#   왼쪽은 정상 방향
#   오른쪽만 PWM 방향 반전
# ============================================================

LEFT_REVERSED = False
RIGHT_REVERSED = True


class ThrusterDriverNode(Node):

    def __init__(self):
        super().__init__('thruster_driver_node')

        # ----------------------------------------------------
        # /cmd_vel subscriber
        # ----------------------------------------------------
        self.cmd_sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.on_cmd_vel,
            10
        )

        # 현재 PWM
        self.cur_left = NEUTRAL_PWM
        self.cur_right = NEUTRAL_PWM

        # 목표 PWM
        self.target_left = NEUTRAL_PWM
        self.target_right = NEUTRAL_PWM

        # 정/역방향 변경 시 중립 유지
        self.hold_until = 0.0

        # 마지막 명령 수신 시간
        self.last_cmd_time = time.monotonic()

        # 20 Hz control loop
        self.timer = self.create_timer(
            0.05,
            self.control_loop
        )

        self.get_logger().info(
            'Thruster Driver Node Started '
            '(Direct Bridge RPC Mode)'
        )

        self.get_logger().info(
            f'Thruster direction: '
            f'LEFT_REVERSED={LEFT_REVERSED}, '
            f'RIGHT_REVERSED={RIGHT_REVERSED}'
        )

    # ========================================================
    # /cmd_vel callback
    # ========================================================

    def on_cmd_vel(self, msg: Twist):

        self.last_cmd_time = time.monotonic()

        # ----------------------------------------------------
        # 입력 범위 제한
        # ----------------------------------------------------
        linear = max(
            -1.0,
            min(1.0, msg.linear.x)
        )

        angular = max(
            -1.0,
            min(1.0, msg.angular.z)
        )

        # ----------------------------------------------------
        # Differential thrust mixing
        #
        # 전진:
        # linear > 0, angular = 0
        #
        # 좌회전 / 우회전:
        # angular 값으로 좌우 출력 차등
        # ----------------------------------------------------
        left_raw = linear - angular
        right_raw = linear + angular

        # ----------------------------------------------------
        # -1.0 ~ +1.0 범위로 정규화
        # ----------------------------------------------------
        scale = max(
            1.0,
            abs(left_raw),
            abs(right_raw)
        )

        left_norm = left_raw / scale
        right_norm = right_raw / scale

        # ----------------------------------------------------
        # 기본 PWM 계산
        # ----------------------------------------------------
        left_pwm = self.calc_pwm(left_norm)
        right_pwm = self.calc_pwm(right_norm)

        # ----------------------------------------------------
        # 추진기 장착 방향 보정
        #
        # LEFT(CCW)  : 그대로
        # RIGHT(CW)  : PWM 반전
        # ----------------------------------------------------
        self.target_left = self.apply_direction(
            left_pwm,
            LEFT_REVERSED
        )

        self.target_right = self.apply_direction(
            right_pwm,
            RIGHT_REVERSED
        )

        self.get_logger().info(
            f'CMD '
            f'linear={linear:.2f} '
            f'angular={angular:.2f} '
            f'| raw L={left_pwm} R={right_pwm} '
            f'| target L={self.target_left} '
            f'R={self.target_right}'
        )

    # ========================================================
    # 입력값 -> PWM
    # ========================================================

    def calc_pwm(self, val: float) -> int:

        # 거의 0이면 중립
        if abs(val) < 0.01:
            return NEUTRAL_PWM

        delta = bounded_integer(
            round(val * MAX_DELTA),
            -MAX_DELTA,
            MAX_DELTA
        )

        # 전진
        if delta > 0:
            return (
                NEUTRAL_PWM
                + DEADBAND
                + delta
            )

        # 후진
        elif delta < 0:
            return (
                NEUTRAL_PWM
                - DEADBAND
                + delta
            )

        return NEUTRAL_PWM

    # ========================================================
    # PWM 방향 반전
    #
    # 예:
    #
    # 1487 기준
    #
    # 1572 -> 1402
    # 1402 -> 1572
    # ========================================================

    @staticmethod
    def reverse_pwm(us: int) -> int:
        return NEUTRAL_PWM - (us - NEUTRAL_PWM)

    # ========================================================
    # 개별 추진기 방향 설정
    # ========================================================

    def apply_direction(
        self,
        pwm: int,
        reversed_: bool
    ) -> int:

        if reversed_:
            return self.reverse_pwm(pwm)

        return pwm

    # ========================================================
    # 현재 PWM 방향 확인
    # ========================================================

    @staticmethod
    def sign(v: int) -> int:

        if v > NEUTRAL_PWM:
            return 1

        if v < NEUTRAL_PWM:
            return -1

        return 0

    # ========================================================
    # PWM ramp
    # ========================================================

    def ramp(
        self,
        cur: int,
        target: int
    ) -> int:

        # 출력 줄이는 경우 즉시 적용
        if (
            abs(target - NEUTRAL_PWM)
            <=
            abs(cur - NEUTRAL_PWM)
        ):
            return target

        # 출력 증가
        if target > cur:
            return min(
                target,
                cur + STEP_US
            )

        return max(
            target,
            cur - STEP_US
        )

    # ========================================================
    # 20 Hz control loop
    # ========================================================

    def control_loop(self):

        now = time.monotonic()

        # ----------------------------------------------------
        # /cmd_vel failsafe
        # ----------------------------------------------------
        if (
            now - self.last_cmd_time
            > CMD_TIMEOUT
        ):
            self.target_left = NEUTRAL_PWM
            self.target_right = NEUTRAL_PWM

        # ----------------------------------------------------
        # 정방향 <-> 역방향 변경 감지
        #
        # 바로 반대 방향으로 돌리지 않고
        # 잠깐 neutral 유지
        # ----------------------------------------------------
        direction_changed = (
            self.sign(self.target_left)
            * self.sign(self.cur_left)
            < 0
            or
            self.sign(self.target_right)
            * self.sign(self.cur_right)
            < 0
        )

        if direction_changed:

            if self.hold_until < now:
                self.hold_until = (
                    now + REVERSE_PAUSE
                )

            self.cur_left = NEUTRAL_PWM
            self.cur_right = NEUTRAL_PWM

        # ----------------------------------------------------
        # reverse pause 중
        # ----------------------------------------------------
        elif self.hold_until > now:

            self.cur_left = NEUTRAL_PWM
            self.cur_right = NEUTRAL_PWM

        # ----------------------------------------------------
        # 정상 PWM 적용
        # ----------------------------------------------------
        else:

            self.cur_left = self.ramp(
                self.cur_left,
                self.target_left
            )

            self.cur_right = self.ramp(
                self.cur_right,
                self.target_right
            )

        # ----------------------------------------------------
        # UNO Q MCU로 전송
        # ----------------------------------------------------
        try:

            self.get_logger().info(
                f'SEND '
                f'L={self.cur_left} '
                f'R={self.cur_right}'
            )

            Bridge.notify(
                'set_thruster_pwm',
                self.cur_left,
                self.cur_right
            )

        except Exception as error:

            self.get_logger().warning(
                f'Thruster Bridge RPC error: '
                f'{error}'
            )


# ============================================================
# main
# ============================================================

def main(args=None):

    rclpy.init(args=args)

    node = ThrusterDriverNode()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        pass

    finally:

        # ----------------------------------------------------
        # 종료 시 반드시 중립
        # ----------------------------------------------------
        try:

            node.get_logger().info(
                'SEND L=NEUTRAL R=NEUTRAL '
                '(shutdown)'
            )

            Bridge.notify(
                'set_thruster_pwm',
                NEUTRAL_PWM,
                NEUTRAL_PWM
            )

        except Exception:
            pass

        node.destroy_node()

        rclpy.shutdown()


if __name__ == '__main__':
    main()
