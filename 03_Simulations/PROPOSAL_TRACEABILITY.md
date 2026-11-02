# PRISM proposal traceability for `3_Simulations`

## Authority and vocabulary

The authoritative requirements source is
`../VERSIONS/v8_Proposal_Grant_Giovani_2026.pdf` (SHA-256 recorded in
`config/proposal_requirements.json`). Page references below use the physical PDF
page, followed by the printed page in parentheses.

The proposal defines **four grant Work Packages**, with activities
**A1.1–A4.4** (Figure 5, PDF p. 9, printed p. 8). The five `WP1`–`WP5` entries
in the legacy `CONTEXT.md` are instead **simulation stages**. They are a
technical decomposition of the source-to-detector model and support only the
simulation/design work of grant WP1. They must not be reported as grant Work
Packages and cannot, by themselves, satisfy grant WP2–WP4.

In new code and reports, refer to the legacy entries as `legacy stage S1` to
`S5`, retaining the old `WP` name only when pointing to an existing file.

## Legacy simulation-stage mapping

| Legacy stage | Technical scope | v8 activity mapping | Evidence boundary |
|---|---|---|---|
| S1 (`WP1`) | Monoenergetic source, Ge(880), crystal footprint, focus and sample plane | A1.1 (partial requirements check); A1.2 (optical baseline) | Simulated acceptance and focus only. It is not an absolute-flux prediction or a frozen design. |
| S2 (`WP2`) | Realistic W-tube spectrum and transport | A1.2 | Requires an absolute, traceable tube spectrum/brightness before rate and acquisition-time claims are possible. |
| S3 (`WP3`) | Slit position/aperture scans | A1.2; input to A1.4 | Produces predicted trade-offs. A selected aperture becomes a design requirement only after tolerance and hardware checks. |
| S4 (`WP4`) | End-to-end SHADOW4 source–slits–crystal–sample model and phase-space export | A1.2; input to A1.3 and A1.4 | The exported phase space must preserve ray status and diffraction weights. It is not sample or detector validation. |
| S5 (`WP5`) | GEANT4 sample fluorescence, scattering and CZT energy deposition | A1.3; input to A1.4 | Simulation can predict spectra and background. Charge transport, electronics and measured CZT performance belong to grant WP2. |

Together S1–S5 can implement the numerical core of **grant WP1**, but D1 and
MS1 additionally require a documented validation basis, approved procurement
specifications and an explicit design-freeze decision.

## Grant WP implementation boundary

| Grant WP/activity | What belongs in `3_Simulations` | What requires hardware, measurement or external action |
|---|---|---|
| **WP1 — Requirements, simulations and design freeze**, M1–M6 | **A1.1:** requirements and acceptance registry. **A1.2:** SHADOW4 scans of source, reflections, crystal, slits, distances, spot, bandwidth, flux and tolerances. **A1.3:** GEANT4 absorption, fluorescence, self-absorption, scattering, background and CZT deposition. **A1.4:** multi-objective selection, scan kinematics and frozen-configuration dossier. See Methodology, PDF pp. 6–7 (printed pp. 5–6), and Organisation, PDF p. 8 (printed p. 7). | Approval of the frozen design and procurement specifications. Calling the workflow measurement-validated requires analytical/VOXES benchmarks or instrument data. |
| **WP2 — CZT, front-end, DAQ, calibration and characterization**, M4–M15 | **A2.1:** configurable 20-pixel, 2-mm CZT geometry, field/weighting-potential and charge-transport model. **A2.2:** synthetic 64-channel, 16-bit, 125-MS/s waveform chain, reconstruction, PSA/ML and fault labels. **A2.3–A2.4:** simulated calibration/rate scans, operating-point optimizer and MS2 evaluator. See PDF pp. 5–6 (printed pp. 4–5). | Fabrication and biasing of the CZT/front-end, DAQ firmware/hardware, channel calibration, measured efficiency/resolution/stability/dead-time/pile-up, and final operating-point validation. |
| **WP3 — Procurement, mechanics, integration and commissioning**, M10–M18 | **A3.1:** design-derived BOM and acceptance-test schema. **A3.2:** kinematic/digital twin, If/I0 exchange geometry, travel, collision and tolerance checks. **A3.3:** control/DAQ emulators, synchronized scan state machine and fault injection. **A3.4:** virtual commissioning and prediction-versus-measurement analysis tools. See PDF pp. 6 and 8–9 (printed pp. 5 and 7–8). | Procurement, mechanical assembly, cabling, alignment, hardware/control integration, commissioning, and the measurements needed for MS3. |
| **WP4 — Ag references and realistic-sample demonstration**, M16–M24 | **A4.1:** synthetic Ag-foil scan and reproducibility analysis. **A4.2:** reference-spectrum forward model and XANES reconstruction. **A4.3:** configurable thick/dilute/heterogeneous sample and chemical-state recovery tests. **A4.4:** predicted performance and operating-domain maps. See PDF pp. 8–10 (printed pp. 7–9). | Ag-foil/reference-compound measurements, the realistic-sample experiment, measured operating-domain validation, and experimental datasets D3/D4 and MS4. |

## Proposal gates

- **MS1/D1, M6:** frozen geometry, approved procurement specifications and a
  validated SHADOW4–GEANT4 workflow.
- **MS2/D2, M15:** measured CZT efficiency above 90% at 50 keV, energy
  resolution at most 2% at 25.5 keV, dead time below 10%, and residual pile-up
  below 5% at the selected rate.
- **MS3, M18:** commissioned scan/calibration; measured rate within 20%, and
  spot size and incident-energy resolution within 10%, of simulation.
- **D3, M21:** measured Ag-foil and reference-compound XANES dataset and
  quantitative validation report.
- **MS4/D4, M24:** measured Ag K-edge XANES with SNR at least 20 and edge
  reproducibility within 1 eV; two chemical states separated by at least
  3 sigma in a realistic sample; measured operating domain documented.
- **EO3:** incident-energy resolution at most 10 eV FWHM and acquisition time
  below 12 h per spectrum, demonstrated for metallic Ag and two oxidized Ag
  compounds (PDF p. 3, printed p. 2).

The optical incident-energy resolution and the CZT fluorescence-energy
resolution are separate observables and must never share one metric name.
Numerical results based only on synthetic data must be labelled `simulation`;
`measurement` is reserved for analysis that ingests traceable experimental
data. Missing inputs that currently prevent unconditional predictions are
listed in `config/proposal_requirements.json`.
