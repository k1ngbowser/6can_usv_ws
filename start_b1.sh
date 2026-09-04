#!/bin/bash
set -euo pipefail

# B1 보드(UNO Q)를 한 번에 띄우는 진입점.
#
# B1은 지금 두 개의 독립된 Docker 컨테이너로 구성된다:
#   - usv_sensors (water_quality_node, gps_driver_node, current_sensor_node)
#   - camera_streaming (camera_node, http_video_server - 카메라만 별도 컨테이너인 이유는
#     CAMERA_STREAMING.md에 있는 디스크 용량 제약 때문. 두 컨테이너는 서로 다른
#     이름/이미지를 쓰고 --network host로 같은 ROS_DOMAIN_ID를 공유하므로 충돌하지 않는다.)
#
# 이 스크립트는 두 컨테이너를 순서대로 띄우기만 하고, 각 패키지의 내부 구조/컨테이너
# 분리 자체는 건드리지 않는다 - B1 보드에서 실행할 때 명령 하나로 끝내기 위한
# 오케스트레이션 레이어일 뿐이다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [1/2] usv_sensors ==="
"$SCRIPT_DIR/src/usv_sensors/start_sensors.sh"

echo "=== [2/2] camera_streaming ==="
"$SCRIPT_DIR/src/camera_streaming/start_camera_streaming.sh"

echo "=== B1 보드 기동 완료: usv_sensors_container, camera_streaming_container ==="
echo "확인: docker ps --filter name=usv_sensors_container --filter name=camera_streaming_container"
