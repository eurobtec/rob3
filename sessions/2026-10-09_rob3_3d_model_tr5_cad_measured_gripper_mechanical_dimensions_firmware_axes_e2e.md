# 2026-10-09 — ROB3 3D model from TR5 CAD, measured gripper, mechanical dimensions, firmware-axes e2e

A multi-repo session across `eurobtec/rob3` (firmware/docs) and
`eurobtec/rob3_ucsim` (CAD + URDF + sim). Themes: turn the donor TR5 3D CAD into
a complete, correctly-posed ROB3 URDF model; reconstruct the un-modelled gripper
from bench measurements as a parametric CAD; capture the arm's mechanical
dimensions; and prove the firmware moves all six axes end-to-end in our ucSim.

## rob3_ucsim — mesh-based URDF from the TR5 CAD

- Vendored the donor CAD (<https://github.com/Fuchsfuchsfuchs/TR5_Roboterarm>)
  into `src/rob3_ucsim/cad/` as **`rob3_arm.step`** (base/tower/upper-arm/forearm)
  and copied the four link meshes into `urdf/meshes/`. Dropped the Autodesk
  `.f3z` (Fusion-only, not needed) and the redundant gripper `.step` copies —
  file policy is now **STEP for the arm solid, STL for the sim**, with
  `gripper.py` as the gripper's source of record. Provenance + policy in
  `cad/README.md`; link↔mesh↔axis mapping in `urdf/README.md`.
- `rob3.urdf` / `.xacro` rewritten mesh-based: the 4 CAD links use the Fusion
  export transforms; joint **names and limits are the firmware axis order**
  (base/shoulder/elbow/wrist_pitch/wrist_roll/gripper) so the viewers keep
  resolving joints by name. Verified it loads in PyBullet with all 6 joints.
- Colours set to the real robot: **black** base + wrist + gripper, **red** the
  three arm segments (axes 0–2). Only two materials in the URDF.

## rob3_ucsim — the gripper (reconstructed from bench measurements)

The TR5 CAD does not model the gripper or wrist. Built `cad/gripper.py`
(CadQuery, STL-only) as a **two-finger four-bar / parallelogram** gripper from
caliper measurements:

- palm 75 × 20 × 15.2 mm; Ø17 × 50 mm wrist cylinder (axis mount 41 mm above the
  palm); each finger = two 6 mm sticks (14 mm total, 50 mm long); triangular
  tips (two equal 25 mm legs, vertical gripping face, rounded outer corner).
- **Parallelogram kinematics** (the two parallel sticks keep each tip VERTICAL
  while it arcs — grips any block squarely). Solved + mesh-verified against the
  measurements: jaw span **0 (closed) / 28 (straight) / 85 mm (open)**, inner
  stick-hole spacing **18 (closed) / 100 (open)**, finger swing −14.5°..+34.8°.
  Closed axis-to-tip 123.4 mm vs the 125 mm caliper reading (model-vs-caliper
  residual noted in the test).
- Several wrong models were tried (rigid-swing, naive parallelogram, bad
  rotation signs) before the measured inner/outer stick-hole spacings pinned the
  real geometry; the key correction was the gripping face sitting 7.5 mm inboard
  of the inner stick hole.

## rob3 — mechanical dimensions + gripper drawing

- `hardware/mechanics.md` (new): [HW]-measured, CAD-cross-checked dimensions —
  base plate 250×160×3.3, box 240×125×86, tower hub Ø82, bracket height 200,
  axis-1 at 275 mm from 0, Ø10 axis bore, upper-arm 200 / forearm 130 mm
  (hole-to-hole), full gripper table, and a **wrist-housing TODO** (bevel gears,
  two belts, a spring, the ~35° roll-drive gear on the cylinder). Reference-frame
  note: URDF world z = 0 is 25 mm below the physical base bottom.
- `hardware/gripper-drawing.svg` (new): 2D front view of the gripper. Base photos
  were bench references, **not committed**.

## Firmware-moves-all-axes (e2e) + tooling discipline

- `simulator/tests/test_firmware_axes_e2e.py` (new): runs the real ROM in **our**
  ucSim build + cl_hw modules — boots past emergency-off, **commands a motor on
  all six axes** when given targets, and each position byte maps within its URDF
  joint limit (firmware↔URDF consistency). Reports the known-[INFER] pot→position
  feedback limitation rather than faking it.
- `tests/test_gripper.py` (new): CAD open/close geometry vs measurements +
  URDF↔CAD mesh consistency + PyBullet load. All 16 repo tests pass.
- Steering fix (`rob3-lessons-learned.md`): a blunt rule to **use our ucSim
  build** (`eurobtec/ucsim/.../ucsim_51`) + the cl_hw modules and **never grab
  `/usr/bin/ucsim_51` or re-search** — a recurring mistake this session.
- Skill fix (`rob3-firmware-sim`): documented **how the firmware actually moves an
  axis** — drive the ADC pot feedback (`push_pot` / the `Plant`), not a direct
  poke of the target byte.

## Commits

- `eurobtec/rob3`      — `d8d1df7` docs(hardware): mechanical dimensions + gripper drawing; pin ucSim build in steering
- `eurobtec/rob3_ucsim` — `46cd966` feat(cad/urdf): mesh-based ROB3 model + measured gripper, firmware-axes e2e test

## Open / next

- **Gripper not yet wired to live open/close in the sim** (the URDF `gripper`
  joint is still the simple DOF; the CAD has open+closed meshes). 
- **Wrist housing** (axes 3/4 gear box) still a stand-in — TODO captured in
  `mechanics.md` with the known internals.
- Closed axis-to-tip is 123.4 mm (model) vs 125 mm (caliper) — ~1.6 mm residual.
