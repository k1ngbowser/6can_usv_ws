# 🚤 6can_usv_project — 협업 템플릿

이 저장소는 아래 **"0. 시스템 요구사항"**에 맞춘 기본 뼈대(scaffolding)입니다. ROS 2 토픽 이름, 메시지 타입, 노드 구조, launch 파일은 이미 요구사항과 일치하도록 맞춰져 있습니다.

- 토픽 인터페이스(이름/타입)만 준수한다면 **내부 클래스 구조, 파일 분할, 알고리즘 구현은 담당자가 자유롭게 재구성**해도 괜찮습니다.
- 자리표시자는 전부 코드에 `TODO(B1 담당자):`, `TODO(B2 담당자):`, `TODO(GCS 담당자):` 주석으로 표시되어 있습니다.
- **아래 문자열을 그대로 복사해서 검색하세요** — "담당자" 자리에 본인 파트 이름을 넣지 마세요. 태그 자체가 고정된 문자열입니다.

```bash
# 전체 TODO 찾기
grep -rn "TODO(" usv_ws/src

# 담당자별로 찾기
grep -rn "TODO(B1 담당자):" usv_ws/src
grep -rn "TODO(B2 담당자):" usv_ws/src
grep -rn "TODO(GCS 담당자):" usv_ws/src
```

---

## ⚙️ 0. 시스템 요구사항

- **ROS 2 버전**: ROS 2 Jazzy Jalisco
  - 세 보드 모두 같은 `ROS_DOMAIN_ID` 사용 (Wi-Fi 기반 DDS 통신 — 도메인 ID가 다르면 서로 안 보임)
- **하드웨어 구성**
  - 지상 관제소(GCS): Raspberry Pi
  - 수상정(USV) 본체: Arduino UNO Q 2대 (B1, B2)
- **Docker 필수 조건**
  - **Arduino UNO Q에서 도는 모든 ROS 2 노드(B1, B2)는 Docker 컨테이너 환경에서 빌드·실행**
  - `--privileged`, `-v /dev:/dev` 등 디바이스 마운트 적용
  - GCS(Raspberry Pi)는 이 조건 대상 아님
- **이번 범위에서 제외한 것**
  - Failsafe 감시 노드(`watchdog_node`)와 heartbeat 패키지는 개발 범위에서 완전히 제외
  - 추진기 드라이버는 `/cmd_vel_safe`가 아니라 **`/cmd_vel`을 직접 구독**
- **GPS 진단 토픽 처리 규칙**
  - `gps_driver_node`의 `/gps/satellites`, `/gps/status` 발행 로직은 코드 안에 유지
  - GCS GUI는 이 두 토픽을 구독하지 않음
- **Arduino 스케치(`.ino`) 필요 여부**
  - Arduino UNO Q는 MCU(STM32)와 Linux가 분리되어 있어, UART·아날로그 핀처럼 물리적으로 MCU에 연결된 장치는 `Arduino_RouterBridge`를 거쳐야만 ROS 쪽에서 값을 받을 수 있음
  - **필요함**: `water_quality_node`, `gps_driver_node` → `usv_sensors/sketch/sketch.ino`에 이미 포함
  - **불필요함**: `camera_node`(USB 카메라, Linux에서 직접 처리), `usv_gcs`의 모든 노드(Raspberry Pi는 MCU/Bridge 구조 자체가 없음)
  - **미정**: `thruster_driver_node`, `actuator_driver_node`(B2) — 모터 드라이버가 MCU 핀에 직접 물리면 `.ino` 필요, I2C/USB 장치라면 순수 파이썬으로도 가능 (하드웨어 미확정, 4항 B2 체크리스트 참고)

---

## 🗺️ 1. 아키텍처 한눈에 보기

| 보드 | 패키지 | 담당 | 실행 환경 |
|---|---|---|---|
| B1 (Arduino UNO Q) | `usv_sensors` | 수질 · GPS · 카메라 | Docker 필수 |
| B2 (Arduino UNO Q) | `usv_actuators` | 추진기 · 펌프 · LED | Docker 필수 |
| GCS (Raspberry Pi) | `usv_gcs` | GUI · 조종 | 네이티브 (Docker 불필요) |

```
usv_ws/src/
├── usv_sensors/     # B1 — water_quality_node, gps_driver_node, camera_node
├── usv_actuators/   # B2 — thruster_driver_node, actuator_driver_node
└── usv_gcs/         # GCS — gui_main_node, joy_to_cmd_node
```

### 인터페이스 계약

아래 표가 이 프로젝트의 **인터페이스 계약**입니다.

- 토픽 이름/메시지 타입을 바꿔야 한다면 **이 표부터 고치고 팀 전체에 공유한 뒤** 코드를 맞추세요.
- 순서를 거꾸로 하면 안 됩니다 — 누군가 코드만 조용히 바꾸면 다른 파트의 구독/발행과 어긋납니다.

| 토픽 | 타입 | 발행 | 구독 |
|---|---|---|---|
| `/water_quality/data` | `std_msgs/msg/String` (JSON) | `usv_sensors` | `usv_gcs` |
| `/gps/fix` | `sensor_msgs/msg/NavSatFix` | `usv_sensors` | `usv_gcs` |
| `/gps/has_fix` | `std_msgs/msg/Bool` | `usv_sensors` | `usv_gcs` |
| `/gps/satellites`, `/gps/status` | `UInt8`, `String` | `usv_sensors` | 미구독 (진단용) |
| `/camera/surface/image_raw`, `/camera/underwater/image_raw` | `sensor_msgs/msg/Image` | `usv_sensors` | `web_video_server` → GCS 웹 UI |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | `usv_gcs` (joy_to_cmd_node) | `usv_actuators`, `usv_gcs` (내부 표시) |
| `/battery/status` | `std_msgs/msg/String` (JSON) | `usv_sensors` (current_sensor_node) | `usv_gcs` |
| `/actuator/pump_cmd` | `std_msgs/msg/Bool` | `usv_gcs` (joy_to_cmd_node) | `usv_actuators`, `usv_gcs` (내부 표시) |
| `/actuator/led_cmd` | `std_msgs/msg/ColorRGBA` | `usv_gcs` | `usv_actuators` |

`/battery/status`의 JSON 구조:

```json
{
  "thruster1":    {"current_a": 0.0, "percentage": 0},
  "thruster2":    {"current_a": 0.0, "percentage": 0},
  "pump_ctrl":    {"current_a": 0.0, "percentage": 0},
  "sensor_board": {"current_a": 0.0, "percentage": 0}
}
```

- 전류 센서 4개 모두 **물리적으로 B1 보드에 연결**되어 I2C 한 버스로 일괄 수신됩니다.
- `usv_actuators`(B2)는 더 이상 배터리를 직접 계측하지 않습니다 — `thruster_driver_node`, `actuator_driver_node`는 PWM/릴레이 제어 역할만 남았습니다.

### 노드 다이어그램

목표로 하는 **최종 구조**입니다 (진행 상황이 아닙니다 — 완료 여부는 4항 체크리스트 참고).

- **네모** = 노드
- **화살표 위 글자** = 토픽 이름
- **점선** = ROS 토픽이 아니거나(HTTP), GCS가 구독하지 않는 진단용 흐름

`watchdog_node` / `heartbeat` / `usv_teleop`는 0항에 따라 제외되어 다이어그램에도 없습니다.

```mermaid
flowchart LR
  JOY([조이스틱 하드웨어])
  BROWSER([웹 브라우저])
  DIAG[[진단용 · GCS 미구독]]

  subgraph GCS["usv_gcs · GCS / Raspberry Pi"]
    J2C[joy_to_cmd_node<br/>조이스틱 원격 제어]
    GUI[gui_main_node<br/>모니터링 및 제어 UI]
  end

  subgraph B1["usv_sensors · B1 · Arduino UNO Q"]
    WQN[water_quality_node<br/>수질 센서 통합 수집]
    GPSN[gps_driver_node<br/>GPS NMEA 파싱 및 측위]
    CAMN[camera_node<br/>USB 카메라 2대 영상 수집]
    WVS[web_video_server<br/>ROS → HTTP 변환기]
    CSN[current_sensor_node<br/>전류 센서 4개 통합 계측]
  end

  subgraph B2["usv_actuators · B2 · Arduino UNO Q"]
    THR[thruster_driver_node<br/>추진기 PWM 제어]
    ACT[actuator_driver_node<br/>펌프 릴레이 · RGB LED 제어]
  end

  JOY -->|/joy| J2C
  J2C -->|/cmd_vel| GUI
  J2C -->|/cmd_vel| THR
  J2C -->|/actuator/pump_cmd| GUI
  J2C -->|/actuator/pump_cmd| ACT

  WQN -->|/water_quality/data| GUI
  GPSN -->|/gps/fix| GUI
  GPSN -->|/gps/has_fix| GUI
  GPSN -.->|/gps/satellites, /gps/status| DIAG
  CSN -->|/battery/status| GUI

  CAMN -->|/camera/surface/image_raw| WVS
  CAMN -->|/camera/underwater/image_raw| WVS
  WVS -. HTTP MJPEG :8080 .-> BROWSER
  GUI -. HTTP :8000 대시보드 .-> BROWSER

  GUI -->|/actuator/led_cmd| ACT
```

---

## 🛠️ 2. 공통 준비 (모든 보드)

이 저장소는 `usv_sensors`(B1) / `usv_actuators`(B2) / `usv_gcs`(GCS) 3개 패키지를 한 워크스페이스에 모아둔 모노레포입니다. **보드 한 대에는 그 보드가 담당하는 패키지 1개만 올라가므로, 어느 보드에서도 워크스페이스 전체를 빌드하지 않습니다.** 클론은 전체 저장소를 받되, 빌드는 항상 3항의 보드별 안내를 따라 `--packages-select`로 해당 패키지만 선택 빌드하세요.

```bash
git clone <이 저장소>
cd usv_project/usv_ws
```

- B1 / B2(Arduino UNO Q): 소스만 받아두면 됩니다. 실제 빌드는 Docker 안에서 `start_sensors.sh` / `start_actuators.sh`가 대신 실행합니다 (3항 참고).
- GCS(Raspberry Pi): 3항의 GCS 절차대로 `usv_gcs`만 선택 빌드합니다.

---

## 🚀 3. 보드별 빌드 & 실행

### B1 — `usv_sensors` (Docker)

```bash
cd usv_ws/src/usv_sensors
pip install -r requirements.txt          # 이미지 안에서는 Dockerfile이 자동 처리
./start_sensors.sh                       # 이미지 빌드(최초 1회) → 컨테이너 실행
./install_autostart.sh                   # (선택) 부팅 시 자동 실행 등록
```

- 카메라 장치 번호는 명령줄로 넘기지 않습니다.
- `usv_ws/src/usv_sensors/config/sensors_params.yaml`의 `surface_device` / `underwater_device` 값을 실제 번호로 고치면 다음 실행부터 자동 반영됩니다.
- 빌드 범위: Docker 이미지 빌드(`Dockerfile`)와 컨테이너 기동(`start_sensors.sh`) 둘 다 `colcon build --packages-select usv_sensors`만 실행합니다 — 이 보드는 `usv_sensors` 외 다른 패키지를 빌드/실행할 필요가 없습니다.

### B2 — `usv_actuators` (Docker)

```bash
cd usv_ws/src/usv_actuators
./start_actuators.sh
./install_autostart.sh                   # (선택)
```

- 빌드 범위: Docker 이미지 빌드(`Dockerfile`)와 컨테이너 기동(`start_actuators.sh`) 둘 다 `colcon build --packages-select usv_actuators`만 실행합니다 — 이 보드는 `usv_actuators` 외 다른 패키지를 빌드/실행할 필요가 없습니다.

파라미터 오버라이드 예시 (모터 드라이버 PWM 범위 확정 후):

```bash
ros2 launch usv_actuators actuators.launch.py max_pwm:=180
```

### GCS — `usv_gcs` (Docker 불필요, Raspberry Pi 네이티브)

```bash
sudo apt install ros-jazzy-web-video-server ros-jazzy-joy
pip install -r usv_ws/src/usv_gcs/requirements.txt
cd usv_ws
colcon build --symlink-install --packages-select usv_gcs
source install/setup.bash
ros2 launch usv_gcs gcs.launch.py
```

- `--packages-select usv_gcs`: GCS(Raspberry Pi)는 `usv_gcs`만 실행하므로 워크스페이스에 있는 `usv_sensors` / `usv_actuators`는 빌드하지 않습니다 (그 두 패키지는 Arduino UNO Q 전용 의존성을 전제로 하며 GCS에는 설치돼 있지 않을 수 있습니다).
- 브라우저에서 `http://<GCS IP>:8000` 접속 시 대시보드가 뜹니다.

파라미터 오버라이드 예시 (조이스틱 축 확정 후):

```bash
ros2 launch usv_gcs gcs.launch.py linear_axis:=1 angular_axis:=0
```

---

## 📋 4. 파트별 작업 가이드

> 아래는 참고용 가이드입니다. **1항의 토픽 이름/메시지 타입(입출력)만 유지**하면, 내부 구현(파일 분할, 클래스 구조, 로직)은 담당자가 자유롭게 새로 짜도 됩니다. 체크리스트는 "확인해보면 좋은 것" 수준이며, 반드시 이 순서를 따라야 하는 건 아닙니다.

### B1 담당자 — `usv_sensors`

**이미 되어있는 것**

- `water_quality_node` — 기존 `gps_and_water_quality_and_ros`(`ros_led`)의 수질 센서 로직을 그대로 포팅. `/water_quality/data` 토픽 하나로 JSON 중계. **수정 불필요**
- `gps_driver_node` — 기존 `gps.py`를 거의 그대로 포팅. `/gps/fix`, `/gps/has_fix` 발행 포함. **수정 불필요**
- `camera_node` — OpenCV로 USB 카메라 2대를 열어 `sensor_msgs/Image` 발행. 구조 완성
- `sketch/sketch.ino`, `sketch/sketch.yaml` — 원래 레포의 아두이노 스케치(MCU에서 GPS UART + 수질 센서 핀을 읽고 `get_water_quality` / `get_gps` RPC 제공)를 그대로 복사
  - `start_sensors.sh`가 부팅 시 이 스케치를 MCU에 자동으로 빌드·업로드
  - **카메라 외에는 전원만 넣으면 GPS/수질 측정 → ROS 토픽 발행까지 자동으로 동작**

**참고할 만한 것** (자유롭게 바꿔도 됨)

- [ ] `config/sensors_params.yaml`의 `surface_device` / `underwater_device` 값(현재 0, 2) — 실제 보드에서 `v4l2-ctl --list-devices`로 확인한 번호로 이 YAML만 고치기 (코드·launch 파일은 안 고쳐도 됨)
- [ ] 카메라 해상도/포맷이 고정 크기 필요하면 `cv2.VideoCapture`에 `set(cv2.CAP_PROP_...)` 호출 추가
- [ ] 카메라는 MCU를 거치지 않고 Linux에서 직접 처리하므로 스케치 수정과 무관
- [ ] `current_sensor_node`(신규) — 전류 센서 4개(추진기1/2, 펌프 제어부, 센서 보드)가 전부 B1에 I2C로 물려있음. 아래를 확정해서 `sketch.ino`에 반영:
  - 실제 전류 센서 칩(예: INA219 / INA226)과 I2C 주소
  - 배터리 용량 대비 `percentage` 환산식
  - `sketch.yaml`에 해당 I2C 센서 라이브러리 추가
  - MCU RPC 이름을 바꾸고 싶다면 `current_sensor_node.py`의 `Bridge.call('get_battery_status')` 호출부만 수정 (`grep -n "TODO(B1" *.py`로 위치 확인)

**동작 확인용 참고**

- `ros2 topic echo /camera/surface/image_raw --once`, `/camera/underwater/image_raw --once` — 실제 프레임 확인
- `ros2 topic echo /water_quality/data`, `/gps/status`, `/battery/status` — MCU 측정값 확인

### B2 담당자 — `usv_actuators`

**이미 되어있는 것**

- ROS 인터페이스(토픽 이름/타입, `/cmd_vel` 직접 구독) 완성
- `/cmd_vel` → 좌/우 추진기 PWM 믹싱 공식(차동 구동) 구현됨
- **배터리 계측 역할은 이 패키지에 없습니다** — 전류 센서 4개가 전부 B1에 물려있어서 `usv_sensors`의 `current_sensor_node`가 `/battery/status`로 통합 발행합니다.

**참고할 만한 것 — 이 패키지가 가장 미완성 상태입니다** (자유롭게 바꿔도 됨)

- [ ] Arduino 스케치(B2 보드용, 아직 없음)에 아래 RPC 핸들러 구현:
  - `set_thruster_pwm(left, right)` — 모터 드라이버 핀에 PWM 출력
  - `set_pump(on)` — 펌프 릴레이 on/off
  - `set_actuator_led(r, g, b)` — RGB LED 핀 출력 (0~255, PWM 밝기 조절)
  - RPC 이름을 바꾸고 싶다면 `thruster_driver_node.py`, `actuator_driver_node.py`의 `Bridge.notify(...)` 호출부만 수정 (`grep -n "TODO(B2" *.py`로 위치 확인)
- [ ] `thruster_driver_node.py`의 좌/우 믹싱 공식이 실제 추진기 배치(개수·위치)와 다르면 `on_cmd_vel()` 로직 교체
- [ ] `usv_actuators/app.yaml`을 실제 Arduino App Lab 앱 이름에 맞춰 확인

**동작 확인용 참고**

- `ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.5}}"` — 추진기 반응 확인

### GCS 담당자 — `usv_gcs`

**이미 되어있는 것**

- `joy_to_cmd_node` — `/joy` → `/cmd_vel` 변환 로직 완성 (축 번호만 확인 필요), 펌프 버튼(`pump_button`, 기본 0번) → `/actuator/pump_cmd` 발행도 포함
- `gui_main_node` — 모든 구독/발행 배선 완성
  - Flask 웹 대시보드(`dashboard_html.py`)가 수질/GPS/배터리/cmd_vel을 1초 주기로 갱신
  - 펌프는 조이스틱 버튼으로만 조작 — GUI는 `/actuator/pump_cmd`를 구독해 상태만 표시 (버튼 없음), LED 색상 컨트롤(`/api/led` → `/actuator/led_cmd`)은 GUI 쪽에 남아있음
  - 듀얼 카메라 스트림은 `web_video_server` 주소를 그대로 `<img>`로 표시

**참고할 만한 것** (자유롭게 바꿔도 됨)

- [ ] 실제 조이스틱으로 `ros2 topic echo /joy` 확인 → 축 번호를 `gcs.launch.py`의 `linear_axis` / `angular_axis` 인자로 반영 (코드는 안 고쳐도 됨)
- [ ] `dashboard_html.py`는 기능 위주 최소 스타일링 상태 — 디자인/레이아웃은 자유롭게 개선 가능 (단, API 응답 구조 `/api/state`는 유지 — `gui_main_node.py`와 계약이 걸려 있음)
- [ ] `gui_main_node.py`의 `BATTERY_WARNING_PCT`(20%)는 실제 배터리 사양 확정되면 조정
- [ ] "GPS 신호 없음" 배너나 배터리 경고색 기준 등 UX는 자유롭게 개선 가능

**동작 확인용 참고**

- `usv_sensors` / `usv_actuators`를 동시에 띄운 상태에서 대시보드(`http://<GCS IP>:8000`)에 실시간 값이 뜨는지, 조이스틱 펌프 버튼 조작 시 대시보드 펌프 상태 표시와 LED 컨트롤 버튼이 동작하는지 확인

---

## ✅ 5. 설계 결정 확인 사항

0항 요구사항을 그대로 따른 부분입니다.

- `watchdog_node`(failsafe)는 0항 "이번 범위에서 제외한 것"에 따라 **아예 만들지 않았습니다**
  - `thruster_driver_node`는 `/cmd_vel_safe`가 아니라 `/cmd_vel`을 직접 구독
- `/gps/satellites`, `/gps/status`는 `gps_driver_node` 안에 발행 코드는 남겨뒀지만 `gui_main_node`는 구독하지 않습니다 (0항 "GPS 진단 토픽 처리 규칙")
- `usv_interfaces`(커스텀 msg) 패키지는 **만들지 않았습니다**
  - 인터페이스 규격이 전부 `std_msgs` / `sensor_msgs` / `geometry_msgs` 표준 타입만 쓰도록 확정
  - 한때 검토했던 커스텀 msg 계획은 폐기된 것으로 보고 반영

---

## 🐳 6. Docker 관련 참고

0항의 Docker 필수 조건은 **UNO Q에서 도는 `usv_sensors`, `usv_actuators`에만 해당**합니다. Raspberry Pi의 `usv_gcs`에는 적용되지 않으므로 Dockerfile이 없습니다.

`usv_sensors/`, `usv_actuators/` 각 폴더에 아래 파일이 들어있어, 나중에 독립 레포로 분리되어도 그대로 쓸 수 있습니다.

| 파일 | 역할 |
|---|---|
| `Dockerfile` | `ros:jazzy-ros-base` 기반 이미지. pip 의존성 설치 + `colcon build` |
| `app.yaml` | Arduino App Lab 앱 메타데이터 |
| `sketch/sketch.ino`, `sketch/sketch.yaml` | MCU(STM32)에서 실행되는 아두이노 스케치. `arduino-app-cli app start`가 부팅마다 빌드·업로드 |
| `start_sensors.sh` / `start_actuators.sh` | 이미지 빌드(최초 1회) → `arduino-app-cli app start`(스케치 포함) → RouterBridge 소켓 대기 → 컨테이너 실행 |
| `systemd/usv-*.service` + `install_autostart.sh` | 부팅 시 자동 실행 등록 |

`start_sensors.sh` / `start_actuators.sh`는 **Arduino App Lab 프레임워크가 보드에 이미 설치되어 있다는 전제**로 `arduino-app-cli app start user:<앱이름>`을 호출합니다.

- **`usv_sensors`**: `sketch/` 폴더 포함 → `install_autostart.sh` 설치 후 **전원만 넣으면 GPS/수질 측정 → ROS 토픽 발행까지 자동 동작**
- **`usv_actuators`**: 실제 Arduino 스케치가 아직 없음 (4항 B2 체크리스트) → 스케치를 작성해 `usv_actuators/sketch/`에 추가하고 App Lab에 등록하기 전까지는 컨테이너가 떠도 하드웨어 제어는 동작하지 않음
