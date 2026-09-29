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
