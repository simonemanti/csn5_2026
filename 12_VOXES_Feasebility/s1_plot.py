#!/usr/bin/env python3
"""Generate the VOXES angular-scan and Fe K-alpha spot figure."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, rc
from scipy import ndimage


HERE = Path(__file__).resolve().parent
DATABASE = HERE / "HAPGrot_Scan.db"
RATE_EXTRACTION_SCRIPT = HERE / "s2_compare.py"
FE_KA_SCAN_CACHE = HERE / "fe_ka_scan_cache.npz"
SPOT_FILE = (
    HERE
    / "2025_05_22_Co_N1000_T1_V25_I700_HAPGrot7225_HAPGphi_10.txt"
)

# Acquisition settings used in 01_GP_Fit_HAPGrot.ipynb.
FRAME_DURATION_S = 2.0
NOMINAL_FRAMES = 150
MAX_HITS_PER_FRAME = 40

# The 512 x 512 Timepix sensor has a 55 micrometre pixel pitch.
PIXEL_PITCH_MM = 0.055

# Required physical figure dimensions.
MM_PER_INCH = 25.4
FIGSIZE = (160.0 / MM_PER_INCH, 100.0 / MM_PER_INCH)
FE_KA_CACHE_VERSION = 1


def angle_from_table_name(table_name: str) -> float:
    """Extract the HAPG rotation angle in degrees from a database table name."""
    match = re.search(r"HAPGrot(\d+)", table_name)
    if match is None:
        raise ValueError(f"Cannot extract an angle from table {table_name!r}")
    return int(match.group(1)) / 100.0


def load_angular_scan() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load the accepted frames and reproduce the notebook's total-rate scan."""
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    acquisition_time = FRAME_DURATION_S * NOMINAL_FRAMES
    scan = []

    with sqlite3.connect(DATABASE) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

        for (table_name,) in tables:
            if "HAPGrot" not in table_name:
                continue
            # Names come from sqlite_master; quoting also protects unusual names.
            quoted_name = table_name.replace('"', '""')
            rows = connection.execute(
                f'SELECT counts FROM "{quoted_name}"'
            ).fetchall()
            frames = np.asarray(
                [np.frombuffer(row[0], dtype=np.uint8) for row in rows]
            )
            accepted = frames[frames.sum(axis=1) < MAX_HITS_PER_FRAME]
            total_counts = accepted.sum(dtype=np.int64)

            scan.append(
                (
                    angle_from_table_name(table_name),
                    total_counts / acquisition_time,
                    np.sqrt(total_counts) / acquisition_time,
                )
            )

    if not scan:
        raise RuntimeError(f"No HAPG rotation tables found in {DATABASE}")

    scan.sort(key=lambda item: item[0])
    return tuple(np.asarray(values) for values in zip(*scan))


def rate_cache_signature() -> np.ndarray:
    """Return the source-file signature used to validate the spectral-fit cache."""
    signature = []
    for source in (DATABASE, RATE_EXTRACTION_SCRIPT):
        if not source.is_file():
            raise FileNotFoundError(source)
        status = source.stat()
        signature.extend((status.st_mtime_ns, status.st_size))
    return np.asarray(signature, dtype=np.int64)


def load_spectral_fe_ka_scan() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load or calculate the spectral-fit Fe K-alpha rate from s2_compare.py."""
    signature = rate_cache_signature()
    if FE_KA_SCAN_CACHE.is_file():
        try:
            with np.load(FE_KA_SCAN_CACHE, allow_pickle=False) as cached:
                cache_is_current = (
                    int(cached["version"]) == FE_KA_CACHE_VERSION
                    and np.array_equal(cached["source_signature"], signature)
                )
                if cache_is_current:
                    return (
                        cached["angles_deg"].copy(),
                        cached["rates_hz"].copy(),
                        cached["errors_hz"].copy(),
                    )
        except (KeyError, OSError, ValueError):
            # A stale or interrupted cache write is safely regenerated below.
            pass

    # Importing the existing routine guarantees that both figures use exactly
    # the same spectral rebinning, Gaussian line shape and weighted fit.
    from s2_compare import load_fe_ka_scan

    measured = load_fe_ka_scan()
    np.savez_compressed(
        FE_KA_SCAN_CACHE,
        version=np.asarray(FE_KA_CACHE_VERSION, dtype=np.int64),
        source_signature=signature,
        angles_deg=measured.motor_angles_deg,
        rates_hz=measured.rates_hz,
        errors_hz=measured.errors_hz,
        line_center_channel=np.asarray(measured.line_center_channel),
        line_sigma_channel=np.asarray(measured.line_sigma_channel),
    )
    return measured.motor_angles_deg, measured.rates_hz, measured.errors_hz


def load_spot() -> np.ndarray:
    """Read and orient the 2-D detector image as in the reference plot."""
    if not SPOT_FILE.is_file():
        raise FileNotFoundError(SPOT_FILE)

    # Some values use a thousands separator, e.g. "1,012".
    data = np.loadtxt(
        SPOT_FILE,
        converters=lambda value: float(value.replace(",", "")),
    )
    if data.ndim != 2:
        raise ValueError(f"Expected a 2-D array in {SPOT_FILE}, got {data.shape}")

    # Detector readout axes are rotated relative to the laboratory X/Y axes.
    return np.rot90(data, k=-1)


def mask_isolated_hot_pixels(data: np.ndarray) -> np.ndarray:
    """Replace isolated bright detector clusters while preserving the main spot."""
    # A lower threshold identifies connected bright structures, while the higher
    # threshold selects only pixels that appear white with the chosen color scale.
    structure_threshold = np.percentile(data, 99.5)
    white_threshold = np.percentile(data, 99.9)
    structures, number = ndimage.label(
        data > structure_threshold,
        structure=np.ones((3, 3), dtype=bool),
    )
    if number == 0:
        return data.copy()

    # The coherent Fe K-alpha spot is by far the largest bright structure.
    sizes = np.bincount(structures.ravel())
    sizes[0] = 0
    main_spot_label = np.argmax(sizes)
    hot_pixels = (data > white_threshold) & (structures != main_spot_label)

    cleaned = data.copy()
    local_median = ndimage.median_filter(data, size=5, mode="reflect")
    cleaned[hot_pixels] = local_median[hot_pixels]
    return cleaned


def make_figure(
    step_color: str | None = None,
    line_color: str | None = None,
    mask_spots: bool = False,
    spectral_rate: bool = False,
) -> plt.Figure:
    if spectral_rate:
        angles, rates, rate_errors = load_spectral_fe_ka_scan()
    else:
        angles, rates, rate_errors = load_angular_scan()
    spot = load_spot()
    if mask_spots:
        spot = mask_isolated_hot_pixels(spot)

    # Define theta_B as the measured angular position of the rate maximum.
    theta_b = angles[np.argmax(rates)]
    relative_angles = angles - theta_b

    plt.style.use("default")
    free_sans_files = [
        font_file
        for font_file in font_manager.findSystemFonts()
        if Path(font_file).stem.startswith("FreeSans")
    ]
    for font_file in free_sans_files:
        font_manager.fontManager.addfont(font_file)
    sans_serif = ["FreeSans"] if free_sans_files else ["DejaVu Sans"]
    rc("font", **{"family": "sans-serif", "sans-serif": sans_serif})
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "lines.linewidth": 1.0,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, (ax_scan, ax_spot) = plt.subplots(
        1,
        2,
        figsize=FIGSIZE,
        dpi=300,
    )
    # Identical square plotting areas: 66 x 66 mm each.
    # The larger left margin leaves more room for the vertical label.
    ax_scan.set_position((0.085, 0.17, 0.4125, 0.66))
    ax_spot.set_position((0.575, 0.17, 0.4125, 0.66))

    # Angular scan.
    if step_color is not None:
        ax_scan.step(
            relative_angles,
            rates,
            where="mid",
            color=step_color,
            linewidth=1.0,
            zorder=2,
        )
    if line_color is not None:
        ax_scan.plot(
            relative_angles,
            rates,
            color=line_color,
            linewidth=1.0,
            zorder=2,
        )
    ax_scan.errorbar(
        relative_angles,
        rates,
        yerr=rate_errors,
        fmt="o",
        color="black",
        markersize=2.2,
        elinewidth=0.8,
        capsize=1.7,
        capthick=0.8,
        label=r"Rate",
        zorder=3,
    )
    ax_scan.axvline(
        0.0,
        color="black",
        linestyle="--",
        linewidth=0.9,
        label=r"$\theta_B$",
        zorder=1,
    )
    ax_scan.set_xlim(-1.7, 1.7)
    ax_scan.set_ylim(0.0, 1.2 * rates.max())
    ax_scan.set_xlabel(r"$\theta-\theta_B$ [deg.]")
    ax_scan.set_ylabel(r"Rate Fe K$\alpha$ [Hz]")
    ax_scan.legend(
        frameon=True,
        framealpha=1.0,
        facecolor="white",
        edgecolor="black",
        fancybox=False,
        loc="upper right",
    )
    ax_scan.grid(False)

    # Detector spot.
    detector_width = spot.shape[1] * PIXEL_PITCH_MM
    detector_height = spot.shape[0] * PIXEL_PITCH_MM
    vmax = np.percentile(spot, 99.9)
    ax_spot.imshow(
        spot,
        origin="lower",
        extent=(0.0, detector_width, 0.0, detector_height),
        cmap="hot",
        vmin=0.0,
        vmax=vmax,
        interpolation="none",
        aspect="equal",
    )
    ax_spot.set_xlim(0.0, detector_width)
    ax_spot.set_ylim(0.0, detector_height)
    ax_spot.set_xlabel("X detector [mm]")
    ax_spot.set_ylabel("Y detector [mm]")
    ax_spot.grid(False)

    return fig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the VOXES feasibility figure."
    )
    interpolation = parser.add_mutually_exclusive_group()
    interpolation.add_argument(
        "--step",
        nargs="?",
        const="red",
        metavar="COLOR",
        help="draw a step interpolation, optionally choosing its color",
    )
    interpolation.add_argument(
        "--line",
        nargs="?",
        const="red",
        metavar="COLOR",
        help="draw a linear interpolation, optionally choosing its color",
    )
    parser.add_argument(
        "--mask",
        action="store_true",
        help="mask isolated white hot-pixel clusters in the detector image",
    )
    parser.add_argument(
        "--spectral-rate",
        action="store_true",
        help=(
            "extract the Fe K-alpha rate with the spectral-fit method used in "
            "s2_compare.py (results are cached)"
        ),
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="save the figure without opening an interactive window",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fig = make_figure(
        step_color=args.step,
        line_color=args.line,
        mask_spots=args.mask,
        spectral_rate=args.spectral_rate,
    )
    for suffix in ("png", "pdf"):
        fig.savefig(HERE / f"v1_feasibility.{suffix}")
    if not args.no_show:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
