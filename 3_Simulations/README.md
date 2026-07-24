# PRISM exploratory Ag K-edge simulation chain

This directory supports PRISM Goal 1 as a candidate Ge(880) optical study. It does
not define the final PRISM architecture, detector choice, or grant work-package
structure. The authoritative proposal is
`../VERSIONS/v2_Proposal_Grant_Giovani_2026-2.pdf`.

The current model tests a possible tube-crystal-sample transport chain and
establishes the numerical workflow. A final fluorescence-XAS design must also
include an explicit incident-energy scan or energy-position encoding strategy,
absolute source flux, sample interactions, and the multichannel CZT response.

WP1 now contains a reproducible monoenergetic SHADOW4 baseline for a symmetric
Ge(880) Von Hamos optic near the Ag K edge.  The 25.52 keV default is just
above the approximately 25.514 keV edge, so it can later seed Ag K-shell
interactions.  It traces a configurable finite
source to a sagittally curved crystal, finds the intensity-weighted sagittal
focus, propagates to a sample plane, and records both geometrical and weighted
diffraction throughput.

## Run WP1

Use the requested environment from the repository root:

```bash
conda run -n shadow4 python 3_Simulations/shadow4/wp1_monoenergetic.py
```

All CLI defaults are visible with:

```bash
conda run -n shadow4 python 3_Simulations/shadow4/wp1_monoenergetic.py --help
```

The source and geometry assumptions are separate from the simulation logic:

- `config/wp1_source.json`
- `config/wp1_geometry.json`

The default 250 mm bend radius and corrected Ge(880) Bragg angle give the
symmetric Von Hamos arm lengths

```text
p = q = R / sin(theta_B).
```

The script also evaluates the general sagittal imaging equation

```text
1/p + 1/q = 2 sin(theta_B) / R
```

when a non-symmetric source distance is configured.  In SHADOW4 this layout is
a sagittal cylindrical `S4SphereCrystal` with downward convexity.  X is the
sagittal/focusing coordinate, Y is the central-ray direction, and Z is the
tangential coordinate.

Default results are written under `3_Simulations/results/wp1/`:

- `wp1_summary.json`: configuration, versions, assumptions, acceptance, focus,
  footprint, and sample spot metrics;
- `wp1_focal_scan.csv`: longitudinal RMS scan;
- `wp1_phase_space.h5`: crystal-footprint, post-crystal, and sample ray groups
  with `x_m, y_m, z_m, dx, dy, dz, energy_keV, weight, status, ray_id`, plus
  resolved distances and focal metadata;
- `wp1_diagnostics.png` and `.pdf`: footprint, post-crystal distribution,
  directions, focal scan, sample profile, and acceptance accounting.
- `wp1_geometry.png` and `.pdf`: central-ray source-crystal-sample layout in
  the local crystal frame and a 3D rendering of the sagittally curved crystal
  surface, including physical dimensions, Bragg angle, and arm lengths.

The diagnostic figure is always passed to `plt.show()` after it is saved.  For
non-interactive batch jobs, select a non-interactive Matplotlib backend in the
environment; `--no-plots` is intended only for automated tests.

Run the tests inside the same environment:

```bash
conda run -n shadow4 python -m unittest discover -s 3_Simulations/tests -v
```

## OASYS2 visualization

The matching visual workflow is `oasys/wp1_monoenergetic.ows`. It connects the
configured geometrical source and sagittal Ge(880) crystal to a sample X-Z
plot, a crystal-footprint X-Y plot, and the SHADOW4 beamline information
viewer. Open it with:

```bash
conda run -n shadow4 python -m oasys2.canvas \
  3_Simulations/oasys/wp1_monoenergetic.ows
```

The environment now contains OASYS2 0.0.55, OASYS2-SHADOW4 0.0.46, and
SHADOW4 0.1.88. Validate the workflow against the installed widget registry
with:

```bash
conda run -n shadow4 python 3_Simulations/oasys/validate_wp1_ows.py
```

The Python driver remains authoritative for batch scans and reusable data
exports; the OASYS2 workflow is intended for interactive visualization and
debugging.

## Interpretation and limitations

SHADOW4 stores dynamical-diffraction reflectivity as ray weight; it does not
randomly discard every off-Bragg ray.  Therefore the reported WP1 throughput is
the sum of valid reflected weights divided by launched weight.  It is
conditional on the angular range in the source configuration and is not an
intrinsic crystal efficiency.  The summary keeps the total weighted rejected
fraction and also gives an exclusive split into geometric miss, diffraction
loss after intercept, and reflected weight.

The HDF5 file deliberately retains all rays for diagnostics.  A GEANT4 importer
must select `status > 0` and resample rows with probability proportional to
`weight`; counting each positive-status row as one photon would distort the
beam.  The sample group uses a local reflected-ray frame with `y_m = 0`; its
resolved distance from the crystal is stored in the group and root metadata.

This first model is deliberately not an absolute-flux prediction.  It assumes a
perfect crystal locally parallel to the cylindrical surface and omits bending
strain, real tube spectrum, windows/air, slits, and absolute tube brightness.
Only X is focused; Z is the flat tangential direction, so its reported width is
not a second focus.  With the thick-crystal approximation enabled, the 1 mm
configuration value is recorded but is not a validated thickness optimization.
The 100 µm Gaussian source size, 250 mm radius, crystal dimensions, and angular
range are exposed assumptions, not optimized hardware recommendations.  The
default ray count and narrowed ±10 µrad tangential sampling window improve the
weighted Monte Carlo statistics while retaining explicit rejection accounting.
