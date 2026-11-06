# PRISM v2 - Simplified explanatory setup

Open `v2_Setup_PRISM.blend`, then **N > PRISM** in the 3D View.

- A bare sample foil, with no frame, tower, holder or translation stage.
- One **30 x 30 x 30 mm cubic CZT case**, with four windows in a **2 x 2 grid** on its flat front face. There are no
  separate module housings, mounting posts, rotary stage or base plate.
- The original source, slits and Ge crystal are retained in the Full view.
- The same two modes: **Fluorescence** and **Incident I0**.
- **Play** animates sample extraction, head rotation and return; **Freeze**
  stops at the current pose. The Switch slider allows manual positioning.

If the sidebar is absent because Blender blocks embedded scripts, select
`PRISM_Controls.py` in the Text Editor and run it with **Alt-P**. The panel is
embedded in the blend and also supplied as `prism_controls_v2.py`.

Dimensions remain in millimetres: four 10 x 10 x 5 mm CZT crystals with
parallel entrance faces in a 2 x 2 grid, centre pitch 12 mm (2 mm gap).
The perpendicular distance from the illuminated sample point to the entrance
plane is 35 mm. The four face centres are at +/-6 mm horizontally and
vertically relative to the face centre; the nominal total active area is
400 mm2. The sample is a bare 25 x 25 x 0.020 mm foil.

Sample lift defaults to 45 mm. After extraction, the head rotates 90 degrees
and makes a small rigid alignment offset (6 mm in each of the two transverse
coordinates), so that **D1 receives the direct beam rather than the gap**.
All four channels and their common cube move together. No mechanism is drawn.
The N-panel exposes the mode switch, animation, sample lift and views.

The box is a conceptual envelope, not a supplier drawing. The sensor geometry
is inherited from v1, but the 2 x 2 faces are now coplanar rather than individually
pointed toward the sample. The previous spherical-cap angular acceptance does
not apply. Colours and arrows are illustrative; arrow widths are not physical
beam sizes. I0 is measured sequentially using D1.

The animation is saved in the blend: 252 frames at 24 fps (10.5 seconds).
The v1 file and its assets are unchanged.

Rebuild from the project root:

```bash
blender -b --python 24_CZT_Channel_Layouts/create_v2_setup_prism.py -- --render
```

Use `-- --help` for all parameters and their defaults.
