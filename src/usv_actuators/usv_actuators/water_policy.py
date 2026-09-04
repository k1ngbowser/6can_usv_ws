"""수질 판정 규칙 — ROS와 무관한 순수 계산.

actuator_driver_node가 가져다 쓴다. 여기에 ROS를 넣지 않는 이유는 보드 없이
노트북에서도 규칙을 검증할 수 있게 하기 위해서다.

3단계 판정 기준 (clarity_pct 0~100, 클수록 깨끗):

    좋음  clarity_pct >= 60   초록   펌프 OFF
    보통  40 <= clarity < 60  노랑   펌프 OFF
    나쁨  clarity_pct < 40    빨강   펌프 ON

B1 스케치가 계산해서 보내주는 clarity_level(문자열 5단계)이 아니라 clarity_pct
숫자를 쓰는 이유는, 임계값을 이쪽에서 바꿀 수 있게 하기 위해서다. clarity_level을
쓰면 기준을 조정할 때마다 B1 담당자의 스케치를 고치고 MCU에 다시 업로드해야 한다.
"""

BAD = 'BAD'
NORMAL = 'NORMAL'
GOOD = 'GOOD'

# 단계별 LED 색 (r, g, b) — ColorRGBA와 같은 0.0~1.0 범위
STAGE_COLOR = {
    BAD: (1.0, 0.0, 0.0),      # 빨강
    NORMAL: (1.0, 1.0, 0.0),   # 노랑
    GOOD: (0.0, 1.0, 0.0),     # 초록
}

# 분수 펌프를 돌리는 단계
PUMP_ON_STAGES = frozenset({BAD})


def classify(clarity_pct, previous=None, bad_below=40.0, good_above=60.0, margin=3.0):
    """clarity_pct를 3단계로 나눈다.

    previous에 직전 단계를 넘기면 히스테리시스가 적용된다. 경계에서 측정값이
    39.8 <-> 40.2로 미세하게 흔들릴 때 펌프 릴레이가 1초마다 딸깍거리는 것을
    막기 위한 것으로, 한 번 어떤 단계에 들어가면 경계를 margin만큼 넘어야
    빠져나온다.
    """
    if previous == BAD:
        bad_below += margin       # 나쁨에서 나오려면 확실히 회복돼야 한다
    elif previous == GOOD:
        good_above -= margin      # 좋음에서 떨어지려면 확실히 나빠져야 한다

    if clarity_pct < bad_below:
        return BAD
    if clarity_pct >= good_above:
        return GOOD
    return NORMAL


def pump_for(stage):
    """해당 단계에서 펌프를 돌려야 하는가."""
    return stage in PUMP_ON_STAGES


def color_for(stage):
    """해당 단계의 LED 색 (r, g, b)."""
    return STAGE_COLOR[stage]
