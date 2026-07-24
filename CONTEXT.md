# PRISM project context

## Authoritative proposal

The current proposal is:

`VERSIONS/v2_Proposal_Grant_Giovani_2026-2.pdf`

Older OLTRE material and alternative `.docx` drafts are historical and must not be
used as the project baseline. Technical notes and RFQ documents are supporting
studies; they do not override the v2 proposal.

## Project identity

- Acronym: **PRISM**
- Full title: **Precision Room-temperature Instrumentation for high-energy x-ray
  absorption Spectroscopy Measurements**
- Applicant: Simone Manti
- Participating unit: INFN Sezione di Frascati

## Main objective

Develop and validate a laboratory platform for in-situ and operando
fluorescence-mode X-ray absorption spectroscopy on realistic samples, with
particular emphasis on absorption edges above 20 keV.

The platform combines crystal optics with efficient room-temperature hard-X-ray
detection. The detector concept in the abstract is a multichannel CZT system with
dedicated low-noise electronics, calibration, count-rate corrections, and spectral
reconstruction.

## Scientific positioning

PRISM addresses thick, dilute, heterogeneous, or environmentally constrained
samples for which transmission XAS is impractical or unrepresentative. Its value is
continuous laboratory access for long in-situ or operando campaigns, complementing
rather than replacing synchrotron, XFEL, and future compact-source measurements.

The project must be presented as detector and instrumentation R&D plus a validated
spectroscopic methodology, not as the purchase of a commercial X-ray source.

## Current methodological baseline

1. Quantitatively define the measurement requirements from the selected absorption
   edges, samples, and chemical observables.
2. Co-optimize source, crystal optics, sample geometry, and detector response using
   ray tracing and radiation-transport simulations.
3. Design and integrate a laboratory fluorescence-XAS prototype at LNF, building on
   VOXES infrastructure and expertise.
4. Validate energy calibration, resolution, useful count rate, background, dead
   time, pile-up, SNR, acquisition time, and reproducibility on reference samples.
5. Demonstrate the recovery of a predefined chemical observable on a realistic
   static and/or operando case study.
6. Assess transferability to EuAPS only after laboratory validation.

## Draft quantitative targets from v2

- acquisition time below 1 hour;
- SNR greater than 20;
- resolving power `E/DeltaE > 4000`;
- sub-keV CZT energy resolution;
- CZT quantum efficiency above 90% up to approximately 40 keV;
- positioning accuracy better than 10 micrometres;
- crystal angular reproducibility at the 0.5 mrad level.

These are proposal targets that still require a precise measurement protocol,
energy, sample, observable, and acceptance definition before they can be treated as
SMART milestones.

## Open inconsistencies in proposal v2

The following v2 passages are placeholders or conflict with the main abstract and
must be corrected in the next proposal version:

- Goal 2 mentions SDD or Si-PN detectors, whereas the abstract defines multichannel
  CZT as the enabling room-temperature detector technology above 20 keV.
- Goal 3 lists Fe, Ni, Mn, and Cu K-edges, all below 20 keV, whereas the stated
  capability gap concerns Mo, Rh, Ag, and Cd K-edges above 20 keV.
- WP1 is described primarily as matching EuAPS, although the main goal is a
  laboratory fluorescence-XAS platform.
- WP4 is an EuAPS demonstration without a preceding fully specified laboratory
  benchmark and realistic-sample demonstration.
- Calibration error and several WP descriptions remain undefined.

Until these points are resolved, use the abstract and the main goal paragraph as the
scientific priority: CZT-based laboratory fluorescence-XAS above 20 keV, followed by
transfer to EuAPS.

## Relation of local technical studies to PRISM

- `3_Simulations/` is an exploratory Ag K-edge Ge(880) SHADOW4/GEANT4 study. It
  supports the simulation goal but does not freeze the final PRISM crystal or
  geometry.
- `2_Lower_Reflection/` studies lower-order contamination for a Ge(880) candidate.
- `RFQ_Xray_source_PRISM_2026.md` investigates source options for a particular HAPG
  von Hamos scenario. That scenario must be validated against the fluorescence-XAS
  measurement concept before procurement.
- VOXES is the laboratory infrastructure and expertise base.
- EuAPS is a synergy and possible later demonstration platform, not a substitute for
  the laboratory validation objective.

## Working principles

- Start from the scientific observable and derive hardware requirements.
- Keep fluorescence-XAS distinct from scan-free transmission-XAS.
- Do not call an optical geometry fixed until the incident-energy encoding and the
  fluorescence reconstruction are explicitly demonstrated.
- Use absolute flux and realistic source, air/window, crystal, sample, detector, and
  DAQ models before making acquisition-time claims.
- State assumptions and uncertainties explicitly.
- Compare simulations with measurements at each integration stage.
- Keep the main validation above 20 keV; lower-energy measurements may be technical
  commissioning checks but not the central scientific demonstration.

## Coding conventions

- Prefer clear, modular, reproducible Python.
- Keep configuration separate from simulation logic.
- Record physical units, random seeds, software versions, and assumptions.
- With Matplotlib, always call `plt.show()` for generated plots.
- With `argparse`, display default values in `--help`.

## Proposal-writing conventions

- Write in concise scientific English.
- Make objectives and milestones SMART.
- Quantify performance at a specified energy and for a specified sample.
- Distinguish Methodology from Organisation: the former explains the scientific
  workflow and validation logic; the latter contains WPs, people, timeline,
  milestones, and deliverables.
- Continuously test the novelty, feasibility, scientific payoff, and likely referee
  criticism of each claim.
