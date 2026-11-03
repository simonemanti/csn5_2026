#!/usr/bin/env python3
"""Compare the measured Fe K-alpha rate with an HAPG(002) rocking curve.

Shadow4 0.1.88 calculates the dynamical diffraction of a perfect crystallite
through CrystalPy, but it does not yet implement ``S4MosaicCrystal``.  The
rocking curve used here is therefore the unpolarized Shadow4 response of a
perfect graphite (002) crystallite convolved with a Gaussian distribution of
crystallite orientations.  The Gaussian FWHM is fitted to the angular scan
unless ``--mosaic-fwhm-deg`` is specified.

Shadow4 returns reflectivity, not an absolute detector rate.  A scale and a
constant background are consequently fitted when comparing it with the data.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit, lsq_linear


HERE = Path(__file__).resolve().parent
DATABASE = HERE / "HAPGrot_Scan.db"

# Acquisition and event-selection settings used in 01_GP_Fit_HAPGrot.ipynb.
FRAME_DURATION_S = 2.0
NOMINAL_FRAMES = 150
MAX_HITS_PER_FRAME = 40
SPECTRUM_REBIN = 2

# Fe K-alpha line energies and approximate statistical weights.  The weighted
# average is the conventional unresolved Fe K-alpha energy.
FE_KA1_EV = 6403.84
FE_KA2_EV = 6390.84
FE_KA_WEIGHTS = np.asarray((2.0 / 3.0, 1.0 / 3.0))
FE_KA_AVG_EV = float(
    np.dot(FE_KA_WEIGHTS, np.asarray((FE_KA1_EV, FE_KA2_EV)))
)

FWHM_FROM_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))
MM_PER_INCH = 25.4
FIGSIZE = (160.0 / MM_PER_INCH, 86.0 / MM_PER_INCH)


@dataclass(frozen=True)
class MeasuredScan:
    motor_angles_deg: np.ndarray
    rates_hz: np.ndarray
    errors_hz: np.ndarray
    line_center_channel: float
    line_sigma_channel: float


@dataclass(frozen=True)
class ShadowCurve:
    deviations_rad: np.ndarray
    doublet_reflectivity: np.ndarray
    average_energy_reflectivity: np.ndarray
    d_spacing_angstrom: float
    bragg_angle_deg: float
    corrected_bragg_angle_deg: float
    perfect_fwhm_mrad: float
    shadow4_version: str


@dataclass(frozen=True)
class ComparisonFit:
    background_hz: float
    scale_hz_per_reflectivity: float
    motor_center_deg: float
    mosaic_fwhm_deg: float
    parameter_errors: np.ndarray
    reduced_chi_squared: float
    fitted_mosaicity: bool


def angle_from_table_name(table_name: str) -> float:
    """Return the motor angle encoded in an SQLite table name."""
    match = re.search(r"HAPGrot(\d+)", table_name)
    if match is None:
        raise ValueError(f"Cannot extract HAPG angle from {table_name!r}")
    return int(match.group(1)) / 100.0


def gaussian_area_model(
    channels: np.ndarray,
    c0: float,
    c1: float,
    c2: float,
    area: float,
    center: float,
    sigma: float,
) -> np.ndarray:
    """Quadratic continuum plus a Gaussian whose parameter is its area."""
    gaussian = np.exp(-0.5 * ((channels - center) / sigma) ** 2)
    gaussian /= sigma * np.sqrt(2.0 * np.pi)
    return c0 + c1 * channels + c2 * channels**2 + area * gaussian


def load_rebinned_spectra() -> list[tuple[float, np.ndarray]]:
    """Load accepted frames and return one rebinned spectrum per motor angle."""
    if not DATABASE.is_file():
        raise FileNotFoundError(DATABASE)

    spectra: list[tuple[float, np.ndarray]] = []
    with sqlite3.connect(DATABASE) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for (table_name,) in tables:
            if "HAPGrot" not in table_name:
                continue
            quoted_name = table_name.replace('"', '""')
            rows = connection.execute(
                f'SELECT counts FROM "{quoted_name}"'
            ).fetchall()
            frames = np.asarray(
                [np.frombuffer(row[0], dtype=np.uint8) for row in rows]
            )
            accepted = frames[frames.sum(axis=1) < MAX_HITS_PER_FRAME]
            counts = accepted.sum(axis=0, dtype=np.int64)
            if counts.size % SPECTRUM_REBIN:
                raise ValueError(
                    f"Spectrum length {counts.size} is not divisible by "
                    f"{SPECTRUM_REBIN}"
                )
            rebinned = counts.reshape(-1, SPECTRUM_REBIN).sum(axis=1)
            spectra.append((angle_from_table_name(table_name), rebinned))

    if not spectra:
        raise RuntimeError(f"No HAPG angular scan found in {DATABASE}")
    spectra.sort(key=lambda item: item[0])
    return spectra


def determine_fe_line_shape(
    channels: np.ndarray, spectra: list[tuple[float, np.ndarray]]
) -> tuple[float, float]:
    """Fit the line position and width in the spectrum with the most counts."""
    counts = max(spectra, key=lambda item: item[1].sum())[1]
    valid = counts > 0
    parameters, _ = curve_fit(
        gaussian_area_model,
        channels[valid],
        counts[valid],
        p0=(1.0, 0.0, 0.0, 4000.0, 280.0, 12.0),
        sigma=np.sqrt(counts[valid]),
        absolute_sigma=True,
        bounds=(
            (-np.inf, -np.inf, -np.inf, 0.0, 260.0, 5.0),
            (np.inf, np.inf, np.inf, np.inf, 300.0, 25.0),
        ),
        maxfev=50_000,
    )
    return float(parameters[4]), float(parameters[5])


def load_fe_ka_scan() -> MeasuredScan:
    """Extract the Fe K-alpha Gaussian area, in Hz, from every spectrum."""
    spectra = load_rebinned_spectra()
    channels = np.arange(
        SPECTRUM_REBIN / 2.0,
        spectra[0][1].size * SPECTRUM_REBIN,
        SPECTRUM_REBIN,
    )
    center, sigma = determine_fe_line_shape(channels, spectra)

    # Fixing the line shape makes low-signal fits stable.  Scaling the channel
    # coordinate also keeps the normal matrix well conditioned.
    reduced_channel = (channels - center) / 100.0
    line_shape = (
        SPECTRUM_REBIN
        * np.exp(-0.5 * ((channels - center) / sigma) ** 2)
        / (sigma * np.sqrt(2.0 * np.pi))
    )
    acquisition_time = FRAME_DURATION_S * NOMINAL_FRAMES

    results = []
    for angle, counts in spectra:
        valid = counts > 0
        weights = 1.0 / np.sqrt(counts[valid])
        design = np.column_stack(
            (
                np.ones(valid.sum()),
                reduced_channel[valid],
                reduced_channel[valid] ** 2,
                line_shape[valid],
            )
        )
        weighted_design = design * weights[:, np.newaxis]
        weighted_counts = counts[valid] * weights

        fit = lsq_linear(
            weighted_design,
            weighted_counts,
            bounds=(
                (-np.inf, -np.inf, -np.inf, 0.0),
                (np.inf, np.inf, np.inf, np.inf),
            ),
        )
        covariance = np.linalg.inv(weighted_design.T @ weighted_design)
        area_counts = fit.x[3]
        area_error = np.sqrt(covariance[3, 3])
        results.append(
            (angle, area_counts / acquisition_time, area_error / acquisition_time)
        )

    angles, rates, errors = (
        np.asarray(values, dtype=float) for values in zip(*results)
    )
    return MeasuredScan(angles, rates, errors, center, sigma)


def contiguous_fwhm(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate the FWHM of the connected peak containing the maximum."""
    peak_index = int(np.nanargmax(y))
    half_maximum = 0.5 * y[peak_index]

    left_below = np.flatnonzero(y[:peak_index] < half_maximum)
    right_below = np.flatnonzero(y[peak_index + 1 :] < half_maximum)
    if not left_below.size or not right_below.size:
        raise ValueError("Curve does not contain both half-maximum crossings")

    left_low = int(left_below[-1])
    left = np.interp(
        half_maximum,
        y[left_low : left_low + 2],
        x[left_low : left_low + 2],
    )

    right_high = peak_index + 1 + int(right_below[0])
    right_pair_y = y[right_high - 1 : right_high + 1][::-1]
    right_pair_x = x[right_high - 1 : right_high + 1][::-1]
    right = np.interp(half_maximum, right_pair_y, right_pair_x)
    return float(right - left)


def calculate_shadow4_curve(thickness_um: float) -> ShadowCurve:
    """Calculate perfect HAPG(002) responses using the Shadow4 crystal class."""
    try:
        from crystalpy.diffraction.Diffraction import Diffraction
        from crystalpy.util.Photon import Photon
        from shadow4.beamline.optical_elements.crystals.s4_plane_crystal import (
            S4PlaneCrystal,
            S4PlaneCrystalElement,
        )
    except ImportError as error:
        raise RuntimeError(
            "Shadow4 is required. Run: conda activate shadow4"
        ) from error

    optical_element = S4PlaneCrystal(
        name="HAPG (002) crystallite",
        material="Graphite",
        miller_index_h=0,
        miller_index_k=0,
        miller_index_l=2,
        thickness=thickness_um * 1e-6,
        is_thick=0,
        f_central=True,
        f_phot_cent=0,
        phot_cent=FE_KA_AVG_EV,
        material_constants_library_flag=0,
    )
    beamline_element = S4PlaneCrystalElement(optical_element=optical_element)
    beamline_element.set_crystalpy_diffraction_setup()
    setup = beamline_element._crystalpy_diffraction_setup

    bragg_angle = float(setup.angleBragg(FE_KA_AVG_EV))
    corrected_bragg_angle = float(setup.angleBraggCorrected(FE_KA_AVG_EV))

    # This interval covers both doublet components and all dynamical-diffraction
    # structure.  Only points close to each line's Bragg angle are evaluated,
    # avoiding unnecessary far-off-Bragg exponentials.
    step = 0.5e-6
    deviations = np.arange(-1.5e-3, 1.8001e-3, step)

    def perfect_response(energy_ev: float) -> np.ndarray:
        absolute_angles = corrected_bragg_angle + deviations
        line_deviations = absolute_angles - float(
            setup.angleBraggCorrected(energy_ev)
        )
        evaluated = np.abs(line_deviations) <= 600e-6
        energies = np.full(evaluated.sum(), energy_ev)
        photon = Photon(
            energy_in_ev=energies,
            direction_vector=setup.vectorIncomingPhotonDirection(
                energies,
                line_deviations[evaluated],
                angle_center_flag=1,
            ),
        )
        amplitudes = Diffraction.calculateDiffractedComplexAmplitudes(
            setup,
            photon,
            is_thick=0,
            calculation_strategy_flag=1,
        )
        reflectivity = np.zeros_like(deviations)
        # Average sigma and pi reflectivities for an unpolarized source.
        reflectivity[evaluated] = 0.5 * (
            np.abs(amplitudes["S"]) ** 2 + np.abs(amplitudes["P"]) ** 2
        )
        reflectivity[~np.isfinite(reflectivity)] = 0.0
        return reflectivity

    ka1 = perfect_response(FE_KA1_EV)
    ka2 = perfect_response(FE_KA2_EV)
    average_energy = perfect_response(FE_KA_AVG_EV)
    doublet = FE_KA_WEIGHTS[0] * ka1 + FE_KA_WEIGHTS[1] * ka2
    perfect_fwhm = contiguous_fwhm(deviations, average_energy) * 1e3

    return ShadowCurve(
        deviations_rad=deviations,
        doublet_reflectivity=doublet,
        average_energy_reflectivity=average_energy,
        d_spacing_angstrom=float(setup.dSpacing()),
        bragg_angle_deg=float(np.degrees(bragg_angle)),
        corrected_bragg_angle_deg=float(np.degrees(corrected_bragg_angle)),
        perfect_fwhm_mrad=perfect_fwhm,
        shadow4_version=importlib.metadata.version("shadow4"),
    )


def mosaic_reflectivity(
    query_rad: np.ndarray | float,
    mosaic_fwhm_deg: float,
    shadow: ShadowCurve,
) -> np.ndarray:
    """Convolve the perfect-crystallite curve with a Gaussian mosaic spread."""
    query = np.atleast_1d(np.asarray(query_rad, dtype=float))
    sigma = np.radians(mosaic_fwhm_deg) / FWHM_FROM_SIGMA
    output = np.empty_like(query)

    # Chunking bounds temporary memory when producing the dense plotting grid.
    for start in range(0, query.size, 256):
        stop = min(start + 256, query.size)
        difference = (
            query[start:stop, np.newaxis]
            - shadow.deviations_rad[np.newaxis, :]
        )
        distribution = np.exp(-0.5 * (difference / sigma) ** 2)
        distribution /= np.sqrt(2.0 * np.pi) * sigma
        output[start:stop] = np.trapezoid(
            shadow.doublet_reflectivity[np.newaxis, :] * distribution,
            shadow.deviations_rad,
            axis=1,
        )
    return output


def fit_comparison(
    measured: MeasuredScan,
    shadow: ShadowCurve,
    fixed_mosaic_fwhm_deg: float | None,
) -> ComparisonFit:
    """Fit background, scale, center, and optionally mosaic FWHM."""
    outer = np.abs(measured.motor_angles_deg - 72.2) > 1.0
    background_guess = max(0.0, float(np.median(measured.rates_hz[outer])))
    center_guess = float(
        measured.motor_angles_deg[np.argmax(measured.rates_hz)]
    )
    mosaic_guess = (
        fixed_mosaic_fwhm_deg
        if fixed_mosaic_fwhm_deg is not None
        else 0.4
    )
    reflectivity_guess = mosaic_reflectivity(0.0, mosaic_guess, shadow)[0]
    scale_guess = (
        measured.rates_hz.max() - background_guess
    ) / reflectivity_guess

    if fixed_mosaic_fwhm_deg is None:

        def model(
            motor_angle: np.ndarray,
            background: float,
            scale: float,
            center: float,
            mosaic_fwhm: float,
        ) -> np.ndarray:
            deviations = np.radians(motor_angle - center)
            return background + scale * mosaic_reflectivity(
                deviations, mosaic_fwhm, shadow
            )

        parameters, covariance = curve_fit(
            model,
            measured.motor_angles_deg,
            measured.rates_hz,
            p0=(background_guess, scale_guess, center_guess, mosaic_guess),
            sigma=measured.errors_hz,
            absolute_sigma=True,
            bounds=(
                (0.0, 0.0, center_guess - 0.8, 0.05),
                (1.0, 1e6, center_guess + 0.8, 1.5),
            ),
            maxfev=2000,
        )
        background, scale, center, mosaic_fwhm = parameters
        model_values = model(measured.motor_angles_deg, *parameters)
        degrees_of_freedom = measured.rates_hz.size - 4
        parameter_errors = np.sqrt(np.diag(covariance))
        fitted_mosaicity = True
    else:

        def model_fixed(
            motor_angle: np.ndarray,
            background: float,
            scale: float,
            center: float,
        ) -> np.ndarray:
            deviations = np.radians(motor_angle - center)
            return background + scale * mosaic_reflectivity(
                deviations, fixed_mosaic_fwhm_deg, shadow
            )

        parameters, covariance = curve_fit(
            model_fixed,
            measured.motor_angles_deg,
            measured.rates_hz,
            p0=(background_guess, scale_guess, center_guess),
            sigma=measured.errors_hz,
            absolute_sigma=True,
            bounds=(
                (0.0, 0.0, center_guess - 0.8),
                (1.0, 1e6, center_guess + 0.8),
            ),
            maxfev=2000,
        )
        background, scale, center = parameters
        mosaic_fwhm = fixed_mosaic_fwhm_deg
        model_values = model_fixed(measured.motor_angles_deg, *parameters)
        degrees_of_freedom = measured.rates_hz.size - 3
        fit_errors = np.sqrt(np.diag(covariance))
        parameter_errors = np.asarray(
            (fit_errors[0], fit_errors[1], fit_errors[2], np.nan)
        )
        fitted_mosaicity = False

    chi_squared = np.sum(
        ((measured.rates_hz - model_values) / measured.errors_hz) ** 2
    )
    return ComparisonFit(
        background_hz=float(background),
        scale_hz_per_reflectivity=float(scale),
        motor_center_deg=float(center),
        mosaic_fwhm_deg=float(mosaic_fwhm),
        parameter_errors=parameter_errors,
        reduced_chi_squared=float(chi_squared / degrees_of_freedom),
        fitted_mosaicity=fitted_mosaicity,
    )


def model_curve_hz(
    relative_angles_deg: np.ndarray,
    fit: ComparisonFit,
    shadow: ShadowCurve,
) -> np.ndarray:
    """Evaluate the fitted, absolutely scaled comparison curve."""
    return fit.background_hz + fit.scale_hz_per_reflectivity * mosaic_reflectivity(
        np.radians(relative_angles_deg), fit.mosaic_fwhm_deg, shadow
    )


def make_figure(
    measured: MeasuredScan,
    shadow: ShadowCurve,
    fit: ComparisonFit,
) -> plt.Figure:
    """Create absolute-rate and normalized-shape comparison panels."""
    plt.style.use("default")
    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7.5,
            "lines.linewidth": 1.1,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    relative_deg = measured.motor_angles_deg - fit.motor_center_deg
    plot_deg = np.linspace(-1.5, 1.5, 1501)
    model_hz = model_curve_hz(plot_deg, fit, shadow)
    model_signal = model_hz - fit.background_hz
    normalized_model = model_signal / model_signal.max()

    measured_signal = measured.rates_hz - fit.background_hz
    measured_peak = measured_signal.max()

    fig, (ax_rate, ax_shape) = plt.subplots(
        1, 2, figsize=FIGSIZE, dpi=300, constrained_layout=True
    )

    ax_rate.errorbar(
        relative_deg,
        measured.rates_hz,
        yerr=measured.errors_hz,
        fmt="o",
        color="black",
        markersize=2.5,
        elinewidth=0.7,
        capsize=1.5,
        label=r"Fe K$\alpha$ misurata",
        zorder=3,
    )
    ax_rate.plot(
        plot_deg,
        model_hz,
        color="#d62728",
        label="Shadow4 + mosaico (scalato)",
        zorder=2,
    )
    ax_rate.axhline(
        fit.background_hz,
        color="0.45",
        linestyle=":",
        linewidth=0.9,
        label="fondo del fit",
    )
    ax_rate.axvline(0.0, color="0.5", linestyle="--", linewidth=0.8)
    ax_rate.set(
        xlim=(-1.5, 1.5),
        ylim=(0.0, 1.14 * measured.rates_hz.max()),
        xlabel=r"$\Delta\theta$ del motore [deg]",
        ylabel=r"Rate Fe K$\alpha$ [Hz]",
        title="Confronto in rate assoluto",
    )
    ax_rate.legend(loc="lower right", frameon=False)
    ax_rate.grid(alpha=0.18)
    secondary = ax_rate.secondary_xaxis(
        "top",
        functions=(
            lambda degrees: np.radians(degrees) * 1e3,
            lambda mrad: np.degrees(mrad * 1e-3),
        ),
    )
    secondary.set_xlabel(r"$\Delta\theta$ [mrad]")

    annotation = (
        rf"$E_{{K\alpha,\mathrm{{avg}}}}={FE_KA_AVG_EV / 1000.0:.4f}$ keV"
        "\n"
        rf"$\theta_B={shadow.bragg_angle_deg:.3f}^\circ$"
        "\n"
        rf"FWHM mosaico eff. $={fit.mosaic_fwhm_deg:.3f}^\circ$"
    )
    ax_rate.text(
        0.03,
        0.96,
        annotation,
        transform=ax_rate.transAxes,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "0.75", "alpha": 0.9},
    )

    relative_mrad = np.radians(relative_deg) * 1e3
    plot_mrad = np.radians(plot_deg) * 1e3
    ax_shape.errorbar(
        relative_mrad,
        measured_signal / measured_peak,
        yerr=measured.errors_hz / measured_peak,
        fmt="o",
        color="black",
        markersize=2.5,
        elinewidth=0.7,
        capsize=1.5,
        label="dati, fondo sottratto",
        zorder=3,
    )
    ax_shape.plot(
        plot_mrad,
        normalized_model,
        color="#d62728",
        label="rocking curve mosaica",
        zorder=2,
    )
    ax_shape.axvline(0.0, color="0.5", linestyle="--", linewidth=0.8)
    ax_shape.set(
        xlim=(-20.0, 20.0),
        ylim=(-0.06, 1.14),
        xlabel=r"$\Delta\theta$ [mrad]",
        ylabel="Risposta normalizzata",
        title="Confronto della forma",
    )
    ax_shape.legend(loc="lower right", frameon=False)
    ax_shape.grid(alpha=0.18)

    inset = ax_shape.inset_axes((0.08, 0.55, 0.39, 0.37))
    perfect = shadow.average_energy_reflectivity
    inset.plot(
        shadow.deviations_rad * 1e3,
        perfect / perfect.max(),
        color="#1f77b4",
        linewidth=0.9,
    )
    inset.set(
        xlim=(-0.25, 0.25),
        ylim=(0.0, 1.08),
        xlabel="mrad",
        title="cristallite perfetto",
    )
    inset.tick_params(labelsize=6)
    inset.xaxis.label.set_size(6)
    inset.yaxis.label.set_size(6)
    inset.title.set_size(6.5)
    inset.grid(alpha=0.15)

    return fig


def build_report(
    measured: MeasuredScan,
    shadow: ShadowCurve,
    fit: ComparisonFit,
) -> str:
    """Return a concise, self-contained interpretation in Italian."""
    plot_deg = np.linspace(-1.5, 1.5, 3001)
    rocking = mosaic_reflectivity(
        np.radians(plot_deg), fit.mosaic_fwhm_deg, shadow
    )
    rocking_fwhm_deg = contiguous_fwhm(plot_deg, rocking)
    mosaic_error = fit.parameter_errors[3]
    mosaic_text = f"{fit.mosaic_fwhm_deg:.4f} deg"
    if fit.fitted_mosaicity:
        mosaic_text += f" +/- {mosaic_error:.4f} deg"
    else:
        mosaic_text += " (fissata)"

    interpretation = (
        "Il profilo misurato e' dominato dalla distribuzione mosaica: la "
        "larghezza del singolo cristallite calcolata da Shadow4 e' molto "
        "minore della larghezza osservata. "
    )
    if fit.reduced_chi_squared > 2.0:
        interpretation += (
            "Il chi-quadro ridotto elevato segnala code/asimmetrie non "
            "descritte dal semplice mosaico gaussiano; la FWHM ottenuta va "
            "quindi letta come mosaicita' efficace, comprendente anche "
            "divergenza, accettanza geometrica e sistema di rotazione. "
        )
    interpretation += (
        "La normalizzazione in Hz e' adattata ai dati: senza flusso incidente, "
        "geometria completa ed efficienza del rivelatore Shadow4 non predice "
        "il rate assoluto."
    )

    return "\n".join(
        (
            "=== Confronto Fe Kalpha - HAPG(002) ===",
            f"Shadow4: {shadow.shadow4_version}",
            f"Fe Kalpha avg (pesi 2:1): {FE_KA_AVG_EV:.3f} eV",
            f"d(002), database xraylib: {shadow.d_spacing_angstrom:.6f} A",
            f"Angolo di Bragg cinematico: {shadow.bragg_angle_deg:.6f} deg",
            (
                "Angolo corretto dinamicamente: "
                f"{shadow.corrected_bragg_angle_deg:.6f} deg"
            ),
            (
                "Centro del picco sul motore: "
                f"{fit.motor_center_deg:.5f} +/- "
                f"{fit.parameter_errors[2]:.5f} deg"
            ),
            (
                "Rate Fe Kalpha massimo (fit spettrale): "
                f"{measured.rates_hz.max():.3f} Hz"
            ),
            f"Fondo del confronto: {fit.background_hz:.4f} Hz",
            f"FWHM della distribuzione mosaica: {mosaic_text}",
            f"FWHM della rocking curve completa: {rocking_fwhm_deg:.4f} deg",
            (
                "FWHM Shadow4 del cristallite perfetto a E_avg: "
                f"{shadow.perfect_fwhm_mrad:.4f} mrad"
            ),
            f"chi2/ndf: {fit.reduced_chi_squared:.2f}",
            "",
            "Commento:",
            interpretation,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the measured Fe K-alpha rate with a Shadow4-based "
            "mosaic HAPG(002) rocking curve."
        )
    )
    parser.add_argument(
        "--mosaic-fwhm-deg",
        type=float,
        default=None,
        help=(
            "fix the Gaussian mosaic FWHM in degrees; by default it is fitted"
        ),
    )
    parser.add_argument(
        "--crystal-thickness-um",
        type=float,
        default=100.0,
        help="perfect-crystallite thickness passed to Shadow4 (default: 100)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "s2_compare",
        help="output basename without extension (default: s2_compare)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="show the figure interactively after saving it",
    )
    args = parser.parse_args()
    if args.mosaic_fwhm_deg is not None and args.mosaic_fwhm_deg <= 0:
        parser.error("--mosaic-fwhm-deg must be positive")
    if args.crystal_thickness_um <= 0:
        parser.error("--crystal-thickness-um must be positive")
    return args


def main() -> None:
    args = parse_args()
    measured = load_fe_ka_scan()
    shadow = calculate_shadow4_curve(args.crystal_thickness_um)
    fit = fit_comparison(measured, shadow, args.mosaic_fwhm_deg)
    figure = make_figure(measured, shadow, fit)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        figure.savefig(args.output.with_suffix(f".{suffix}"), dpi=300)
    report = build_report(measured, shadow, fit)
    args.output.with_name(f"{args.output.name}_report.txt").write_text(
        report + "\n", encoding="utf-8"
    )
    print(report)

    if args.show:
        plt.show()
    plt.close(figure)


if __name__ == "__main__":
    main()
