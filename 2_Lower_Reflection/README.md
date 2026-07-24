# Lower-order reflections of Ge(880)

This is a PRISM candidate-optics study supporting the design simulations. Ge(880)
has not yet been selected as the final crystal in the authoritative v2 proposal.

The default calculation studies a symmetric perfect Ge(880) crystal set to
20 keV. At the same physical orientation, the parallel planes are `n(110)`.
The Ge diamond-lattice extinction rules remove the odd orders, so the allowed
lower orders are:

| Reflection | Nominal energy at the Ge(880), 20 keV setting |
|---|---:|
| Ge(220) | 5 keV |
| Ge(440) | 10 keV |
| Ge(660) | 15 keV |
| Ge(880) | 20 keV |

Small energy shifts printed by the script come from the refraction-corrected
Bragg angle used by `crystalpy`.

Run in the requested environment:

```bash
conda run -n shadow4 python 2_Lower_Reflection/s1_reflection.py
```

The script produces PNG/PDF plots and a CSV table. It uses the same
`PerfectCrystalDiffraction` Guigay thick-crystal calculation called by
SHADOW4's `S4Crystal`. The plotted quantity is the unpolarized intrinsic
reflectivity, `(R_sigma + R_pi)/2`. The CSV reports both the angular integral
and its energy-equivalent value from `dE/dtheta = -E cot(theta)`. The lower
plot uses the latter because it is the more relevant throughput proxy for a
broadband laboratory source at a fixed crystal angle. It must still be
multiplied by the actual spectral flux and beamline transmission at each
energy.

Absolute output rates cannot be obtained from reflectivity alone. For each
order `i`, they require a source/beamline calculation of

```text
N_i = integral Phi(E,theta) R_i(E,theta) T(E) A(E,theta) dE dtheta,
```

where `Phi` is the incident spectral-angular flux, `T` contains windows,
filters and air paths, and `A` is the geometrical/detector acceptance. A full
SHADOW4 ray trace should therefore launch the actual polychromatic source and
compare the sum of statistical ray weights reaching the sample/detector in
bands around 5, 10, 15 and 20 keV.

For a CZT resolving time `tau`, the leading two-photon pile-up rates close to
20 keV are approximately

```text
P_440+440 = N_440^2 tau
P_220+660 = 2 N_220 N_660 tau
```

for low occupancy (`N_total tau << 1`). Use the measured effective resolving
time of the complete CZT plus shaping/DAQ chain, not just the sensor charge
collection time. Filters can strongly suppress 5 and 10 keV photons and must
be included before drawing a pile-up conclusion.

For fluorescence XAS the relevant ROI is normally the selected fluorescence
line, not the 20 keV incident energy. Check a different ROI with, for example,
`--pileup-roi 17.5 --pileup-tolerance 0.3`.

Limitations: this script models a flat, symmetric, perfect Ge crystal. Bending,
strain, Johann error, source divergence, finite apertures and crystal defects
must be included in the final SHADOW4 beamline model.
