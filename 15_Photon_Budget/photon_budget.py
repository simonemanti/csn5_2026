#!/usr/bin/env python3
"""Minimum absolute photon budget for the PRISM Ag K-edge reference case.

SHADOW4 is the only ray-tracing / Monte-Carlo engine used here.  The X-ray
tube normalization is a deliberately simple Kramers-law screening estimate.
Material attenuation, Ag fluorescence cross sections, and CZT absorption are
evaluated analytically with xraylib; no GEANT4 particle transport is used.

The purpose is a proposal-level feasibility envelope, not a final instrument
prediction.  In particular, the absolute tube output must later be replaced
by a calibrated spectrum or supplier fluence data.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import shadow4  # noqa: F401 -- fail early if SHADOW4 is unavailable
import xraylib
from crystalpy.diffraction.DiffractionSetupXraylib import DiffractionSetupXraylib
from crystalpy.diffraction.GeometryType import BraggDiffraction
from shadow4.beam.s4_beam import S4Beam
from shadow4.beamline.optical_elements.crystals.s4_sphere_crystal import (
    S4SphereCrystal,
    S4SphereCrystalElement,
)
from shadow4.sources.source_geometrical.source_geometrical import SourceGeometrical
from syned.beamline.element_coordinates import ElementCoordinates
from syned.beamline.shape import Convexity, Direction, Rectangle


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "baseline.json"
DEFAULT_OUTPUT_DIR = ROOT / "results"
KEV_TO_J = 1.602176634e-16
FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))
LINE_CODES = {
    "KA1": xraylib.KA1_LINE,
    "KA2": xraylib.KA2_LINE,
    "KB1": xraylib.KB1_LINE,
    "KB2": xraylib.KB2_LINE,
    "KB3": xraylib.KB3_LINE,
}


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError("configuration root must be a JSON object")
    validate_config(config)
    return config


def finite_number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def validate_config(config: dict[str, Any]) -> None:
    required = (
        "run",
        "source_model",
        "incident_beam",
        "passive_path",
        "crystal",
        "geometry",
        "sample",
        "detector",
        "measurement",
        "plot",
    )
    for key in required:
        if not isinstance(config.get(key), dict):
            raise ValueError(f"missing configuration object: {key}")

    run = config["run"]
    nrays = run.get("nrays_per_seed")
    seeds = run.get("seeds")
    if isinstance(nrays, bool) or not isinstance(nrays, int) or nrays < 1000:
        raise ValueError("run.nrays_per_seed must be an integer >= 1000")
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 1 for seed in seeds)
    ):
        raise ValueError("run.seeds must contain positive integers")

    source_model = config["source_model"]
    finite_number(
        source_model.get("target_atomic_number"),
        "source_model.target_atomic_number",
        positive=True,
    )
    finite_number(
        source_model.get("kramers_efficiency_coefficient_per_volt"),
        "source_model.kramers_efficiency_coefficient_per_volt",
        positive=True,
    )
    low = finite_number(
        source_model.get("absolute_output_scale_low"),
        "source_model.absolute_output_scale_low",
        positive=True,
    )
    nominal = finite_number(
        source_model.get("absolute_output_scale_nominal"),
        "source_model.absolute_output_scale_nominal",
        positive=True,
    )
    high = finite_number(
        source_model.get("absolute_output_scale_high"),
        "source_model.absolute_output_scale_high",
        positive=True,
    )
    if not low < nominal < high:
        raise ValueError("absolute source scales must satisfy low < nominal < high")
    scenarios = source_model.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("source_model.scenarios must be a non-empty list")
    names: set[str] = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ValueError(f"source scenario {index} must be an object")
        name = scenario.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("source scenario names must be unique non-empty strings")
        names.add(name)
        voltage = finite_number(
            scenario.get("voltage_kV"), f"scenario {name} voltage_kV", positive=True
        )
        finite_number(
            scenario.get("electrical_power_W"),
            f"scenario {name} electrical_power_W",
            positive=True,
        )
        energy = finite_number(
            config["incident_beam"].get("energy_keV"),
            "incident_beam.energy_keV",
            positive=True,
        )
        if voltage <= energy:
            raise ValueError(f"scenario {name} voltage must exceed photon energy")

    beam = config["incident_beam"]
    finite_number(beam.get("effective_bandwidth_eV"), "effective_bandwidth_eV", positive=True)
    for key in ("sigma_x_m", "sigma_z_m"):
        finite_number(beam.get(key), f"incident_beam.{key}", positive=True)
    for low_key, high_key in (
        ("horizontal_angle_min_rad", "horizontal_angle_max_rad"),
        ("vertical_angle_min_rad", "vertical_angle_max_rad"),
    ):
        lower = finite_number(beam.get(low_key), low_key)
        upper = finite_number(beam.get(high_key), high_key)
        if lower >= upper:
            raise ValueError(f"{low_key} must be below {high_key}")

    crystal = config["crystal"]
    hkl = crystal.get("miller_indices")
    if (
        not isinstance(hkl, list)
        or len(hkl) != 3
        or any(isinstance(value, bool) or not isinstance(value, int) for value in hkl)
    ):
        raise ValueError("crystal.miller_indices must contain three integers")
    for key in (
        "thickness_m",
        "radius_m",
        "width_sagittal_m",
        "length_tangential_m",
    ):
        finite_number(crystal.get(key), f"crystal.{key}", positive=True)

    sample = config["sample"]
    if sample.get("material") != "Ag":
        raise ValueError("this minimum model currently supports an Ag sample")
    for key in ("density_g_cm3", "thickness_um"):
        finite_number(sample.get(key), f"sample.{key}", positive=True)
    lines = sample.get("useful_lines")
    if (
        not isinstance(lines, list)
        or not lines
        or any(line not in LINE_CODES for line in lines)
    ):
        raise ValueError(f"sample.useful_lines must use {sorted(LINE_CODES)}")

    detector = config["detector"]
    for key in (
        "density_g_cm3",
        "thickness_mm",
        "active_width_mm",
        "active_height_mm",
        "distance_mm",
    ):
        finite_number(detector.get(key), f"detector.{key}", positive=True)
    for key in ("photopeak_collection_fraction", "live_time_fraction"):
        value = finite_number(detector.get(key), f"detector.{key}", positive=True)
        if value > 1.0:
            raise ValueError(f"detector.{key} cannot exceed one")

    measurement = config["measurement"]
    points = measurement.get("xanes_points")
    if isinstance(points, bool) or not isinstance(points, int) or points < 2:
        raise ValueError("measurement.xanes_points must be an integer >= 2")
    for key in ("target_snr_per_point", "benchmark_time_h"):
        finite_number(measurement.get(key), f"measurement.{key}", positive=True)
    finite_number(
        measurement.get("background_to_signal_ratio"),
        "measurement.background_to_signal_ratio",
    )
    if measurement["background_to_signal_ratio"] < 0:
        raise ValueError("background_to_signal_ratio cannot be negative")

    waterfall = config["plot"].get("waterfall_scenario")
    if waterfall not in names:
        raise ValueError("plot.waterfall_scenario must name a source scenario")


def stable_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def diffraction_setup(crystal: dict[str, Any]) -> DiffractionSetupXraylib:
    h, k, l = crystal["miller_indices"]
    return DiffractionSetupXraylib(
        geometry_type=BraggDiffraction(),
        crystal_name=str(crystal["material"]),
        thickness=float(crystal["thickness_m"]),
        miller_h=h,
        miller_k=k,
        miller_l=l,
        asymmetry_angle=float(crystal["asymmetry_angle_rad"]),
        azimuthal_angle=0.0,
    )


def corrected_bragg_angle_rad(crystal: dict[str, Any], energy_keV: float) -> float:
    angle = diffraction_setup(crystal).angleBraggCorrected(1000.0 * energy_keV)
    return float(np.asarray(angle).reshape(-1)[0])


def symmetric_von_hamos_arm_m(radius_m: float, bragg_angle_rad: float) -> float:
    return radius_m / math.sin(bragg_angle_rad)


def image_distance_m(
    source_distance_m: float, radius_m: float, bragg_angle_rad: float
) -> float:
    inverse = 2.0 * math.sin(bragg_angle_rad) / radius_m - 1.0 / source_distance_m
    if inverse <= 0:
        raise ValueError("configured source distance has no positive sagittal image")
    return 1.0 / inverse


def build_source(
    beam_config: dict[str, Any], nrays: int, seed: int
) -> SourceGeometrical:
    source = SourceGeometrical(
        name="PRISM Ag K-edge photon-budget source",
        nrays=nrays,
        seed=seed,
    )
    source.set_spatial_type_gaussian(
        sigma_h=float(beam_config["sigma_x_m"]),
        sigma_v=float(beam_config["sigma_z_m"]),
    )
    source.set_depth_distribution_off()
    source.set_angular_distribution_flat(
        hdiv1=float(beam_config["horizontal_angle_min_rad"]),
        hdiv2=float(beam_config["horizontal_angle_max_rad"]),
        vdiv1=float(beam_config["vertical_angle_min_rad"]),
        vdiv2=float(beam_config["vertical_angle_max_rad"]),
    )
    source.set_energy_distribution_singleline(
        1000.0 * float(beam_config["energy_keV"]), unit="eV"
    )
    source.set_polarization(
        polarization_degree=float(beam_config["polarization_degree"]),
        phase_diff=0.0,
        coherent_beam=0,
    )
    return source


def build_crystal(crystal: dict[str, Any], energy_keV: float) -> S4SphereCrystal:
    h, k, l = crystal["miller_indices"]
    boundary = Rectangle(
        x_left=-0.5 * float(crystal["width_sagittal_m"]),
        x_right=0.5 * float(crystal["width_sagittal_m"]),
        y_bottom=-0.5 * float(crystal["length_tangential_m"]),
        y_top=0.5 * float(crystal["length_tangential_m"]),
    )
    return S4SphereCrystal(
        name=f"{crystal['material']}({h}{k}{l}) candidate",
        boundary_shape=boundary,
        material=str(crystal["material"]),
        miller_index_h=h,
        miller_index_k=k,
        miller_index_l=l,
        asymmetry_angle=float(crystal["asymmetry_angle_rad"]),
        is_thick=int(bool(crystal["use_thick_crystal_approximation"])),
        thickness=float(crystal["thickness_m"]),
        f_central=True,
        f_phot_cent=0,
        phot_cent=1000.0 * energy_keV,
        file_refl="",
        f_bragg_a=bool(float(crystal["asymmetry_angle_rad"])),
        f_ext=0,
        material_constants_library_flag=0,
        radius=float(crystal["radius_m"]),
        is_cylinder=True,
        cylinder_direction=Direction.SAGITTAL,
        convexity=Convexity.DOWNWARD,
    )


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0 or not math.isfinite(total):
        raise ValueError("no positive finite weights")
    return float(np.sum(values * weights) / total)


def weighted_sigma(values: np.ndarray, weights: np.ndarray) -> float:
    mean = weighted_mean(values, weights)
    return math.sqrt(max(weighted_mean((values - mean) ** 2, weights), 0.0))


def trace_optics_once(
    config: dict[str, Any], nrays: int, seed: int
) -> dict[str, float | int]:
    beam_config = config["incident_beam"]
    crystal_config = config["crystal"]
    geometry = config["geometry"]
    energy_keV = float(beam_config["energy_keV"])
    bragg = corrected_bragg_angle_rad(crystal_config, energy_keV)
    radius = float(crystal_config["radius_m"])
    symmetric_arm = symmetric_von_hamos_arm_m(radius, bragg)
    source_distance = (
        symmetric_arm
        if geometry["source_to_crystal_m"] is None
        else float(geometry["source_to_crystal_m"])
    )
    predicted_image = image_distance_m(source_distance, radius, bragg)
    sample_distance = (
        predicted_image
        if geometry["crystal_to_sample_m"] is None
        else float(geometry["crystal_to_sample_m"])
    )

    incident = build_source(beam_config, nrays, seed).get_beam()
    element = S4SphereCrystalElement(
        optical_element=build_crystal(crystal_config, energy_keV),
        coordinates=ElementCoordinates(
            p=source_distance,
            q=0.0,
            angle_radial=0.0,
            angle_azimuthal=0.0,
            angle_radial_out=None,
        ),
        input_beam=incident,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        post_crystal, footprint = element.trace_beam()

    incident_weight = float(incident.get_intensity(nolost=1))
    reflected_weight = float(post_crystal.get_intensity(nolost=1))
    throughput = reflected_weight / incident_weight
    footprint_status = footprint.get_column(10)
    geometric_fraction = float(np.count_nonzero(footprint_status > 0) / nrays)

    sample_beam = post_crystal.duplicate()
    sample_beam.retrace(sample_distance, resetY=True)
    status = sample_beam.get_column(10)
    weights = sample_beam.get_column(23)
    x_m = sample_beam.get_column(1)
    z_m = sample_beam.get_column(3)
    mask = (
        (status > 0)
        & np.isfinite(weights)
        & (weights > 0)
        & np.isfinite(x_m)
        & np.isfinite(z_m)
    )
    if np.count_nonzero(mask) < 10 or float(np.sum(weights[mask])) <= 0:
        raise RuntimeError("too few useful rays after the crystal")

    effective_rays = float(np.sum(weights[mask]) ** 2 / np.sum(weights[mask] ** 2))
    return {
        "seed": seed,
        "nrays": nrays,
        "throughput": throughput,
        "geometric_intercept_fraction": geometric_fraction,
        "mean_reflectivity_after_intercept": throughput / geometric_fraction,
        "sample_gaussian_equivalent_fwhm_x_mm": (
            1000.0 * FWHM_FACTOR * weighted_sigma(x_m[mask], weights[mask])
        ),
        "sample_gaussian_equivalent_fwhm_z_mm": (
            1000.0 * FWHM_FACTOR * weighted_sigma(z_m[mask], weights[mask])
        ),
        "effective_reflected_rays": effective_rays,
        "bragg_angle_deg": math.degrees(bragg),
        "source_to_crystal_m": source_distance,
        "crystal_to_sample_m": sample_distance,
    }


def summarize_optics(rows: list[dict[str, float | int]]) -> dict[str, Any]:
    fields = (
        "throughput",
        "geometric_intercept_fraction",
        "mean_reflectivity_after_intercept",
        "sample_gaussian_equivalent_fwhm_x_mm",
        "sample_gaussian_equivalent_fwhm_z_mm",
        "effective_reflected_rays",
    )
    summary: dict[str, Any] = {"seeds": [int(row["seed"]) for row in rows]}
    for field in fields:
        values = np.asarray([float(row[field]) for row in rows])
        summary[field] = {
            "mean": float(np.mean(values)),
            "sample_std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
            "standard_error": (
                float(np.std(values, ddof=1) / math.sqrt(values.size))
                if values.size > 1
                else 0.0
            ),
            "minimum": float(np.min(values)),
            "maximum": float(np.max(values)),
        }
    for field in ("bragg_angle_deg", "source_to_crystal_m", "crystal_to_sample_m"):
        summary[field] = float(rows[0][field])
    return summary


def kramers_spectral_photon_rate_per_keV(
    energy_keV: float,
    voltage_kV: float,
    electrical_power_W: float,
    target_atomic_number: int,
    efficiency_coefficient_per_volt: float,
) -> tuple[float, float, float]:
    """Return all-angle continuum photon rate density and power diagnostics.

    Kramers photon continuum is taken as dN/dE = A (E0-E)/E.  A is
    normalized so the integral of E*dN/dE equals eta*P, with the screening
    efficiency eta = coefficient * Z * tube_voltage_in_volts.
    """
    if not 0 < energy_keV < voltage_kV:
        return 0.0, 0.0, 0.0
    efficiency = min(
        efficiency_coefficient_per_volt
        * target_atomic_number
        * voltage_kV
        * 1000.0,
        1.0,
    )
    xray_power_W = efficiency * electrical_power_W
    normalization = 2.0 * xray_power_W / (KEV_TO_J * voltage_kV**2)
    spectral_rate = normalization * (voltage_kV - energy_keV) / energy_keV
    return spectral_rate, efficiency, xray_power_W


def phase_space_solid_angle_sr(beam: dict[str, Any]) -> float:
    """Small-angle solid angle represented by the SHADOW4 direction window."""
    horizontal = float(beam["horizontal_angle_max_rad"]) - float(
        beam["horizontal_angle_min_rad"]
    )
    vertical = float(beam["vertical_angle_max_rad"]) - float(
        beam["vertical_angle_min_rad"]
    )
    return horizontal * vertical


def element_transmission(
    symbol: str, density_g_cm3: float, thickness_cm: float, energy_keV: float
) -> float:
    z = xraylib.SymbolToAtomicNumber(symbol)
    return math.exp(
        -xraylib.CS_Total(z, energy_keV) * density_g_cm3 * thickness_cm
    )


def passive_transmission(config: dict[str, Any], energy_keV: float) -> dict[str, float]:
    path = config["passive_path"]
    be = element_transmission(
        "Be", 1.848, 0.1 * float(path["beryllium_window_mm"]), energy_keV
    )
    al = element_transmission(
        "Al", 2.699, 0.1 * float(path["aluminium_filter_mm"]), energy_keV
    )
    air_data = xraylib.GetCompoundDataNISTByName("Air, Dry (near sea level)")
    air = math.exp(
        -xraylib.CS_Total_CP("Air, Dry (near sea level)", energy_keV)
        * float(air_data["density"])
        * 100.0
        * float(path["air_path_m"])
    )
    return {
        "beryllium_window": be,
        "aluminium_filter": al,
        "air": air,
        "combined": be * al * air,
    }


def rectangular_solid_angle_sr(width_mm: float, height_mm: float, distance_mm: float) -> float:
    """Exact on-axis solid angle of a rectangle."""
    a = 0.5 * width_mm
    b = 0.5 * height_mm
    d = distance_mm
    return 4.0 * math.atan2(a * b, d * math.sqrt(d * d + a * a + b * b))


def czt_mass_attenuation_cm2_g(energy_keV: float) -> float:
    stoichiometry = {"Cd": 0.9, "Zn": 0.1, "Te": 1.0}
    molar_mass = sum(
        count * xraylib.AtomicWeight(xraylib.SymbolToAtomicNumber(element))
        for element, count in stoichiometry.items()
    )
    return sum(
        count
        * xraylib.AtomicWeight(xraylib.SymbolToAtomicNumber(element))
        / molar_mass
        * xraylib.CS_Total(xraylib.SymbolToAtomicNumber(element), energy_keV)
        for element, count in stoichiometry.items()
    )


def czt_intrinsic_efficiency(
    energy_keV: float, density_g_cm3: float, thickness_mm: float
) -> float:
    mu = czt_mass_attenuation_cm2_g(energy_keV)
    return 1.0 - math.exp(-mu * density_g_cm3 * 0.1 * thickness_mm)


def slab_fluorescence_probability(
    incident_energy_keV: float,
    sample: dict[str, Any],
) -> tuple[float, list[dict[str, float]]]:
    """Probability per incident photon for useful fluorescence escaping a slab.

    The sample is treated as a uniform plane-parallel Ag slab.  The analytic
    depth integral includes attenuation of the incident beam and self-
    absorption of each emitted line toward the detector take-off direction.
    """
    z = xraylib.SymbolToAtomicNumber(str(sample["material"]))
    if incident_energy_keV <= xraylib.EdgeEnergy(z, xraylib.K_SHELL):
        return 0.0, []
    density = float(sample["density_g_cm3"])
    thickness_cm = 1.0e-4 * float(sample["thickness_um"])
    cos_incident = math.cos(math.radians(float(sample["incident_angle_to_normal_deg"])))
    cos_exit = math.cos(
        math.radians(float(sample["detector_takeoff_angle_to_normal_deg"]))
    )
    if cos_incident <= 0 or cos_exit <= 0:
        raise ValueError("sample angles must be below 90 degrees")
    mu_incident = xraylib.CS_Total(z, incident_energy_keV)

    rows: list[dict[str, float]] = []
    total = 0.0
    for line_name in sample["useful_lines"]:
        line_code = LINE_CODES[line_name]
        line_energy = xraylib.LineEnergy(z, line_code)
        production = xraylib.CS_FluorLine_Kissel(
            z, line_code, incident_energy_keV
        )
        mu_exit = xraylib.CS_Total(z, line_energy)
        exponent_per_cm = density * (
            mu_incident / cos_incident + mu_exit / cos_exit
        )
        probability = (
            density
            * production
            / cos_incident
            * (-math.expm1(-exponent_per_cm * thickness_cm))
            / exponent_per_cm
        )
        rows.append(
            {
                "line": line_name,
                "energy_keV": line_energy,
                "production_cross_section_cm2_g": production,
                "escape_probability_per_incident_photon": probability,
            }
        )
        total += probability
    return total, rows


def signal_time_h(
    signal_rate_s: float,
    points: int,
    target_snr: float,
    background_to_signal: float,
) -> float:
    if signal_rate_s <= 0:
        return math.inf
    seconds_per_point = target_snr**2 * (1.0 + background_to_signal) / signal_rate_s
    return points * seconds_per_point / 3600.0


def evaluate_scenarios(
    config: dict[str, Any], optics: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_model = config["source_model"]
    beam = config["incident_beam"]
    detector = config["detector"]
    measurement = config["measurement"]
    energy_keV = float(beam["energy_keV"])
    bandwidth_keV = 1.0e-3 * float(beam["effective_bandwidth_eV"])
    traced_solid_angle = phase_space_solid_angle_sr(beam)
    transmissions = passive_transmission(config, energy_keV)
    optical_throughput = float(optics["throughput"]["mean"])
    fluorescence_probability, lines = slab_fluorescence_probability(
        energy_keV, config["sample"]
    )
    detector_solid_angle = rectangular_solid_angle_sr(
        float(detector["active_width_mm"]),
        float(detector["active_height_mm"]),
        float(detector["distance_mm"]),
    )
    line_weight = sum(
        row["escape_probability_per_incident_photon"] for row in lines
    )
    mean_line_energy = sum(
        row["energy_keV"] * row["escape_probability_per_incident_photon"]
        for row in lines
    ) / line_weight
    intrinsic_efficiency = czt_intrinsic_efficiency(
        mean_line_energy,
        float(detector["density_g_cm3"]),
        float(detector["thickness_mm"]),
    )
    detection_chain = (
        intrinsic_efficiency
        * float(detector["photopeak_collection_fraction"])
        * float(detector["live_time_fraction"])
    )
    low_scale = float(source_model["absolute_output_scale_low"])
    nominal_scale = float(source_model["absolute_output_scale_nominal"])
    high_scale = float(source_model["absolute_output_scale_high"])

    rows: list[dict[str, Any]] = []
    stages_by_name: dict[str, Any] = {}
    for scenario in source_model["scenarios"]:
        spectral_rate, efficiency, xray_power = kramers_spectral_photon_rate_per_keV(
            energy_keV=energy_keV,
            voltage_kV=float(scenario["voltage_kV"]),
            electrical_power_W=float(scenario["electrical_power_W"]),
            target_atomic_number=int(source_model["target_atomic_number"]),
            efficiency_coefficient_per_volt=float(
                source_model["kramers_efficiency_coefficient_per_volt"]
            ),
        )
        emitted_band = spectral_rate * bandwidth_keV * nominal_scale
        traced_phase_space = emitted_band * traced_solid_angle / (4.0 * math.pi)
        after_passive = traced_phase_space * transmissions["combined"]
        at_sample = after_passive * optical_throughput
        fluorescence_4pi = at_sample * fluorescence_probability
        toward_detector = fluorescence_4pi * detector_solid_angle / (4.0 * math.pi)
        recorded = toward_detector * detection_chain
        time_nominal = signal_time_h(
            recorded,
            int(measurement["xanes_points"]),
            float(measurement["target_snr_per_point"]),
            float(measurement["background_to_signal_ratio"]),
        )
        rate_low = recorded * low_scale / nominal_scale
        rate_high = recorded * high_scale / nominal_scale
        time_best = time_nominal * nominal_scale / high_scale
        time_worst = time_nominal * nominal_scale / low_scale
        row = {
            "name": scenario["name"],
            "label": scenario["label"],
            "voltage_kV": float(scenario["voltage_kV"]),
            "electrical_power_W": float(scenario["electrical_power_W"]),
            "bremsstrahlung_efficiency": efficiency,
            "estimated_total_xray_power_W": xray_power,
            "spectral_photon_rate_all_angles_per_s_per_keV": spectral_rate,
            "photon_rate_at_sample_per_s": at_sample,
            "recorded_useful_rate_per_s": recorded,
            "recorded_useful_rate_low_per_s": rate_low,
            "recorded_useful_rate_high_per_s": rate_high,
            "full_xanes_time_h": time_nominal,
            "full_xanes_time_best_h": time_best,
            "full_xanes_time_worst_h": time_worst,
            "meets_12h_nominal": time_nominal
            <= float(measurement["benchmark_time_h"]),
        }
        rows.append(row)
        stages_by_name[scenario["name"]] = {
            "emitted_in_band_all_angles": emitted_band,
            "within_traced_angular_phase_space": traced_phase_space,
            "after_window_filter_and_air": after_passive,
            "at_sample_after_SHADOW4_crystal": at_sample,
            "escaping_useful_Ag_fluorescence_4pi": fluorescence_4pi,
            "entering_CZT_solid_angle": toward_detector,
            "recorded_useful_CZT_photopeak": recorded,
        }

    common = {
        "incident_energy_keV": energy_keV,
        "effective_bandwidth_eV": float(beam["effective_bandwidth_eV"]),
        "source_emission_solid_angle_sr": 4.0 * math.pi,
        "traced_solid_angle_sr": traced_solid_angle,
        "passive_transmissions": transmissions,
        "SHADOW4_conditional_crystal_throughput": optical_throughput,
        "sample_useful_fluorescence_probability_4pi": fluorescence_probability,
        "fluorescence_lines": lines,
        "detector_solid_angle_sr": detector_solid_angle,
        "detector_fraction_of_4pi": detector_solid_angle / (4.0 * math.pi),
        "mean_useful_line_energy_keV": mean_line_energy,
        "CZT_intrinsic_efficiency": intrinsic_efficiency,
        "CZT_photopeak_and_live_factor": detection_chain,
        "stages_by_scenario": stages_by_name,
    }
    return rows, common


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def make_figure(
    config: dict[str, Any],
    scenario_rows: list[dict[str, Any]],
    common: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    import matplotlib.pyplot as plt

    waterfall_name = str(config["plot"]["waterfall_scenario"])
    sample_thickness_um = float(config["sample"]["thickness_um"])
    detector = config["detector"]
    stages = common["stages_by_scenario"][waterfall_name]
    ordered_stages = [
        ("emitted_in_band_all_angles", "Tube output in 10 eV"),
        (
            "within_traced_angular_phase_space",
            "Traced angular phase space",
        ),
        ("after_window_filter_and_air", "After Be / Al / air"),
        ("at_sample_after_SHADOW4_crystal", "At sample (SHADOW4)"),
        (
            "escaping_useful_Ag_fluorescence_4pi",
            "Escaping Ag Kα into 4π",
        ),
        ("entering_CZT_solid_angle", "Toward CZT"),
        ("recorded_useful_CZT_photopeak", "Recorded photopeak"),
    ]
    stage_labels = [label for _, label in ordered_stages]
    stage_values = np.asarray([stages[key] for key, _ in ordered_stages], dtype=float)
    colors = [
        "#355C7D",
        "#3D6D8E",
        "#4E8397",
        "#5C9E8F",
        "#8AB17D",
        "#D4A373",
        "#C76D4A",
    ]

    fig, (ax_budget, ax_time) = plt.subplots(
        1, 2, figsize=(12.4, 5.2), gridspec_kw={"width_ratios": [1.35, 1.0]}
    )
    positions = np.arange(len(stage_values))
    ax_budget.barh(positions, stage_values, color=colors, height=0.68)
    ax_budget.set_xscale("log")
    ax_budget.set_yticks(positions, stage_labels, fontsize=9)
    ax_budget.invert_yaxis()
    ax_budget.set_xlabel("Photon rate [s$^{-1}$]")
    ax_budget.set_title("Ag K-edge photon-budget waterfall\n40 kV, 2 kW W-tube screening case")
    ax_budget.grid(axis="x", which="both", ls=":", alpha=0.45)
    for y, value in zip(positions, stage_values):
        ax_budget.text(
            value * 1.22,
            y,
            f"{value:.2g}",
            ha="left",
            va="center",
            fontsize=8,
        )

    x = np.arange(len(scenario_rows))
    nominal = np.asarray([row["full_xanes_time_h"] for row in scenario_rows])
    best = np.asarray([row["full_xanes_time_best_h"] for row in scenario_rows])
    worst = np.asarray([row["full_xanes_time_worst_h"] for row in scenario_rows])
    lower = nominal - best
    upper = worst - nominal
    ax_time.errorbar(
        x,
        nominal,
        yerr=np.vstack([lower, upper]),
        fmt="o",
        markersize=8,
        capsize=5,
        lw=1.8,
        color="#355C7D",
        ecolor="#7A8FA3",
        label="Kramers estimate; 0.3–3× output envelope",
    )
    benchmark = float(config["measurement"]["benchmark_time_h"])
    ax_time.axhline(
        benchmark,
        color="#B23A48",
        ls="--",
        lw=1.6,
        label=f"{benchmark:g} h proposal benchmark",
    )
    ax_time.set_yscale("log")
    ax_time.set_xticks(x, [row["label"] for row in scenario_rows])
    ax_time.set_ylabel("Time for 101-point XANES [h]")
    ax_time.set_title("Conservative SNR=20 per point\nbackground/signal = 1")
    ax_time.grid(axis="y", which="both", ls=":", alpha=0.45)
    ax_time.legend(fontsize=8.2, loc="upper right")
    for index, row in enumerate(scenario_rows):
        ax_time.annotate(
            f"{row['recorded_useful_rate_per_s']:.2g} s$^{{-1}}$",
            (index, row["full_xanes_time_h"]),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )

    fig.suptitle(
        "PRISM feasibility screening: Ge(880) von Hamos + 2 mm CZT",
        fontsize=13,
        y=1.02,
    )
    fig.text(
        0.5,
        -0.025,
        (
            "Reference case: 25.52 keV, 10 eV resolution element, "
            f"{sample_thickness_um:g} µm Ag foil, "
            f"{float(detector['active_width_mm']):g}×"
            f"{float(detector['active_height_mm']):g} mm² CZT at "
            f"{float(detector['distance_mm']):g} mm. "
            "Absolute tube output is not vendor-calibrated."
        ),
        ha="center",
        fontsize=8.5,
    )
    fig.tight_layout()
    png_path = output_dir / "prism_photon_budget.png"
    pdf_path = output_dir / "prism_photon_budget.pdf"
    fig.savefig(png_path, dpi=int(config["plot"]["dpi"]), bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.show()
    return png_path, pdf_path


def write_proposal_note(
    path: Path,
    config: dict[str, Any],
    scenario_rows: list[dict[str, Any]],
    optics: dict[str, Any],
    common: dict[str, Any],
) -> None:
    benchmark = next(row for row in scenario_rows if row["name"] == "benchmark_2kW")
    upgrade = next(row for row in scenario_rows if row["name"] == "upgrade_500W")
    throughput = 100.0 * float(optics["throughput"]["mean"])
    throughput_sem = 100.0 * float(optics["throughput"]["standard_error"])
    spot_x = float(optics["sample_gaussian_equivalent_fwhm_x_mm"]["mean"])
    spot_z = float(optics["sample_gaussian_equivalent_fwhm_z_mm"]["mean"])
    omega_fraction = 100.0 * float(common["detector_fraction_of_4pi"])
    sample_thickness_um = float(config["sample"]["thickness_um"])
    lines = ", ".join(
        f"{row['line']} ({row['energy_keV']:.3f} keV)"
        for row in common["fluorescence_lines"]
    )
    text = f"""# Proposal-ready photon-budget note

## Numbers that can be quoted with their assumptions

- The five-seed SHADOW4 Ge(880) calculation gives a conditional weighted
  crystal throughput of **{throughput:.3f} ± {throughput_sem:.3f}%**
  (standard error over seeds) for the explicitly launched angular phase space.
- The predicted sample spot is **{spot_x:.3f} × {spot_z:.3f} mm²
  Gaussian-equivalent FWHM**.
- A 40 × 40 mm² CZT array at 30 mm covers **{omega_fraction:.1f}% of 4π**.
- For a {sample_thickness_um:g} µm Ag foil the analytic xraylib slab model includes incident
  attenuation and self-absorption of {lines}.
- The nominal useful CZT rates are **{upgrade['recorded_useful_rate_per_s']:.2f}
  s⁻¹** for the 100 kV/500 W screening case and
  **{benchmark['recorded_useful_rate_per_s']:.2f} s⁻¹** for the 40 kV/2 kW
  benchmark case.
- Requiring SNR=20 independently at each of 101 points and assuming
  background/signal=1 gives nominal full-scan times of
  **{upgrade['full_xanes_time_h']:.1f} h** and
  **{benchmark['full_xanes_time_h']:.1f} h**, respectively.
- The uncalibrated tube-output envelope (0.3–3 times the Kramers estimate)
  expands the 2 kW result to
  **{benchmark['full_xanes_time_best_h']:.1f}–{benchmark['full_xanes_time_worst_h']:.1f} h**.

## Suggested proposal wording

> A preliminary absolute photon budget was constructed for the Ag K-edge
> reference case using SHADOW4 ray tracing of a cylindrically bent Ge(880)
> optic. For the modeled source phase space, the five-seed weighted optical
> conditional crystal throughput is {throughput:.3f}% and the beam at the
> sample is approximately {spot_x:.2f} × {spot_z:.2f} mm²
> Gaussian-equivalent FWHM. Coupling this result to analytical
> attenuation, Ag Kα fluorescence and a 2 mm CZT response gives a nominal
> useful rate of {benchmark['recorded_useful_rate_per_s']:.1f} counts s⁻¹ for
> a 40 kV/2 kW W-tube and a 40 × 40 mm² CZT array at 30 mm. Under the
> deliberately conservative requirement of SNR=20 at each of 101 XANES
> points with background equal to signal, the corresponding acquisition is
> approximately {benchmark['full_xanes_time_h']:.1f} h, below the 12 h
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
> 25.52 keV, 10 eV effective bandwidth, {sample_thickness_um:g} µm Ag foil, 40 × 40 mm² by 2 mm
> CZT at 30 mm, SNR=20 per point and background/signal=1.

## Mandatory caveat

This is a feasibility screening calculation. The absolute result is dominated
by the unvalidated Kramers tube normalization, the assumed 10 eV effective
bandwidth, ideal perfect-crystal response, reference-foil geometry, and
detector photopeak/live-time factors. It must be updated with a measured or
supplier-calibrated tube spectrum and with measured crystal/CZT response
before it is used as a procurement guarantee.
"""
    path.write_text(text, encoding="utf-8")


def run(
    config_path: Path,
    output_dir: Path,
    *,
    nrays_override: int | None = None,
    seeds_override: list[int] | None = None,
    make_plots: bool = True,
) -> dict[str, Any]:
    config = load_config(config_path)
    nrays = (
        int(config["run"]["nrays_per_seed"])
        if nrays_override is None
        else nrays_override
    )
    seeds = (
        [int(seed) for seed in config["run"]["seeds"]]
        if seeds_override is None
        else seeds_override
    )
    if nrays < 1000:
        raise ValueError("nrays override must be >= 1000")
    if not seeds or any(seed < 1 for seed in seeds):
        raise ValueError("seed override must contain positive integers")

    output_dir.mkdir(parents=True, exist_ok=True)
    optics_rows = [trace_optics_once(config, nrays, seed) for seed in seeds]
    optics_summary = summarize_optics(optics_rows)
    scenario_rows, common = evaluate_scenarios(config, optics_summary)

    optics_fields = [
        "seed",
        "nrays",
        "throughput",
        "geometric_intercept_fraction",
        "mean_reflectivity_after_intercept",
        "sample_gaussian_equivalent_fwhm_x_mm",
        "sample_gaussian_equivalent_fwhm_z_mm",
        "effective_reflected_rays",
        "bragg_angle_deg",
        "source_to_crystal_m",
        "crystal_to_sample_m",
    ]
    scenario_fields = [
        "name",
        "voltage_kV",
        "electrical_power_W",
        "bremsstrahlung_efficiency",
        "estimated_total_xray_power_W",
        "spectral_photon_rate_all_angles_per_s_per_keV",
        "photon_rate_at_sample_per_s",
        "recorded_useful_rate_per_s",
        "recorded_useful_rate_low_per_s",
        "recorded_useful_rate_high_per_s",
        "full_xanes_time_h",
        "full_xanes_time_best_h",
        "full_xanes_time_worst_h",
        "meets_12h_nominal",
    ]
    write_csv(output_dir / "shadow4_seed_results.csv", optics_rows, optics_fields)
    write_csv(output_dir / "source_scenarios.csv", scenario_rows, scenario_fields)

    waterfall_name = str(config["plot"]["waterfall_scenario"])
    stage_rows = [
        {"stage": name, "photon_rate_per_s": value}
        for name, value in common["stages_by_scenario"][waterfall_name].items()
    ]
    write_csv(
        output_dir / "budget_stages.csv",
        stage_rows,
        ["stage", "photon_rate_per_s"],
    )

    plot_paths: list[str] = []
    if make_plots:
        png, pdf = make_figure(config, scenario_rows, common, output_dir)
        plot_paths = [str(png), str(pdf)]

    write_proposal_note(
        output_dir / "proposal_numbers.md",
        config,
        scenario_rows,
        optics_summary,
        common,
    )
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": [str(Path(sys.executable)), *sys.argv],
        "config_path": str(config_path.resolve()),
        "config_sha256": stable_hash(config),
        "script_sha256": file_sha256(Path(__file__).resolve()),
        "configuration": config,
        "model_scope": (
            "SHADOW4 crystal ray tracing plus analytic xraylib attenuation, "
            "fluorescence, and detector absorption; no GEANT4."
        ),
        "software": {
            "python": platform.python_version(),
            "shadow4": package_version("shadow4"),
            "crystalpy": package_version("crystalpy"),
            "syned": package_version("syned"),
            "xraylib": package_version("xraylib"),
            "numpy": package_version("numpy"),
            "matplotlib": package_version("matplotlib"),
        },
        "run": {"nrays_per_seed": nrays, "seeds": seeds},
        "optics": optics_summary,
        "photon_budget_common": common,
        "source_scenarios": scenario_rows,
        "assumptions_and_limitations": [
            "The tube continuum uses Kramers law normalized by eta=9e-10*Z*V and isotropic emission.",
            "A 0.3-3x envelope is retained because no calibrated tube spectrum is available.",
            "The 10 eV incident bandwidth is a proposal requirement, not derived by this monoenergetic trace.",
            "The Ge(880) crystal is perfect and unstrained; manufacturing errors and bending strain are absent.",
            "The launched angular window is treated as the accepted collimated source phase space.",
            "The small-angle solid angle uses dx_prime*dz_prime; the omitted direction-cosine Jacobian changes this baseline by less than 0.1%.",
            "The Ag sample is a uniform plane-parallel foil; fluorescence and self-absorption are analytic.",
            "Only Ag K-alpha lines are counted as useful signal in the configured baseline.",
            "CZT charge transport is represented by an explicit photopeak collection factor, not particle transport.",
            "Background is represented by a configurable background-to-signal ratio.",
            "No GEANT4, electronics waveform simulation, pile-up transport, or scattering spectrum is included.",
        ],
        "outputs": {
            "summary_json": str((output_dir / "photon_budget_summary.json").resolve()),
            "optics_csv": str((output_dir / "shadow4_seed_results.csv").resolve()),
            "scenarios_csv": str((output_dir / "source_scenarios.csv").resolve()),
            "stages_csv": str((output_dir / "budget_stages.csv").resolve()),
            "proposal_note": str((output_dir / "proposal_numbers.md").resolve()),
            "plots": plot_paths,
        },
    }
    summary_path = output_dir / "photon_budget_summary.json"
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--nrays",
        type=int,
        default=None,
        help="override rays per SHADOW4 seed",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="override the configured random seeds",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="skip PNG/PDF generation (intended for tests)",
    )
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    summary = run(
        args.config,
        args.output_dir,
        nrays_override=args.nrays,
        seeds_override=args.seeds,
        make_plots=not args.no_plots,
    )
    print("PRISM minimum photon budget complete")
    print(
        "SHADOW4 throughput: "
        f"{100.0 * summary['optics']['throughput']['mean']:.4f}%"
    )
    for scenario in summary["source_scenarios"]:
        print(
            f"{scenario['name']}: "
            f"{scenario['recorded_useful_rate_per_s']:.3g} useful count/s, "
            f"{scenario['full_xanes_time_h']:.3g} h for the configured scan"
        )
    print(f"Results: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
