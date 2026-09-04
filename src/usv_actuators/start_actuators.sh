#!/bin/bash
set -euo pipefail

# B2 보드(UNO Q)에서 usv_actuators(thruster_driver_node + actuator_driver_node)를
# Docker 컨테이너로 띄우는 스크립트. gps_and_water_quality_and_ros/start_water_quality.sh를
# 기반으로 만들었다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${USV_ACTUATORS_PROJECT_DIR:-$SCRIPT_DIR}"
CONTAINER_NAME="usv_actuators_container"
IMAGE_NAME="usv_actuators_image"

cd "$PROJECT_DIR"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "[0] Docker image missing; building it..."
    docker build -t "$IMAGE_NAME" "$PROJECT_DIR"
fi

echo "[1] Starting Arduino App (thruster + pump/LED sketch)..."
arduino-app-cli app start user:usv_actuators

echo "[2] Waiting for Arduino Router..."
for i in $(seq 1 30); do
    if [ -S /var/run/arduino-router.sock ]; then
        echo "Arduino Router ready."
        break
    fi
    sleep 1
done

if [ ! -S /var/run/arduino-router.sock ]; then
    echo "ERROR: Arduino Router socket not ready."
    exit 1
fi

echo "[3] Removing old ROS container..."
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[4] Starting ROS 2 container (usv_actuators)..."
# README.md 0항의 Docker 필수 조건(--privileged / -v /dev:/dev 등 디바이스 마운트 적용)을 그대로 반영.
# --packages-select usv_actuators: 이 보드(B2)에는 usv_actuators만 올라가므로 워크스페이스에
# 다른 패키지가 섞여 있어도 그것까지 같이 빌드하지 않는다.
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    --restart unless-stopped \
    --privileged \
    -e ROS_DOMAIN_ID=0 \
    -v /dev:/dev \
    -v /var/run/arduino-router.sock:/var/run/arduino-router.sock \
    -v "$PROJECT_DIR:/ros2_ws/src/usv_actuators" \
    "$IMAGE_NAME" \
    bash -c '
        source /opt/ros/jazzy/setup.bash
        cd /ros2_ws
        colcon build --symlink-install --packages-select usv_actuators
        source /ros2_ws/install/setup.bash
        ros2 launch usv_actuators actuators.launch.py
    '

echo "[5] usv_actuators nodes started (thruster_driver_node, actuator_driver_node)."
