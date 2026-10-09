# Mechanical Dimensions

Physical dimensions of the ROB3 arm structure, measured on the robot and
cross-checked against the TR5 3D CAD
([Fuchsfuchsfuchs/TR5_Roboterarm](https://github.com/Fuchsfuchsfuchs/TR5_Roboterarm),
`3D_CAD/TR5_Modell_V1.*`). The CAD is the geometry source of truth for the
simulation URDF (`rob3_ucsim` `urdf/`), but physical caliper readings are the
ground truth where the two differ.

Provenance:
- **[HW]** — measured on the physical robot (caliper).
- **[CAD]** — read from the TR5 CAD mesh bounding box.

## Base

The base is a **bottom mounting plate** with a **box body** sitting on it, which
carries the rotating tower (axis 0).

### Bottom mounting plate

| Dimension | [HW] measured | [CAD] mesh | Notes |
| :-------- | :------------ | :--------- | :---- |
| Length    | 250 mm        | 250 mm     | exact match |
| Width     | 160 mm        | 160 mm     | exact match |
| Thickness | 3.3 mm        | ~3.0 mm    | thin bottom slab; CAD ~0.3 mm thinner (idealized/faceting) |

### Box body (on top of the plate)

| Dimension | [HW] measured | [CAD] mesh | Notes |
| :-------- | :------------ | :--------- | :---- |
| Length    | 240 mm        | 242 mm     | within ~2 mm |
| Width     | 125 mm        | 125 mm     | exact match |
| Height    | 86 mm         | 85 mm      | measured from the plate bottom (includes the mounting-plate thickness); within ~1 mm |

Notes:
- The box height is given **including** the underneath mounting plate, i.e. from
  the bottom face of the plate to the top of the box.
- In the CAD/URDF frame the base mesh spans z = 25 .. 110 mm (85 mm overall),
  with the full 250×160 footprint only at the plate (z ≈ 25..28 mm) and the
  242×125 box footprint on top (top slab at z ≈ 100..110 mm, where the tower
  mounts).
- The CAD and the physical robot agree to within ~1–2 mm on every base
  dimension — a good HW↔CAD cross-validation.

## Tower (axis 0) — rotating hub

The tower (German *Turm*) is the rotating assembly on top of the base box; it
carries axis 0 (base rotation). Its lowest feature is a **cylindrical hub**
sitting directly on the base-box top.

| Feature | [HW] measured | [CAD] mesh | Notes |
| :------ | :------------ | :--------- | :---- |
| Hub cylinder diameter | 82 mm | ~80 mm | within ~2 mm |
| Hub cylinder height   | —     | ~5 mm  | short collar/flange (z ≈ 110..115 mm); a ~Ø10 mm spigot sits below it at z ≈ 100 mm |
| Bracket (tetraeder) height | 200 mm | 200 mm | match. From the hub base seat (z ≈ 100 mm) up to the axis-1 (shoulder) pivot (z = 300 mm) → 200 mm. The full tower mesh envelope is 230 mm (z 100..330), the extra ~30 mm being the yoke above the pivot. |

Notes:
- The hub cylinder is at z ≈ 100..115 mm in the CAD/URDF frame (i.e. just above
  the base-box top at z ≈ 110 mm).
- Only the **bottom hub** is cylindrical. Above it the tower is **not** a
  cylinder — the CAD flares to the full 155 × 104 mm footprint and then becomes
  a bracket/yoke of two ~104 mm-spaced side plates up to z ≈ 330 mm, where the
  shoulder joint (axis 1) mounts. Overall tower envelope: 155 × 104 × 230 mm.

## Axis mounting heights (assembly)

Where each axis pivot sits, measured from the robot's **standing surface**
(bottom of the base plate = physical 0). This is the assembly/kinematic
information: how the parts stack up.

| Axis | Pivot | [HW] height from 0 | [CAD] / URDF | Notes |
| :--- | :---- | :----------------- | :----------- | :---- |
| 0 → 1 | shoulder axis (where the tower/axis 0 carries axis 1) | 275 mm | 275 mm | match. URDF shoulder joint is at world Z=300 mm; the base-plate bottom sits at world Z=25 mm, so 300−25 = **275 mm** above the physical base — agrees with the bench measurement. |

Axis mounting hole (shaft bore):

| Feature | [HW] measured | [CAD] mesh | Notes |
| :------ | :------------ | :--------- | :---- |
| Axis mounting hole diameter | 10 mm | ~10 mm | the bore the axis shaft passes through; CAD shows a Ø≈10 mm hole centered at x ≈ −35 mm (the axis-0/axis-1 column centerline) at the shoulder-pivot height |

Link lengths (center-to-center between axis holes):

| Link | Between | [HW] measured | [CAD] / URDF | Notes |
| :--- | :------ | :------------ | :----------- | :---- |
| Axis 1 (upper arm / Oberarm) | shoulder hole → elbow hole | 200 mm | 200 mm | match. URDF elbow joint origin is x = 0.200 m in the upper-arm frame; the mesh bores sit at x ≈ −35 mm and ≈ +165 mm → 200 mm center-to-center |
| Axis 2 (forearm / Unterarm) | elbow hole → wrist hole | 130 mm | 130 mm | match. Forearm mesh bores centered at x ≈ 165 mm and ≈ 295 mm → 130 mm center-to-center (the mesh is 171 mm overall; the ends extend past the holes). The wrist pivot is therefore at the x ≈ 295 mm hole, not the mesh tip (x ≈ 313 mm). |

> **Reference-frame note:** the CAD/URDF world origin (z=0) is **not** the
> bottom of the robot — the base-plate bottom sits at world z = 25 mm. So a
> height "from 0" on the physical robot equals the URDF world Z **minus 25 mm**.

## Gripper (axis 5)

Two-finger four-bar (scissor) linkage; each finger is two parallel links
driven from the wrist gearbox, ending in a triangular jaw. Not modelled in the
TR5 CAD — reconstructed from bench photos + caliper measurements and built as a
parametric model (`rob3_ucsim` `cad/gripper.py` → `gripper.step` + `gripper.stl`).

| Feature | [HW] measured | Notes |
| :------ | :------------ | :---- |
| Palm plate width | 75 mm | left–right |
| Palm plate height | 20 mm | top–bottom |
| Palm plate thickness | 15.2 mm | |
| Finger link thickness | 9.4 mm | |
| Finger link length | 50 mm | pivot hole → link end |
| Finger link width | 14 mm | total of the two sticks (outer-to-outer) |
| Finger stick width | 6 mm each | each finger = TWO parallel 6 mm sticks with a ~2 mm gap between them |
| Finger stick mount holes | top + bottom | each stick has a hole at BOTH ends: top pivots to the palm, bottom pivots to the tip (four-bar) |
| Pivot pin diameter | 2 mm each | small/negligible pins at the stick and tip pivot holes |
| Finger-to-finger gap | 52 mm | horizontal gap between the two fingers at the palm, when CLOSED |
| Finger pivot hole | 15 mm below palm top | where the fingers start |
| Fingertip thickness | 15.2 mm | |
| Fingertip shape | right triangle, two equal 25 mm legs | inner leg VERTICAL (gripping face), top leg HORIZONTAL, outer corner ROUNDED |
| Fingertip connection hole | 5 mm from top of the horizontal side | where the tip attaches to the link |
| Axis-to-palm cylinder | Ø17 × 50 mm | the cylinder from the wrist axis down to the palm; mounted to the palm at its bottom end |
| Cylinder axis mount hole | 41 mm from palm (9 mm from top) | where the cylinder attaches to the previous axis (wrist roll); so the axis is 41 mm above the palm top |
| Axis center → fingertip end (CLOSED) | 125 mm | overall closed length (axis @ 41 mm above palm → pivot 56 mm → links hang ~28° from vertical → tip) |
| Jaw span (OPEN) | 85 mm | gap between the two fingers, fully open |

**Connection to the arm:** the gripper cylinder mounts to the **wrist axis**,
which is the end of **axis 2 (forearm, 130 mm elbow→wrist hole)**. So the gripper
hangs off the forearm's wrist hole (x ≈ 295 mm in the forearm frame).

**Scissor kinematic:** opening and closing move the top gap and the fingertips
in *opposite* directions. CLOSED → fingers 52 mm apart at the palm, fingertips
together. OPEN → the fingers rotate about their pivots so the top gap closes
toward 0 while the fingertips spread to the 85 mm span.

**Closed-length check:** axis (41 mm above palm top) → finger pivot (15 mm below
palm top) = 56 mm; + link (50) + tip (25) = 131 mm if perfectly vertical, vs the
measured 125 mm closed → the links hang ~28° from vertical when closed (the
scissor pose). Consistent to ~6 mm.

See also: `hardware/gripper-drawing.svg` (2D front view). The dimensions
were taken from bench photos + caliper measurements (photos not committed).

## Wrist housing (axes 3 & 4) — TODO, not yet modeled

The gear housing **between the forearm and the gripper** drives the two wrist
motions: **wrist pitch (axis 3, up/down)** and **wrist roll (axis 4, rotate the
gripper)**. (Observed on bench photos + measured; photos not committed.)

Status: **NOT modeled in CAD.** In the URDF, `link4` (wrist_pitch) and `link5`
(wrist_roll) are **primitive cylinder stand-ins**. The simulation motion is
already correct (both joints rotate as the firmware commands); only the visual
shape of the housing is a placeholder.

Not required for the simulation — tracked here for future CAD completeness.
Known internals to capture when modeling it:
- **bevel gears** (drive the two wrist axes)
- **two belts** (drive transmission)
- **a spring** (return/tension)
- the bracket/box and the mount where the Ø17 × 50 mm gripper cylinder plugs in

**Wrist-roll drive:** the Ø17 × 50 mm gripper cylinder carries a **gear**; a
mating gear on the **motor** meshes with it, so the motor rotates the cylinder
= wrist roll (axis 4), spinning the whole gripper. The cylinder is thus a
*driven shaft with a gear*, not a passive standoff. The mesh uses an **angled
(~35°) bevel-type gear** — the motor shaft is not parallel to the cylinder, so
the angled gear turns the drive direction between the two shafts.

## See also

- `rob3_ucsim` `src/rob3_ucsim/urdf/README.md` — how the CAD meshes map to the
  URDF links (base_link, tower, upperarm, forearm) and the firmware axes.
- [`motors/README.md`](motors/README.md) — the six axes and their motors/pots.
