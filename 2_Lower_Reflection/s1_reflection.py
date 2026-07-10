#!/usr/bin/env python3
"""Spaghetti plot of the Bragg reflections of a germanium crystal."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import shadow4  # noqa: F401  (ensures that the Shadow4 environment is loaded)
from crystalpy.diffraction.DiffractionSetupXraylib import DiffractionSetupXraylib
from crystalpy.diffraction.GeometryType import BraggDiffraction


def reflection_families(max_index):
    """Return unique h >= k >= l >= 0 reflection families."""
    return [
        (h, k, l)
        for h in range(1, max_index + 1)
        for k in range(h + 1)
        for l in range(k + 1)
        if h + k + l > 0
    ]


def diffraction_setup(h, k, l, thickness):
    return DiffractionSetupXraylib(
        geometry_type=BraggDiffraction(),
        crystal_name="Ge",
        thickness=thickness,
        miller_h=h,
        miller_k=k,
        miller_l=l,
        asymmetry_angle=0.0,
        azimuthal_angle=0.0,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Plot the Bragg-angle spaghetti diagram for a Ge crystal using "
            "the diffraction libraries distributed with Shadow4."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--emin", type=float, default=20.0,
                        help="minimum photon energy (keV)")
    parser.add_argument("--emax", type=float, default=30.0,
                        help="maximum photon energy (keV)")
    parser.add_argument("--points", type=int, default=600,
                        help="number of energy points per curve")
    parser.add_argument("--max-index", type=int, default=16,
                        help="largest Miller index to consider")
    parser.add_argument("--thickness", type=float, default=1.0,
                        help="crystal thickness (mm; does not alter Bragg angles)")
    parser.add_argument("--edge-energy", type=float, default=25.5,
                        help="absorption-edge energy used to select reflections (keV)")
    parser.add_argument("--min-angle", type=float, default=75.0,
                        help="minimum Bragg angle displayed (degrees)")
    parser.add_argument("--max-angle", type=float, default=85.0,
                        help="maximum Bragg angle displayed (degrees)")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).with_suffix(""),
                        help="output path without extension")
    args = parser.parse_args()

    if args.emin <= 0 or args.emax <= args.emin:
        parser.error("require 0 < emin < emax")
    if args.points < 2:
        parser.error("--points must be at least 2")
    if args.max_index < 1:
        parser.error("--max-index must be positive")
    if args.thickness <= 0:
        parser.error("--thickness must be positive")
    if not args.emin <= args.edge_energy <= args.emax:
        parser.error("--edge-energy must lie between emin and emax")
    if not 0 <= args.min_angle < args.max_angle <= 90:
        parser.error("require 0 <= min-angle < max-angle <= 90")

    energy_kev = np.linspace(args.emin, args.emax, args.points)
    energy_ev = 1e3 * energy_kev
    edge_ev = 1e3 * args.edge_energy
    thickness_m = args.thickness * 1e-3

    fig, ax = plt.subplots(figsize=(9, 6))
    plotted = 0

    for h, k, l in reflection_families(args.max_index):
        setup = diffraction_setup(h, k, l, thickness_m)

        # xraylib's structure factor includes the Ge diamond-lattice
        # selection rules, so extinct reflections are removed here.
        if abs(setup.FH(edge_ev)) < 1e-8:
            continue

        angles_deg = np.degrees(setup.angleBragg(energy_ev))
        edge_angle_deg = np.degrees(setup.angleBragg(edge_ev))

        # Retain only reflections that are in the selected high-angle window
        # exactly at the absorption edge of interest.
        if not args.min_angle <= edge_angle_deg <= args.max_angle:
            continue

        visible = (
            np.isfinite(angles_deg)
            & (angles_deg >= args.min_angle)
            & (angles_deg <= args.max_angle)
        )
        if not np.any(visible):
            continue

        indices = f"{h} {k} {l}"
        ax.plot(
            energy_kev[visible],
            angles_deg[visible],
            lw=1.15,
            label=rf"Ge ({indices}), $\theta_B$={edge_angle_deg:.2f}°",
        )
        plotted += 1

    if plotted == 0:
        parser.error("no allowed Ge reflections are visible with these settings")

    ax.set(
        title=(
            "Ge reflections for Ag K-edge XANES "
            f"({args.edge_energy:g} keV; {plotted} families)"
        ),
        xlabel="Photon energy [keV]",
        ylabel=r"Bragg angle $\theta_B$ [deg]",
        xlim=(args.emin, args.emax),
        ylim=(args.min_angle, args.max_angle),
    )
    ax.axvline(args.edge_energy, color="black", ls="--", lw=1.0,
               label=f"Ag K-edge ({args.edge_energy:g} keV)")
    ax.grid(ls=":", alpha=0.65)
    ax.legend(loc="upper right")
    fig.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output.with_suffix(".png"), dpi=300)
    fig.savefig(args.output.with_suffix(".pdf"))
    print(f"Plotted {plotted} allowed Ge reflection families.")
    print(f"Saved {args.output.with_suffix('.png')}")
    print(f"Saved {args.output.with_suffix('.pdf')}")
    plt.show()


if __name__ == "__main__":
    main()
