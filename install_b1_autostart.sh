#!/bin/bash
set -euo pipefail

# B1 보드의 두 컨테이너(usv_sensors, camera_streaming) 자동 실행을 한 번에 등록한다.
# sudo를 이 스크립트 자체에 붙이지 말 것 - 각 install_autostart.sh가 알아서 처리한다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [1/2] usv-sensors.service ==="
"$SCRIPT_DIR/src/usv_sensors/install_autostart.sh"

echo "=== [2/2] camera-streaming.service ==="
"$SCRIPT_DIR/src/camera_streaming/install_autostart.sh"

echo "=== B1 보드 자동 실행 등록 완료 ==="
