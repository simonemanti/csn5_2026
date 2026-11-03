#!/usr/bin/env python3
"""Export the flat Ge(220) sigma-reflectivity curve used in the PRISM icon.

The defaults reproduce the material, reflection, energy, thickness and scan
of the supplied OASYS reference. This is an ideal-crystal illustration, not
the predicted response of PRISM's bent Ge(880) monochromator.
Run with the shadow4-mosaics conda environment (shadow4, crystalpy and xraylib).
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--energy-ev", type=float, default=10000.0,
                        help="photon energy in eV")
    parser.add_argument("--thickness-mm", type=float, default=7.0,
                        help="perfect-crystal thickness in mm")
    parser.add_argument("--scan-urad", type=float, default=100.0,
                        help="scan half width around the corrected Bragg angle")
    parser.add_argument("--points", type=int, default=1001,
                        help="number of angular samples")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).with_name("reflectivity_Ge220.dat"),
                        help="output table for PGFPlots")
    args = parser.parse_args()
    if min(args.energy_ev, args.thickness_mm, args.scan_urad) <= 0:
        parser.error("energy, thickness and scan must be positive")
    if args.points < 101:
        parser.error("at least 101 angular samples are required")

    source = Path(__file__).resolve().parents[2] / "02_Lower_Reflection/s1_reflection.py"
    spec = importlib.util.spec_from_file_location("prism_reflection", source)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    setup = model.diffraction_setup(2, 2, 0, args.thickness_mm * 1e-3)
    offsets_urad = np.linspace(-args.scan_urad, args.scan_urad, args.points)
    _, reflectivity_sigma, _ = model.reflectivity_profile(
        setup, args.energy_ev, setup.angleBraggCorrected(args.energy_ev),
        offsets_urad * 1e-6,
    )
    if not np.all(np.isfinite(reflectivity_sigma)):
        raise ValueError("non-finite reflectivity")
    if np.min(reflectivity_sigma) < 0 or np.max(reflectivity_sigma) > 1 + 1e-6:
        raise ValueError("reflectivity outside the physical interval")
    np.savetxt(
        args.output, np.column_stack((offsets_urad, reflectivity_sigma)),
        header=(f"offset_urad R_sigma Ge220 E{args.energy_ev:g}eV "
                f"thickness{args.thickness_mm:g}mm flat perfect crystal; "
                "crystalpy Guigay thick-crystal; illustrative icon only"),
    )
    print(f"Saved {len(offsets_urad)} samples to {args.output}")
    print(f"Peak sigma reflectivity: {reflectivity_sigma.max():.6f}")


if __name__ == "__main__":
    main()
