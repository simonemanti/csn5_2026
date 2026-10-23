# PRISM focusing-area vignettes

All illustrations: 240 x 240 mm canvas, black circular border, pastel background.
PNG exports: 1800 x 1800 pixels, transparent outside the badge.

| Folder | Background | Files |
|---|---|---|
| 1_XAS | C0, 50% white | SVG, PNG |
| 2_XANES | C1, 50% white | SVG, PNG |
| 3_CZT | C4, 50% white | TikZ TEX, PDF, SVG, PNG, XYZ, Makefile |
| 4_Crystal | C2, 50% white | TikZ TEX, PDF, SVG, PNG, data, Makefile |
| 5_Pulse_Shape | C3, 50% white | TikZ TEX, PDF, SVG, PNG, data, Makefile |

## Build and edit

Run `make` here, or within an individual TikZ vignette folder.
Requires lualatex with TikZ/standalone/fontspec and the installed Arial font, pdftocairo and Inkscape.
Use `make -B PNG_WIDTH=2400` for a different PNG resolution.
`make clean` removes only intermediate `.build` folders.
Edit the `.tex` sources to change the drawings. Curves are embedded as vector
coordinates; the `.dat` files preserve the underlying numeric values.
The SVGs are vector exports with outlined text.
The root XAS.svg/XANES.svg originals and the Cathode reference are preserved.
Previous versions are in `.previous_v1` and `.previous_v2`.

## CZT

Ball-and-stick style inspired by `3_CZT/Cathode/v2_LiCoO2.png`.
The structure is rebuilt for zinc-blende CZT, not copied from the LiCoO2 lattice.
FCC cation sites: (0,0,0), (0,1/2,1/2), (1/2,0,1/2), (1/2,1/2,0).
Te sites: those positions shifted by (1/4,1/4,1/4).
The finite 28-atom cluster joins unlike sites at sqrt(3)/4 lattice units.
Zn substitutes selected Cd sites for illustration; no detector composition x
or measured lattice parameter is asserted. XYZ coordinates are in lattice units.
Jmol/CPK atom colors: Cd #FFD98F; Zn #7D80B0; Te #D47A00. Perspective is orthographic with shaded spheres.
Crystallographic reference: https://www.mdpi.com/2073-4352/8/1/26

## Crystal

Bent wafer with a schematic atomic surface grid, inspired by
`../3_Simulations/O-2094 subsrate for Von Hamos analyzer 50x25 R206.pdf`.
That drawing specifies an aluminium substrate, 52 x 27 mm, R=206 mm.
The vignette exaggerates curvature. The surface grid is a visual symbol,
not a resolved Ge(880) atomic termination or a scaled mechanical model.

The asymmetric reflectivity curve is calculated, not hand-drawn: existing
`../2_Lower_Reflection/s1_reflection.py`, diffraction_setup(8,8,0,1e-3),
reflectivity_profile at 25500 eV about the corrected Bragg angle.
It is (R_sigma + R_pi)/2 from crystalpy's Guigay thick-crystal calculation,
for a flat perfect Ge(880) crystal, 1 mm thick. The displayed domain is +/-4 urad;
the ordinate is intrinsic reflectivity. Axes omit numerical ticks for icon use.
This is an ideal-crystal illustration: bending, strain and beam divergence are
not included, so the curve does not predict the response of the bent assembly.
Raw plotted values are in `4_Crystal/reflectivity.dat`.

## Pulse Shape

Real events selected by `../13_CZT/s1_plot.py`:
- check mark: index 3428, PSA prediction 1, num_peaks=1;
- cross: index 19518, PSA prediction 0, num_peaks=2.

Source HDF5 (current location):
`/home/smanti/WORK/SIDDHARTA/CZT/09_CZT_BTF/DATA/20261802_102216_Snap_Bin_file_ch0.h5`.
Predictions verified against `../13_CZT/max_values_test.h5`.
Each waveform is baseline-subtracted using its first 32 samples and normalized
to its maximum absolute amplitude. All 656 samples are retained, without smoothing.
The horizontal coordinate is a fraction of the full acquisition window, with
no numeric time scale claimed. Traces and acceptance symbols are black.
Numeric values are saved in `5_Pulse_Shape/waveforms.dat`.

## Typography

Text labels use Arial Bold; mathematical symbols use bold math.
The reference XAS/XANES SVGs retain their existing outlined labels.
Jmol colors: https://biomodel.uah.es/Jmol/colors/jmol_colors.en.htm
