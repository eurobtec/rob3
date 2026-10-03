# 2026-10-03 — Extract the `rob3` Python library, make the ROS 2 driver depend on it, org profile

A packaging/tooling session, entirely in sibling repos (nothing changes in this
firmware repo). The ROS-independent core of the ROS 2 driver was lifted into a
standalone pip library, the driver was refactored to consume it, both verified
end-to-end against the real ROM in ucSim, and the `eurobtec` org got a profile
page + a ROB3 avatar.

## New sibling repository

- **[eurobtec/rob3_py](https://github.com/eurobtec/rob3_py)** — a pure-Python,
  ROS-independent library for the ROB3 RS-232 low-level protocol, extracted from
  `rob3_ros2_driver`. `src/` layout, installable (`pip install rob3`), MIT.
  - Modules (`src/rob3/`): `protocol` (wire codec), `transport` (pyserial,
    lazy-imported), `calibration` (joint↔0..255 count), `client` (`Rob3Client`
    = codec + transport; was `rob3_interface.py`), `fake_robot` (byte-level fake
    controller on a PTY), and a new **`teleop`** keyboard example app.
  - Console scripts: `rob3-teleop` (jog the arm from a terminal against the real
    robot, a ucSim pty, or `--fake`), `rob3-fake-robot`.
  - Tests: `test_protocol`, `test_calibration`, `test_client_fake`,
    `test_teleop`, and an opt-in `test_sim_roundtrip` (skips without ucSim).
    **30 pass.** Scripts: `sim_bringup.py`, `test_codec_vs_rom.sh`; docs:
    `docs/SIMULATION.md`. These moved here from the driver repo.

## `rob3_ros2_driver` — refactored to depend on `rob3`

The driver no longer vendors the codec/transport/calibration/client; it imports
them from the `rob3` library.

- Removed the five core modules and the duplicated tests/scripts/doc (now in
  `rob3_py`); the ament package is down to the two ROS files
  (`rob3_driver_node.py`, `jog_keyboard.py`).
- `rob3_driver_node.py`: `from rob3 import Calibration, Rob3Client, make_transport`.
- `setup.py`: `install_requires += rob3`; the `rob3_fake_robot` entry point now
  targets `rob3.fake_robot:main`. `package.xml` documents the pip dependency
  (not a rosdep key). `test_teleop_ucsim.py`: `from rob3 import Calibration`.
- **Dockerfile**: `python3 -m pip install "rob3[serial] @ git+…rob3_py.git"`
  before `colcon build`; the apt layer gained **`python3-pip` + `git`** (the
  `osrf/ros:lyrical-desktop` base ships neither `pip` on PATH nor `git`-less
  — the first build failed on `pip: command not found`, caught by actually
  building). READMEs note the `rob3-ros2:lyrical` image is **local-only** (no
  registry) and must be built from the Dockerfile first.

### Verification [SIM]

- Image builds; inside it `rob3` imports, `Rob3DriverNode` imports, and the node
  comes up (degrades gracefully with no `/dev/ttyUSB0`).
- **Full ROS 2 teleop against the real ROM in ucSim passes**
  (`test_teleop_ucsim.py`, host `ucsim_51` + `adc`/`rxd` + ROM mounted in): the
  node handshakes over a live pty (`check_often` on), an all-axis query
  round-trips (`[140, 147, 177, 47, 135, 64]`), a `+jog` on axis 1 moves **only**
  that axis to the calibrated count (147→103) with firmware ACK, `-jog` reverses
  it (103→191), link healthy after. This exercises the new `rob3.Rob3Client`/
  `rob3.Calibration` through the real firmware.

## `eurobtec` org profile + avatar

- **[eurobtec/.github](https://github.com/eurobtec/.github)** —
  `profile/README.md` org landing page: the ROB3 projects (rob3 / rob3_py /
  rob3_ros2_driver) and the ucSim tooling (pyucsim / ucsim-mcp / ucsim fork), an
  ASCII diagram down to the real **ROB 3** arm, and the provenance convention.
- A **ROB3 avatar** drawn to match the TR5/ROB3 silhouette (black base, blue
  shoulder motor, aluminium links, dark wrist, two-finger gripper + "ROB3"
  wordmark): `rob3-logo.svg` → `rob3-logo.png` (640×640). Must be uploaded via
  the GitHub web UI (no API/CLI for org avatars).

## Provenance
- `rob3_py` codec/calibration/client behaviour — unit tests ([no-HW]) + the
  codec-vs-ROM cross-check ([SIM]).
- The driver refactor is proven by the live `test_teleop_ucsim.py` run against
  the ROM in ucSim — [SIM]. The Dockerfile fix was proven by a real image build.
- Nothing in this firmware repo changed; the ROM and its golden byte-match are
  untouched.
