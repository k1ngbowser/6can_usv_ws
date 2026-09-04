# 카메라 스트리밍 (Surface / Underwater) → HTTP:8000

수면(surface) 카메라와 수중(underwater) 카메라 영상을 ROS 2 토픽으로 발행하고,
HTTP MJPEG 스트림으로 변환해 내보내는 파이프라인입니다. 브라우저 UI(화면
구성)는 이 프로젝트의 범위가 아니며, 스트림 URL을 제공하는 데까지만 다룹니다.

전부 **자체 작성한 가벼운 Python/OpenCV 코드**로 만들었습니다 (`usb_cam`,
`web_video_server` ROS 패키지는 쓰지 않습니다 — 두 패키지가 boost-dev,
ffmpeg-dev, GTK/Qt 등을 끌고 와서 이 보드(9.8GB 디스크)에서는 이미지 빌드가
디스크 부족으로 계속 실패했습니다. 대신 `opencv-python-headless`(pip, GUI
의존성 없음) 하나만 써서 이미지 용량을 947MB → 1.1GB 수준으로 유지했습니다).

## 아키텍처

```text
surface 카메라(USB) ──┐
                      ├─ camera_node(OpenCV) ──▶ /camera/surface/image_raw ────┐
underwater 카메라(USB)┘                          /camera/underwater/image_raw ─┤
                                                                                ▼
                                                                  http_video_server
                                                              http://<보드IP>:8000
```

- `camera_node`가 `cv2.VideoCapture`로 두 카메라를 열어 `sensor_msgs/msg/Image`를
  초당 15프레임(기본값)으로 계속 발행합니다. (정지 이미지 한 장이 아니라
  연속 프레임 스트림입니다.) 카메라가 없거나 열기 실패하면 죽지 않고 계속
  재시도만 합니다.
- `http_video_server`가 그 두 토픽을 구독해 `cv2.imencode`로 JPEG 변환 후,
  Python 표준 `http.server`로 MJPEG(`multipart/x-mixed-replace`) 스트림을
  내보냅니다.
- ROS 2 Jazzy는 UNO Q Linux 위 **별도의** Docker 컨테이너
  (`camera_streaming_container`, 이미지 `camera_streaming_image`)에서 실행됩니다.
  같은 B1 보드에서 도는 수질/GPS 컨테이너(`usv_sensors_container` / `usv_sensors_image`)와
  이름이 완전히 분리되어 있어 서로 절대 충돌하지 않습니다. `--network host`라서
  컨테이너 안에서 연 포트가 보드의 실제 포트로 바로 노출되고, 같은
  `ROS_DOMAIN_ID=0`을 쓰므로 두 컨테이너의 ROS 2 토픽은 호스트 네트워크
  위에서 서로 정상적으로 보입니다(간섭 없이 공존). B1 보드를 통째로 올릴 땐
  레포 루트의 `start_b1.sh`가 이 컨테이너와 `usv_sensors` 컨테이너를 순서대로
  띄운다 (README.md 3항 참고).

## 패키지 위치

```text
6can_usv_ws/src/camera_streaming/
├── Dockerfile
├── requirements.txt            # opencv-python-headless, numpy
├── start_camera_streaming.sh   # 이미지 빌드(최초 1회) → 컨테이너 실행
├── install_autostart.sh        # (선택) 부팅 시 자동 실행 등록 (systemd/camera-streaming.service)
├── package.xml
├── setup.py / setup.cfg
├── camera_streaming/
│   ├── camera_node.py         # OpenCV 캡처 → ROS 2 Image 발행
│   └── http_video_server.py   # ROS 2 Image 구독 → HTTP MJPEG
└── launch/camera_streaming.launch.py
```

## ROS 2 토픽

| 토픽 | 타입 | 설명 |
|---|---|---|
| `/camera/surface/image_raw` | `sensor_msgs/msg/Image` | 표면 카메라 원본 프레임 (bgr8) |
| `/camera/underwater/image_raw` | `sensor_msgs/msg/Image` | 수중 카메라 원본 프레임 (bgr8) |

## HTTP 엔드포인트 (기본 포트 8000)

| URL | 설명 |
|---|---|
| `http://<보드IP>:8000/` | 현재 스트리밍 가능한 토픽 목록 페이지 |
| `http://<보드IP>:8000/stream?topic=/camera/surface/image_raw` | 표면 카메라 **실시간 영상** (MJPEG, `<img>` 태그로 그대로 재생됨) |
| `http://<보드IP>:8000/stream?topic=/camera/underwater/image_raw` | 수중 카메라 **실시간 영상** |
| `http://<보드IP>:8000/snapshot?topic=/camera/surface/image_raw` | 표면 카메라 정지 이미지 한 장(jpeg) |
| `http://<보드IP>:8000/snapshot?topic=/camera/underwater/image_raw` | 수중 카메라 정지 이미지 한 장(jpeg) |

화면을 여러 개 동시에 띄우고 싶으면 `<img src="...">` 태그를 토픽별로 나란히
두면 됩니다. 서버가 커넥션마다 별도 스레드로 처리해서 동시 스트리밍에
문제없습니다.

```html
<img src="http://<보드IP>:8000/stream?topic=/camera/surface/image_raw">
<img src="http://<보드IP>:8000/stream?topic=/camera/underwater/image_raw">
```

## launch 인자 (기본값)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `surface_device` | `/dev/video2` | 표면 카메라 V4L2 장치 경로 |
| `underwater_device` | `/dev/video3` | 수중 카메라 V4L2 장치 경로 |
| `port` | `8000` | HTTP 포트 |

기본값 `/dev/video2`, `/dev/video3`는 보드 내장 Venus 인코더/디코더가 이미
`/dev/video0`, `/dev/video1`을 쓰고 있어서 USB 카메라가 보통 2번부터 잡힐
것이라는 **예상값**입니다.

## 실제 USB 카메라 연결 후 할 일

1. 카메라 2대를 **UNO Q 보드**의 USB 포트에 연결합니다 (노트북이 아니라 보드에
   꽂아야 이 파이프라인이 잡을 수 있습니다).
2. 실제로 잡힌 장치 번호를 확인합니다.
   ```bash
   v4l2-ctl --list-devices
   ```
3. 기본값(`/dev/video2`, `/dev/video3`)과 다르면 `start_camera_streaming.sh`가
   실행하는 `ros2 launch` 줄에 인자를 추가하고 다시 실행합니다 (스크립트 자체는
   그대로 두고, 그 안의 `ros2 launch camera_streaming camera_streaming.launch.py`
   줄만 아래처럼 인자를 붙이면 됩니다):
   ```bash
   cd 6can_usv_ws/src/camera_streaming
   ./start_camera_streaming.sh
   # 장치 번호가 다르면: 컨테이너 안에서
   #   ros2 launch camera_streaming camera_streaming.launch.py \
   #       surface_device:=/dev/videoX underwater_device:=/dev/videoY
   ```
4. 정상 동작 확인:
   ```bash
   docker logs camera_streaming_container --tail 50
   curl http://localhost:8000/
   ```

## 부팅 시 자동 실행

```bash
cd 6can_usv_ws/src/camera_streaming
./install_autostart.sh
```

`systemd/camera-streaming.service`를 설치해 부팅 시 `start_camera_streaming.sh`를
자동 실행하도록 등록합니다 (컨테이너 자체도 `--restart unless-stopped`라 Docker
데몬이 살아있는 한 다시 켜집니다). B1 보드의 다른 컨테이너(`usv_sensors_container`)와
이름/이미지가 겹치지 않으므로 서로의 자동 실행에 영향을 주지 않습니다. 두 컨테이너를
한 번에 등록하려면 레포 루트의 `install_b1_autostart.sh`를 쓰세요.

## 현재 알려진 상태 (이 문서 작성 시점)

- 보드에 실제 USB 카메라가 아직 연결되어 있지 않습니다 (`lsusb` 결과 없음).
  `/dev/video0`, `/dev/video1`은 카메라가 아니라 SoC 내장 Venus
  인코더/디코더입니다.
- 파이프라인 자체는 합성 프레임(테스트 rclpy 퍼블리셔)으로 끝까지
  검증했습니다: `http_video_server`가 두 토픽 모두 인식했고, `/snapshot`이
  두 토픽 다 정확한 640x480 유효 JPEG를 반환했으며, `/stream`이 발행 중
  4초 동안 다수의 MJPEG 프레임 경계를 내보내 **연속 영상 스트림**임을
  확인했습니다.
- 실제 카메라가 없는 동안 `camera_node`는 계속 재시도하며 조용히 대기합니다.
  로그에 `could not open /dev/videoN, will retry`가 반복해서 보이는 것이
  정상입니다.
- 다른 팀의 `ros_jazzy_container`(수질/GPS)는 이 작업 내내 정상 가동
  상태였고, 앞으로도 이 컨테이너와는 이름/포트가 겹치지 않습니다.

## 확인 명령어 모음

```bash
# 컨테이너 로그
docker logs camera_streaming_container --tail 50

# 토픽 확인
docker exec camera_streaming_container bash -lc \
  'source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && ros2 topic list | grep camera'

# HTTP 응답 확인
curl http://localhost:8000/
curl -o /tmp/surface.jpg "http://localhost:8000/snapshot?topic=/camera/surface/image_raw"
```

## 문제 해결

| 증상 | 확인할 것 |
|---|---|
| `/camera/...` 토픽이 안 보임 | `v4l2-ctl --list-devices`로 실제 장치 번호 확인 후 launch 인자 수정 |
| `/snapshot`이 404 | 아직 그 토픽에 프레임이 한 번도 안 들어온 상태 — 카메라 연결/토픽 발행 확인 |
| 포트 8000 응답 없음 | `ss -tlnp \| grep 8000`으로 다른 프로세스가 포트를 쓰고 있는지 확인 |
| 컨테이너가 계속 재시작됨 | `docker logs camera_streaming_container`로 어느 노드에서 나는 오류인지 확인 |
