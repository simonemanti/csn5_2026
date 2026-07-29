# PRISM Ag K-edge simulation context

## Authority and vocabulary

The requirements authority is
[`../VERSIONS/v8_Proposal_Grant_Giovani_2026.pdf`](../VERSIONS/v8_Proposal_Grant_Giovani_2026.pdf).
The SHA-256 and extracted requirements are recorded in
[`config/proposal_requirements.json`](config/proposal_requirements.json).

The v8 proposal defines four grant Work Packages and activities A1.1-A4.4.
This directory retains five historical filenames labelled `WP1`-`WP5`; they
are internal **simulation stages S1-S5**, not grant WPs:

| Internal stage | Legacy filename | Numerical role | Main v8 mapping |
|---|---|---|---|
| S1 | `wp1_monoenergetic.py` | Monoenergetic Ge(880) optical baseline | A1.1-A1.2, partial |
| S2 | `wp2_tube_source.py` | SpekPy W-tube spectrum and normalized transport | A1.2 |
| S3 | `wp3_slit_scan.py` | Controlled slit position/aperture scan | A1.2; input to A1.4 |
| S4 | `wp4_end_to_end.py` | End-to-end SHADOW4 screening and gated phase-space export | A1.2; input to A1.3-A1.4 |
| S5 | `geant4/wp5_fluorescence/` | Ag interaction, fluorescence/background, and simplified CZT response | A1.3; input to A1.4 |

Together they implement the numerical core of grant WP1. They do not by
themselves satisfy its validation/design-freeze gate, and they cannot complete
grant WP2 detector/DAQ work, grant WP3 procurement/integration/commissioning,
or grant WP4 measurements on reference and realistic samples. The detailed
mapping and evidence boundary are in
[`PROPOSAL_TRACEABILITY.md`](PROPOSAL_TRACEABILITY.md).

## Scientific objective and candidate chain

The implemented chain screens a VOXES-inspired, sagittally focusing Ge(880)
layout for fluorescence-mode XAS near the Ag K edge:

```text
W-anode tube -> Slit 1 -> Slit 2 -> Ge(880) -> Ag sample -> CZT
                      SHADOW4                    Geant4
```

The model studies:

- source spectrum and normalized flux in an explicit angular/energy window;
- crystal interception, weighted diffraction, footprint, focus, and sample
  phase space;
- slit effects on divergence, illumination, flux, spot, and bandwidth;
- the flux/spot/incident-energy-resolution compromise;
- Ag fluorescence and scattering followed by a simplified CZT deposit;
- conditional detector angle, distance, area, and thickness trade-offs.

Incident-energy resolution and CZT fluorescence-energy resolution are distinct
observables. The v8 10 eV EO3 gate refers to incident-energy resolution.

## Coordinate and interface conventions

For the SHADOW4 source frame, `+y` is the incident central ray and `x,z` are
transverse. The Geant4 bridge retains that convention: the Ag thickness is
along `y`, and detector angle is measured from `+y` toward `+x` in the `x-y`
plane.

The S2/S4 HDF5 contract is
`PRISM_SHADOW4_PHASE_SPACE_V1` with groups `source`, `post_crystal`, and
`sample`. Each group stores:

```text
x_m, y_m, z_m, dx, dy, dz, energy_keV, weight, status, ray_id
```

SHADOW4 diffraction is carried by `weight`, whose unit is `photons/mAs` for
the normalized S2-S4 chain. Downstream transport must retain finite rows with
`status > 0` and `weight > 0` and sample them proportionally to weight. S5
records the represented weight per unit Geant4 event rather than assigning
every surviving SHADOW4 row equal physical importance.

## Implemented stages

### S1 (`WP1`) — monoenergetic baseline

S1 defines the finite source and sagittally curved Ge(880), traces the
crystal/sample planes, resolves the imaging arms, scans the sagittal focus, and
exports acceptance, footprint, profile, focal, geometry, and phase-space
artifacts.

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp1_monoenergetic.py
```

The default crystal is a finite 1 mm Ge crystal. Only `x` is sagittally
focused; `z` is the flat tangential direction.

### S2 (`WP2`) — realistic tube spectrum

S2 creates and caches the configured SpekPy W-anode spectrum, samples its
explicit energy window, converts the on-axis fluence to photons/mAs in the
sampled solid angle, and transports it through the S1 optic.

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp2_tube_source.py
```

Energy, position, and direction are factorized. Current and exposure scale
reported rates only. Outputs comprise strict JSON metadata, spectrum CSV,
HDF5 source/post-crystal/sample phase space, cache, and PNG/PDF diagnostics.

### S3 (`WP3`) — slit scan

S3 applies ideal rectangular masks before the crystal. For a controlled
comparison, every case within a seed duplicates one identical S2 beam; only
cases completed for all configured seeds are selection-eligible.

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp3_slit_scan.py
```

It exports per-case/per-seed CSV, complete aggregation JSON, Pareto membership,
a conditional diagnostic selection, and PNG/PDF plots. This selection is not
a manufacturing aperture or alignment recommendation.

### S4 (`WP4`) — end-to-end screening

S4 scans curvature, source/image arm scaling, and slit designs, aggregates
independent seeds, applies physical gates, and conditionally exports a sample
phase space.

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp4_end_to_end.py
```

Three safeguards define the S4/S5 boundary:

1. The bundled geometry uses the configured finite 1 mm Ge thickness
   (`use_thick_crystal_approximation: false`). WP4 rejects the current
   CrystalPy thick-crystal approximation because it produces non-physical
   off-Bragg tails. The behavior is locked by:

   ```bash
   conda run -n shadow4 python -m unittest \
     3_Simulations/tests/test_crystal_thickness_regression.py -v
   ```

2. The physical incident-energy FWHM is extracted from a dedicated
   monoenergetic transmission response `T(E)`, with common source
   coordinates/directions at every energy and interpolated half-height
   crossings. This value, not the polychromatic Gaussian-equivalent
   `2.35482 * sigma(E)` diagnostic, is tested against the 10 eV gate.

   A `--max-cases` run that truncates the configured grid is always a software
   smoke/partial scan and cannot satisfy the S4-to-S5 hand-off gate.

3. A feasible case is written as `wp4_phase_space.h5` with
   `downstream_wp5_design_input_approved=true`. If no case meets every gate,
   S4 exports only `wp4_diagnostic_phase_space.h5`, labels the selected
   minimum-violation fallback
   `diagnostic_fallback_infeasible_not_for_wp5_design_input`, and sets the
   approval attribute false. This file is not S5-ready. A validated campaign
   invalidates older hand-off artifacts when it starts and publishes its new
   HDF5 atomically only after the remaining outputs succeed.

The S5 preparer requires the exact S4 schema, `photons/mAs` units on the root
and `/sample/weight`, group `/sample`, and explicitly true downstream approval.
It refuses an infeasible, unapproved, or non-conforming file by default.
`--allow-diagnostic-input` is an explicit software-pipeline diagnostic
override only; it does not change feasibility, approve downstream design use,
or validate the hardware.

### S5 (`WP5`) — Ag/CZT Geant4 transport and detector scan

S5 uses `G4EmLivermorePhysics`, enables fluorescence, Auger cascades and PIXE,
and transports prepared sample-plane primaries through a homogeneous Ag slab
to a homogeneous `Cd0.9Zn0.1Te` active volume. It records raw deposits,
particle/primary/secondary components, a phenomenological Gaussian response,
and Ag K-alpha/K-beta creation and CZT-entry counters.
The C++-stored `smeared_edep_keV` response is authoritative for both the scan
and the default single-run analysis; `--resmear` is an explicit alternative
analysis from raw deposited energy.
When only `N` of `M` independently resampled prepared rows are transported,
the C++ event weight is multiplied by `M/N`; this preserves the represented
upstream photons/mAs while increasing Monte Carlo uncertainty.

Build against the local Geant4 11.2.2 prefix:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
cmake -S 3_Simulations/geant4/wp5_fluorescence \
  -B /tmp/prism-wp5-build \
  -DGeant4_DIR=/home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/lib/cmake/Geant4 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/prism-wp5-build -j2
```

Prepare, transport, analyze, and scan:

```bash
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/prepare_phase_space.py \
  --input 3_Simulations/results/wp4/wp4_phase_space.h5 \
  --events 100000 \
  --output 3_Simulations/results/wp5/wp5_phase_space.csv

source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
/tmp/prism-wp5-build/prism_wp5 \
  --input 3_Simulations/results/wp5/wp5_phase_space.csv \
  --output 3_Simulations/results/wp5/wp5_events.csv

MPLBACKEND=Agg conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/analyze_results.py \
  --input 3_Simulations/results/wp5/wp5_events.csv \
  --output-dir 3_Simulations/results/wp5

source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
MPLBACKEND=Agg conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/scan_detector.py \
  --binary /tmp/prism-wp5-build/prism_wp5 \
  --input 3_Simulations/results/wp5/wp5_phase_space.csv \
  --scan-config 3_Simulations/config/wp5_scan.json \
  --output-dir 3_Simulations/results/wp5/detector_scan
```

The full configured detector scan requires an approved S4 input, at least
100,000 prepared events, three independent Geant4 seeds, and the configured
per-seed K-alpha/K-beta/ROI count gates before labelling its result
`conditional_simulation_diagnostic_not_approved_hardware`. A truncated grid,
synthetic/diagnostic input, explicit event limit, insufficient prepared events,
or insufficient seed count is labelled as a software smoke/partial scan
instead; a full run that fails signal-count gates is explicitly
insufficient-statistics. See
[`geant4/wp5_fluorescence/README.md`](geant4/wp5_fluorescence/README.md) for
the full contracts, diagnostic override, synthetic smoke input, and outputs.

## Execution and evidence rules

- Keep source, geometry, scan, response, and selection inputs configurable.
- Use reproducible seeds and record resolved parameters and software versions.
- Every argparse `--help` must display effective defaults.
- Every Matplotlib entry point must call `plt.show()` after saving plots.
- Label purely numerical outputs `simulation` or `diagnostic`; reserve
  `measurement` and `validated` for traceable experimental data.
- A numerical Pareto/utility selection is not a design freeze, detector
  approval, procurement specification, or experimental operating domain.
- Do not infer absolute rate or acquisition time without a calibrated tube
  brightness/acceptance chain and explicit current/exposure metadata.
- Do not optimize or approve detector hardware from an infeasible S4 input.

Run the software tests with:

```bash
conda run -n shadow4 python -m unittest discover \
  -s 3_Simulations/tests -v
```

These tests validate code paths, physical safeguards, formats, and executable
interfaces; they do not constitute the experimental validation required by
the v8 proposal.

## Known model limits

The current implementation omits tube heel-effect correlations, unconfigured
windows/air, crystal bending strain and manufacturing errors, slit-edge
physics, measured sample composition/morphology, and a detailed CZT/electronics
chain. The detector has no contacts, dead layers, segmentation, fields,
weighting potential, charge transport/trapping, charge sharing, electronics,
pile-up, or dead time. The Gaussian response is parameterized rather than
calibrated. All fluxes, efficiencies, spectra, and selected geometries are
therefore conditional on their stated inputs and assumptions.
