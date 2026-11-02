#!/usr/bin/env python3
"""Lower-order contamination of a Ge(hkl) perfect-crystal reflection.

The default case is Ge(880) at 20 keV.  Reflections parallel to (880) are
n(110), n=1,...,8.  crystalpy/xraylib applies the Ge diamond-lattice
selection rules and the dynamical diffraction calculation used by SHADOW4
provides the sigma and pi reflectivities.

The calculated intensities are *intrinsic crystal reflectivities*.  Absolute
rates additionally require the incident spectral flux, angular distribution,
filters/air paths and detector acceptance.
"""

import argparse
import csv
import math
from functools import reduce
from pathlib import Path

import matplotlib
import numpy as np
import shadow4  # noqa: F401 -- fail early if the Shadow4 env is not active
from crystalpy.diffraction.DiffractionSetupXraylib import DiffractionSetupXraylib
from crystalpy.diffraction.GeometryType import BraggDiffraction
from crystalpy.diffraction.PerfectCrystalDiffraction import PerfectCrystalDiffraction
from crystalpy.util.ComplexAmplitudePhoton import ComplexAmplitudePhoton
from crystalpy.util.ComplexAmplitudePhotonBunch import ComplexAmplitudePhotonBunch


def diffraction_setup(h, k, l, thickness_m):
    return DiffractionSetupXraylib(
        geometry_type=BraggDiffraction(),
        crystal_name="Ge",
        thickness=thickness_m,
        miller_h=h,
        miller_k=k,
        miller_l=l,
        asymmetry_angle=0.0,
        azimuthal_angle=0.0,
    )


def parallel_orders(target_hkl):
    """Return all integer sub-orders parallel to target_hkl."""
    common = reduce(math.gcd, (abs(v) for v in target_hkl))
    if common == 0:
        raise ValueError("(000) is not a reflection")
    primitive = tuple(v // common for v in target_hkl)
    return [(n, tuple(n * v for v in primitive)) for n in range(1, common + 1)]


def resonant_energy(setup, target_angle, estimate_ev):
    """Energy whose refraction-corrected Bragg angle equals target_angle."""
    lo, hi = 0.90 * estimate_ev, 1.10 * estimate_ev

    def f(energy):
        return setup.angleBraggCorrected(energy) - target_angle

    flo, fhi = f(lo), f(hi)
    if not np.isfinite(flo) or not np.isfinite(fhi) or flo * fhi > 0:
        raise RuntimeError("could not bracket the resonant energy")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if flo * fmid <= 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)


def reflectivity_profile(setup, energy_ev, target_angle, offsets_rad):
    """Unpolarized reflectivity versus physical angle around target_angle."""
    corrected_bragg = setup.angleBraggCorrected(energy_ev)
    bunch = ComplexAmplitudePhotonBunch()
    for offset in offsets_rad:
        deviation = target_angle + offset - corrected_bragg
        bunch.addPhoton(
            ComplexAmplitudePhoton(
                energy_in_ev=energy_ev,
                direction_vector=setup.vectorIncomingPhotonDirection(
                    energy_ev, deviation, angle_center_flag=1
                ),
                Esigma=1.0,
                Epi=1.0,
            )
        )
    perfect_crystal = PerfectCrystalDiffraction.initializeFromDiffractionSetupAndEnergy(
        setup, energy_ev, calculation_strategy_flag=1
    )
    # This is the same Guigay/thick-crystal call made by S4Crystal.  Calling
    # PerfectCrystalDiffraction directly also avoids a crystalpy bunch-wrapper
    # bug that currently discards the is_thick flag.
    out = perfect_crystal.calculatePhotonOut(
        bunch,
        apply_reflectivity=True,
        calculation_method=1,
        is_thick=1,
        use_transfer_matrix=0,
    ).toDictionary()
    rs = np.asarray(out["intensityS"])
    rp = np.asarray(out["intensityP"])
    return 0.5 * (rs + rp), rs, rp


def pileup_pairs(rows, target_energy_kev, tolerance_kev):
    pairs = []
    lower = [row for row in rows if row["order"] < row["target_order"]]
    for i, first in enumerate(lower):
        for second in lower[i:]:
            summed = first["energy_kev"] + second["energy_kev"]
            if abs(summed - target_energy_kev) <= tolerance_kev:
                pairs.append((first["hkl"], second["hkl"], summed))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="SHADOW4/crystalpy lower-order study for a Ge reflection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--h", type=int, default=8)
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--l", type=int, default=0)
    parser.add_argument("--energy", type=float, default=20.0,
                        help="target energy (keV)")
    parser.add_argument("--thickness", type=float, default=1.0,
                        help="perfect-crystal thickness (mm)")
    parser.add_argument("--scan-urad", type=float, default=500.0,
                        help="half width of the common angular scan (urad)")
    parser.add_argument("--display-urad", type=float, default=100.0,
                        help="half width displayed in the rocking-curve panel (urad)")
    parser.add_argument("--points", type=int, default=10001,
                        help="points in each rocking curve")
    parser.add_argument("--pileup-tolerance", type=float, default=0.15,
                        help="two-photon sum tolerance around target (keV)")
    parser.add_argument("--pileup-roi", type=float, default=None,
                        help="pile-up ROI center (keV; default: target energy)")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).with_suffix(""),
                        help="output path without extension")
    parser.add_argument("--show", action="store_true",
                        help="open an interactive plot window")
    args = parser.parse_args()

    target_hkl = (args.h, args.k, args.l)
    if (args.energy <= 0 or args.thickness <= 0 or args.scan_urad <= 0
            or args.display_urad <= 0):
        parser.error("energy, thickness and scan-urad must be positive")
    if args.display_urad > args.scan_urad:
        parser.error("--display-urad cannot exceed --scan-urad")
    if args.points < 101:
        parser.error("--points must be at least 101")

    thickness_m = 1e-3 * args.thickness
    target_energy_ev = 1e3 * args.energy
    orders = parallel_orders(target_hkl)
    target_order = orders[-1][0]
    target_setup = diffraction_setup(*target_hkl, thickness_m)
    target_angle = target_setup.angleBraggCorrected(target_energy_ev)
    offsets = np.linspace(-args.scan_urad, args.scan_urad, args.points) * 1e-6

    rows = []
    for order, hkl in orders:
        setup = diffraction_setup(*hkl, thickness_m)
        nominal_ev = target_energy_ev * order / target_order

        # xraylib includes the fcc + diamond basis extinction rules.
        if abs(setup.FH(nominal_ev)) < 1e-10:
            print(f"Ge{hkl}: extinct (not included)")
            continue

        energy_ev = resonant_energy(setup, target_angle, nominal_ev)
        reflectivity, rs, rp = reflectivity_profile(
            setup, energy_ev, target_angle, offsets
        )
        integrated_urad = np.trapezoid(reflectivity, offsets) * 1e6
        rows.append({
            "order": order,
            "target_order": target_order,
            "hkl": hkl,
            "nominal_energy_kev": nominal_ev / 1e3,
            "energy_kev": energy_ev / 1e3,
            "energy_shift_ev": energy_ev - nominal_ev,
            "peak_reflectivity": float(reflectivity.max()),
            "integrated_reflectivity_urad": float(integrated_urad),
            # Bragg differential dE/dtheta = -E*cot(theta).  This converts
            # the rocking-curve area into the narrow-band energy integral
            # relevant to a broadband source at a fixed crystal angle.
            "energy_integrated_reflectivity_ev": float(
                integrated_urad * 1e-6 * energy_ev / np.tan(target_angle)
            ),
            "reflectivity": reflectivity,
            "rs": rs,
            "rp": rp,
        })

    if not rows or rows[-1]["hkl"] != target_hkl:
        parser.error(f"target Ge{target_hkl} is extinct or invalid")

    target_integral = rows[-1]["integrated_reflectivity_urad"]
    target_energy_integral = rows[-1]["energy_integrated_reflectivity_ev"]
    for row in rows:
        row["relative_integrated_reflectivity"] = (
            row["integrated_reflectivity_urad"] / target_integral
        )
        row["relative_energy_integral"] = (
            row["energy_integrated_reflectivity_ev"] / target_energy_integral
        )

    if not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax_curve, ax_bar) = plt.subplots(
        2, 1, figsize=(9.2, 8.0), gridspec_kw={"height_ratios": [2.1, 1.0]}
    )
    colors = plt.cm.viridis(np.linspace(0.12, 0.88, len(rows)))
    for row, color in zip(rows, colors):
        hkl_text = "".join(str(v) for v in row["hkl"])
        ax_curve.plot(
            offsets * 1e6,
            row["reflectivity"],
            color=color,
            lw=1.6,
            label=(f"Ge({hkl_text}), {row['energy_kev']:.4f} keV, "
                   f"A={row['integrated_reflectivity_urad']:.2f} µrad"),
        )

    labels = [f"Ge({''.join(str(v) for v in r['hkl'])})\n{r['energy_kev']:.3f} keV"
              for r in rows]
    relative = [r["relative_energy_integral"] for r in rows]
    bars = ax_bar.bar(labels, relative, color=colors)
    for bar, value in zip(bars, relative):
        ax_bar.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}×",
                    ha="center", va="bottom", fontsize=9)

    angle_deg = np.degrees(target_angle)
    ax_curve.set(
        title=(f"Lower orders parallel to Ge({args.h}{args.k}{args.l}) at "
               f"{args.energy:g} keV; common crystal angle {angle_deg:.4f}°"),
        xlabel=r"Crystal-angle offset from Ge target setting [$\mu$rad]",
        ylabel="Intrinsic reflectivity (unpolarized)",
        xlim=(-args.display_urad, args.display_urad),
        ylim=(0, 1.04),
    )
    ax_curve.grid(ls=":", alpha=0.6)
    ax_curve.legend(fontsize=8.5, loc="upper right")
    ax_bar.set(
        ylabel=r"$\int R(E)dE$ relative to target",
        title="Broadband fixed-angle throughput proxy (multiply by incident spectral flux and transmission)",
    )
    ax_bar.grid(axis="y", ls=":", alpha=0.6)
    ax_bar.set_ylim(0, max(relative) * 1.18)
    fig.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    png_path = args.output.with_suffix(".png")
    pdf_path = args.output.with_suffix(".pdf")
    csv_path = args.output.with_suffix(".csv")
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)

    fields = [
        "order", "h", "k", "l", "nominal_energy_kev", "energy_kev",
        "energy_shift_ev", "peak_reflectivity",
        "integrated_reflectivity_urad", "relative_integrated_reflectivity",
        "energy_integrated_reflectivity_ev", "relative_energy_integral",
    ]
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "order": row["order"],
                "h": row["hkl"][0], "k": row["hkl"][1], "l": row["hkl"][2],
                **{name: row[name] for name in fields[4:]},
            })

    print(f"\nGe{target_hkl} at {args.energy:g} keV: corrected angle = {angle_deg:.6f} deg")
    print("Allowed parallel orders (unpolarized perfect-crystal calculation):")
    print(" hkl       E_res [keV]  R_peak  int.R [urad]  angular rel.  continuum rel.")
    for row in rows:
        print(f" {str(row['hkl']):10s} {row['energy_kev']:11.6f} "
              f"{row['peak_reflectivity']:7.4f} "
              f"{row['integrated_reflectivity_urad']:13.4f} "
              f"{row['relative_integrated_reflectivity']:11.3f}x "
              f"{row['relative_energy_integral']:13.3f}x")

    pileup_roi = args.energy if args.pileup_roi is None else args.pileup_roi
    pairs = pileup_pairs(rows, pileup_roi, args.pileup_tolerance)
    if pairs:
        print(f"\nLower-order two-photon sums within {args.pileup_tolerance:g} keV "
              f"of the {pileup_roi:g} keV ROI:")
        for first, second, summed in pairs:
            print(f" Ge{first} + Ge{second} -> {summed:.6f} keV")
    else:
        print("\nNo lower-order two-photon sums fall within the selected tolerance.")
    print("\nThese are reflectivities, not absolute photon rates. For rates use")
    print("N_i = integral Phi(E,theta) * R_i(E,theta) * T(E) * acceptance dE dtheta.")
    print(f"Saved {png_path}, {pdf_path}, and {csv_path}")

    if args.show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()
