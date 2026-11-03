#!/usr/bin/env python3
"""Inspect and plot the raw CZT spectrum and the CNN-selected events."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, rc


HERE = Path(__file__).resolve().parent
INPUT_FILE = HERE / "max_values_test.h5"
MAX_VALUES_DATASET = "max_values_test"
PREDICTIONS_DATASET = "predictions_test"

MM_PER_INCH = 25.4
FIGSIZE = (160.0 / MM_PER_INCH, 100.0 / MM_PER_INCH)


def configure_style() -> None:
    """Use the same typography as the other figures in this directory."""
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
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 9,
            "lines.linewidth": 1.0,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_data(input_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load and validate maximum amplitudes and CNN predictions."""
    if not input_file.is_file():
        raise FileNotFoundError(input_file)

    with h5py.File(input_file, "r") as data_file:
        missing = [
            name
            for name in (MAX_VALUES_DATASET, PREDICTIONS_DATASET)
            if name not in data_file
        ]
        if missing:
            raise KeyError(
                f"Missing dataset(s) in {input_file}: {', '.join(missing)}"
            )
        maximum = np.asarray(data_file[MAX_VALUES_DATASET][:])
        prediction = np.asarray(data_file[PREDICTIONS_DATASET][:])

    if maximum.ndim != 1 or prediction.ndim != 1:
        raise ValueError(
            "Expected one-dimensional datasets, got "
            f"{maximum.shape} and {prediction.shape}"
        )
    if maximum.shape != prediction.shape:
        raise ValueError(
            "Maximum amplitudes and predictions have different lengths: "
            f"{maximum.size} and {prediction.size}"
        )
    if not np.all(np.isfinite(maximum)):
        invalid = np.count_nonzero(~np.isfinite(maximum))
        raise ValueError(f"Found {invalid} non-finite maximum amplitudes")

    return maximum, prediction


def print_summary(
    maximum: np.ndarray,
    prediction: np.ndarray,
    xmin: float,
    xmax: float,
) -> None:
    """Print a compact data summary useful for subsequent calibration."""
    classes, counts = np.unique(prediction, return_counts=True)
    class_summary = ", ".join(
        f"{label}: {count}" for label, count in zip(classes, counts)
    )
    selected = prediction == 1
    visible = (maximum >= xmin) & (maximum <= xmax)

    print(f"Input events: {maximum.size}")
    print(f"Raw-channel range: {maximum.min():g} to {maximum.max():g}")
    print(f"CNN classes: {class_summary}")
    print(f"CNN pred == 1: {np.count_nonzero(selected)}")
    print(
        f"Events in plotted range [{xmin:g}, {xmax:g}]: "
        f"raw={np.count_nonzero(visible)}, "
        f"pred==1={np.count_nonzero(visible & selected)}"
    )


def histogram_edges(xmin: float, xmax: float, bin_width: float) -> np.ndarray:
    """Return fixed-width bin edges spanning the requested raw-channel range."""
    number_of_bins = int(np.ceil((xmax - xmin) / bin_width))
    return xmin + np.arange(number_of_bins + 1) * bin_width


def make_figure(
    maximum: np.ndarray,
    prediction: np.ndarray,
    xmin: float,
    xmax: float,
    rebin: int,
    logarithmic: bool = True,
) -> plt.Figure:
    """Plot all events and the subset classified as one peak by the CNN."""
    configure_style()
    edges = histogram_edges(xmin, xmax, rebin)
    raw_counts, _ = np.histogram(maximum, bins=edges)
    cnn_counts, _ = np.histogram(maximum[prediction == 1], bins=edges)

    figure, axis = plt.subplots(figsize=FIGSIZE, dpi=300)
    axis.stairs(
        raw_counts,
        edges,
        color="blue",
        label="Raw spectrum",
    )
    axis.stairs(
        cnn_counts,
        edges,
        color="magenta",
        label="CNN: pred = 1",
    )

    axis.set_xlim(xmin, xmax)
    if logarithmic:
        axis.set_yscale("log")
    axis.set_xlabel("Maximum amplitude [raw ADC channel]")
    axis.set_ylabel(f"Counts / {rebin} ADC channels")
    axis.grid(color="0.75", linewidth=0.6, alpha=0.65)
    axis.legend(loc="upper right")
    figure.tight_layout()
    return figure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the raw CZT maximum-amplitude spectrum and compare it "
            "with events for which the CNN predicts class 1."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_FILE,
        help="input HDF5 file",
    )
    parser.add_argument(
        "--xmin",
        type=float,
        default=0.0,
        help="lower displayed raw channel",
    )
    parser.add_argument(
        "--xmax",
        type=float,
        default=2000.0,
        help="upper displayed raw channel",
    )
    parser.add_argument(
        "--rebin",
        type=int,
        default=4,
        help="number of raw ADC channels per histogram bin",
    )
    parser.add_argument(
        "--linear",
        action="store_true",
        help="use a linear instead of logarithmic count axis",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="save the figure without opening an interactive window",
    )
    args = parser.parse_args()
    if args.xmax <= args.xmin:
        parser.error("require --xmax > --xmin")
    if args.rebin <= 0:
        parser.error("require --rebin > 0")
    return args


def main() -> None:
    args = parse_args()
    maximum, prediction = load_data(args.input)
    print_summary(maximum, prediction, args.xmin, args.xmax)
    figure = make_figure(
        maximum,
        prediction,
        xmin=args.xmin,
        xmax=args.xmax,
        rebin=args.rebin,
        logarithmic=not args.linear,
    )

    output = HERE / "v2_CZT"
    figure.savefig(output.with_suffix(".png"), dpi=300)
    figure.savefig(output.with_suffix(".pdf"))
    if not args.no_show:
        plt.show()
    plt.close(figure)


if __name__ == "__main__":
    main()
