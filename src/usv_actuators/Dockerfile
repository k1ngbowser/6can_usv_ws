FROM docker.io/ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# system deps
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
COPY . /ros2_ws/src/usv_actuators

RUN rosdep update

RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    rosdep install --from-paths src --ignore-src -y"

RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    colcon build --packages-select usv_actuators"

ENV ROS_DOMAIN_ID=0

CMD ["/bin/bash", "-c", "source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && ros2 launch usv_actuators actuators.launch.py"]
