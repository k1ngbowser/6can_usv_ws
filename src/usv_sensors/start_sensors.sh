#!/bin/bash
set -euo pipefail

# B1 보드(UNO Q)에서 usv_sensors(water_quality_node + gps_driver_node + camera_node)를
# Docker 컨테이너로 띄우는 스크립트. gps_and_water_quality_and_ros/start_water_quality.sh를
# 기반으로 만들었다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${USV_SENSORS_PROJECT_DIR:-$SCRIPT_DIR}"
CONTAINER_NAME="usv_sensors_container"
IMAGE_NAME="usv_sensors_image"

cd "$PROJECT_DIR"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "[0] Docker image missing; building it..."
    docker build -t "$IMAGE_NAME" "$PROJECT_DIR"
fi

echo "[1] Starting Arduino App (water_quality + GPS sketch)..."
arduino-app-cli app start user:usv_sensors

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

echo "[4] Starting ROS 2 container (usv_sensors)..."
# --privileged -v /dev:/dev: camera_node가 USB 카메라(/dev/videoN)에 접근하기 위해 필요.
# README.md 0항의 Docker 필수 조건(--privileged / -v /dev:/dev 등 디바이스 마운트 적용)을 그대로 반영.
# 소스를 바인드 마운트하고 컨테이너 시작 시 다시 빌드해서, 이미지 재빌드 없이
# 코드 수정을 바로 반영할 수 있게 한다 (gps_and_water_quality_and_ros와 동일 패턴).
# --packages-select usv_sensors: 이 보드(B1)에는 usv_sensors만 올라가므로 워크스페이스에
# 다른 패키지가 섞여 있어도 그것까지 같이 빌드하지 않는다.
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    --restart unless-stopped \
    --privileged \
    -e ROS_DOMAIN_ID=0 \
    -v /dev:/dev \
    -v /var/run/arduino-router.sock:/var/run/arduino-router.sock \
    -v "$PROJECT_DIR:/ros2_ws/src/usv_sensors" \
    "$IMAGE_NAME" \
    bash -c '
        source /opt/ros/jazzy/setup.bash
        cd /ros2_ws
        colcon build --symlink-install --packages-select usv_sensors
        source /ros2_ws/install/setup.bash
        ros2 launch usv_sensors sensors.launch.py
    '

echo "[5] usv_sensors nodes started (water_quality_node, gps_driver_node, camera_node)."
