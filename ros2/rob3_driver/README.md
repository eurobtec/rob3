# ROB3 ROS 2 driver

A ROS 2 **Lyrical** driver for the **Eurobtec ROB 3** 6-axis robot, talking to
the robot's Intel 8031 controller over its **RS-232** serial link. It is
implemented in Python and provides a protocol client, ROS 2 driver node, robot
description, launch configuration, and controller configuration.

The wire protocol is the ROB3 low-level protocol, reverse-engineered and
verified against the ROM/simulator (see `../hardware/host/command.md` and
`../firmware/src/annotated/rs232.asm`). The driver speaks the
same bytes to either **real hardware** (`/dev/ttyUSB0`) or the **ucSim
simulator** (via its `-S` UART socket), so it can be developed without the robot.

## Layout

```
ros2/rob3_driver/
├── package.xml
├── setup.py / setup.cfg
├── resource/rob3_driver
├── rob3_driver/
│   ├── protocol.py           # pure ROB3 wire-protocol codec (no ROS deps)
│   ├── transport.py          # serial + TCP-socket transports (real HW / ucSim -S)
│   ├── calibration.py        # joint <-> 0..255 count mapping (per-axis)
│   ├── rob3_interface.py     # protocol + transport = high-level robot client
│   └── rob3_driver_node.py   # ROS 2 node: JointState, trajectory action, services
├── launch/rob3.launch.py
├── config/rob3_controllers.yaml
├── urdf/rob3.urdf.xacro
└── test/                     # pytest unit tests (protocol codec, calibration)
```

## Architecture

| Component | Responsibility |
| :-------- | :-------------- |
| `protocol.py` | Encode ROB3 commands and decode controller replies |
| `transport.py` | Communicate over serial hardware or the ucSim TCP socket |
| `rob3_interface.py` | Provide a high-level client for the ROB3 protocol |
| `rob3_driver_node.py` | Publish joint states and provide trajectory/action services |
| `launch/`, `config/`, `urdf/` | Describe and configure the ROB3 ROS 2 system |

## Build with Docker

Run these commands from the repository root. The ROS 2 Lyrical desktop image
provides the ROS environment and `colcon`:

```bash
docker pull osrf/ros:lyrical-desktop

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/home/ubuntu" \
  -w /home/ubuntu \
  osrf/ros:lyrical-desktop \
  bash -lc 'source /opt/ros/lyrical/setup.bash && colcon build --base-paths ros2'
```

The build artifacts are written to `build/`, `install/`, and `log/` in the
repository root.

## Run RViz in Docker (no simulator)

From the repository root, start a container with a virtual X display and a
browser-accessible VNC connection. This mode skips the ROB3 transport driver
and publishes zero joint positions for viewing the URDF:

```bash
docker run --rm -it --name rob3-rviz -p 6080:6080 \
  -v "$PWD:/home/ubuntu" -w /home/ubuntu \
  osrf/ros:lyrical-desktop bash
```

Then, inside the container, run:

```bash
set -e
apt-get update
apt-get install -y xvfb x11vnc novnc ros-lyrical-xacro \
  ros-lyrical-robot-state-publisher ros-lyrical-joint-state-publisher
source /opt/ros/lyrical/setup.bash
colcon --log-base /tmp/rob3-log build --base-paths ros2 \
  --build-base /tmp/rob3-build --install-base /tmp/rob3-install
source /tmp/rob3-install/setup.bash
xvfb-run -a -s "-screen 0 1400x900x24" bash -lc '
  export LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1
  x11vnc -display "$DISPLAY" -forever -shared -nopw \
    -rfbport 5900 -listen 0.0.0.0 >/tmp/x11vnc.log 2>&1 &
  websockify --web=/usr/share/novnc 6080 localhost:5900 \
    >/tmp/websockify.log 2>&1 &
  exec ros2 launch rob3_driver rob3.launch.py driver:=false rviz:=true
'
```

In the Codespaces **Ports** view, open port `6080` in a browser and visit
`/vnc.html?autoconnect=1&resize=remote`. Exit the container with `exit` or
Ctrl+C. To connect the driver to ucSim or hardware instead, omit
`driver:=false` and provide the appropriate transport arguments.

## Quickstart (against the simulator)

```bash
# 1) build a ucSim with a serial socket and load the ROB3 ROM (see simulator/)
ucsim_51 -t 51 -X 11.0592M -S port=54321 simulator/build/rob3.hex

# 2) run the driver pointed at that socket
ros2 launch rob3_driver rob3.launch.py transport:=tcp host:=127.0.0.1 port:=54321

# real hardware instead:
ros2 launch rob3_driver rob3.launch.py transport:=serial device:=/dev/ttyUSB0
```

See `rob3_driver/protocol.py` for the exact wire encoding; every command there
is annotated with its ROM provenance.

## Status / scope

- Protocol codec + transports + driver node + URDF/launch/config: implemented.
- Position control (single + all-axis) and readback: implemented per the
  verified protocol.
- Speed/time-factor moves (`0x70`–`0x7F`) and the stored-program upload are
  wired in the codec but the trajectory controller uses simple position
  setpoints by default.
- Joint↔count calibration uses the per-axis bench values from
  `../hardware/motors/` where available; unmeasured axes use a linear placeholder
  clearly marked in `calibration.py`.
