#!/usr/bin/env python3
"""WP4 end-to-end SHADOW4 screening and phase-space export.

This stage combines the SpekPy-normalized WP2 source with the configurable
pre-crystal apertures from WP3 and the curved-crystal transport validated in
WP1.  It performs a reproducible multi-seed design scan, identifies the
non-dominated candidates, and exports one selected *simulation candidate* for
WP5.  Selection here is not an approved hardware design freeze.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import wp1_monoenergetic as wp1  # noqa: E402
import wp2_tube_source as wp2  # noqa: E402
import wp3_slit_scan as wp3  # noqa: E402


DEFAULT_TUBE_CONFIG = SIMULATION_ROOT / "config" / "wp2_tube_source.json"
DEFAULT_GEOMETRY_CONFIG = SIMULATION_ROOT / "config" / "wp1_geometry.json"
DEFAULT_SCAN_CONFIG = SIMULATION_ROOT / "config" / "wp4_optimization.json"
DEFAULT_OUTPUT_DIR = SIMULATION_ROOT / "results" / "wp4"
GAUSSIAN_FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))

METRIC_KEYS = (
    "sample_photons_per_mAs",
    "slit_transmission_fraction",
    "crystal_weighted_acceptance_fraction",
    "crystal_end_to_end_acceptance_fraction",
    "sample_sigma_x_m",
    "sample_sigma_z_m",
    "sample_fwhm_x_m",
    "sample_fwhm_z_m",
    "incident_energy_mean_keV",
    "incident_energy_sigma_eV",
    "incident_energy_gaussian_equivalent_fwhm_eV",
    "energy_window_edge_weight_fraction",
    "sample_divergence_sigma_x_mrad",
    "sample_divergence_sigma_z_mrad",
    "energy_x_correlation",
    "effective_weighted_rays",
)


def load_json(path: Path) -> dict[str, Any]:
    """Load an object-valued JSON document."""
    return wp1.load_json(path)


def require_finite(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive and finite" if positive else "finite"
        raise ValueError(f"{label} must be {qualifier}")
    return result


def validate_scan_config(config: Mapping[str, Any]) -> None:
    """Validate the WP4 grid without silently inventing missing settings."""
    require_finite(config.get("reference_energy_keV"), "reference_energy_keV", positive=True)
    nrays = config.get("nrays_per_seed")
    if isinstance(nrays, bool) or not isinstance(nrays, int) or nrays < 100:
        raise ValueError("nrays_per_seed must be an integer of at least 100")
    seeds = config.get("seeds")
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 1 for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("seeds must be a non-empty list of distinct positive integers")
    importance = config.get("trace_energy_importance")
    if not isinstance(importance, Mapping):
        raise ValueError("trace_energy_importance must be an object")
    energy_minimum = require_finite(
        importance.get("minimum_keV"),
        "trace_energy_importance.minimum_keV",
        positive=True,
    )
    energy_maximum = require_finite(
        importance.get("maximum_keV"),
        "trace_energy_importance.maximum_keV",
        positive=True,
    )
    reference_energy = float(config["reference_energy_keV"])
    if not energy_minimum < reference_energy < energy_maximum:
        raise ValueError(
            "trace_energy_importance must bracket reference_energy_keV"
        )
    resolution_scan = config.get("resolution_scan")
    if not isinstance(resolution_scan, Mapping):
        raise ValueError("resolution_scan must be an object")
    resolution_rays = resolution_scan.get("nrays_per_seed")
    if (
        isinstance(resolution_rays, bool)
        or not isinstance(resolution_rays, int)
        or resolution_rays < 100
    ):
        raise ValueError(
            "resolution_scan.nrays_per_seed must be an integer of at least 100"
        )
    resolution_minimum = require_finite(
        resolution_scan.get("minimum_keV"),
        "resolution_scan.minimum_keV",
        positive=True,
    )
    resolution_maximum = require_finite(
        resolution_scan.get("maximum_keV"),
        "resolution_scan.maximum_keV",
        positive=True,
    )
    if not resolution_minimum < reference_energy < resolution_maximum:
        raise ValueError("resolution_scan must bracket reference_energy_keV")
    resolution_step_eV = require_finite(
        resolution_scan.get("step_eV"),
        "resolution_scan.step_eV",
        positive=True,
    )
    if resolution_step_eV > 0.5:
        raise ValueError(
            "resolution_scan.step_eV must be at most 0.5 eV for the 10 eV gate"
        )
    batch_points = resolution_scan.get("batch_energy_points")
    if (
        isinstance(batch_points, bool)
        or not isinstance(batch_points, int)
        or not 1 <= batch_points <= 100
    ):
        raise ValueError(
            "resolution_scan.batch_energy_points must be an integer in [1, 100]"
        )

    grid = config.get("geometry_grid")
    if not isinstance(grid, Mapping):
        raise ValueError("geometry_grid must be an object")
    for key in (
        "crystal_radius_m",
        "source_distance_scale_of_symmetric_arm",
        "sample_distance_scale_of_paraxial_image",
    ):
        values = grid.get(key)
        if not isinstance(values, list) or not values:
            raise ValueError(f"geometry_grid.{key} must be a non-empty list")
        for value in values:
            require_finite(value, f"geometry_grid.{key}", positive=True)

    designs = config.get("slit_designs")
    if not isinstance(designs, list) or not designs:
        raise ValueError("slit_designs must be a non-empty list")
    names: set[str] = set()
    for design in designs:
        if not isinstance(design, Mapping):
            raise ValueError("each slit design must be an object")
        name = design.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("slit design names must be unique non-empty strings")
        names.add(name)
        slits = design.get("slits")
        if not isinstance(slits, list):
            raise ValueError(f"slit design {name!r} requires a slits list")
        fractions: list[float] = []
        for slit in slits:
            if not isinstance(slit, Mapping):
                raise ValueError(f"slits in design {name!r} must be objects")
            for key in ("width_x_m", "height_z_m"):
                require_finite(slit.get(key), f"{name}.{key}", positive=True)
            fraction = require_finite(
                slit.get("distance_fraction_of_source_crystal_arm"),
                f"{name}.distance_fraction_of_source_crystal_arm",
                positive=True,
            )
            if fraction >= 1.0:
                raise ValueError(f"slit {slit.get('name')!r} must be before the crystal")
            fractions.append(fraction)
            for key in ("center_x_m", "center_z_m"):
                require_finite(slit.get(key, 0.0), f"{name}.{key}")
        if fractions != sorted(fractions):
            raise ValueError(f"slits in design {name!r} must be ordered downstream")

    selection = config.get("selection")
    expected_selection = {
        "constraints",
        "objective_weights",
        "robustness_cv_penalty",
    }
    if not isinstance(selection, Mapping) or set(selection) != expected_selection:
        raise ValueError(
            f"selection must contain exactly {sorted(expected_selection)}"
        )
    constraints = selection.get("constraints")
    weights = selection.get("objective_weights")
    if not isinstance(constraints, Mapping) or not isinstance(weights, Mapping):
        raise ValueError("selection requires constraints and objective_weights objects")
    expected_constraints = {
        "incident_energy_resolution_fwhm_eV_max",
        "independent_seeds_min",
        "sample_fwhm_x_m_max",
        "effective_weighted_rays_min",
        "resolution_peak_effective_rays_min",
        "resolution_peak_offset_eV_max",
        "resolution_peak_energy_std_eV_max",
        "resolution_fwhm_cv_max",
        "energy_window_edge_weight_fraction_max",
    }
    if set(constraints) != expected_constraints:
        raise ValueError(
            "selection.constraints must contain exactly "
            f"{sorted(expected_constraints)}"
        )
    for key, value in constraints.items():
        require_finite(value, f"selection.constraints.{key}", positive=True)
    independent_seeds_min = constraints["independent_seeds_min"]
    if (
        isinstance(independent_seeds_min, bool)
        or not isinstance(independent_seeds_min, int)
        or independent_seeds_min < 2
    ):
        raise ValueError(
            "selection.constraints.independent_seeds_min must be an integer "
            "of at least two"
        )
    expected_weights = {
        "sample_photons_per_mAs",
        "incident_energy_resolution_fwhm_eV",
        "sample_fwhm_x_m",
    }
    if set(weights) != expected_weights:
        raise ValueError(f"objective_weights must contain exactly {sorted(expected_weights)}")
    weight_sum = sum(require_finite(value, f"objective_weights.{key}") for key, value in weights.items())
    if any(float(value) < 0.0 for value in weights.values()) or not math.isclose(
        weight_sum, 1.0, abs_tol=1.0e-12
    ):
        raise ValueError("objective weights must be non-negative and sum to one")
    robustness_penalty = require_finite(
        selection.get("robustness_cv_penalty"), "robustness_cv_penalty"
    )
    if robustness_penalty < 0.0:
        raise ValueError("robustness_cv_penalty cannot be negative")


def parse_seed_list(value: str) -> list[int]:
    try:
        seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from error
    if not seeds or any(seed < 1 for seed in seeds) or len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("seeds must be distinct positive integers")
    return seeds


def case_identifier(
    radius_index: int,
    source_index: int,
    sample_index: int,
    slit_index: int,
) -> str:
    return f"r{radius_index:02d}_p{source_index:02d}_q{sample_index:02d}_s{slit_index:02d}"


def materialize_slits(
    design: Mapping[str, Any], source_distance_m: float
) -> list[dict[str, Any]]:
    """Convert relative slit positions to the absolute WP3 schema."""
    slits: list[dict[str, Any]] = []
    for slit in design["slits"]:
        slits.append(
            {
                "name": str(slit["name"]),
                "distance_from_source_m": (
                    float(slit["distance_fraction_of_source_crystal_arm"])
                    * source_distance_m
                ),
                "width_x_m": float(slit["width_x_m"]),
                "height_z_m": float(slit["height_z_m"]),
                "center_x_m": float(slit.get("center_x_m", 0.0)),
                "center_z_m": float(slit.get("center_z_m", 0.0)),
            }
        )
    return slits


def enumerate_cases(
    scan_config: Mapping[str, Any],
    base_geometry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Resolve each geometry/slit candidate into an executable case."""
    reference_energy_keV = float(scan_config["reference_energy_keV"])
    crystal_base = base_geometry["crystal"]
    bragg_angle_rad = wp1.corrected_bragg_angle_rad(
        crystal_base, 1000.0 * reference_energy_keV
    )
    grid = scan_config["geometry_grid"]
    cases: list[dict[str, Any]] = []
    indexed_product = product(
        enumerate(grid["crystal_radius_m"]),
        enumerate(grid["source_distance_scale_of_symmetric_arm"]),
        enumerate(grid["sample_distance_scale_of_paraxial_image"]),
        enumerate(scan_config["slit_designs"]),
    )
    for (
        (radius_index, radius_m),
        (source_index, source_scale),
        (sample_index, sample_scale),
        (slit_index, slit_design),
    ) in indexed_product:
        radius_m = float(radius_m)
        source_scale = float(source_scale)
        sample_scale = float(sample_scale)
        symmetric_arm_m = wp1.von_hamos_symmetric_arm_m(radius_m, bragg_angle_rad)
        source_distance_m = source_scale * symmetric_arm_m
        paraxial_image_m = wp1.sagittal_image_distance_m(
            source_distance_m, radius_m, bragg_angle_rad
        )
        sample_distance_m = sample_scale * paraxial_image_m
        geometry = copy.deepcopy(dict(base_geometry))
        geometry["crystal"]["radius_m"] = radius_m
        geometry["distances"]["source_to_crystal_m"] = source_distance_m
        geometry["distances"]["crystal_to_sample_m"] = sample_distance_m
        case = {
            "case_id": case_identifier(
                radius_index, source_index, sample_index, slit_index
            ),
            "radius_m": radius_m,
            "source_distance_scale": source_scale,
            "sample_distance_scale": sample_scale,
            "source_distance_m": source_distance_m,
            "sample_distance_m": sample_distance_m,
            "paraxial_image_m": paraxial_image_m,
            "slit_design": str(slit_design["name"]),
            "slits": materialize_slits(slit_design, source_distance_m),
            "geometry_config": geometry,
        }
        cases.append(case)
    return cases


def positive_mask(arrays: Mapping[str, np.ndarray]) -> np.ndarray:
    mask = (arrays["status"] > 0.0) & (arrays["weight"] > 0.0)
    for key in ("x_m", "y_m", "z_m", "dx", "dy", "dz", "energy_keV", "weight"):
        mask &= np.isfinite(arrays[key])
    return mask


def safe_weighted_sigma(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size < 2 or float(np.sum(weights)) <= 0.0:
        return math.nan
    return math.sqrt(wp1.weighted_variance(values, weights))


def effective_sample_size(weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    denominator = float(np.sum(weights**2))
    return total**2 / denominator if total > 0.0 and denominator > 0.0 else 0.0


def energy_window_edge_weight_fraction(
    energy_keV: np.ndarray,
    weights: np.ndarray,
    minimum_keV: float,
    maximum_keV: float,
) -> float:
    """Return weight in the outer 5% of the traced energy window.

    A non-negligible value signals that the importance window may truncate the
    monochromator response, in which case its width must not be accepted as an
    incident-energy resolution.
    """
    width_keV = maximum_keV - minimum_keV
    if width_keV <= 0.0:
        raise ValueError("energy importance limits must be ordered")
    total = float(np.sum(weights))
    if total <= 0.0:
        return 1.0
    margin_keV = 0.05 * width_keV
    edge = (energy_keV <= minimum_keV + margin_keV) | (
        energy_keV >= maximum_keV - margin_keV
    )
    return float(np.sum(weights[edge]) / total)


def evaluate_case(
    source_beam: Any,
    source_metadata: Mapping[str, Any],
    case: Mapping[str, Any],
    reference_energy_keV: float,
    energy_importance: Mapping[str, Any],
    *,
    verbose_shadow4: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Trace one case and return scalar metrics plus reusable beams."""
    masked_beam, slit_metrics = wp3.apply_slit_sequence(
        source_beam, case["slits"]
    )
    footprint, post_crystal, coordinates, resolved_geometry = wp2.trace_incident_beam(
        masked_beam,
        case["geometry_config"],
        reference_energy_keV=reference_energy_keV,
        verbose_shadow4=verbose_shadow4,
    )
    sample_distance_m = float(resolved_geometry["configured_crystal_to_sample_m"])
    sample_beam = wp1.propagate_beam(post_crystal, sample_distance_m)

    source_arrays = wp1.beam_arrays(source_beam)
    masked_arrays = wp1.beam_arrays(masked_beam)
    post_arrays = wp1.beam_arrays(post_crystal)
    sample_arrays = wp1.beam_arrays(sample_beam)
    source_mask = positive_mask(source_arrays)
    masked_mask = positive_mask(masked_arrays)
    post_mask = positive_mask(post_arrays)
    sample_mask = positive_mask(sample_arrays)
    if np.count_nonzero(sample_mask) < 2:
        raise RuntimeError("fewer than two positive weighted rays reach the sample")

    launched_weight = float(np.sum(source_arrays["weight"][source_mask]))
    after_slit_weight = float(np.sum(masked_arrays["weight"][masked_mask]))
    sample_weights = sample_arrays["weight"][sample_mask]
    sample_weight = float(np.sum(sample_weights))
    sample_x = sample_arrays["x_m"][sample_mask]
    sample_z = sample_arrays["z_m"][sample_mask]
    sample_energy = sample_arrays["energy_keV"][sample_mask]
    angle_x = 1.0e3 * np.arctan2(
        sample_arrays["dx"][sample_mask], sample_arrays["dy"][sample_mask]
    )
    angle_z = 1.0e3 * np.arctan2(
        sample_arrays["dz"][sample_mask], sample_arrays["dy"][sample_mask]
    )
    sigma_x_m = safe_weighted_sigma(sample_x, sample_weights)
    sigma_z_m = safe_weighted_sigma(sample_z, sample_weights)
    energy_sigma_keV = safe_weighted_sigma(sample_energy, sample_weights)
    energy_minimum_keV = float(energy_importance["minimum_keV"])
    energy_maximum_keV = float(energy_importance["maximum_keV"])
    edge_weight_fraction = energy_window_edge_weight_fraction(
        sample_energy,
        sample_weights,
        energy_minimum_keV,
        energy_maximum_keV,
    )
    variance_x = sigma_x_m**2
    variance_energy = energy_sigma_keV**2
    covariance = (
        wp1.weighted_covariance(sample_energy, sample_x, sample_weights)
        if variance_x > 0.0 and variance_energy > 0.0
        else math.nan
    )
    correlation = (
        covariance / math.sqrt(variance_x * variance_energy)
        if math.isfinite(covariance)
        else math.nan
    )
    crystal_acceptance = wp1.acceptance_metrics(
        masked_beam, footprint, post_crystal
    )
    metrics = {
        "launched_photons_per_mAs": launched_weight,
        "after_slits_photons_per_mAs": after_slit_weight,
        "sample_photons_per_mAs": sample_weight,
        "slit_transmission_fraction": (
            after_slit_weight / launched_weight if launched_weight > 0.0 else 0.0
        ),
        "crystal_weighted_acceptance_fraction": float(
            crystal_acceptance[
                "mean_reflectivity_for_geometrically_intercepted_rays"
            ]
        ),
        "crystal_end_to_end_acceptance_fraction": float(
            crystal_acceptance["weighted_accepted_fraction"]
        ),
        "end_to_end_transmission_fraction": (
            sample_weight / launched_weight if launched_weight > 0.0 else 0.0
        ),
        "sample_sigma_x_m": sigma_x_m,
        "sample_sigma_z_m": sigma_z_m,
        "sample_fwhm_x_m": GAUSSIAN_FWHM_FACTOR * sigma_x_m,
        "sample_fwhm_z_m": GAUSSIAN_FWHM_FACTOR * sigma_z_m,
        "incident_energy_mean_keV": wp1.weighted_mean(
            sample_energy, sample_weights
        ),
        "incident_energy_sigma_eV": 1000.0 * energy_sigma_keV,
        "incident_energy_gaussian_equivalent_fwhm_eV": (
            1000.0 * GAUSSIAN_FWHM_FACTOR * energy_sigma_keV
        ),
        "energy_window_edge_weight_fraction": edge_weight_fraction,
        "sample_divergence_sigma_x_mrad": safe_weighted_sigma(
            angle_x, sample_weights
        ),
        "sample_divergence_sigma_z_mrad": safe_weighted_sigma(
            angle_z, sample_weights
        ),
        "energy_x_correlation": correlation,
        "effective_weighted_rays": effective_sample_size(sample_weights),
        "usable_sample_rows": int(np.count_nonzero(sample_mask)),
    }
    artifacts = {
        "masked_source": masked_beam,
        "footprint": footprint,
        "post_crystal": post_crystal,
        "sample": sample_beam,
        "coordinates": coordinates,
        "resolved_geometry": resolved_geometry,
        "slit_metrics": slit_metrics,
        "source_metadata": dict(source_metadata),
        "metrics": metrics,
    }
    return metrics, artifacts


def resolution_energy_grid(scan: Mapping[str, Any]) -> np.ndarray:
    minimum_eV = 1000.0 * float(scan["minimum_keV"])
    maximum_eV = 1000.0 * float(scan["maximum_keV"])
    step_eV = float(scan["step_eV"])
    intervals = int(round((maximum_eV - minimum_eV) / step_eV))
    if intervals < 2 or not math.isclose(
        minimum_eV + intervals * step_eV,
        maximum_eV,
        rel_tol=0.0,
        abs_tol=1.0e-8,
    ):
        raise ValueError(
            "resolution_scan range must be an integer multiple of step_eV"
        )
    return minimum_eV + step_eV * np.arange(intervals + 1, dtype=float)


def half_maximum_response_metrics(
    energy_eV: np.ndarray, transmission: np.ndarray
) -> dict[str, Any]:
    """Resolve the FWHM of a sampled monoenergetic transmission response."""
    energy = np.asarray(energy_eV, dtype=float)
    response = np.asarray(transmission, dtype=float)
    if (
        energy.ndim != 1
        or response.shape != energy.shape
        or energy.size < 3
        or np.any(~np.isfinite(energy))
        or np.any(~np.isfinite(response))
        or np.any(response < 0.0)
        or np.any(np.diff(energy) <= 0.0)
    ):
        raise ValueError("invalid monoenergetic response arrays")
    peak_index = int(np.argmax(response))
    peak = float(response[peak_index])
    result: dict[str, Any] = {
        "resolved": False,
        "peak_energy_eV": float(energy[peak_index]),
        "peak_transmission_fraction": peak,
        "left_half_maximum_eV": None,
        "right_half_maximum_eV": None,
        "incident_energy_resolution_fwhm_eV": None,
        "reason": "",
    }
    if peak <= 0.0:
        result["reason"] = "monoenergetic response has no positive transmission"
        return result
    half = 0.5 * peak
    left_candidates = np.flatnonzero(response[:peak_index] <= half)
    right_candidates = np.flatnonzero(response[peak_index + 1 :] <= half)
    if left_candidates.size == 0 or right_candidates.size == 0:
        result["reason"] = (
            "one or both half-maximum crossings lie outside the configured "
            "resolution scan"
        )
        return result
    left_low = int(left_candidates[-1])
    left_high = left_low + 1
    right_high = peak_index + 1 + int(right_candidates[0])
    right_low = right_high - 1

    def interpolate(first: int, second: int) -> float:
        y0 = float(response[first])
        y1 = float(response[second])
        if math.isclose(y0, y1, rel_tol=0.0, abs_tol=1.0e-30):
            return 0.5 * float(energy[first] + energy[second])
        fraction = (half - y0) / (y1 - y0)
        return float(energy[first] + fraction * (energy[second] - energy[first]))

    left_crossing = interpolate(left_low, left_high)
    right_crossing = interpolate(right_low, right_high)
    fwhm_eV = right_crossing - left_crossing
    if not math.isfinite(fwhm_eV) or fwhm_eV <= 0.0:
        result["reason"] = "interpolated half-maximum crossings are invalid"
        return result
    result.update(
        {
            "resolved": True,
            "left_half_maximum_eV": left_crossing,
            "right_half_maximum_eV": right_crossing,
            "incident_energy_resolution_fwhm_eV": fwhm_eV,
            "reason": "",
        }
    )
    return result


def monoenergetic_transmission_batch(
    probe_source: Any,
    case: Mapping[str, Any],
    reference_energy_keV: float,
    energy_eV: np.ndarray,
    *,
    verbose_shadow4: bool,
) -> list[tuple[float, float]]:
    """Trace tiled common phase-space rays and return ``(T(E), N_eff)``."""
    energies = np.asarray(energy_eV, dtype=float)
    if (
        energies.ndim != 1
        or energies.size == 0
        or np.any(~np.isfinite(energies))
        or np.any(energies <= 0.0)
    ):
        raise ValueError("monoenergetic batch energies must be positive and finite")
    masked_base, _ = wp3.apply_slit_sequence(
        probe_source, case["slits"]
    )
    base_arrays = wp1.beam_arrays(masked_base)
    base_mask = positive_mask(base_arrays)
    input_weight = float(np.sum(base_arrays["weight"][base_mask]))
    if input_weight <= 0.0:
        raise RuntimeError("no positive source weight passes the configured slits")
    base_count = masked_base.get_number_of_rays()
    tiled = np.tile(masked_base.rays, (energies.size, 1))
    mono_source = type(masked_base).initialize_from_array(tiled)
    mono_source.set_photon_energy_eV(np.repeat(energies, base_count))
    footprint, post_crystal, _, _ = wp2.trace_incident_beam(
        mono_source,
        case["geometry_config"],
        reference_energy_keV=reference_energy_keV,
        verbose_shadow4=verbose_shadow4,
    )
    post_arrays = wp1.beam_arrays(post_crystal)
    post_mask = positive_mask(post_arrays)
    results: list[tuple[float, float]] = []
    for index in range(energies.size):
        row_slice = slice(index * base_count, (index + 1) * base_count)
        mask = post_mask[row_slice]
        reflected_weights = post_arrays["weight"][row_slice][mask]
        reflected_weight = float(np.sum(reflected_weights))
        transmission = reflected_weight / input_weight
        if not 0.0 <= transmission <= 1.0 + 1.0e-12:
            raise RuntimeError("unphysical monoenergetic transmission outside [0, 1]")
        results.append(
            (transmission, effective_sample_size(reflected_weights))
        )
    return results


def monoenergetic_transmission_point(
    probe_source: Any,
    case: Mapping[str, Any],
    reference_energy_keV: float,
    energy_eV: float,
    *,
    verbose_shadow4: bool,
) -> tuple[float, float]:
    """Single-energy convenience wrapper for tests and focused diagnostics."""
    return monoenergetic_transmission_batch(
        probe_source,
        case,
        reference_energy_keV,
        np.asarray([energy_eV], dtype=float),
        verbose_shadow4=verbose_shadow4,
    )[0]


def scan_resolution_responses(
    cases: Sequence[Mapping[str, Any]],
    probe_sources: Mapping[int, Any],
    seeds: Sequence[int],
    reference_energy_keV: float,
    scan: Mapping[str, Any],
    *,
    verbose_shadow4: bool,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Scan T(E) with common rays and summarize physical half-max FWHM."""
    energy_eV = resolution_energy_grid(scan)
    batch_points = int(scan["batch_energy_points"])
    records: list[dict[str, Any]] = []
    seed_summaries_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seed in seeds:
        probe_source = probe_sources[int(seed)]
        for case in cases:
            transmissions: list[float] = []
            peak_effective: list[float] = []
            failed = False
            error_text = ""
            for start in range(0, energy_eV.size, batch_points):
                batch = energy_eV[start : start + batch_points]
                try:
                    batch_results = monoenergetic_transmission_batch(
                        probe_source,
                        case,
                        reference_energy_keV,
                        batch,
                        verbose_shadow4=verbose_shadow4,
                    )
                    for energy, (transmission, effective) in zip(
                        batch, batch_results
                    ):
                        transmissions.append(transmission)
                        peak_effective.append(effective)
                        records.append(
                            {
                                "case_id": case["case_id"],
                                "seed": int(seed),
                                "energy_eV": float(energy),
                                "transmission_fraction": transmission,
                                "effective_reflected_rays": effective,
                                "status": "ok",
                                "error": "",
                            }
                        )
                except (
                    OSError,
                    ValueError,
                    RuntimeError,
                    FloatingPointError,
                ) as error:
                    failed = True
                    error_text = str(error)
                    for energy in batch:
                        records.append(
                            {
                                "case_id": case["case_id"],
                                "seed": int(seed),
                                "energy_eV": float(energy),
                                "transmission_fraction": None,
                                "effective_reflected_rays": None,
                                "status": "failed",
                                "error": error_text,
                            }
                        )
                    break
            if failed:
                seed_summaries_by_case[str(case["case_id"])].append(
                    {
                        "seed": int(seed),
                        "resolved": False,
                        "reason": error_text,
                    }
                )
                continue
            metrics = half_maximum_response_metrics(
                energy_eV, np.asarray(transmissions, dtype=float)
            )
            peak_index = int(np.argmax(transmissions))
            metrics.update(
                {
                    "seed": int(seed),
                    "effective_reflected_rays_at_peak": float(
                        peak_effective[peak_index]
                    ),
                }
            )
            seed_summaries_by_case[str(case["case_id"])].append(metrics)

    summaries: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = str(case["case_id"])
        seed_summaries = seed_summaries_by_case.get(case_id, [])
        resolved = [
            item
            for item in seed_summaries
            if item.get("resolved")
            and item.get("incident_energy_resolution_fwhm_eV") is not None
        ]
        widths = np.asarray(
            [
                float(item["incident_energy_resolution_fwhm_eV"])
                for item in resolved
            ],
            dtype=float,
        )
        peaks = np.asarray(
            [float(item["peak_energy_eV"]) for item in resolved], dtype=float
        )
        effective = np.asarray(
            [
                float(item["effective_reflected_rays_at_peak"])
                for item in resolved
            ],
            dtype=float,
        )
        complete = len(resolved) == len(seeds)
        summaries[case_id] = {
            "case_id": case_id,
            "seed_summaries": seed_summaries,
            "successful_resolution_seeds": len(resolved),
            "resolution_resolved_all_seeds": complete,
            "incident_energy_resolution_fwhm_eV_mean": (
                float(np.mean(widths)) if widths.size else math.nan
            ),
            "incident_energy_resolution_fwhm_eV_std": (
                float(np.std(widths, ddof=1)) if widths.size > 1 else 0.0
            ),
            "resolution_peak_energy_eV_mean": (
                float(np.mean(peaks)) if peaks.size else math.nan
            ),
            "resolution_peak_offset_eV_mean": (
                float(
                    np.mean(
                        np.abs(
                            peaks - 1000.0 * reference_energy_keV
                        )
                    )
                )
                if peaks.size
                else math.nan
            ),
            "resolution_peak_energy_eV_std": (
                float(np.std(peaks, ddof=1)) if peaks.size > 1 else 0.0
            ),
            "resolution_fwhm_cv": (
                float(np.std(widths, ddof=1) / np.mean(widths))
                if widths.size > 1 and float(np.mean(widths)) > 0.0
                else 0.0
            ),
            "resolution_peak_effective_rays_min": (
                float(np.min(effective)) if effective.size else 0.0
            ),
        }
    return records, summaries


def flatten_result_row(
    case: Mapping[str, Any], seed: int, metrics: Mapping[str, Any]
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "seed": seed,
        "radius_m": case["radius_m"],
        "source_distance_scale": case["source_distance_scale"],
        "sample_distance_scale": case["sample_distance_scale"],
        "source_distance_m": case["source_distance_m"],
        "sample_distance_m": case["sample_distance_m"],
        "slit_design": case["slit_design"],
        "active_slits": len(case["slits"]),
        "status": "ok",
        "error": "",
    }
    row.update(metrics)
    return row


def aggregate_rows(
    rows: Sequence[Mapping[str, Any]], cases_by_id: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "ok":
            grouped[str(row["case_id"])].append(row)
    aggregates: list[dict[str, Any]] = []
    for case_id, case_rows in grouped.items():
        case = cases_by_id[case_id]
        aggregate: dict[str, Any] = {
            "case_id": case_id,
            "radius_m": case["radius_m"],
            "source_distance_scale": case["source_distance_scale"],
            "sample_distance_scale": case["sample_distance_scale"],
            "source_distance_m": case["source_distance_m"],
            "sample_distance_m": case["sample_distance_m"],
            "slit_design": case["slit_design"],
            "active_slits": len(case["slits"]),
            "successful_seeds": len(case_rows),
        }
        for metric in METRIC_KEYS:
            values = np.asarray([float(row[metric]) for row in case_rows], dtype=float)
            finite = values[np.isfinite(values)]
            aggregate[f"{metric}_mean"] = (
                float(np.mean(finite)) if finite.size else math.nan
            )
            aggregate[f"{metric}_std"] = (
                float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0
            )
        aggregates.append(aggregate)
    return aggregates


def dominates(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    objectives = (
        ("sample_photons_per_mAs_mean", True),
        ("incident_energy_resolution_fwhm_eV_mean", False),
        ("sample_fwhm_x_m_mean", False),
    )
    weakly_better = True
    strictly_better = False
    for key, maximize in objectives:
        a = float(first[key])
        b = float(second[key])
        if not math.isfinite(a) or not math.isfinite(b):
            return False
        better_or_equal = a >= b if maximize else a <= b
        strictly = a > b if maximize else a < b
        weakly_better &= better_or_equal
        strictly_better |= strictly
    return weakly_better and strictly_better


def pareto_case_ids(aggregates: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(candidate["case_id"])
        for candidate in aggregates
        if not any(
            dominates(other, candidate)
            for other in aggregates
            if other["case_id"] != candidate["case_id"]
        )
    ]


def normalized_benefit(
    values: np.ndarray, *, maximize: bool, logarithmic: bool = False
) -> np.ndarray:
    transformed = np.asarray(values, dtype=float)
    if logarithmic:
        transformed = np.log10(np.maximum(transformed, np.finfo(float).tiny))
    low = float(np.nanmin(transformed))
    high = float(np.nanmax(transformed))
    if not math.isfinite(low) or not math.isfinite(high) or math.isclose(low, high):
        return np.ones_like(transformed)
    normalized = (transformed - low) / (high - low)
    return normalized if maximize else 1.0 - normalized


def select_candidate(
    aggregates: list[dict[str, Any]], selection: Mapping[str, Any]
) -> dict[str, Any]:
    if not aggregates:
        raise RuntimeError("no successful WP4 case is available for selection")
    flux = np.asarray(
        [row["sample_photons_per_mAs_mean"] for row in aggregates], dtype=float
    )
    bandwidth = np.asarray(
        [
            row["incident_energy_resolution_fwhm_eV_mean"]
            for row in aggregates
        ],
        dtype=float,
    )
    spot = np.asarray(
        [row["sample_fwhm_x_m_mean"] for row in aggregates], dtype=float
    )
    benefits = {
        "sample_photons_per_mAs": normalized_benefit(
            flux, maximize=True, logarithmic=True
        ),
        "incident_energy_resolution_fwhm_eV": normalized_benefit(
            bandwidth, maximize=False
        ),
        "sample_fwhm_x_m": normalized_benefit(spot, maximize=False),
    }
    weights = selection["objective_weights"]
    constraints = selection["constraints"]
    penalty_factor = float(selection["robustness_cv_penalty"])
    pareto_ids = set(pareto_case_ids(aggregates))
    for index, aggregate in enumerate(aggregates):
        utility = sum(
            float(weights[key]) * float(benefits[key][index]) for key in weights
        )
        cvs: list[float] = []
        for metric in (
            "sample_photons_per_mAs",
            "incident_energy_resolution_fwhm_eV",
            "sample_fwhm_x_m",
        ):
            mean = abs(float(aggregate[f"{metric}_mean"]))
            standard = float(aggregate[f"{metric}_std"])
            if mean > 0.0 and math.isfinite(standard):
                cvs.append(standard / mean)
        robustness_penalty = penalty_factor * (sum(cvs) / len(cvs) if cvs else 0.0)
        violations = [
            max(
                0.0,
                float(constraints["independent_seeds_min"])
                / max(float(aggregate["successful_seeds"]), 1.0e-30)
                - 1.0,
            ),
            max(
                0.0,
                float(
                    aggregate["incident_energy_resolution_fwhm_eV_mean"]
                )
                / float(
                    constraints[
                        "incident_energy_resolution_fwhm_eV_max"
                    ]
                )
                - 1.0,
            ),
            max(
                0.0,
                float(aggregate["sample_fwhm_x_m_mean"])
                / float(constraints["sample_fwhm_x_m_max"])
                - 1.0,
            ),
            max(
                0.0,
                float(aggregate["energy_window_edge_weight_fraction_mean"])
                / float(
                    constraints["energy_window_edge_weight_fraction_max"]
                )
                - 1.0,
            ),
            max(
                0.0,
                float(constraints["effective_weighted_rays_min"])
                / max(float(aggregate["effective_weighted_rays_mean"]), 1.0e-30)
                - 1.0,
            ),
            max(
                0.0,
                float(constraints["resolution_peak_effective_rays_min"])
                / max(
                    float(aggregate["resolution_peak_effective_rays_min"]),
                    1.0e-30,
                )
                - 1.0,
            ),
            max(
                0.0,
                float(aggregate["resolution_peak_energy_eV_std"])
                / float(
                    constraints["resolution_peak_energy_std_eV_max"]
                )
                - 1.0,
            ),
            max(
                0.0,
                float(aggregate["resolution_peak_offset_eV_mean"])
                / float(constraints["resolution_peak_offset_eV_max"])
                - 1.0,
            ),
            max(
                0.0,
                float(aggregate["resolution_fwhm_cv"])
                / float(constraints["resolution_fwhm_cv_max"])
                - 1.0,
            ),
        ]
        aggregate["objective_utility"] = utility
        aggregate["robustness_penalty"] = robustness_penalty
        aggregate["selection_score"] = utility - robustness_penalty
        aggregate["constraint_violation"] = float(sum(violations))
        aggregate["constraints_satisfied"] = not any(value > 0.0 for value in violations)
        aggregate["pareto_optimal"] = aggregate["case_id"] in pareto_ids

    feasible = [row for row in aggregates if row["constraints_satisfied"]]
    if feasible:
        selected = max(feasible, key=lambda row: float(row["selection_score"]))
        basis = "highest configured utility among simulation-feasible candidates"
    else:
        selected = min(
            aggregates,
            key=lambda row: (
                float(row["constraint_violation"]),
                -float(row["selection_score"]),
            ),
        )
        basis = (
            "minimum normalized constraint violation because no scanned case "
            "met every simulation gate"
        )
    status = (
        "simulation_candidate_not_an_approved_design_freeze"
        if bool(selected["constraints_satisfied"])
        else "diagnostic_fallback_infeasible_not_for_wp5_design_input"
    )
    return {
        "selected_case_id": selected["case_id"],
        "basis": basis,
        "constraints_satisfied": bool(selected["constraints_satisfied"]),
        "selected_metrics": selected,
        "pareto_case_ids": sorted(pareto_ids),
        "status": status,
    }


def write_rows_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty scan table")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        ""
                        if value is None
                        or (
                            isinstance(value, (float, np.floating))
                            and not math.isfinite(float(value))
                        )
                        else value
                    )
                    for key, value in row.items()
                }
            )


def json_ready(value: Any) -> Any:
    """Convert NumPy values and non-finite floats to strict-JSON values."""
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_sample_csv(path: Path, sample_beam: Any) -> int:
    arrays = wp1.beam_arrays(sample_beam)
    mask = positive_mask(arrays)
    fields = (
        "x_m",
        "y_m",
        "z_m",
        "dx",
        "dy",
        "dz",
        "energy_keV",
        "weight",
        "status",
        "ray_id",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        for values in zip(*(arrays[field][mask] for field in fields)):
            writer.writerow(values)
    return int(np.count_nonzero(mask))


def make_plots(
    output_dir: Path,
    aggregates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    selected_artifacts: Mapping[str, Any],
    plot_config: Mapping[str, Any],
    seed: int,
) -> tuple[Path, Path]:
    selected_id = str(selection["selected_case_id"])
    partial_scan = not bool(
        selection.get("full_configured_case_grid_executed", True)
    )
    selected_label = (
        "selected software-smoke/partial-scan case"
        if partial_scan
        else "selected simulation candidate"
    )
    flux = np.asarray(
        [row["sample_photons_per_mAs_mean"] for row in aggregates], dtype=float
    )
    bandwidth = np.asarray(
        [
            row["incident_energy_resolution_fwhm_eV_mean"]
            for row in aggregates
        ],
        dtype=float,
    )
    spot_um = 1.0e6 * np.asarray(
        [row["sample_fwhm_x_m_mean"] for row in aggregates], dtype=float
    )
    radii_mm = 1.0e3 * np.asarray([row["radius_m"] for row in aggregates])
    selected_flags = np.asarray(
        [row["case_id"] == selected_id for row in aggregates], dtype=bool
    )

    sample_arrays = wp1.beam_arrays(selected_artifacts["sample"])
    sample_mask = positive_mask(sample_arrays)
    indices = np.flatnonzero(sample_mask)
    maximum = int(plot_config["maximum_scatter_rays"])
    if indices.size > maximum:
        generator = np.random.default_rng(seed)
        indices = np.sort(generator.choice(indices, maximum, replace=False))
    colors = sample_arrays["energy_keV"][indices]

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.5))
    ax_pareto, ax_geometry, ax_phase, ax_spectrum = axes.flat
    scatter = ax_pareto.scatter(
        bandwidth,
        flux,
        c=spot_um,
        cmap="viridis_r",
        s=45,
        alpha=0.85,
    )
    ax_pareto.scatter(
        bandwidth[selected_flags],
        flux[selected_flags],
        marker="*",
        s=240,
        facecolor="none",
        edgecolor="black",
        linewidth=1.5,
        label=selected_label,
    )
    fig.colorbar(scatter, ax=ax_pareto, label="Sample FWHM x [µm]")
    ax_pareto.set(
        xlabel="Modeled incident-energy response T(E), half-maximum FWHM [eV]",
        ylabel="Predicted photons/mAs at sample",
        title="Flux–bandwidth trade-off",
        yscale="log",
    )
    ax_pareto.legend(fontsize=8)

    for slit_name in sorted({str(row["slit_design"]) for row in aggregates}):
        mask = np.asarray(
            [row["slit_design"] == slit_name for row in aggregates], dtype=bool
        )
        ax_geometry.scatter(
            radii_mm[mask],
            spot_um[mask],
            label=slit_name,
            alpha=0.8,
        )
    ax_geometry.set(
        xlabel="Crystal radius [mm]",
        ylabel="Sample FWHM x [µm]",
        title="Geometry and aperture comparison",
    )
    ax_geometry.legend(fontsize=7)

    phase = ax_phase.scatter(
        1.0e3 * sample_arrays["x_m"][indices],
        1.0e3 * sample_arrays["z_m"][indices],
        c=colors,
        s=3,
        cmap="turbo",
        rasterized=True,
    )
    fig.colorbar(phase, ax=ax_phase, label="Incident energy [keV]")
    ax_phase.set(
        xlabel="Sample x [mm]",
        ylabel="Sample z [mm]",
        title=(
            "Partial-scan sample phase space"
            if partial_scan
            else "Selected sample phase space"
        ),
    )

    ax_spectrum.hist(
        sample_arrays["energy_keV"][sample_mask],
        bins=int(plot_config["spectrum_bins"]),
        weights=sample_arrays["weight"][sample_mask],
        histtype="step",
        lw=1.6,
    )
    ax_spectrum.set(
        xlabel="Incident energy [keV]",
        ylabel="Photons/mAs per bin",
        title=(
            "Partial-scan spectrum at sample"
            if partial_scan
            else "Selected spectrum at sample"
        ),
    )

    for axis in axes.flat:
        axis.grid(ls=":", alpha=0.4)
    fig.suptitle(
        "WP4 software smoke / partial scan"
        if partial_scan
        else "WP4 end-to-end SHADOW4 simulation screening"
    )
    fig.tight_layout()
    png_path = output_dir / "wp4_diagnostics.png"
    pdf_path = output_dir / "wp4_diagnostics.pdf"
    fig.savefig(png_path, dpi=240)
    fig.savefig(pdf_path)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="FigureCanvasAgg is non-interactive, and thus cannot be shown",
            category=UserWarning,
        )
        plt.show()
    plt.close(fig)
    return png_path, pdf_path


def make_resolution_plot(
    output_dir: Path,
    selected_case_id: str,
    records: Sequence[Mapping[str, Any]],
) -> tuple[Path, Path]:
    """Plot per-seed and mean monoenergetic T(E) for the selected case."""
    selected_records = [
        row
        for row in records
        if str(row["case_id"]) == selected_case_id
        and row.get("status") == "ok"
    ]
    grouped: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in selected_records:
        grouped[int(row["seed"])].append(row)
    if not grouped:
        raise RuntimeError("selected case has no resolution-response records")

    fig, axis = plt.subplots(figsize=(9.0, 5.7))
    common_energy: np.ndarray | None = None
    transmissions: list[np.ndarray] = []
    for seed, seed_rows in sorted(grouped.items()):
        ordered = sorted(seed_rows, key=lambda row: float(row["energy_eV"]))
        energy = np.asarray([row["energy_eV"] for row in ordered], dtype=float)
        response = np.asarray(
            [row["transmission_fraction"] for row in ordered], dtype=float
        )
        if common_energy is None:
            common_energy = energy
        elif not np.array_equal(common_energy, energy):
            raise RuntimeError("resolution-response energy grids differ by seed")
        transmissions.append(response)
        axis.plot(
            energy,
            response,
            alpha=0.45,
            linewidth=1.0,
            label=f"seed {seed}",
        )
    assert common_energy is not None
    mean_response = np.mean(np.vstack(transmissions), axis=0)
    mean_metrics = half_maximum_response_metrics(
        common_energy, mean_response
    )
    axis.plot(
        common_energy,
        mean_response,
        color="black",
        linewidth=2.0,
        label="mean T(E)",
    )
    if mean_metrics["resolved"]:
        half = 0.5 * float(mean_metrics["peak_transmission_fraction"])
        left = float(mean_metrics["left_half_maximum_eV"])
        right = float(mean_metrics["right_half_maximum_eV"])
        axis.hlines(
            half,
            left,
            right,
            color="tab:red",
            linewidth=1.5,
            label=(
                "mean half maximum; "
                f"FWHM={float(mean_metrics['incident_energy_resolution_fwhm_eV']):.3g} eV"
            ),
        )
        axis.vlines(
            [left, right],
            0.0,
            half,
            color="tab:red",
            linestyle=":",
            linewidth=1.0,
        )
    axis.set(
        xlabel="Monoenergetic probe energy [eV]",
        ylabel="Weighted transmission T(E)",
        title=(
            f"WP4 physical incident-energy response — {selected_case_id}"
        ),
    )
    axis.grid(linestyle=":", alpha=0.4)
    axis.legend(fontsize=8)
    fig.tight_layout()
    png_path = output_dir / "wp4_resolution_response.png"
    pdf_path = output_dir / "wp4_resolution_response.pdf"
    fig.savefig(png_path, dpi=240)
    fig.savefig(pdf_path)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="FigureCanvasAgg is non-interactive, and thus cannot be shown",
            category=UserWarning,
        )
        plt.show()
    plt.close(fig)
    return png_path, pdf_path


def invalidate_previous_phase_space_exports(output_dir: Path) -> list[str]:
    """Remove exact WP4 hand-off artifacts before a new campaign starts."""
    paths = [
        output_dir / "wp4_phase_space.h5",
        output_dir / "wp4_diagnostic_phase_space.h5",
        output_dir / "wp4_phase_space.h5.incomplete",
        output_dir / "wp4_diagnostic_phase_space.h5.incomplete",
        output_dir / "wp4_sample_phase_space.csv",
        output_dir / "wp4_diagnostic_sample_phase_space.csv",
    ]
    for path in paths:
        if path.is_dir():
            raise IsADirectoryError(
                f"refusing to replace WP4 artifact directory: {path}"
            )
    removed: list[str] = []
    for path in paths:
        if path.exists() or path.is_symlink():
            path.unlink()
            removed.append(str(path))
    return removed


def run_optimization(args: argparse.Namespace) -> dict[str, Any]:
    tube_config = load_json(args.tube_config)
    geometry_config = load_json(args.geometry_config)
    scan_config = load_json(args.scan_config)
    validate_scan_config(scan_config)
    wp1.validate_geometry_config(geometry_config)
    if bool(geometry_config["crystal"]["use_thick_crystal_approximation"]):
        raise ValueError(
            "WP4 requires the configured finite crystal thickness: the "
            "CrystalPy thick-crystal branch produces non-physical off-Bragg tails"
        )
    source_reference_energy_keV = float(
        tube_config["source_phase_space"]["reference_energy_keV"]
    )
    if not math.isclose(
        source_reference_energy_keV,
        float(scan_config["reference_energy_keV"]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError(
            "WP2 source_phase_space.reference_energy_keV and "
            "WP4 reference_energy_keV must match"
        )
    scan_config["nrays_per_seed"] = int(args.nrays)
    scan_config["seeds"] = list(args.seeds)
    scan_config["resolution_scan"]["nrays_per_seed"] = int(
        args.resolution_nrays
    )
    validate_scan_config(scan_config)
    tube_config["energy_importance"] = copy.deepcopy(
        scan_config["trace_energy_importance"]
    )
    cases = enumerate_cases(scan_config, geometry_config)
    cases_generated = len(cases)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("the requested case limit leaves no WP4 case")
    case_limit_applied = len(cases) < cases_generated
    cases_by_id = {str(case["case_id"]): case for case in cases}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    removed_stale_alternate_outputs = (
        invalidate_previous_phase_space_exports(args.output_dir)
    )
    cache_dir = args.output_dir / "spectrum_cache"
    spectrum = wp2.load_or_generate_spectrum(
        tube_config,
        cache_dir=cache_dir,
        force_regenerate=args.force_spectrum_cache,
    )
    rows: list[dict[str, Any]] = []
    source_by_seed: dict[int, tuple[Any, dict[str, Any]]] = {}
    reference_energy_keV = float(scan_config["reference_energy_keV"])
    for seed in scan_config["seeds"]:
        source_by_seed[seed] = wp2.build_polychromatic_source(
            tube_config,
            spectrum,
            nrays=int(scan_config["nrays_per_seed"]),
            seed=int(seed),
        )
        source_beam, source_metadata = source_by_seed[seed]
        for case in cases:
            try:
                metrics, _ = evaluate_case(
                    source_beam,
                    source_metadata,
                    case,
                    reference_energy_keV,
                    scan_config["trace_energy_importance"],
                    verbose_shadow4=args.verbose_shadow4,
                )
                rows.append(flatten_result_row(case, seed, metrics))
            except (OSError, ValueError, RuntimeError, FloatingPointError) as error:
                rows.append(
                    {
                        "case_id": case["case_id"],
                        "seed": seed,
                        "radius_m": case["radius_m"],
                        "source_distance_scale": case["source_distance_scale"],
                        "sample_distance_scale": case["sample_distance_scale"],
                        "source_distance_m": case["source_distance_m"],
                        "sample_distance_m": case["sample_distance_m"],
                        "slit_design": case["slit_design"],
                        "active_slits": len(case["slits"]),
                        "status": "failed",
                        "error": str(error),
                    }
                )

    aggregates = aggregate_rows(rows, cases_by_id)
    probe_sources: dict[int, Any] = {}
    for seed in scan_config["seeds"]:
        probe_sources[int(seed)], _ = wp2.build_polychromatic_source(
            tube_config,
            spectrum,
            nrays=int(scan_config["resolution_scan"]["nrays_per_seed"]),
            seed=int(seed),
        )
    resolution_records, resolution_summaries = scan_resolution_responses(
        cases,
        probe_sources,
        scan_config["seeds"],
        reference_energy_keV,
        scan_config["resolution_scan"],
        verbose_shadow4=args.verbose_shadow4,
    )
    for aggregate in aggregates:
        resolution_summary = resolution_summaries.get(
            str(aggregate["case_id"]),
            {
                "successful_resolution_seeds": 0,
                "resolution_resolved_all_seeds": False,
                "incident_energy_resolution_fwhm_eV_mean": math.nan,
                "incident_energy_resolution_fwhm_eV_std": math.nan,
                "resolution_peak_energy_eV_mean": math.nan,
                "resolution_peak_offset_eV_mean": math.nan,
                "resolution_peak_energy_eV_std": math.nan,
                "resolution_fwhm_cv": math.nan,
                "resolution_peak_effective_rays_min": 0.0,
            },
        )
        aggregate.update(
            {
                key: value
                for key, value in resolution_summary.items()
                if key not in {"case_id", "seed_summaries"}
            }
        )
    eligible_aggregates = [
        aggregate
        for aggregate in aggregates
        if int(aggregate["successful_seeds"]) == len(scan_config["seeds"])
        and bool(aggregate["resolution_resolved_all_seeds"])
    ]
    if not eligible_aggregates:
        raise RuntimeError(
            "no WP4 candidate completed every configured seed with both "
            "polychromatic metrics and two resolved half-maximum crossings"
        )
    selection = select_candidate(eligible_aggregates, scan_config["selection"])
    selection["executed_subset_constraints_satisfied"] = bool(
        selection["constraints_satisfied"]
    )
    selection["full_configured_case_grid_executed"] = not case_limit_applied
    if case_limit_applied:
        selection["executed_subset_status"] = selection["status"]
        selection["constraints_satisfied"] = False
        selection["status"] = (
            "software_smoke_or_partial_scan_not_for_wp5_design_input"
        )
        selection["basis"] = (
            "A case limit truncated the configured geometry/slit grid; "
            "the selected subset result is a software smoke/partial scan only."
        )
    selected_case = cases_by_id[str(selection["selected_case_id"])]
    selected_seed = int(scan_config["seeds"][0])
    selected_source, selected_source_metadata = source_by_seed[selected_seed]
    selected_metrics, selected_artifacts = evaluate_case(
        selected_source,
        selected_source_metadata,
        selected_case,
        reference_energy_keV,
        scan_config["trace_energy_importance"],
        verbose_shadow4=args.verbose_shadow4,
    )

    scan_csv_path = args.output_dir / "wp4_scan.csv"
    aggregate_csv_path = args.output_dir / "wp4_aggregates.csv"
    resolution_csv_path = args.output_dir / "wp4_resolution_response.csv"
    downstream_ready = bool(selection["constraints_satisfied"])
    phase_space_path = args.output_dir / (
        "wp4_phase_space.h5"
        if downstream_ready
        else "wp4_diagnostic_phase_space.h5"
    )
    phase_space_incomplete_path = phase_space_path.with_name(
        phase_space_path.name + ".incomplete"
    )
    sample_csv_path = args.output_dir / (
        "wp4_sample_phase_space.csv"
        if downstream_ready
        else "wp4_diagnostic_sample_phase_space.csv"
    )
    candidate_path = args.output_dir / "wp4_candidate_design.json"
    summary_path = args.output_dir / "wp4_summary.json"
    write_rows_csv(scan_csv_path, rows)
    write_rows_csv(aggregate_csv_path, aggregates)
    write_rows_csv(resolution_csv_path, resolution_records)
    valid_csv_rows = write_sample_csv(
        sample_csv_path, selected_artifacts["sample"]
    )

    phase_metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "WP4_end_to_end",
        "validation_level": "simulation",
        "selection_status": selection["status"],
        "downstream_wp5_design_input_approved": downstream_ready,
        "producer": "wp4_end_to_end.py",
        "source_group_description": (
            "Selected WP4 source after the configured ideal slit status masks."
        ),
        "selected_case": {
            key: value
            for key, value in selected_case.items()
            if key != "geometry_config"
        },
        "selected_seed": selected_seed,
        "selected_metrics": selected_metrics,
        "source_metadata": selected_source_metadata,
        "geometry": selected_artifacts["resolved_geometry"],
        "slit_metrics": selected_artifacts["slit_metrics"],
        "normalization": {
            "weight_unit": "photons/mAs",
            "current_exposure_scaling": "multiply weight by current_mA * exposure_s",
            "sampled_solid_angle_sr": selected_source_metadata[
                "sampled_solid_angle_sr"
            ],
            "energy_importance_minimum_keV": float(
                tube_config["energy_importance"]["minimum_keV"]
            ),
            "energy_importance_maximum_keV": float(
                tube_config["energy_importance"]["maximum_keV"]
            ),
        },
    }
    wp2.save_phase_space(
        phase_space_incomplete_path,
        selected_artifacts["masked_source"],
        selected_artifacts["post_crystal"],
        selected_artifacts["sample"],
        json_ready(phase_metadata),
    )

    if case_limit_applied:
        candidate_evidence_boundary = (
            "Software smoke/partial-scan result from a truncated configured "
            "grid. It is not a WP5 design input or a complete numerical screening."
        )
    elif downstream_ready:
        candidate_evidence_boundary = (
            "Reproducible numerical screening candidate that passed every "
            "configured simulation gate. Design-freeze approval, supplier "
            "tolerances, calibrated tube brightness, and measurement validation "
            "remain external gates."
        )
    else:
        candidate_evidence_boundary = (
            "Constraint-violating numerical diagnostic exported only for "
            "pipeline inspection. It is not a WP5 design input; design-freeze "
            "approval and measurement validation remain external gates."
        )
    candidate_document = {
        "status": selection["status"],
        "selection_basis": selection["basis"],
        "constraints_satisfied": selection["constraints_satisfied"],
        "case": {
            key: value
            for key, value in selected_case.items()
            if key != "geometry_config"
        },
        "geometry_config": selected_case["geometry_config"],
        "metrics_first_seed": selected_metrics,
        "aggregate_metrics": selection["selected_metrics"],
        "downstream_wp5_design_input_approved": downstream_ready,
        "evidence_boundary": candidate_evidence_boundary,
    }
    with candidate_path.open("w", encoding="utf-8") as stream:
        json.dump(
            json_ready(candidate_document),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")

    plots: list[str] = []
    if not args.no_plots:
        png_path, pdf_path = make_plots(
            args.output_dir,
            eligible_aggregates,
            selection,
            selected_artifacts,
            scan_config["plots"],
            selected_seed,
        )
        resolution_png, resolution_pdf = make_resolution_plot(
            args.output_dir,
            str(selection["selected_case_id"]),
            resolution_records,
        )
        plots = [
            str(png_path),
            str(pdf_path),
            str(resolution_png),
            str(resolution_pdf),
        ]

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "WP4_end_to_end",
        "validation_level": "simulation",
        "scan_config": scan_config,
        "cases_requested": len(cases),
        "cases_generated": cases_generated,
        "cases_executed": len(cases),
        "case_limit_applied": case_limit_applied,
        "max_cases_cli": int(args.max_cases),
        "seeds": scan_config["seeds"],
        "successful_traces": sum(row["status"] == "ok" for row in rows),
        "failed_traces": sum(row["status"] != "ok" for row in rows),
        "aggregates": aggregates,
        "selection_eligible_cases": len(eligible_aggregates),
        "resolution_summaries": resolution_summaries,
        "selection": selection,
        "selected_first_seed_metrics": selected_metrics,
        "phase_space_rows": valid_csv_rows,
        "removed_stale_alternate_outputs": removed_stale_alternate_outputs,
        "assumptions": [
            "The SpekPy on-axis spectrum is factorized from source position and direction.",
            "Absolute normalization inherits the sampled solid-angle and photons/mAs assumptions of WP2.",
            "Each case uses identical initial rays within a seed for controlled comparison.",
            "Independent configured seeds quantify Monte Carlo variation but not hardware tolerances.",
            "Crystal bending strain, air, windows, manufacturing errors, sample interactions, and detector response are outside WP4.",
            "Incident-energy resolution is the interpolated half-maximum width of a dedicated finite-thickness monoenergetic transmission response T(E) using common source rays at every energy.",
            "The polychromatic 2.35482-sigma width is retained only as a Gaussian-equivalent spectrum diagnostic and is not used for the 10 eV gate.",
            "The outer 5 percent of the WP4 energy-importance window is gated to detect a truncated response.",
            "The selected result is a simulation candidate, not an approved design freeze or procurement recommendation.",
        ],
        "outputs": {
            "summary_json": str(summary_path),
            "scan_csv": str(scan_csv_path),
            "aggregate_csv": str(aggregate_csv_path),
            "resolution_response_csv": str(resolution_csv_path),
            "candidate_design_json": str(candidate_path),
            "phase_space_hdf5_for_wp5": (
                str(phase_space_path) if downstream_ready else None
            ),
            "diagnostic_phase_space_hdf5": (
                None if downstream_ready else str(phase_space_path)
            ),
            "sample_phase_space_csv": str(sample_csv_path),
            "plots": plots,
        },
    }
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(
            json_ready(summary),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")
    phase_space_incomplete_path.replace(phase_space_path)
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    bundled = load_json(DEFAULT_SCAN_CONFIG)
    parser = argparse.ArgumentParser(
        description=(
            "Scan the complete SpekPy source, slit, Ge crystal, and sample-plane "
            "SHADOW4 chain and export one simulation candidate for WP5"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tube-config",
        type=Path,
        default=DEFAULT_TUBE_CONFIG,
        help="WP2 tube/source JSON configuration",
    )
    parser.add_argument(
        "--geometry-config",
        type=Path,
        default=DEFAULT_GEOMETRY_CONFIG,
        help="base WP1 crystal/geometry JSON configuration",
    )
    parser.add_argument(
        "--scan-config",
        type=Path,
        default=DEFAULT_SCAN_CONFIG,
        help="WP4 scan and selection JSON configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory receiving scan, candidate, phase-space, and plot outputs",
    )
    parser.add_argument(
        "--nrays",
        type=int,
        default=int(bundled["nrays_per_seed"]),
        help="rays generated for each independent seed",
    )
    parser.add_argument(
        "--seeds",
        type=parse_seed_list,
        default=list(bundled["seeds"]),
        metavar="SEED[,SEED...]",
        help="independent random seeds",
    )
    parser.add_argument(
        "--resolution-nrays",
        type=int,
        default=int(bundled["resolution_scan"]["nrays_per_seed"]),
        help=(
            "common phase-space rays per seed and energy point in the "
            "monoenergetic T(E) resolution scan"
        ),
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="limit geometry/slit candidates in configured order; zero means all",
    )
    parser.add_argument(
        "--force-spectrum-cache",
        action="store_true",
        help="regenerate the SpekPy cache even when the operating-point hash matches",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="skip PNG/PDF diagnostic plots for automated tests",
    )
    parser.add_argument(
        "--verbose-shadow4",
        action="store_true",
        help="show SHADOW4 low-level trace diagnostics",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.nrays < 100:
        parser.error("--nrays must be at least 100")
    if args.resolution_nrays < 100:
        parser.error("--resolution-nrays must be at least 100")
    if args.max_cases < 0:
        parser.error("--max-cases must be zero or positive")
    try:
        summary = run_optimization(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    selection = summary["selection"]
    metrics = summary["selected_first_seed_metrics"]
    resolution_fwhm_eV = float(
        selection["selected_metrics"][
            "incident_energy_resolution_fwhm_eV_mean"
        ]
    )
    print(
        f"Selected {selection['selected_case_id']} "
        f"({selection['status']}; {selection['basis']})."
    )
    print(
        f"Predicted sample flux = {metrics['sample_photons_per_mAs']:.6g} photons/mAs; "
        "modeled incident-energy resolution = "
        f"{resolution_fwhm_eV:.6g} eV FWHM from T(E); "
        f"sample FWHM x = {1.0e6 * metrics['sample_fwhm_x_m']:.6g} um."
    )
    print(f"Summary: {summary['outputs']['summary_json']}")


if __name__ == "__main__":
    main()
