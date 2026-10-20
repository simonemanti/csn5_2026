# PRISM source-to-detector simulation chain

`3_Simulations` implements five internal numerical stages for the candidate
laboratory Ag K-edge fluorescence-XAS system:

```text
W tube -> ideal slits -> finite Ge(880) crystal -> Ag sample -> CZT
          SHADOW4 (S1-S4)                  Geant4 (S5)
```

The authoritative proposal is
[`../VERSIONS/v8_Proposal_Grant_Giovani_2026.pdf`](../VERSIONS/v8_Proposal_Grant_Giovani_2026.pdf),
not the historical v2 draft. The proposal defines **four grant Work Packages**
with activities A1.1-A4.4. The five legacy `WP1`-`WP5` names used in this
directory are **simulation stages S1-S5**, not those grant WPs. They implement
the numerical core of grant WP1 and provide design inputs; software alone
cannot complete the procurement, hardware, commissioning, or experimental
activities in grant WP2-WP4.

See [`PROPOSAL_TRACEABILITY.md`](PROPOSAL_TRACEABILITY.md) for the detailed
mapping and [`config/proposal_requirements.json`](config/proposal_requirements.json)
for the machine-readable v8 requirements, gates, units, and missing inputs.

## Runtime conventions

Run commands below from the repository root. Python stages use the `shadow4`
environment. Every CLI exposes its effective defaults with `--help`:

```bash
conda run -n shadow4 python 3_Simulations/shadow4/wp1_monoenergetic.py --help
conda run -n shadow4 python 3_Simulations/shadow4/wp2_tube_source.py --help
conda run -n shadow4 python 3_Simulations/shadow4/wp3_slit_scan.py --help
conda run -n shadow4 python 3_Simulations/shadow4/wp4_end_to_end.py --help
```

All plotting entry points save their figures and call `plt.show()`. For batch
runs, select a non-interactive backend rather than removing that call:

```bash
MPLBACKEND=Agg conda run -n shadow4 python <script> <arguments>
```

Configuration is separate from simulation logic:

- `config/wp1_source.json` and `config/wp1_geometry.json`: source and Ge(880)
  baseline;
- `config/wp2_tube_source.json`: W-tube operating point, filtration,
  normalization, and energy-importance window;
- `config/wp3_slits.json`: slit positions, apertures, seeds, and Pareto
  objectives;
- `config/wp4_optimization.json`: end-to-end geometry grid, physical
  resolution scan, constraints, and selection;
- `config/wp5_detector.json` and `config/wp5_scan.json`: Geant4 reference
  geometry and detector scan.

Random seeds and resolved configuration are recorded in the outputs. Values in
these files are model assumptions, not approved hardware specifications.

## S1 (`WP1`) — monoenergetic Ge(880) baseline

Run the finite-source, monoenergetic SHADOW4 baseline:

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp1_monoenergetic.py
```

It traces a sagittally curved Ge(880) analyzer at 25.52 keV, resolves the
source-crystal and crystal-sample arms, scans the sagittal focus, and reports
geometrical interception separately from weighted diffraction acceptance. The
default geometry uses the configured finite 1 mm crystal thickness.

Outputs under `3_Simulations/results/wp1/` are:

- `wp1_summary.json`;
- `wp1_focal_scan.csv`;
- `wp1_phase_space.h5`;
- `wp1_diagnostics.{png,pdf}`;
- `wp1_geometry.{png,pdf}`.

The matching OASYS2 workflow is for interactive inspection:

```bash
conda run -n shadow4 python 3_Simulations/oasys/validate_wp1_ows.py
conda run -n shadow4 python -m oasys2.canvas --no-update \
  3_Simulations/oasys/wp1_monoenergetic.ows
```

The Python driver remains authoritative for batch results and reusable exports.

## S2 (`WP2`) — normalized SpekPy W-tube source

Run the configured SpekPy spectrum and polychromatic SHADOW4 transport:

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp2_tube_source.py
```

The SpekPy spectrum is cached by the complete operating point. The explicitly
sampled energy window and solid angle are converted to SHADOW4 ray weights in
`photons/mAs`; tube current and exposure are reporting-only multipliers and do
not regenerate the spectrum or ray trace. The energy, source position, and
direction distributions are factorized assumptions.

Outputs under `3_Simulations/results/wp2/` are:

- `wp2_summary.json`: configuration, cache identity, normalization,
  assumptions, throughput, and reporting-only rate scaling;
- `wp2_spectrum.csv`: complete source spectrum and incident/post-crystal
  sampled spectra;
- `wp2_phase_space.h5`: `source`, `post_crystal`, and `sample` groups;
- `wp2_diagnostics.{png,pdf}`;
- `cache/`: operating-point-keyed SpekPy data.

## S3 (`WP3`) — controlled two-slit scan

Run the configured aperture and position grid:

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp3_slit_scan.py
```

Within each seed, every case duplicates the same incident WP2 beam before
applying ideal rectangular, perfectly absorbing slit masks. Independent seeds
are aggregated only when all configured traces succeed. The scan reports
throughput, divergence, crystal illumination, sample spot, incident-energy
width, Pareto membership, and a **simulation diagnostic** selection. It does
not model slit-edge scatter or establish a hardware recommendation.

Outputs under `3_Simulations/results/wp3/` are:

- `wp3_case_seed_metrics.csv`;
- `wp3_aggregation.json`;
- `wp3_diagnostics.{png,pdf}`;
- `spectrum_cache/`.

## S4 (`WP4`) — end-to-end SHADOW4 screening and gated export

Run the source/slit/crystal/sample grid and its dedicated resolution scan:

```bash
conda run -n shadow4 python \
  3_Simulations/shadow4/wp4_end_to_end.py
```

The bundled geometry deliberately sets
`use_thick_crystal_approximation: false` and transports through the configured
finite 1 mm Ge crystal. The current CrystalPy thick-crystal approximation
creates non-physical off-Bragg wings for this polychromatic study; WP4 rejects
that mode. `tests/test_crystal_thickness_regression.py` preserves the central
response check and the suppression of the spurious wings:

```bash
conda run -n shadow4 python -m unittest \
  3_Simulations/tests/test_crystal_thickness_regression.py -v
```

The v8 EO3 gate of at most 10 eV applies to the **incident-energy resolution**.
WP4 evaluates it from the FWHM of a dedicated monoenergetic transmission
response `T(E)`, using common source coordinates and directions at every
energy and interpolated half-maximum crossings. The polychromatic
`2.35482 * sigma(E)` width is retained only as a Gaussian-equivalent diagnostic
and is not used for the 10 eV gate. A response with missing half-maximum
crossings or excessive energy-window edge weight is not selection-ready.
`--max-cases` is a software-smoke/partial-scan control: whenever it truncates
the configured 40-case grid, S4 forces a diagnostic status and cannot publish
an S5-approved phase space even if the executed subset passes its metric gates.

Outputs under `3_Simulations/results/wp4/` are:

- `wp4_scan.csv` and `wp4_aggregates.csv`;
- `wp4_resolution_response.csv`;
- `wp4_candidate_design.json` and `wp4_summary.json`;
- `wp4_sample_phase_space.csv` for feasible cases, otherwise
  `wp4_diagnostic_sample_phase_space.csv`;
- `wp4_diagnostics.{png,pdf}`;
- `wp4_resolution_response.{png,pdf}`;
- `wp4_phase_space.h5` only when every configured simulation gate is met.

If no scanned case is feasible, the minimum-violation case is explicitly
labelled `diagnostic_fallback_infeasible_not_for_wp5_design_input` and written
as `wp4_diagnostic_phase_space.h5`. In that case
`phase_space_hdf5_for_wp5` is `null`, the HDF5 approval attribute is false, and
the file is not an S5 design input. It may be opened only for an explicitly
diagnostic pipeline test with `--allow-diagnostic-input`; that switch does not
make the candidate feasible or WP5-ready.

At the start of a validated S4 campaign, the script invalidates every prior
feasible/diagnostic HDF5 and sample CSV in that exact output directory. The new
HDF5 is first written with an `.incomplete` suffix and published atomically
only after the other outputs and summary succeed, so a failed rerun cannot
leave an older phase space at the default S5 path.

## S5 (`WP5`) — Ag fluorescence and simplified CZT response

The full build, prepare, transport, analysis, and detector-scan interface is
documented in
[`geant4/wp5_fluorescence/README.md`](geant4/wp5_fluorescence/README.md).
The local Geant4 11.2.2 prefix is:

```text
/home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install
```

Build the serial C++ model outside the source tree:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
cmake -S 3_Simulations/geant4/wp5_fluorescence \
  -B /tmp/prism-wp5-build \
  -DGeant4_DIR=/home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/lib/cmake/Geant4 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/prism-wp5-build -j2
/tmp/prism-wp5-build/prism_wp5 --help
```

Prepare a **feasible, approved-by-the-simulation-gates** S4 export, transport
it, and analyze the event data:

```bash
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/prepare_phase_space.py \
  --input 3_Simulations/results/wp4/wp4_phase_space.h5 \
  --group sample \
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
```

Scan detector angle, sample-to-front-face distance, face area, and active
thickness over the configured multi-seed grid:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
MPLBACKEND=Agg conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/scan_detector.py \
  --binary /tmp/prism-wp5-build/prism_wp5 \
  --input 3_Simulations/results/wp5/wp5_phase_space.csv \
  --scan-config 3_Simulations/config/wp5_scan.json \
  --output-dir 3_Simulations/results/wp5/detector_scan
```

The complete bundled 48-case, three-seed, all-event scan is labelled
`conditional_simulation_diagnostic_not_approved_hardware` only for an approved
S4 input and cases satisfying the configured screening-statistics gates
(at least 100,000 prepared events and at least 25 K-alpha entries, 25 K-beta
entries, and 25 fluorescence-ROI events per seed). A synthetic/diagnostic
input, case limit, insufficient prepared events/seeds, or explicit event limit
is instead labelled
`software_smoke_or_partial_detector_scan_not_for_screening_claims`; a full run
with no statistically eligible geometry is labelled
`conditional_detector_scan_insufficient_statistics_not_for_screening_claims`.
Neither status can approve a CZT geometry or replace calibration,
charge-transport/electronics modeling, tolerance checks, or measurements.

## Data contracts

| Artifact | Contract |
|---|---|
| S2/S4 HDF5 | Root schema `PRISM_SHADOW4_PHASE_SPACE_V1`; groups `source`, `post_crystal`, and `sample`; datasets `x_m, y_m, z_m, dx, dy, dz, energy_keV, weight, status, ray_id`. |
| SHADOW4 weights | `weight` is `photons/mAs`; diffraction is encoded in weight, and only finite rows with `status > 0` and `weight > 0` are usable downstream. |
| S4 downstream gate | The S5 design-input path requires schema `PRISM_SHADOW4_PHASE_SPACE_V1`, root and `/sample/weight` units `photons/mAs`, group `/sample`, and an explicitly true root `downstream_wp5_design_input_approved` attribute (or valid metadata fallback). Missing/mismatched fields and false approval are accepted only with the recorded diagnostic override. |
| Prepared S5 CSV | Schema `PRISM_WP5_PHASE_SPACE_V1`; weighted resampling creates unit Monte Carlo events and records `normalization_weight_per_event = sum(valid upstream weight) / events` in comments and a sidecar metadata JSON. CSV and sidecar are published from `.incomplete` files; the C++ reader requires `requested_events` to equal the actual row count. |
| Raw Geant4 CSV | Schema `PRISM_WP5_RAW_V1`; one row per primary with source identity/normalization, raw and phenomenologically smeared CZT deposits, and Ag K-alpha/K-beta creation and detector-entry counters. The C++ transport rejects prepared CSVs without schema `PRISM_WP5_PHASE_SPACE_V1`, unit-event columns, and explicit per-event normalization. If `--events N` uses a random prepared prefix, the event weight is rescaled by `M/N` so the represented upstream total remains unchanged. |
| S5 analysis/scan | JSON schemas `PRISM_WP5_ANALYSIS_V1` and `PRISM_WP5_DETECTOR_SCAN_V1`, plus CSV tables and PNG/PDF diagnostics. Both use the stored C++ `smeared_edep_keV`; the single-run analyzer re-smears raw deposits only with explicit `--resmear`. |

Counting each positive SHADOW4 row as one photon would discard its diffraction
weight and bias the source. The preparer therefore performs weighted
resampling while preserving the represented upstream normalization.

## Validation commands and evidence boundary

Run the complete Python suite in the required environment:

```bash
conda run -n shadow4 python -m unittest discover \
  -s 3_Simulations/tests -v
```

Include the compiled executable in S5 interface and scan smoke tests:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
PRISM_WP5_BINARY=/tmp/prism-wp5-build/prism_wp5 \
  conda run -n shadow4 python -m unittest \
  3_Simulations/tests/test_wp5.py -v
```

These tests establish software behavior, serialization, deterministic
interfaces, physical gating logic, and executable smoke transport. They are
not experimental validation of throughput, energy resolution, efficiency,
background, acquisition time, or a design freeze.

Current common limitations include factorized tube phase space, an ideal
unstrained crystal, ideal slit absorption, vacuum transport without
unconfigured windows/air, a homogeneous Ag slab, and homogeneous
`Cd0.9Zn0.1Te`. CZT contacts, dead layers, pixels, electric/weighting fields,
charge trapping, charge sharing, electronics, pile-up, and dead time are not
modeled. Absolute rates remain conditional on the SpekPy brightness,
sampled-solid-angle normalization, current, exposure, and acquisition
metadata.
