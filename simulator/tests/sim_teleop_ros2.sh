#!/usr/bin/env bash
# Run the ROS 2 TELEOP integration test (JointJog -> rob3_driver -> ROB3
# firmware in ucSim) inside the rob3-ros2 container.
#
# ucSim free-runs the whole time; the REAL driver node talks to the firmware
# over a live serial pty, a control_msgs/JointJog moves the simulated arm, and
# the test asserts the jog reached the firmware (calibrated count + ACK) over
# the live link. This is the end-to-end proof enabled by the issue-004
# `check_often` fix.
#
# Requirements on the HOST:
#   * the rob3-ros2 image (default tag: rob3-ros2:lyrical; override IMAGE=...)
#   * a stock ucsim_51 0.9.9+ build at UCSIM_HOST; the driver enables the
#     issue-004 fix at runtime via config memory (expr uart0_check_often=1)
#   * this firmware repo (ROM + cl_hw modules)
#   * the rob3_ros2_driver checkout (for the test file)
#
# Everything is mounted read-only into the container; nothing host-side is
# modified. Skips cleanly (exit 0) if the image is absent.
set -euo pipefail

IMAGE="${IMAGE:-rob3-ros2:lyrical}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"               # simulator/
ROB3="$(cd "$HERE/.." && pwd)"                          # repo root
UCSIM_HOST="${UCSIM_HOST:-$HOME/github/eurobtec/ucsim}"
DRIVER_HOST="${DRIVER_HOST:-$HOME/github/eurobtec/rob3_ros2_driver/rob3_driver}"
TIMEOUT="${TELEOP_TIMEOUT:-150}"

skip() { echo "SKIP  $1"; echo "sim_teleop_ros2: SKIPPED"; exit 0; }

command -v docker >/dev/null 2>&1 || skip "docker not available"
docker image inspect "$IMAGE" >/dev/null 2>&1 || skip "image $IMAGE not found"
[ -x "$UCSIM_HOST/src/sims/s51.src/ucsim_51" ] || skip "ucsim_51 not built at $UCSIM_HOST"
[ -f "$DRIVER_HOST/test/test_teleop_ucsim.py" ] || skip "driver teleop test not found at $DRIVER_HOST"

exec timeout "$((TIMEOUT + 40))" docker run --rm \
  -v "$ROB3:/host/rob3:ro" \
  -v "$UCSIM_HOST:/host/ucsim:ro" \
  -v "$DRIVER_HOST/test:/host/drvtest:ro" \
  "$IMAGE" bash -lc "
    source /opt/ros/\$ROS_DISTRO/setup.bash
    source /opt/rob3_ws/install/setup.bash
    UCSIM_51=/host/ucsim/src/sims/s51.src/ucsim_51 \
    ROB3_ROM='/host/rob3/firmware/legacy/hex/M2764A@DIP28.HEX' \
    ROB3_MODS=/host/rob3/simulator/ucsim-modules \
    TELEOP_TIMEOUT=$TIMEOUT \
    python3 /host/drvtest/test_teleop_ucsim.py
  "
