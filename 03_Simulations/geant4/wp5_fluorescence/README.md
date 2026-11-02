# S5 (`WP5`) Ag fluorescence and CZT response

This directory implements the fifth **internal simulation stage**:

```text
feasible S4 sample phase space -> Ag slab -> fluorescence/background
                                           -> simplified CZT deposition
```

`WP5` is a retained filename, not grant WP5: the authoritative v8 proposal has
four grant Work Packages. This software supports grant A1.3 and provides
conditional input to A1.4. It does not implement the fabrication,
electronics/DAQ, calibration, commissioning, or experimental validation
required elsewhere in the proposal.

The incident central ray is `+y`; `x` and `z` are transverse. The Ag sample is
centred at the origin with thickness along `y`. Detector angle is measured
from `+y` toward `+x` in the `x-y` plane, so 90 degrees places the CZT along
`+x` with its face directed toward the sample.

All Python and C++ command-line interfaces show effective defaults with
`--help`. The Python plotting scripts save PNG/PDF files and always call
`plt.show()`; use `MPLBACKEND=Agg` for batch work.

```bash
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/prepare_phase_space.py --help
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/analyze_results.py --help
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/scan_detector.py --help
```

## Build the Geant4 executable

The repository is configured for the local Geant4 11.2.2 installation at:

```text
/home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install
```

Configure and build outside the source tree:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
cmake -S 3_Simulations/geant4/wp5_fluorescence \
  -B /tmp/prism-wp5-build \
  -DGeant4_DIR=/home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/lib/cmake/Geant4 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/prism-wp5-build -j2
/tmp/prism-wp5-build/prism_wp5 --help
```

For another installation, source its `geant4.sh` and omit `-DGeant4_DIR` when
its prefix is already discoverable through `CMAKE_PREFIX_PATH`.

The model uses `G4EmLivermorePhysics`, fluorescence, Auger cascades, PIXE, and
a configurable production cut. The reference defaults in
`../../config/wp5_detector.json` mirror the C++ CLI, but command-line values
are authoritative.

## 1. Prepare the S4 phase space

The normal design-chain input is the S4 file created only after all configured
simulation gates are met:

```bash
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/prepare_phase_space.py \
  --input 3_Simulations/results/wp4/wp4_phase_space.h5 \
  --group sample \
  --events 100000 \
  --output 3_Simulations/results/wp5/wp5_phase_space.csv
```

The non-diagnostic importer requires root schema
`PRISM_SHADOW4_PHASE_SPACE_V1`, group `/sample`, root and dataset weight units
`photons/mAs`, and an explicitly true
`downstream_wp5_design_input_approved` flag. It then retains only finite
`status > 0`, `weight > 0` rows, normalizes directions, and resamples rows with
probability proportional to their SHADOW4 weight. It writes unit Monte Carlo
events and records:

```text
normalization_weight_per_event = sum(valid upstream weight) / events
```

The prepared CSV uses schema `PRISM_WP5_PHASE_SPACE_V1`; metadata is written
both as leading comments and to `wp5_phase_space.metadata.json`. Both files
are published atomically from `.incomplete` paths. The C++ reader rejects a
truncated file unless its actual event-row count equals `requested_events`.

### Infeasible S4 diagnostic input

If S4 finds no case satisfying all gates, it writes
`wp4_diagnostic_phase_space.h5`, labels it
`diagnostic_fallback_infeasible_not_for_wp5_design_input`, and sets
`downstream_wp5_design_input_approved=false`. The preparer rejects that file by
default.

It can be forced through the interface only for an explicit software-pipeline
diagnostic:

```bash
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/prepare_phase_space.py \
  --input 3_Simulations/results/wp4/wp4_diagnostic_phase_space.h5 \
  --group sample \
  --events 10000 \
  --allow-diagnostic-input \
  --output /tmp/wp5_diagnostic_phase_space.csv
```

`--allow-diagnostic-input` is also required for an older WP1 or arbitrary HDF5
that lacks any part of the S4 schema/unit/approval contract. It records every
override reason but does not satisfy the incident-energy-resolution gate,
approve a design, or make the phase space WP5-ready for design claims.

### Synthetic software smoke input

An independent synthetic fallback is available only for interface and
particle-transport smoke tests:

```bash
conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/prepare_phase_space.py \
  --synthetic-monoenergetic \
  --events 200 \
  --output /tmp/wp5_synthetic.csv
```

Synthetic input is not evidence for tube flux, a feasible S4 geometry,
acquisition time, or detector performance.

## 2. Transport particles

Source the Geant4 runtime data and run the prepared unit events:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
/tmp/prism-wp5-build/prism_wp5 \
  --input 3_Simulations/results/wp5/wp5_phase_space.csv \
  --output 3_Simulations/results/wp5/wp5_events.csv
```

`--events 0` (the default) consumes every prepared CSV row. If `--events N`
uses only a prefix of `M` independently resampled rows, the transport changes
the per-event normalization from `W/M` to `W/N` (factor `M/N`). The represented
upstream total therefore stays `W`, with correspondingly larger Monte Carlo
uncertainty. Geometry, physics, seed, source gap, production cut, and Gaussian
response parameters can be overridden explicitly; inspect all defaults with:

```bash
/tmp/prism-wp5-build/prism_wp5 --help
```

The transport rejects an input CSV unless it declares
`schema=PRISM_WP5_PHASE_SPACE_V1` and a positive
`normalization_weight_per_event`, and every row satisfies the unit-event
contract; there is no silent unit-weight fallback.

The raw event CSV schema is `PRISM_WP5_RAW_V1`. It has one row per primary and
records:

- source event/row, position, direction, energy, unit weight, and represented
  normalization;
- total, primary, secondary, gamma, electron, and other CZT deposits;
- reproducibly smeared deposited energy;
- secondary-gamma, Ag K-alpha, and Ag K-beta creation counts;
- secondary-gamma and Ag K-alpha/K-beta CZT-entry counts and entered energy.

## 3. Analyze one detector geometry

```bash
MPLBACKEND=Agg conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/analyze_results.py \
  --input 3_Simulations/results/wp5/wp5_events.csv \
  --output-dir 3_Simulations/results/wp5
```

The analyzer writes:

- `wp5_summary.json`, schema `PRISM_WP5_ANALYSIS_V1`;
- `wp5_spectrum.png`;
- `wp5_spectrum.pdf`.

It reports raw/smeared detection proxies, represented input weight, Ag
K-alpha/K-beta regions of interest, non-ROI background, secondary creation and
CZT-entry counters, and the exact centred-rectangle solid-angle estimate.
By default the stored C++ `smeared_edep_keV` column is authoritative, matching
the detector scanner. To perform a separate sensitivity analysis from raw
deposits, pass `--resmear` together with the desired response parameters and
seed; that mode is recorded in the summary. Deposited-energy ROIs depend on
the parameterized smearing model; they are not a measured CZT calibration.

## 4. Scan detector geometry

The configured scan varies angle, sample-centre-to-front-face distance, active
face width/height, and active thickness. The bundled grid contains 48 geometry
cases and three independent Geant4 seeds. `events: 0` uses every prepared row
in each run.

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
MPLBACKEND=Agg conda run -n shadow4 python \
  3_Simulations/geant4/wp5_fluorescence/scan_detector.py \
  --binary /tmp/prism-wp5-build/prism_wp5 \
  --input 3_Simulations/results/wp5/wp5_phase_space.csv \
  --scan-config 3_Simulations/config/wp5_scan.json \
  --output-dir 3_Simulations/results/wp5/detector_scan
```

The scanner requires every configured seed to succeed before a geometry is
selection-eligible. The bundled screening contract also requires an approved
S4 input, at least 100,000 prepared events, at least three independent seeds,
and—for every seed—at least 25 K-alpha CZT entries, 25 K-beta entries, and 25
fluorescence-ROI events. These configurable count gates correspond to about
20% relative Poisson uncertainty at the threshold; they are a minimum
numerical-screening criterion, not detector validation. The scan compares
weighted Ag K-alpha/K-beta entries,
deposited-energy fluorescence-ROI and background proxies, geometrical solid
angle, and active volume. A complete 48-case, three-seed, all-event
multi-objective/Pareto result is labelled:

```text
conditional_simulation_diagnostic_not_approved_hardware
```

Outputs are:

- `wp5_detector_scan_runs.csv`;
- `wp5_detector_scan_aggregates.csv`;
- `wp5_detector_scan_summary.json`, schema
  `PRISM_WP5_DETECTOR_SCAN_V1`;
- `wp5_detector_scan.{png,pdf}`;
- optional per-case raw event CSVs when `--keep-raw` is supplied.

Use `--max-cases`, `--seeds`, and `--events` for bounded software smoke tests.
A synthetic/diagnostic input, truncated grid, insufficient prepared-event or
seed count, or explicit event limit automatically changes the status to
`software_smoke_or_partial_detector_scan_not_for_screening_claims`; it cannot
be reported as the complete conditional screening. If a full otherwise
eligible run has no geometry passing every per-seed signal-count gate, its
status is
`conditional_detector_scan_insufficient_statistics_not_for_screening_claims`.

## Validation

Run the Python contracts and pure numerical tests:

```bash
conda run -n shadow4 python -m unittest \
  3_Simulations/tests/test_wp5.py -v
```

Build the binary first and expose it to include the compiled help and real
single-case detector-scan smoke checks:

```bash
source /home/smanti/CODES/GEANT4/geant4-v11.2.2/geant-install/bin/geant4.sh
PRISM_WP5_BINARY=/tmp/prism-wp5-build/prism_wp5 \
  conda run -n shadow4 python -m unittest \
  3_Simulations/tests/test_wp5.py -v
```

These checks validate software interfaces, event accounting, strict
serialization, geometry enumeration, and smoke transport. They do not
constitute experimental validation.

## Model and evidence limits

- Ag is a homogeneous rectangular slab.
- CZT is homogeneous active `Cd0.9Zn0.1Te`; contacts, dead layers, pixel gaps,
  electric and weighting fields, charge transport/trapping, charge sharing,
  electronics, pile-up, and dead time are absent.
- The Gaussian energy resolution is phenomenological and not a measured
  calibration.
- Detection efficiencies and ROI/background quantities are conditional
  weighted proxies per represented input phase-space weight.
- The centred-rectangle solid angle is an independent geometric estimate; it
  does not replace Geant4 transport.
- Absolute rates require a physically calibrated S2/S4 normalization and
  explicit current, exposure, and live-time metadata.
- A useful fluorescence spectrum or stable multi-objective scan may require
  many more events than a smoke test because fluorescence yield and detector
  solid angle are limited.
- No scan result in this directory is an approved detector design, procurement
  decision, acceptance test, or experimental operating point.
