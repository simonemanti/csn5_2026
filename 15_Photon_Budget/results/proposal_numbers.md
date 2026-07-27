# Proposal-ready photon-budget note

## Numbers that can be quoted with their assumptions

- The five-seed SHADOW4 Ge(880) calculation gives a conditional weighted
  source-to-sample throughput of **0.386 ± 0.004%**
  (standard error over seeds) for the explicitly launched angular phase space.
- The predicted sample spot is **0.240 × 0.238 mm² FWHM**.
- A 40 × 40 mm² CZT array at 30 mm covers **10.0% of 4π**.
- For a 20 µm Ag foil the analytic xraylib slab model includes incident
  attenuation and self-absorption of KA1 (22.163 keV), KA2 (21.990 keV).
- The nominal useful CZT rates are **2.27
  s⁻¹** for the 100 kV/500 W screening case and
  **4.42 s⁻¹** for the 40 kV/2 kW
  benchmark case.
- Requiring SNR=20 independently at each of 101 points and assuming
  background/signal=1 gives nominal full-scan times of
  **9.9 h** and
  **5.1 h**, respectively.
- The uncalibrated tube-output envelope (0.3–3 times the Kramers estimate)
  expands the 2 kW result to
  **1.7–16.9 h**.

## Suggested proposal wording

> A preliminary absolute photon budget was constructed for the Ag K-edge
> reference case using SHADOW4 ray tracing of a cylindrically bent Ge(880)
> optic. For the modeled source phase space, the five-seed weighted optical
> throughput is 0.386% and the beam at the sample is approximately
> 0.24 × 0.24 mm² FWHM. Coupling this result to analytical
> attenuation, Ag Kα fluorescence and a 2 mm CZT response gives a nominal
> useful rate of 4.4 counts s⁻¹ for
> a 40 kV/2 kW W-tube and a 40 × 40 mm² CZT array at 30 mm. Under the
> deliberately conservative requirement of SNR=20 at each of 101 XANES
> points with background equal to signal, the corresponding acquisition is
> approximately 5.1 h, below the 12 h
> literature benchmark. Because the tube spectrum is not yet calibrated, an
> explicit 0.3–3× source-output envelope is retained; the calculation
> therefore supports feasibility and identifies source output and detector
> solid angle as validation gates, rather than constituting a final
> performance claim.

## Suggested figure caption

> Preliminary Ag K-edge photon budget for the PRISM reference geometry.
> Left: rate waterfall from the Kramers-normalized W-tube continuum through
> the SHADOW4 Ge(880) transport, Ag Kα production and CZT detection. Right:
> conservative 101-point XANES acquisition-time estimate for three source
> operating points. Error bars show a 0.3–3× absolute source-output envelope,
> reflecting the absence of vendor-calibrated spectral fluence. Assumptions:
> 25.52 keV, 10 eV effective bandwidth, 20 µm Ag foil, 40 × 40 mm² by 2 mm
> CZT at 30 mm, SNR=20 per point and background/signal=1.

## Mandatory caveat

This is a feasibility screening calculation. The absolute result is dominated
by the unvalidated Kramers tube normalization, the assumed 10 eV effective
bandwidth, ideal perfect-crystal response, reference-foil geometry, and
detector photopeak/live-time factors. It must be updated with a measured or
supplier-calibrated tube spectrum and with measured crystal/CZT response
before it is used as a procurement guarantee.
