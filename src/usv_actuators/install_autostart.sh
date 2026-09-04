#!/bin/bash
set -euo pipefail

# gps_and_water_quality_and_ros/install_autostart.sh와 동일한 패턴.
# sudo를 이 스크립트 자체에 붙이지 말 것 — 현재 사용자를 서비스 실행 계정으로 저장하고,
# 필요한 설정 명령에만 내부적으로 sudo를 사용한다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SOURCE="$SCRIPT_DIR/systemd/usv-actuators.service"
SERVICE_TARGET="/etc/systemd/system/usv-actuators.service"

if [ "${EUID}" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi

RUN_USER="${SUDO_USER:-$(id -un)}"
RUN_GROUP="$(id -gn "$RUN_USER")"
HOME_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)"

escaped_project_dir=${SCRIPT_DIR//&/\\&}
escaped_project_dir=${escaped_project_dir//|/\\|}
escaped_home_dir=${HOME_DIR//&/\\&}
escaped_home_dir=${escaped_home_dir//|/\\|}
sed \
    -e "s|@PROJECT_DIR@|$escaped_project_dir|g" \
    -e "s|@RUN_USER@|$RUN_USER|g" \
    -e "s|@RUN_GROUP@|$RUN_GROUP|g" \
    -e "s|@HOME_DIR@|$escaped_home_dir|g" \
    "$SERVICE_SOURCE" \
    | "${SUDO[@]}" tee "$SERVICE_TARGET" >/dev/null

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable --now usv-actuators.service

echo "Autostart installed: usv-actuators.service"
echo "Check status with: sudo systemctl status usv-actuators.service"
