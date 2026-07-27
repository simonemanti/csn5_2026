# PRISM minimum photon budget

This directory contains a proposal-level feasibility model for the Ag K-edge
reference experiment described in `../VERSIONS/v5_Proposal_Grant_Giovani_2026.pdf`.
It implements the smallest calculation that connects the existing SHADOW4
optical baseline to an absolute fluorescence count-rate estimate.

The modeled chain is

```text
W tube -> Be window -> Al filter -> air -> curved Ge(880) -> Ag sample -> CZT
```

SHADOW4 is the only ray-tracing or Monte-Carlo engine. `xraylib`, which is also
the material-constants backend used by SHADOW4 in this model, supplies analytic
attenuation coefficients, Ag fluorescence cross sections, line energies, and
CZT absorption. There is no GEANT4 transport, SpekPy source, or detector-event
simulation.

## Main result produced

Running the baseline creates:

- `results/prism_photon_budget.png` and `.pdf`: proposal-ready two-panel figure;
- `results/photon_budget_summary.json`: complete machine-readable provenance;
- `results/shadow4_seed_results.csv`: seed-by-seed optical convergence;
- `results/source_scenarios.csv`: rates and acquisition times for three tube
  operating points;
- `results/budget_stages.csv`: photon-rate waterfall;
- `results/proposal_numbers.md`: suggested text, caption, numbers, and mandatory
  caveat for the proposal.

Run from the repository root:

```bash
MPLBACKEND=Agg python 12_Photon_Budget/photon_budget.py
```

All command-line defaults are visible with:

```bash
python 12_Photon_Budget/photon_budget.py --help
```

The script calls `plt.show()` after saving the figure. `MPLBACKEND=Agg` makes
that call non-blocking for batch execution.

Run the tests with:

```bash
MPLBACKEND=Agg python -m unittest discover -s 12_Photon_Budget/tests -v
```

## What is calculated by SHADOW4

The ray trace reuses the verified candidate geometry from `3_Simulations`:

- symmetric, sagittally curved perfect Ge(880);
- 250 mm bending radius;
- 40 x 20 mm crystal aperture;
- 100 micrometre RMS Gaussian source size in both transverse axes;
- central energy 25.52 keV, just above the 25.514 keV Ag K edge;
- symmetric von Hamos arms obtained from
  `p = q = R / sin(theta_B)`;
- five independent random seeds in the production configuration.

SHADOW4 returns the weighted crystal throughput, geometrical interception and
sample spot. Reported spot widths are `2.355 × weighted RMS`, i.e. Gaussian-
equivalent FWHM values rather than histogram half-maximum measurements. The
throughput is conditional on the launched direction window:

```text
x': -0.06 ... +0.06 rad
z': -10 ... +10 microrad
```

That direction window is explicitly converted to a small-angle solid angle in
the absolute budget. The omitted direction-cosine Jacobian changes this
baseline by less than 0.1%. Consequently, the SHADOW4 conditional crystal
throughput is never mislabelled as an intrinsic efficiency of the complete
instrument or multiplied into an unrelated source acceptance.

## Absolute tube screening model

The W-tube continuum uses the Kramers form

```text
dN/dE = A (E0 - E) / E
```

and the engineering bremsstrahlung-efficiency approximation

```text
eta = 9e-10 Z V,
```

with `V` in volts. `A` is chosen so that integrating photon energy over the
continuum returns `eta` times the electrical tube power. The test suite checks
this energy normalization numerically.

The output is treated conservatively as isotropic over `4 pi`. Real tube
take-off angle, target self-absorption, housing, beam port and generator
operating curve are not known. Therefore the calculation retains an explicit
`0.3-3x` absolute-output envelope. This interval is a sensitivity range, not a
statistical confidence interval.

The three configured hardware cases are:

| Case | Operating point | Interpretation |
|---|---:|---|
| Phase-0 W | 60 kV, 75 W | proposed W replacement screening case, not the certified current Mo tube |
| Fallback | 100 kV, 500 W | integrated-source design point from the local RFQ study |
| Benchmark | 40 kV, 2 kW | operating point used for Ag K-edge measurements by Yamamoto (2026) |

The actual in-kind certificate describes a 60 kV, 50 W Mo tube. The 75 W W case
is retained only because it represents the proposed W replacement discussed in
the local source study. It must not be described as installed hardware.

## Passive losses

The baseline applies:

- 0.127 mm Be window;
- 0.2 mm Al filter, matching the minimum filter that removed the reported
  Ge(880) artefacts in the local Yamamoto paper;
- 1.03 m of dry air, approximately the sum of the two symmetric optical arms.

All values are editable in `config/baseline.json`.

## Analytic Ag fluorescence model

The reference sample is a uniform 20 micrometre Ag foil, matching the Yamamoto
reference measurement, at 45 degrees incidence
and 45 degrees take-off. For line `l`, the depth-integrated escape probability is

```text
P_l = (rho sigma_l / cos(alpha))
      [1 - exp(-rho t (mu_in/cos(alpha) + mu_l/cos(beta)))]
      / [rho (mu_in/cos(alpha) + mu_l/cos(beta))].
```

`sigma_l` is the xraylib Kissel fluorescence-production cross section. The
baseline useful ROI contains Ag K-alpha-1 and K-alpha-2. Incident attenuation
and fluorescence self-absorption are both included. Scattering and a detailed
background spectrum are not simulated; background enters only through the
declared background-to-signal ratio.

This reference-foil result does not predict the rate from a dilute or operando
sample. Concentration, matrix composition and geometry must be added before
making that claim.

## CZT screening model

The baseline is a 40 x 40 mm2, 2 mm thick Cd0.9Zn0.1Te array at 30 mm from the
sample. The exact on-axis rectangular solid angle is used. Intrinsic absorption
is calculated from the stoichiometric mass fractions and xraylib coefficients.
An explicit photopeak-collection factor of 0.85 and live-time factor of 0.90
represent charge sharing, incomplete collection, ROI losses and DAQ live time.

These two empirical factors are deliberately kept separate from intrinsic
absorption so that future CZT measurements can replace them directly.

## Acquisition-time definition

The proposal figure uses a deliberately conservative protocol:

- 101 sequential XANES points;
- SNR = 20 required independently at every point;
- background/signal = 1;
- identical useful rate at each point.

For useful signal rate `S` and background `B = b S`,

```text
t_point = SNR^2 (1 + b) / S.
```

The full scan time is `101 t_point`. This is stricter than an SNR requirement
defined only on an integrated edge step. Conversely, it does not include motor
motion, settling, calibration exposures or repeat scans.

## What can and cannot be claimed

The result can support this limited statement:

> Under explicit reference-foil, source, optical and detector assumptions, a
> high-power W tube and a large-solid-angle CZT array can reach the published
> 12 h Ag K-edge laboratory benchmark in the nominal screening model.

It cannot support:

- a procurement guarantee or 20% absolute-rate prediction;
- performance for dilute, thick or operando samples;
- a validated scattering background, dead-time or pile-up spectrum;
- a final crystal choice or bending-strain tolerance;
- performance of HAPG: this calculation is specifically an ideal Ge(880)
  candidate and SHADOW4 does not model HAPG mosaicity;
- a measured 10 eV incident bandwidth;
- a claim that the 75 W W tube is already installed.

The dominant validation gates are a calibrated tube spectrum at the actual
take-off angle, measured bent-crystal throughput/bandwidth, and measured
CZT photopeak efficiency and usable per-channel rate.

## Local evidence used

- `../VERSIONS/v5_Proposal_Grant_Giovani_2026.pdf`: current detailed PRISM
  methodology and Ag K-edge validation targets;
- `../SANDBOX/Yamamoto_2026_SelectionMonochromator.pdf`: 40 kV/50 mA W-tube,
  Ge(880), 0.2 mm Al filtering and approximately 12 h Ag K-edge benchmark;
- `../3_Simulations/`: verified monoenergetic SHADOW4 candidate baseline;
- `../1_Efficiency_Detectors/`: independent xraylib detector-efficiency study;
- `../Tubo_InKind/Documentation_XrayTube_MXR.pdf`: certificate for the actual
  60 kV/50 W Mo in-kind tube.
