# Setup schematic

The final source is `v1_scheme_setup.tex`. It reproduces the user-edited layout,
including the two selected boundary rays, component labels and equation positions.

```sh
make                              # default NAME=v1_
make NAME=v1_scheme_setup.tex      # equivalent explicit filename
make PNG_WIDTH=2640
make help
```

Outputs: `v1_scheme_setup.svg` and `v1_scheme_setup.png`.
Canvas: **8.8 × 5.4 cm**. Default raster: **2640 × 1620 pixels**.
`make clean` removes only the selected SVG and PNG; it preserves source files.

## Editable SVG

The Makefile exports directly from TikZ via XeLaTeX/XDV and dvisvgm, without PDF
conversion. `editable_svg.py` retains seven editable Arial label groups,
including the two-line source label, and seven vector formula groups.
Use Inkscape's Text tool to edit labels; mathematical contents are edited in
TikZ and rebuilt. Rebuilding replaces manual edits to the generated SVG.

## Geometry

- Ag K-edge nominal energy: 25.514 keV.
- Ge(880), lattice parameter 5.6579 Å; d880 = a/sqrt(128).
- R = 20.6 cm; theta_B = 29.06857 degrees; nominal deflection = 58.13713 degrees.
- Nominal source–crystal and crystal–sample arms: p = q = R/sin(theta_B) = 42.40 cm.
- The sample surface is 45 degrees to the nominal incident beam.
- Incident/reflected rays: Matplotlib C1 (#FF7F0E).
- Three fluorescence arrows toward the CZT entrance: Matplotlib C2 (#2CA02C).
- Crystal support, Ag sample and CZT use neutral gray fills and borders.
- Nominal ray distances, substrate chord length and the 10 cm bar use an isotropic scale.
  The layout scope applies a uniform factor of 1.08, never unequal x/y scaling.

The two rays pass through both slit openings, reach different crystal points,
and converge at the sample. Their incoming paths cross between the slits, as in
the effective-source construction in the supplied reference. Slit apertures and
source/sample/detector icons and collection distances are illustrative.
The drawn envelope symbolizes focusing; it is not a validated in-plane ray
trace, since von Hamos sagittal focusing is perpendicular to this optical view.
The p=q annotation refers to the nominal arms, not each boundary-ray length.

## Substrate dimensions

Source: `../03_Simulations/O-2094 subsrate for Von Hamos analyzer 50x25 R206.pdf`,
sheet 1/1. The drawing dimensions the **aluminum substrate**, not the Ge wafer:
52 × 27 mm, R = 206 mm, center thickness 10 mm, edge reference thickness 11.6 mm.
The gray icon retains its 52 mm chord length; the 27 mm dimension is perpendicular
to that section. At the user’s request, its sag is visually exaggerated by a
factor of 3 on the front face to make the curvature visible. The back stays
flat; only the front-face sag is exaggerated relative to the physical profile. The boundary-ray endpoints
follow the drawn surface. Physical R=20.6 cm and the nominal p=q value are unchanged. Curvature direction in the 2D layout remains
symbolic, with the central tangent at the nominal Bragg orientation.
The filename's 50x25 does not establish a wafer aperture or Ge thickness.

## Formula proportions

The SVG transform check found a maximum principal scale ratio of
1.0000000000000002 across 53 formula glyph/line instances in the earlier layout:
no anisotropic stretching. The final layout uses the same undistorted glyphs
and mathematical font. The wide appearance is the Computer Modern bold design.
