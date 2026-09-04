FROM docker.io/ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# system deps
# NOTE: cv_bridge/web_video_server/usb_cam are deliberately NOT installed here.
# Those apt packages pull in boost-dev/ffmpeg-dev/GTK/Qt, which overflowed this
# board's disk during earlier attempts. camera_node/http_video_server instead
# build sensor_msgs/Image by hand and serve MJPEG with Python's stdlib
# http.server, so opencv-python-headless (pip) is the only heavy dependency.
RUN apt-get update && apt-get install -y \
    tmux \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# python deps
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt --break-system-packages \
    && pip cache purge

# Workspace
WORKDIR /ros2_ws
COPY . /ros2_ws/src/camera_streaming

RUN rosdep update

RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    rosdep install --from-paths src --ignore-src -y"

RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    colcon build --packages-select camera_streaming"

ENV ROS_DOMAIN_ID=0

CMD ["/bin/bash", "-c", "source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && ros2 launch camera_streaming camera_streaming.launch.py"]
