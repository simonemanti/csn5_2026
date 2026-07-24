# PRISM — Grant Giovani INFN CSN5 2026

PRISM stands for **Precision Room-temperature Instrumentation for high-energy x-ray
absorption Spectroscopy Measurements**.

The current proposal source of truth is
[`VERSIONS/v2_Proposal_Grant_Giovani_2026-2.pdf`](VERSIONS/v2_Proposal_Grant_Giovani_2026-2.pdf).
Older OLTRE documents and alternative proposal drafts are retained only as historical
material.

## Project goal

PRISM will develop and validate a laboratory fluorescence-XAS platform for in-situ
and operando measurements on thick, dilute, heterogeneous, or otherwise
transmission-incompatible samples. The target capability is hard-X-ray absorption
spectroscopy above 20 keV using crystal optics and a room-temperature multichannel
CZT detector.

The platform is intended to recover quantitative chemical information, such as
absorption-edge shifts, near-edge intensity changes, and coordination-sensitive
spectral features, during long laboratory measurement campaigns. It complements
synchrotron and XFEL access and may later be transferred to compact-source
infrastructures such as EuAPS.

## Capability gap

Laboratory fluorescence-XAS above approximately 20 keV remains limited by the
coupled effects of:

- source flux and accepted phase space;
- crystal reflectivity, bandwidth, and energy resolution;
- sample and operando-cell absorption;
- fluorescence solid angle and scattering background;
- detector quantum efficiency and segmentation;
- electronic noise, count-rate capability, dead time, and pile-up;
- calibration and spectral-reconstruction uncertainty;
- acquisition time required for a chemically meaningful observable.

Silicon detectors lose efficiency in this range, while high-purity germanium systems
require cryogenic operation. PRISM investigates multichannel CZT as an efficient
room-temperature alternative coupled to optimized crystal optics and reconstruction.

## Scientific scope

The v2 proposal identifies Mo, Rh, Ag, and Cd K-edges as the principal high-energy
domain. The final proposal should select:

- one commissioning edge;
- one primary quantitative benchmark;
- one realistic static or operando case study;
- an optional higher-energy extension enabled only after the measured performance
  satisfies the laboratory validation gate.

Lower-energy Fe, Ni, Mn, or Cu measurements may be useful for commissioning existing
VOXES components, but they are not consistent with the central above-20-keV novelty
and should not be presented as the main PRISM validation.

## Methodological workflow

### 1. Requirements

Translate the selected edge, sample, and chemical observable into quantitative
requirements for energy range, resolving power, incident flux, fluorescence yield,
SNR, background, detector rate, and acquisition time.

### 2. Digital co-design

Combine source modelling, SHADOW4 crystal ray tracing, GEANT4 sample and detector
transport, and a realistic electronics/reconstruction response. Optimize the entire
measurement chain rather than ranking components by nominal tube power or detector
efficiency alone.

### 3. Detector development

Determine CZT thickness, pixel or channel geometry, active area, solid-angle
coverage, front-end shaping, and DAQ requirements. Characterize efficiency,
linearity, resolution, channel uniformity, dead time, pile-up, stability, and
background rejection.

### 4. Prototype integration

Integrate the selected source, optics, sample environment, motion and alignment
systems, CZT module, monitoring, and DAQ at LNF. Commission individual subsystems
before end-to-end operation.

### 5. Laboratory validation

Compare measured and simulated flux, energy calibration, resolution, spectral
response, SNR, dead time, background, acquisition time, and reproducibility. Validate
the recovered XANES observables against reference data.

### 6. Scientific demonstration and transfer

Demonstrate a predefined chemical observable on a realistic static and/or operando
sample. Only after this laboratory gate, assess transferability to EuAPS.

## Draft performance targets

Proposal v2 currently states:

- acquisition time below 1 hour;
- SNR greater than 20;
- resolving power `E/DeltaE > 4000`;
- sub-keV CZT energy resolution;
- CZT quantum efficiency above 90% up to approximately 40 keV;
- positioning accuracy better than 10 micrometres;
- crystal angular reproducibility at the 0.5 mrad level.

Each target must be tied to a defined edge, sample, spectral observable, acquisition
protocol, and uncertainty before becoming a milestone.

## Infrastructure and synergies

- **VOXES:** laboratory infrastructure, crystal-spectroscopy experience, mechanics,
  alignment, monitoring, and validation environment.
- **EuAPS:** possible transfer and demonstration after laboratory validation.
- **PANDORA:** potential synergy to be defined by a concrete shared method, resource,
  or measurement rather than by name alone.

## Repository map

- `VERSIONS/`: proposal versions; v2 is currently authoritative.
- `REFERENCES/`: grant-writing and scientific reference proposals.
- `2024/`, `2025/`: recent Grant Giovani examples and presentations.
- `1_Efficiency_Detectors/`: detector-efficiency studies.
- `2_Lower_Reflection/`: lower-order-reflection study for a Ge(880) candidate.
- `3_Simulations/`: exploratory Ag K-edge Ge(880) SHADOW4 simulation chain.
- `4_Quotation_XTube/`: X-ray source quotations.
- `RFQ_Xray_source_PRISM_2026.md`: source-market study for a specific HAPG von Hamos
  scenario; it is not the proposal source of truth.
- `X_Gantt_Table/`, `Y_Cost/`: organisation and cost material.

## Decisions still required

Proposal v2 contains several internal inconsistencies that must be resolved in the
next revision:

1. Replace the Goal 2 reference to SDD or Si-PN with a detector plan consistent with
   the multichannel CZT concept in the abstract, or explicitly redefine their limited
   monitoring role.
2. Replace the Fe/Ni/Mn/Cu main validation in Goal 3 with one or more K-edges above
   20 keV; retain low-energy measurements only as commissioning.
3. Define whether the crystal is a scanning monochromator before the sample or part
   of a scan-free energy-position encoding scheme. A transmission-style von Hamos
   arrangement does not by itself establish energy-resolved fluorescence-XAS.
4. Make laboratory validation the central project gate and EuAPS the subsequent
   transfer demonstration.
5. Specify the realistic sample, expected chemical change, reference spectrum, and
   success threshold.
6. Complete the undefined calibration outcome, WP3, WP4, organisation, costs, and
   risk table.

## Development conventions

- Keep geometry, source, detector, and run settings outside simulation logic.
- Record units, random seeds, software versions, and assumptions.
- Validate each subsystem before end-to-end optimization.
- Use absolute flux and realistic losses before predicting acquisition times.
- With Matplotlib, always call `plt.show()`.
- With `argparse`, expose default values in `--help`.
