#!/bin/bash
set -euo pipefail

# B1 보드(UNO Q)에서 camera_streaming(camera_node + http_video_server)을
# Docker 컨테이너로 띄우는 스크립트. usv_sensors/start_sensors.sh와 같은 패턴.
#
# usv_sensors와 달리 Arduino MCU(Arduino_RouterBridge)를 전혀 거치지 않는다 -
# 카메라는 USB(V4L2)로 Linux에서 직접 잡으므로 arduino-router 소켓 대기 단계가 없다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CAMERA_STREAMING_PROJECT_DIR:-$SCRIPT_DIR}"
CONTAINER_NAME="camera_streaming_container"
IMAGE_NAME="camera_streaming_image"

cd "$PROJECT_DIR"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "[0] Docker image missing; building it..."
    docker build -t "$IMAGE_NAME" "$PROJECT_DIR"
fi

echo "[1] Removing old ROS container..."
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[2] Starting ROS 2 container (camera_streaming)..."
# --privileged -v /dev:/dev: camera_node가 USB 카메라(/dev/videoN)에 접근하기 위해 필요.
# README.md 0항의 Docker 필수 조건(--privileged / -v /dev:/dev 등 디바이스 마운트 적용)을 그대로 반영.
# 소스를 바인드 마운트하고 컨테이너 시작 시 다시 빌드해서, 이미지 재빌드 없이
# 코드 수정을 바로 반영할 수 있게 한다 (usv_sensors/start_sensors.sh와 동일 패턴).
# --packages-select camera_streaming: 이 보드(B1)에는 usv_sensors, camera_streaming
# 두 컨테이너가 같이 뜨지만, 각 컨테이너는 자기 패키지만 선택 빌드한다.
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    --restart unless-stopped \
    --privileged \
    -e ROS_DOMAIN_ID=0 \
    -v /dev:/dev \
    -v "$PROJECT_DIR:/ros2_ws/src/camera_streaming" \
    "$IMAGE_NAME" \
    bash -c '
        source /opt/ros/jazzy/setup.bash
        cd /ros2_ws
        colcon build --symlink-install --packages-select camera_streaming
        source /ros2_ws/install/setup.bash
        ros2 launch camera_streaming camera_streaming.launch.py
    '

echo "[3] camera_streaming nodes started (camera_node, http_video_server, HTTP :8000)."
