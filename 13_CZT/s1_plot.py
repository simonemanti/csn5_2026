#!/usr/bin/env python3
"""Plot representative CZT waveforms and the PSA-selected energy spectrum."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
import xraylib
from matplotlib import font_manager, rc


HERE = Path(__file__).resolve().parent
WORK_ROOT = HERE.parents[2]
BTF_ROOT = (
    WORK_ROOT / "SIDDHARTA/CZT/02_CZT_BTF/02_CZT_BTF"
)

SPECTRUM_FILE = HERE / "max_values_test.h5"
WAVEFORM_FILE = (
    BTF_ROOT / "DATA/20261802_102216_Snap_Bin_file_ch0.h5"
)
PEAK_FIT_FILE = BTF_ROOT / "01_Figure_Of_Merit/2_chfit_erf.h5"

MAX_VALUES_DATASET = "max_values_test"
PREDICTIONS_DATASET = "predictions_test"

# All examples lie in the same Pb K-line amplitude range (194--208 channels).
# The accepted traces were additionally chosen for a flat pre-trigger region
# (no pre-pulse above 2.1% of the normalized amplitude) and one clean step;
# the rejected traces contain two distinct steps.
ACCEPTED_WAVEFORM_INDICES = (3428, 9630, 40210)
REJECTED_WAVEFORM_INDICES = (18788, 19518, 46063)
BASELINE_SAMPLES = 32
WAVEFORM_TMAX_US = 5.0

PB_ATOMIC_NUMBER = 82
FWHM_FROM_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))

MM_PER_INCH = 25.4
# Same physical size as 12_VOXES_Feasebility/s1_plot.py.
FIGSIZE = (160.0 / MM_PER_INCH, 100.0 / MM_PER_INCH)


@dataclass(frozen=True)
class PeakCalibration:
    """Two-point Pb calibration and Gaussian peak widths."""

    la_energy_kev: float
    ka_energy_kev: float
    kb_energy_kev: float
    la_center_channel: float
    ka_center_channel: float
    kb_center_channel: float
    la_sigma_channel: float
    ka_sigma_channel: float
    kb_sigma_channel: float
    slope_kev_per_channel: float
    intercept_kev: float

    def channel_to_energy(
        self, channel: float | np.ndarray
    ) -> float | np.ndarray:
        return self.slope_kev_per_channel * channel + self.intercept_kev

    def energy_to_channel(
        self, energy_kev: float | np.ndarray
    ) -> float | np.ndarray:
        return (energy_kev - self.intercept_kev) / self.slope_kev_per_channel

    def fwhm_kev(self, sigma_channel: float) -> float:
        return (
            FWHM_FROM_SIGMA
            * sigma_channel
            * self.slope_kev_per_channel
        )


def configure_style() -> None:
    """Use the typography of the other proposal figures."""
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
            "legend.fontsize": 8,
            "lines.linewidth": 1.0,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def decode_names(values: np.ndarray) -> list[str]:
    return [
        value.decode() if isinstance(value, bytes) else str(value)
        for value in values
    ]


def load_spectrum_data(
    spectrum_file: Path,
) -> tuple[np.ndarray, np.ndarray]:
    """Load maximum amplitudes and their aligned PSA predictions."""
    if not spectrum_file.is_file():
        raise FileNotFoundError(spectrum_file)

    with h5py.File(spectrum_file, "r") as data_file:
        maximum = np.asarray(data_file[MAX_VALUES_DATASET][:])
        prediction = np.asarray(data_file[PREDICTIONS_DATASET][:])

    if maximum.ndim != 1 or prediction.ndim != 1:
        raise ValueError(
            "Expected one-dimensional spectrum datasets, got "
            f"{maximum.shape} and {prediction.shape}"
        )
    if maximum.shape != prediction.shape:
        raise ValueError(
            "Maximum amplitudes and predictions have different shapes: "
            f"{maximum.shape} and {prediction.shape}"
        )
    if not np.all(np.isfinite(maximum)):
        raise ValueError("The spectrum contains non-finite amplitudes")

    return maximum, prediction


def load_waveform_examples(
    waveform_file: Path,
    prediction: np.ndarray,
) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
    """Load, baseline-subtract and normalize representative pulse shapes."""
    if not waveform_file.is_file():
        raise FileNotFoundError(waveform_file)

    accepted_indices = np.asarray(ACCEPTED_WAVEFORM_INDICES, dtype=int)
    rejected_indices = np.asarray(REJECTED_WAVEFORM_INDICES, dtype=int)
    all_indices = np.concatenate((accepted_indices, rejected_indices))

    with h5py.File(waveform_file, "r") as data_file:
        number_of_events = int(data_file["waveforms"].shape[0])
        if np.any(all_indices >= number_of_events):
            raise IndexError(
                f"Waveform index exceeds the {number_of_events} available events"
            )

        time_axis = np.asarray(data_file["time_axis"][:], dtype=float)
        # Reading the six rows individually preserves the intentional display
        # order; h5py otherwise requires advanced indices to be sorted.
        waveforms = np.asarray(
            [data_file["waveforms"][index] for index in all_indices],
            dtype=float,
        )
        features = np.asarray(
            [data_file["features"][index] for index in all_indices],
            dtype=float,
        )
        feature_names = decode_names(data_file["feature_names"][:])

    # This is the first file in the concatenation used to generate the PSA
    # prediction array, so its local row indices equal the global indices.
    if not np.all(prediction[accepted_indices] == 1):
        raise ValueError("An accepted waveform no longer has PSA prediction 1")
    if not np.all(prediction[rejected_indices] == 0):
        raise ValueError("A rejected waveform no longer has PSA prediction 0")

    name_to_index = {name: index for index, name in enumerate(feature_names)}
    if "num_peaks" in name_to_index:
        number_of_peaks = features[:, name_to_index["num_peaks"]]
        expected = np.concatenate(
            (
                np.ones(accepted_indices.size),
                2.0 * np.ones(rejected_indices.size),
            )
        )
        if not np.array_equal(number_of_peaks, expected):
            raise ValueError(
                "The selected waveform examples no longer have the expected "
                "single-step/double-step topology"
            )

    time_span = time_axis[-1] - time_axis[0]
    if not np.isfinite(time_span) or time_span <= 0.0:
        raise ValueError("The waveform time axis has an invalid span")
    time_axis_us = (
        WAVEFORM_TMAX_US
        * (time_axis - time_axis[0])
        / time_span
    )

    normalized = []
    for waveform in waveforms:
        baseline_size = min(BASELINE_SAMPLES, waveform.size)
        corrected = waveform - np.mean(waveform[:baseline_size])
        scale = np.max(np.abs(corrected))
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError("Cannot normalize a zero-amplitude waveform")
        normalized.append(corrected / scale)

    number_accepted = accepted_indices.size
    return (
        time_axis_us,
        normalized[:number_accepted],
        normalized[number_accepted:],
    )


def read_fit_parameter(data_file: h5py.File, name: str) -> float:
    path = f"parameters/{name}"
    if path not in data_file:
        raise KeyError(f"Missing fit parameter {path}")
    return float(data_file[path].attrs["value"])


def load_peak_calibration(peak_fit_file: Path) -> PeakCalibration:
    """Build a linear calibration from the fitted Pb Kα and Kβ centroids."""
    if not peak_fit_file.is_file():
        raise FileNotFoundError(peak_fit_file)

    with h5py.File(peak_fit_file, "r") as data_file:
        la_center = read_fit_parameter(data_file, "Pb_Lalpha_center")
        ka_center = read_fit_parameter(data_file, "Pb_Kalpha_center")
        kb_center = read_fit_parameter(data_file, "Pb_Kbeta_center")
        la_sigma = read_fit_parameter(data_file, "Pb_Lalpha_sigma")
        ka_sigma = read_fit_parameter(data_file, "Pb_Kalpha_sigma")
        kb_sigma = read_fit_parameter(data_file, "Pb_Kbeta_sigma")

    # xraylib's KA_LINE is the intensity-weighted unresolved K-alpha energy;
    # K-beta is referenced to the dominant K-beta1 transition.
    la_energy = float(xraylib.LineEnergy(PB_ATOMIC_NUMBER, xraylib.LA_LINE))
    ka_energy = float(xraylib.LineEnergy(PB_ATOMIC_NUMBER, xraylib.KA_LINE))
    kb_energy = float(xraylib.LineEnergy(PB_ATOMIC_NUMBER, xraylib.KB1_LINE))
    slope = (kb_energy - ka_energy) / (kb_center - ka_center)
    intercept = ka_energy - slope * ka_center

    return PeakCalibration(
        la_energy_kev=la_energy,
        ka_energy_kev=ka_energy,
        kb_energy_kev=kb_energy,
        la_center_channel=la_center,
        ka_center_channel=ka_center,
        kb_center_channel=kb_center,
        la_sigma_channel=la_sigma,
        ka_sigma_channel=ka_sigma,
        kb_sigma_channel=kb_sigma,
        slope_kev_per_channel=slope,
        intercept_kev=intercept,
    )


def histogram_edges(
    calibration: PeakCalibration,
    emin_kev: float,
    emax_kev: float,
    rebin: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return matching raw-channel and calibrated-energy bin edges."""
    channel_min = calibration.energy_to_channel(emin_kev)
    channel_max = calibration.energy_to_channel(emax_kev)
    first_edge = np.floor(channel_min / rebin) * rebin
    last_edge = np.ceil(channel_max / rebin) * rebin
    channel_edges = np.arange(first_edge, last_edge + rebin, rebin)
    energy_edges = calibration.channel_to_energy(channel_edges)
    return channel_edges, energy_edges


def plot_waveforms(
    axis: plt.Axes,
    time_axis: np.ndarray,
    accepted: list[np.ndarray],
    rejected: list[np.ndarray],
) -> None:
    """Plot clean single-step and rejected double-step pulse examples."""
    for index, waveform in enumerate(rejected):
        axis.plot(
            time_axis,
            waveform,
            color="C3",
            alpha=0.82,
            linewidth=1.0,
            label="PSA rejected" if index == 0 else "_nolegend_",
        )
    for index, waveform in enumerate(accepted):
        axis.plot(
            time_axis,
            waveform,
            color="C2",
            alpha=0.88,
            linewidth=1.0,
            label="PSA accepted" if index == 0 else "_nolegend_",
        )

    axis.set_xlim(float(time_axis[0]), float(time_axis[-1]))
    axis.set_ylim(-0.08, 1.08)
    axis.set_xlabel("t [µs]")
    axis.set_ylabel("Normalized amplitude")
    axis.grid(color="0.75", linestyle=":", linewidth=0.6)
    axis.legend(loc="lower right")


def plot_spectrum(
    axis: plt.Axes,
    maximum: np.ndarray,
    prediction: np.ndarray,
    calibration: PeakCalibration,
    emin_kev: float,
    emax_kev: float,
    rebin: int,
    ylog: bool,
) -> None:
    """Plot raw and PSA-selected spectra on the calibrated energy axis."""
    channel_edges, energy_edges = histogram_edges(
        calibration,
        emin_kev=emin_kev,
        emax_kev=emax_kev,
        rebin=rebin,
    )
    raw_counts, _ = np.histogram(maximum, bins=channel_edges)
    psa_counts, _ = np.histogram(
        maximum[prediction == 1],
        bins=channel_edges,
    )

    axis.stairs(
        raw_counts,
        energy_edges,
        color="C3",
        linewidth=1.0,
        label="Raw",
    )
    axis.stairs(
        psa_counts,
        energy_edges,
        color="C2",
        linewidth=1.0,
        label="PSA",
    )

    # Stagger the horizontal peak names to keep the nearby labels distinct.
    for energy, label, vertical_position in (
        (calibration.ka_energy_kev, r"Pb K$\alpha$", 0.96),
        (calibration.kb_energy_kev, r"Pb K$\beta$", 0.86),
    ):
        axis.text(
            energy,
            vertical_position,
            label,
            transform=axis.get_xaxis_transform(),
            rotation=0,
            ha="center",
            va="top",
            fontsize=7,
        )

    bin_centers = 0.5 * (energy_edges[:-1] + energy_edges[1:])
    coincidence_region = (bin_centers >= 140.0) & (bin_centers <= 165.0)
    if np.any(coincidence_region):
        local_indices = np.flatnonzero(coincidence_region)
        coincidence_index = local_indices[
            np.argmax(raw_counts[coincidence_region])
        ]
        axis.text(
            bin_centers[coincidence_index],
            1.15 * raw_counts[coincidence_index],
            "Coincidence",
            ha="center",
            va="bottom",
            fontsize=7,
        )

    energy_bin_width = rebin * calibration.slope_kev_per_channel
    axis.set_xlim(emin_kev, emax_kev)
    first_major_tick = np.ceil(emin_kev / 20.0) * 20.0
    axis.set_xticks(
        np.arange(first_major_tick, emax_kev + 0.1, 20.0)
    )
    positive_counts = np.concatenate(
        (raw_counts[raw_counts > 0], psa_counts[psa_counts > 0])
    )
    if ylog:
        axis.set_yscale("log")
    if positive_counts.size and ylog:
        axis.set_ylim(
            max(0.8, 0.6 * np.percentile(positive_counts, 5.0)),
            1.45 * positive_counts.max(),
        )
    elif positive_counts.size:
        axis.set_ylim(0.0, 1.15 * positive_counts.max())
    axis.set_ylim(1e2,1e4)
    axis.set_xlabel("Energy [keV]")
    axis.set_ylabel(f"Counts / {energy_bin_width:.1f} keV")
    axis.grid(color="0.75", linestyle=":", linewidth=0.6, alpha=0.75)
    axis.legend(loc="upper right")


def make_figure(
    spectrum_file: Path,
    waveform_file: Path,
    peak_fit_file: Path,
    emin_kev: float,
    emax_kev: float,
    rebin: int,
    ylog: bool,
) -> tuple[plt.Figure, PeakCalibration]:
    """Build the final two-panel CZT proposal figure."""
    maximum, prediction = load_spectrum_data(spectrum_file)
    time_axis, accepted, rejected = load_waveform_examples(
        waveform_file,
        prediction,
    )
    calibration = load_peak_calibration(peak_fit_file)

    configure_style()
    figure, (waveform_axis, spectrum_axis) = plt.subplots(
        1,
        2,
        figsize=FIGSIZE,
        dpi=300,
    )
    plot_waveforms(waveform_axis, time_axis, accepted, rejected)
    plot_spectrum(
        spectrum_axis,
        maximum,
        prediction,
        calibration,
        emin_kev=emin_kev,
        emax_kev=emax_kev,
        rebin=rebin,
        ylog=ylog,
    )
    waveform_axis.set_box_aspect(1)
    spectrum_axis.set_box_aspect(1)
    plt.tight_layout()
    return figure, calibration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot representative CZT waveforms and raw/PSA-selected spectra."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--spectrum-file",
        type=Path,
        default=SPECTRUM_FILE,
        help="HDF5 file containing maxima and PSA predictions",
    )
    parser.add_argument(
        "--waveform-file",
        type=Path,
        default=WAVEFORM_FILE,
        help="original HDF5 file containing the representative waveforms",
    )
    parser.add_argument(
        "--peak-fit-file",
        type=Path,
        default=PEAK_FIT_FILE,
        help="HDF5 fit result containing the Pb K-line centroids and widths",
    )
    parser.add_argument(
        "--emin",
        type=float,
        default=20.0,
        help="minimum displayed energy in keV",
    )
    parser.add_argument(
        "--emax",
        type=float,
        default=180.0,
        help="maximum displayed energy in keV",
    )
    parser.add_argument(
        "--rebin",
        type=int,
        default=4,
        help="number of raw ADC channels per spectrum bin",
    )
    parser.add_argument(
        "--ylog",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use a logarithmic spectrum count axis; use --no-ylog for linear",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="save the figure without opening an interactive window",
    )
    args = parser.parse_args()

    if args.emax <= args.emin:
        parser.error("require --emax > --emin")
    if args.rebin <= 0:
        parser.error("require --rebin > 0")
    return args


def print_calibration_summary(calibration: PeakCalibration) -> None:
    la_fwhm = calibration.fwhm_kev(calibration.la_sigma_channel)
    ka_fwhm = calibration.fwhm_kev(calibration.ka_sigma_channel)
    kb_fwhm = calibration.fwhm_kev(calibration.kb_sigma_channel)
    print(
        "Calibration: "
        f"E [keV] = {calibration.slope_kev_per_channel:.9f} "
        f"* channel {calibration.intercept_kev:+.9f}"
    )
    print(
        f"Pb Lalpha: center={calibration.la_center_channel:.3f} channel, "
        f"FWHM={la_fwhm:.3f} keV, "
        f"resolution={100.0 * la_fwhm / calibration.la_energy_kev:.2f}%"
    )
    print(
        f"Pb Kalpha: center={calibration.ka_center_channel:.3f} channel, "
        f"FWHM={ka_fwhm:.3f} keV, "
        f"resolution={100.0 * ka_fwhm / calibration.ka_energy_kev:.2f}%"
    )
    print(
        f"Pb Kbeta:  center={calibration.kb_center_channel:.3f} channel, "
        f"FWHM={kb_fwhm:.3f} keV, "
        f"resolution={100.0 * kb_fwhm / calibration.kb_energy_kev:.2f}%"
    )


def main() -> None:
    args = parse_args()
    figure, calibration = make_figure(
        spectrum_file=args.spectrum_file,
        waveform_file=args.waveform_file,
        peak_fit_file=args.peak_fit_file,
        emin_kev=args.emin,
        emax_kev=args.emax,
        rebin=args.rebin,
        ylog=args.ylog,
    )

    output = HERE / "v1_CZT"
    figure.savefig(output.with_suffix(".png"), dpi=300)
    figure.savefig(output.with_suffix(".pdf"))
    print_calibration_summary(calibration)
    if not args.no_show:
        plt.show()
    plt.close(figure)


if __name__ == "__main__":
    main()
