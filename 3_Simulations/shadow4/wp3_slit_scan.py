#!/usr/bin/env python3
"""Controlled two-slit scans for the legacy WP3 simulation stage.

The grant v8 activity supported by this script is A1.2.  Every case within one
seed starts from the same WP2 polychromatic beam.  Rectangular pre-crystal
apertures are applied by projecting each incident ray to the slit plane and
marking blocked rays as lost before the common WP2 crystal trace.

Outputs are assumption-dependent simulation diagnostics.  The Pareto set and
selected diagnostic case are not hardware or procurement recommendations.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from shadow4.beam.s4_beam import S4Beam


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import wp1_monoenergetic as wp1  # noqa: E402
from wp2_tube_source import (  # noqa: E402
    build_polychromatic_source,
    load_or_generate_spectrum,
    trace_incident_beam,
)


DEFAULT_SCAN_CONFIG = SIMULATION_ROOT / "config" / "wp3_slits.json"
DEFAULT_TUBE_CONFIG = SIMULATION_ROOT / "config" / "wp2_tube_source.json"
DEFAULT_GEOMETRY_CONFIG = SIMULATION_ROOT / "config" / "wp1_geometry.json"
DEFAULT_OUTPUT_DIR = SIMULATION_ROOT / "results" / "wp3"
GAUSSIAN_FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))
LOST_AT_INVALID_INPUT = -3099.0
LOST_AT_SLIT_BASE = -3100.0

PERFORMANCE_METRICS = (
    "launched_photons_per_mAs",
    "after_slits_photons_per_mAs",
    "sample_photons_per_mAs",
    "slit_transmission_fraction",
    "crystal_geometric_transmission_fraction",
    "crystal_weighted_acceptance_fraction",
    "source_to_sample_transmission_fraction",
    "after_slits_divergence_sigma_x_mrad",
    "after_slits_divergence_sigma_z_mrad",
    "crystal_illumination_sigma_x_m",
    "crystal_illumination_sigma_tangential_m",
    "sample_sigma_x_m",
    "sample_sigma_z_m",
    "sample_fwhm_x_m",
    "sample_fwhm_z_m",
    "incident_energy_mean_keV",
    "incident_energy_sigma_eV",
    "incident_energy_fwhm_eV",
    "incident_energy_histogram_fwhm_eV",
    "energy_x_correlation",
    "effective_weighted_rays",
)


def load_json(path: Path) -> dict[str, Any]:
    """Load an object-valued JSON document."""
    return wp1.load_json(path)


def require_finite(value: Any, label: str, *, positive: bool = False) -> float:
    """Return a finite float or raise a configuration error."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive and finite" if positive else "finite"
        raise ValueError(f"{label} must be {qualifier}")
    return result


def validate_slit_sequence(slits: Sequence[Mapping[str, Any]]) -> None:
    """Validate the absolute slit schema used by WP3 and downstream WP4."""
    names: set[str] = set()
    distances: list[float] = []
    for index, slit in enumerate(slits):
        if not isinstance(slit, Mapping):
            raise ValueError(f"slit {index} must be an object")
        name = slit.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("slit names must be unique non-empty strings")
        names.add(name)
        distances.append(
            require_finite(
                slit.get("distance_from_source_m"),
                f"{name}.distance_from_source_m",
                positive=True,
            )
        )
        for key in ("width_x_m", "height_z_m"):
            require_finite(slit.get(key), f"{name}.{key}", positive=True)
        for key in ("center_x_m", "center_z_m"):
            require_finite(slit.get(key), f"{name}.{key}")
    if distances != sorted(distances) or len(set(distances)) != len(distances):
        raise ValueError("slits must have distinct downstream-ordered distances")


def validate_scan_config(config: Mapping[str, Any]) -> None:
    """Validate the controlled scan definition without inventing defaults."""
    for key in ("wp2_source_config", "geometry_config"):
        if not isinstance(config.get(key), str) or not str(config[key]).strip():
            raise ValueError(f"{key} must be a non-empty path string")
    require_finite(
        config.get("reference_energy_keV"),
        "reference_energy_keV",
        positive=True,
    )
    nrays = config.get("nrays_per_seed")
    if isinstance(nrays, bool) or not isinstance(nrays, int) or nrays < 100:
        raise ValueError("nrays_per_seed must be an integer of at least 100")
    seeds = config.get("seeds")
    if (
        not isinstance(seeds, list)
        or len(seeds) < 2
        or any(
            isinstance(seed, bool) or not isinstance(seed, int) or seed < 1
            for seed in seeds
        )
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError(
            "seeds must contain at least two distinct positive integers"
        )
    slits = config.get("slits")
    if not isinstance(slits, list) or len(slits) != 2:
        raise ValueError("WP3 requires exactly two configurable slits")
    validate_slit_sequence(slits)
    position_scans: list[list[float]] = []
    for slit in slits:
        positions = slit.get("position_scan_m")
        if not isinstance(positions, list) or len(positions) < 2:
            raise ValueError(
                f"{slit['name']}.position_scan_m must contain at least two positions"
            )
        numeric_positions = [
            require_finite(
                value,
                f"{slit['name']}.position_scan_m",
                positive=True,
            )
            for value in positions
        ]
        if len(set(numeric_positions)) != len(numeric_positions):
            raise ValueError(
                f"{slit['name']}.position_scan_m values must be unique"
            )
        if float(slit["distance_from_source_m"]) not in numeric_positions:
            raise ValueError(
                f"{slit['name']}.position_scan_m must include its nominal position"
            )
        position_scans.append(sorted(numeric_positions))
    if max(position_scans[0]) >= min(position_scans[1]):
        raise ValueError(
            "all scanned slit_1 positions must precede every slit_2 position"
        )

    scan = config.get("scan")
    if not isinstance(scan, Mapping):
        raise ValueError("scan must be an object")
    scales = scan.get("aperture_scale_factors")
    if not isinstance(scales, list) or not scales:
        raise ValueError("scan.aperture_scale_factors must be a non-empty list")
    numeric_scales = [
        require_finite(value, "aperture_scale_factor", positive=True)
        for value in scales
    ]
    if len(set(numeric_scales)) != len(numeric_scales):
        raise ValueError("aperture scale factors must be unique")
    for key in (
        "include_open_case",
        "include_single_slit_cases",
        "include_two_slit_cases",
    ):
        if scan.get(key) is not True:
            raise ValueError(f"scan.{key} must be true for the required WP3 grid")

    pareto = config.get("pareto")
    if not isinstance(pareto, Mapping):
        raise ValueError("pareto must be an object")
    maximize = pareto.get("maximize")
    minimize = pareto.get("minimize")
    if (
        not isinstance(maximize, list)
        or not maximize
        or not isinstance(minimize, list)
        or not minimize
    ):
        raise ValueError("pareto maximize/minimize must be non-empty lists")
    objectives = [*maximize, *minimize]
    if len(set(objectives)) != len(objectives):
        raise ValueError("Pareto objectives must be unique")
    unknown = set(objectives) - set(PERFORMANCE_METRICS)
    if unknown:
        raise ValueError(f"unknown Pareto metrics: {sorted(unknown)}")

    plots = config.get("plots")
    maximum = plots.get("maximum_points") if isinstance(plots, Mapping) else None
    if (
        isinstance(maximum, bool)
        or not isinstance(maximum, int)
        or maximum < 100
    ):
        raise ValueError("plots.maximum_points must be an integer of at least 100")


def _positive_mask(arrays: Mapping[str, np.ndarray]) -> np.ndarray:
    mask = (arrays["status"] > 0.0) & (arrays["weight"] > 0.0)
    for key in ("x_m", "y_m", "z_m", "dx", "dy", "dz", "weight"):
        mask &= np.isfinite(arrays[key])
    mask &= np.abs(arrays["dy"]) > 1.0e-15
    return mask


def _weight_sum(arrays: Mapping[str, np.ndarray], mask: np.ndarray) -> float:
    return float(np.sum(arrays["weight"][mask]))


def apply_slit_sequence(
    incident_beam: S4Beam,
    slits: Sequence[Mapping[str, Any]],
) -> tuple[S4Beam, list[dict[str, Any]]]:
    """Apply ordered rectangular apertures without mutating ``incident_beam``.

    Parameters
    ----------
    incident_beam
        WP2 source beam in the source frame.
    slits
        Ordered mappings with ``name``, ``distance_from_source_m``,
        ``width_x_m``, ``height_z_m``, ``center_x_m`` and ``center_z_m``.

    Returns
    -------
    masked_beam, stage_metrics
        A duplicate S4Beam whose blocked rays have negative SHADOW status, and
        one photons/mAs accounting record per aperture.
    """
    validate_slit_sequence(slits)
    masked_beam = incident_beam.duplicate()
    arrays = wp1.beam_arrays(masked_beam)
    status = np.asarray(arrays["status"], dtype=float).copy()

    initially_positive = status > 0.0
    valid = _positive_mask(arrays)
    status[initially_positive & ~valid] = LOST_AT_INVALID_INPUT
    masked_beam.set_column(10, status)

    stage_metrics: list[dict[str, Any]] = []
    initial_weight = _weight_sum(arrays, valid)
    for index, slit in enumerate(slits):
        arrays = wp1.beam_arrays(masked_beam)
        active = _positive_mask(arrays)
        distance_m = float(slit["distance_from_source_m"])
        path_m = np.full(arrays["dy"].shape, np.nan, dtype=float)
        path_m[active] = (
            distance_m - arrays["y_m"][active]
        ) / arrays["dy"][active]
        projected_x_m = arrays["x_m"] + path_m * arrays["dx"]
        projected_z_m = arrays["z_m"] + path_m * arrays["dz"]
        inside = (
            active
            & np.isfinite(path_m)
            & (path_m >= 0.0)
            & np.isfinite(projected_x_m)
            & np.isfinite(projected_z_m)
            & (
                np.abs(projected_x_m - float(slit["center_x_m"]))
                <= 0.5 * float(slit["width_x_m"])
            )
            & (
                np.abs(projected_z_m - float(slit["center_z_m"]))
                <= 0.5 * float(slit["height_z_m"])
            )
        )
        blocked = active & ~inside
        input_rays = int(np.count_nonzero(active))
        passed_rays = int(np.count_nonzero(inside))
        input_weight = _weight_sum(arrays, active)
        passed_weight = _weight_sum(arrays, inside)
        status = np.asarray(arrays["status"], dtype=float).copy()
        status[blocked] = LOST_AT_SLIT_BASE - float(index + 1)
        masked_beam.set_column(10, status)
        stage_metrics.append(
            {
                "stage_index": index + 1,
                "name": str(slit["name"]),
                "distance_from_source_m": distance_m,
                "width_x_m": float(slit["width_x_m"]),
                "height_z_m": float(slit["height_z_m"]),
                "center_x_m": float(slit["center_x_m"]),
                "center_z_m": float(slit["center_z_m"]),
                "input_rays": input_rays,
                "passed_rays": passed_rays,
                "blocked_rays": input_rays - passed_rays,
                "input_photons_per_mAs": input_weight,
                "passed_photons_per_mAs": passed_weight,
                "blocked_photons_per_mAs": input_weight - passed_weight,
                "stage_transmission_fraction": (
                    passed_weight / input_weight if input_weight > 0.0 else 0.0
                ),
                "cumulative_transmission_fraction": (
                    passed_weight / initial_weight if initial_weight > 0.0 else 0.0
                ),
            }
        )
    return masked_beam, stage_metrics


def _materialize_slit(
    slit: Mapping[str, Any], factor: float, position_m: float
) -> dict[str, Any]:
    result = copy.deepcopy(dict(slit))
    result.pop("position_scan_m", None)
    result["distance_from_source_m"] = position_m
    result["width_x_m"] = factor * float(slit["width_x_m"])
    result["height_z_m"] = factor * float(slit["height_z_m"])
    result["aperture_scale_factor"] = factor
    return result


def _factor_label(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def generate_scan_cases(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Generate open, one-slit and two-slit controlled-comparison cases."""
    validate_scan_config(config)
    base_slits = list(config["slits"])
    scales = [float(value) for value in config["scan"]["aperture_scale_factors"]]
    options = [
        [
            _materialize_slit(slit, factor, float(position_m))
            for position_m, factor in product(slit["position_scan_m"], scales)
        ]
        for slit in base_slits
    ]
    cases: list[dict[str, Any]] = [
        {
            "case_id": "open",
            "mode": "open",
            "slits": [],
        }
    ]
    for slit_index, slit in enumerate(base_slits, start=1):
        for option in options[slit_index - 1]:
            cases.append(
                {
                    "case_id": (
                        f"single_{slit['name']}_"
                        f"d{_factor_label(option['distance_from_source_m'])}_"
                        f"s{_factor_label(option['aperture_scale_factor'])}"
                    ),
                    "mode": "single",
                    "slits": [option],
                    "active_base_slits": [slit_index],
                }
            )
    for first_option, second_option in product(*options):
        cases.append(
            {
                "case_id": (
                    f"both_d{_factor_label(first_option['distance_from_source_m'])}_"
                    f"s{_factor_label(first_option['aperture_scale_factor'])}_"
                    f"d{_factor_label(second_option['distance_from_source_m'])}_"
                    f"s{_factor_label(second_option['aperture_scale_factor'])}"
                ),
                "mode": "two",
                "slits": [
                    first_option,
                    second_option,
                ],
                "active_base_slits": [1, 2],
            }
        )
    identifiers = [case["case_id"] for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("generated slit case identifiers are not unique")
    return cases


def _weighted_sigma(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size < 2 or float(np.sum(weights)) <= 0.0:
        raise RuntimeError("at least two positive weighted rays are required")
    return math.sqrt(wp1.weighted_variance(values, weights))


def _effective_sample_size(weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    denominator = float(np.sum(weights**2))
    return total**2 / denominator if total > 0.0 and denominator > 0.0 else 0.0


def _weighted_correlation(
    first: np.ndarray, second: np.ndarray, weights: np.ndarray
) -> float | None:
    sigma_first = _weighted_sigma(first, weights)
    sigma_second = _weighted_sigma(second, weights)
    if sigma_first <= 0.0 or sigma_second <= 0.0:
        return None
    covariance = wp1.weighted_covariance(first, second, weights)
    value = covariance / (sigma_first * sigma_second)
    return float(np.clip(value, -1.0, 1.0))


def _weighted_histogram_fwhm(
    values: np.ndarray, weights: np.ndarray
) -> float:
    if values.size < 2 or float(np.ptp(values)) <= 0.0:
        return 0.0
    bins = int(np.clip(round(math.sqrt(values.size)), 24, 256))
    histogram, edges = np.histogram(values, bins=bins, weights=weights)
    if not np.any(histogram > 0.0):
        return 0.0
    above = np.flatnonzero(histogram >= 0.5 * float(np.max(histogram)))
    if above.size == 0:
        return 0.0
    return float(edges[above[-1] + 1] - edges[above[0]])


def _sample_distance_m(resolved_geometry: Mapping[str, Any]) -> float:
    for key in (
        "configured_crystal_to_sample_m",
        "crystal_to_sample_m",
        "paraxial_predicted_crystal_to_focus_m",
    ):
        value = resolved_geometry.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result = float(value)
            if math.isfinite(result) and result > 0.0:
                return result
    raise ValueError("WP2 resolved geometry has no positive sample distance")


def beam_performance_metrics(
    incident_beam: S4Beam,
    masked_beam: S4Beam,
    footprint: S4Beam,
    post_crystal: S4Beam,
    resolved_geometry: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute flat WP3 throughput, divergence, footprint, spot and spectrum metrics."""
    incident = wp1.beam_arrays(incident_beam)
    masked = wp1.beam_arrays(masked_beam)
    footprint_arrays = wp1.beam_arrays(footprint)
    post = wp1.beam_arrays(post_crystal)
    incident_mask = _positive_mask(incident)
    masked_mask = _positive_mask(masked)
    footprint_mask = (
        masked_mask
        & (footprint_arrays["status"] > 0.0)
        & np.isfinite(footprint_arrays["x_m"])
        & np.isfinite(footprint_arrays["y_m"])
    )
    post_mask = _positive_mask(post)
    if np.count_nonzero(post_mask) < 2:
        raise RuntimeError("fewer than two positive weighted rays leave the crystal")

    sample_distance_m = _sample_distance_m(resolved_geometry)
    sample_beam = wp1.propagate_beam(post_crystal, sample_distance_m)
    sample = wp1.beam_arrays(sample_beam)
    sample_mask = _positive_mask(sample)
    if np.count_nonzero(sample_mask) < 2:
        raise RuntimeError("fewer than two positive weighted rays reach the sample")

    launched_weight = _weight_sum(incident, incident_mask)
    masked_weight = _weight_sum(masked, masked_mask)
    illuminated_weight = _weight_sum(masked, footprint_mask)
    sample_weight = _weight_sum(sample, sample_mask)
    if launched_weight <= 0.0 or masked_weight <= 0.0 or illuminated_weight <= 0.0:
        raise RuntimeError("non-positive photons/mAs in WP3 throughput accounting")

    masked_weights = masked["weight"][masked_mask]
    input_angle_x_mrad = 1.0e3 * np.arctan2(
        masked["dx"][masked_mask], masked["dy"][masked_mask]
    )
    input_angle_z_mrad = 1.0e3 * np.arctan2(
        masked["dz"][masked_mask], masked["dy"][masked_mask]
    )
    illumination_weights = masked["weight"][footprint_mask]
    sample_weights = sample["weight"][sample_mask]
    sample_x_m = sample["x_m"][sample_mask]
    sample_z_m = sample["z_m"][sample_mask]
    sample_energy_keV = sample["energy_keV"][sample_mask]
    energy_sigma_eV = 1000.0 * _weighted_sigma(
        sample_energy_keV, sample_weights
    )
    sample_sigma_x_m = _weighted_sigma(sample_x_m, sample_weights)
    sample_sigma_z_m = _weighted_sigma(sample_z_m, sample_weights)
    post_weight = _weight_sum(post, post_mask)

    return {
        "launched_rays": int(np.count_nonzero(incident_mask)),
        "after_slits_rays": int(np.count_nonzero(masked_mask)),
        "crystal_illuminated_rays": int(np.count_nonzero(footprint_mask)),
        "usable_sample_rays": int(np.count_nonzero(sample_mask)),
        "launched_photons_per_mAs": launched_weight,
        "after_slits_photons_per_mAs": masked_weight,
        "crystal_illuminated_photons_per_mAs": illuminated_weight,
        "post_crystal_photons_per_mAs": post_weight,
        "sample_photons_per_mAs": sample_weight,
        "slit_transmission_fraction": masked_weight / launched_weight,
        "crystal_geometric_transmission_fraction": (
            illuminated_weight / masked_weight
        ),
        "crystal_weighted_acceptance_fraction": (
            post_weight / illuminated_weight
        ),
        "source_to_sample_transmission_fraction": (
            sample_weight / launched_weight
        ),
        "after_slits_divergence_sigma_x_mrad": _weighted_sigma(
            input_angle_x_mrad, masked_weights
        ),
        "after_slits_divergence_sigma_z_mrad": _weighted_sigma(
            input_angle_z_mrad, masked_weights
        ),
        "crystal_illumination_sigma_x_m": _weighted_sigma(
            footprint_arrays["x_m"][footprint_mask], illumination_weights
        ),
        "crystal_illumination_sigma_tangential_m": _weighted_sigma(
            footprint_arrays["y_m"][footprint_mask], illumination_weights
        ),
        "sample_plane_distance_from_crystal_m": sample_distance_m,
        "sample_sigma_x_m": sample_sigma_x_m,
        "sample_sigma_z_m": sample_sigma_z_m,
        "sample_fwhm_x_m": GAUSSIAN_FWHM_FACTOR * sample_sigma_x_m,
        "sample_fwhm_z_m": GAUSSIAN_FWHM_FACTOR * sample_sigma_z_m,
        "incident_energy_mean_keV": wp1.weighted_mean(
            sample_energy_keV, sample_weights
        ),
        "incident_energy_sigma_eV": energy_sigma_eV,
        "incident_energy_fwhm_eV": GAUSSIAN_FWHM_FACTOR * energy_sigma_eV,
        "incident_energy_histogram_fwhm_eV": (
            1000.0
            * _weighted_histogram_fwhm(sample_energy_keV, sample_weights)
        ),
        "energy_x_correlation": _weighted_correlation(
            sample_energy_keV, sample_x_m, sample_weights
        ),
        "effective_weighted_rays": _effective_sample_size(sample_weights),
        "bandwidth_definition": (
            "incident_energy_fwhm_eV is Gaussian-equivalent 2.35482*sigma; "
            "incident_energy_histogram_fwhm_eV is the weighted histogram half-maximum width"
        ),
    }


def _source_to_crystal_m(
    geometry_config: Mapping[str, Any], reference_energy_keV: float
) -> float:
    configured = geometry_config["distances"]["source_to_crystal_m"]
    if configured is not None:
        return float(configured)
    bragg_angle_rad = wp1.corrected_bragg_angle_rad(
        geometry_config["crystal"], 1000.0 * reference_energy_keV
    )
    return wp1.von_hamos_symmetric_arm_m(
        float(geometry_config["crystal"]["radius_m"]), bragg_angle_rad
    )


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def _evaluate_case(
    source_beam: S4Beam,
    case: Mapping[str, Any],
    geometry_config: Mapping[str, Any],
    reference_energy_keV: float,
    *,
    verbose_shadow4: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    masked_beam, stage_metrics = apply_slit_sequence(
        source_beam, case["slits"]
    )
    footprint, post_crystal, _coordinates, resolved_geometry = (
        trace_incident_beam(
            masked_beam,
            geometry_config,
            reference_energy_keV=reference_energy_keV,
            verbose_shadow4=verbose_shadow4,
        )
    )
    metrics = beam_performance_metrics(
        source_beam,
        masked_beam,
        footprint,
        post_crystal,
        resolved_geometry,
    )
    for stage in stage_metrics:
        prefix = f"stage_{stage['stage_index']}_{_slug(stage['name'])}"
        for key in (
            "input_photons_per_mAs",
            "passed_photons_per_mAs",
            "blocked_photons_per_mAs",
            "stage_transmission_fraction",
            "cumulative_transmission_fraction",
        ):
            metrics[f"{prefix}_{key}"] = stage[key]
    return metrics, stage_metrics


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _beam_fingerprint(beam: S4Beam) -> str:
    return hashlib.sha256(np.asarray(beam.rays).tobytes()).hexdigest()


def _aggregate_records(
    records: Sequence[Mapping[str, Any]],
    cases_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    failed: dict[str, int] = defaultdict(int)
    for record in records:
        case_id = str(record["case_id"])
        if record["status"] == "ok":
            grouped[case_id].append(record)
        else:
            failed[case_id] += 1

    aggregates: list[dict[str, Any]] = []
    for case_id, successful in grouped.items():
        metrics: dict[str, dict[str, float | int | None]] = {}
        for key in PERFORMANCE_METRICS:
            values = [
                float(record["metrics"][key])
                for record in successful
                if record["metrics"].get(key) is not None
                and math.isfinite(float(record["metrics"][key]))
            ]
            if not values:
                metrics[key] = {
                    "mean": None,
                    "std": None,
                    "sem": None,
                    "minimum": None,
                    "maximum": None,
                    "count": 0,
                }
                continue
            array = np.asarray(values, dtype=float)
            standard = float(np.std(array, ddof=1)) if array.size > 1 else 0.0
            metrics[key] = {
                "mean": float(np.mean(array)),
                "std": standard,
                "sem": standard / math.sqrt(array.size),
                "minimum": float(np.min(array)),
                "maximum": float(np.max(array)),
                "count": int(array.size),
            }
        case = cases_by_id[case_id]
        aggregates.append(
            {
                "case_id": case_id,
                "mode": case["mode"],
                "slits": case["slits"],
                "successful_seeds": len(successful),
                "failed_seeds": failed[case_id],
                "metrics": metrics,
            }
        )
    return aggregates


def _objective_value(aggregate: Mapping[str, Any], metric: str) -> float:
    value = aggregate["metrics"][metric]["mean"]
    return float(value) if value is not None else math.nan


def _dominates(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    maximize: Sequence[str],
    minimize: Sequence[str],
) -> bool:
    weak = True
    strict = False
    for metric in maximize:
        a = _objective_value(first, metric)
        b = _objective_value(second, metric)
        if not math.isfinite(a) or not math.isfinite(b):
            return False
        weak &= a >= b
        strict |= a > b
    for metric in minimize:
        a = _objective_value(first, metric)
        b = _objective_value(second, metric)
        if not math.isfinite(a) or not math.isfinite(b):
            return False
        weak &= a <= b
        strict |= a < b
    return weak and strict


def _pareto_front(
    aggregates: Sequence[Mapping[str, Any]],
    maximize: Sequence[str],
    minimize: Sequence[str],
) -> list[str]:
    return [
        str(candidate["case_id"])
        for candidate in aggregates
        if not any(
            _dominates(other, candidate, maximize, minimize)
            for other in aggregates
            if other["case_id"] != candidate["case_id"]
        )
    ]


def _diagnostic_selection(
    aggregates: Sequence[Mapping[str, Any]],
    pareto_ids: Sequence[str],
    maximize: Sequence[str],
    minimize: Sequence[str],
) -> dict[str, Any]:
    candidates = [
        aggregate
        for aggregate in aggregates
        if aggregate["case_id"] in set(pareto_ids)
    ]
    if not candidates:
        raise RuntimeError("no finite Pareto candidate is available")
    benefit_rows: list[list[float]] = [[] for _ in candidates]
    for metric, should_maximize in [
        *((metric, True) for metric in maximize),
        *((metric, False) for metric in minimize),
    ]:
        values = np.asarray(
            [_objective_value(candidate, metric) for candidate in candidates],
            dtype=float,
        )
        if not np.all(np.isfinite(values)):
            raise RuntimeError(f"non-finite Pareto objective {metric}")
        low = float(np.min(values))
        high = float(np.max(values))
        if math.isclose(low, high):
            normalized = np.ones_like(values)
        else:
            normalized = (values - low) / (high - low)
            if not should_maximize:
                normalized = 1.0 - normalized
        for row, benefit in zip(benefit_rows, normalized):
            row.append(float(benefit))
    scores = [float(np.mean(row)) for row in benefit_rows]
    index = int(np.argmax(scores))
    selected = candidates[index]
    return {
        "selected_case_id": selected["case_id"],
        "equal_weight_normalized_objective_score": scores[index],
        "basis": (
            "equal-weight normalized compromise within the simulated Pareto front"
        ),
        "status": "simulation_diagnostic_not_hardware_recommendation",
        "hardware_recommendation": False,
    }


def _write_case_seed_csv(
    path: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    rows: list[dict[str, Any]] = []
    for record in records:
        row = {
            "case_id": record["case_id"],
            "mode": record["mode"],
            "seed": record["seed"],
            "status": record["status"],
            "error": record.get("error", ""),
            "active_slits": len(record["slits"]),
        }
        row.update(record.get("metrics", {}))
        rows.append(_json_ready(row))
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _make_plots(
    output_dir: Path,
    aggregates: Sequence[Mapping[str, Any]],
    pareto_ids: Sequence[str],
    selection: Mapping[str, Any],
) -> tuple[Path, Path]:
    import matplotlib.pyplot as plt

    case_ids = [str(row["case_id"]) for row in aggregates]
    modes = [str(row["mode"]) for row in aggregates]
    flux = np.asarray(
        [_objective_value(row, "sample_photons_per_mAs") for row in aggregates]
    )
    bandwidth = np.asarray(
        [_objective_value(row, "incident_energy_fwhm_eV") for row in aggregates]
    )
    spot_um = 1.0e6 * np.asarray(
        [_objective_value(row, "sample_fwhm_x_m") for row in aggregates]
    )
    slit_transmission = np.asarray(
        [_objective_value(row, "slit_transmission_fraction") for row in aggregates]
    )
    crystal_transmission = np.asarray(
        [
            _objective_value(row, "crystal_weighted_acceptance_fraction")
            for row in aggregates
        ]
    )
    divergence = np.asarray(
        [
            _objective_value(row, "after_slits_divergence_sigma_x_mrad")
            for row in aggregates
        ]
    )
    illumination_mm = 1.0e3 * np.asarray(
        [
            _objective_value(row, "crystal_illumination_sigma_x_m")
            for row in aggregates
        ]
    )
    pareto_mask = np.asarray(
        [case_id in set(pareto_ids) for case_id in case_ids], dtype=bool
    )
    selected_mask = np.asarray(
        [case_id == selection["selected_case_id"] for case_id in case_ids],
        dtype=bool,
    )

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.5))
    ax_tradeoff, ax_spot, ax_transmission, ax_illumination = axes.flat
    scatter = ax_tradeoff.scatter(
        bandwidth,
        flux,
        c=spot_um,
        cmap="viridis_r",
        s=48,
        alpha=0.85,
    )
    ax_tradeoff.scatter(
        bandwidth[pareto_mask],
        flux[pareto_mask],
        s=100,
        facecolor="none",
        edgecolor="tab:red",
        label="Pareto",
    )
    ax_tradeoff.scatter(
        bandwidth[selected_mask],
        flux[selected_mask],
        marker="*",
        s=240,
        facecolor="none",
        edgecolor="black",
        label="diagnostic selection",
    )
    fig.colorbar(scatter, ax=ax_tradeoff, label="Sample FWHM x [µm]")
    ax_tradeoff.set(
        title="Flux–bandwidth trade-off",
        xlabel="Incident-energy Gaussian-equivalent FWHM [eV]",
        ylabel="Predicted photons/mAs at sample",
        yscale="log",
    )
    ax_tradeoff.legend(fontsize=8)

    colors = {"open": "black", "single": "tab:blue", "two": "tab:orange"}
    for mode in ("open", "single", "two"):
        mask = np.asarray([value == mode for value in modes])
        ax_spot.scatter(
            spot_um[mask],
            flux[mask],
            label=mode,
            color=colors[mode],
            alpha=0.8,
        )
    ax_spot.set(
        title="Spot–flux comparison",
        xlabel="Sample FWHM x [µm]",
        ylabel="Predicted photons/mAs at sample",
        yscale="log",
    )
    ax_spot.legend(fontsize=8)

    indices = np.arange(len(case_ids))
    ax_transmission.scatter(
        indices, slit_transmission, label="slit transmission", s=30
    )
    ax_transmission.scatter(
        indices, crystal_transmission, label="crystal weighted acceptance", s=30
    )
    ax_transmission.set(
        title="Per-stage transmission",
        xlabel="Configured case index",
        ylabel="Fraction",
        ylim=(0.0, 1.05),
    )
    ax_transmission.legend(fontsize=8)

    scatter = ax_illumination.scatter(
        divergence,
        illumination_mm,
        c=slit_transmission,
        cmap="plasma",
        s=48,
    )
    fig.colorbar(scatter, ax=ax_illumination, label="Slit transmission")
    ax_illumination.set(
        title="Divergence and crystal illumination",
        xlabel="After-slit sagittal divergence σ [mrad]",
        ylabel="Crystal illumination σx [mm]",
    )

    for axis in axes.flat:
        axis.grid(ls=":", alpha=0.4)
    fig.suptitle(
        "WP3 slit scan — simulation diagnostics, not hardware recommendations"
    )
    fig.tight_layout()
    png_path = output_dir / "wp3_diagnostics.png"
    pdf_path = output_dir / "wp3_diagnostics.pdf"
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


def parse_seed_list(value: str) -> list[int]:
    try:
        seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "seeds must be comma-separated integers"
        ) from error
    if (
        len(seeds) < 2
        or any(seed < 1 for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise argparse.ArgumentTypeError(
            "seeds must contain at least two distinct positive integers"
        )
    return seeds


def run_scan(args: argparse.Namespace) -> dict[str, Any]:
    scan_config = load_json(args.scan_config)
    scan_config["nrays_per_seed"] = int(args.nrays)
    scan_config["seeds"] = list(args.seeds)
    validate_scan_config(scan_config)
    tube_config = load_json(args.tube_config)
    geometry_config = load_json(args.geometry_config)
    wp1.validate_geometry_config(geometry_config)

    reference_energy_keV = float(scan_config["reference_energy_keV"])
    source_reference_energy_keV = float(
        tube_config["source_phase_space"]["reference_energy_keV"]
    )
    if not math.isclose(
        source_reference_energy_keV,
        reference_energy_keV,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError(
            "WP2 source_phase_space.reference_energy_keV and "
            "WP3 reference_energy_keV must match"
        )
    source_distance_m = _source_to_crystal_m(
        geometry_config, reference_energy_keV
    )
    scanned_positions = [
        float(position_m)
        for slit in scan_config["slits"]
        for position_m in slit["position_scan_m"]
    ]
    if max(scanned_positions) >= source_distance_m:
        raise ValueError(
            "every configured slit must be upstream of the resolved crystal plane"
        )

    cases = generate_scan_cases(scan_config)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("the requested case limit leaves no WP3 case")
    cases_by_id = {str(case["case_id"]): case for case in cases}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    spectrum = load_or_generate_spectrum(
        tube_config,
        cache_dir=args.output_dir / "spectrum_cache",
        force_regenerate=args.force_spectrum_cache,
    )
    records: list[dict[str, Any]] = []
    source_metadata_by_seed: dict[str, Any] = {}
    source_fingerprints: dict[str, str] = {}
    for seed in scan_config["seeds"]:
        source_beam, source_metadata = build_polychromatic_source(
            tube_config,
            spectrum,
            nrays=int(scan_config["nrays_per_seed"]),
            seed=int(seed),
        )
        source_metadata_by_seed[str(seed)] = _json_ready(source_metadata)
        source_fingerprints[str(seed)] = _beam_fingerprint(source_beam)
        for case in cases:
            try:
                metrics, stage_metrics = _evaluate_case(
                    source_beam,
                    case,
                    geometry_config,
                    reference_energy_keV,
                    verbose_shadow4=args.verbose_shadow4,
                )
                records.append(
                    {
                        "case_id": case["case_id"],
                        "mode": case["mode"],
                        "slits": case["slits"],
                        "seed": int(seed),
                        "status": "ok",
                        "error": "",
                        "metrics": metrics,
                        "stage_metrics": stage_metrics,
                    }
                )
            except (OSError, ValueError, RuntimeError, FloatingPointError) as error:
                records.append(
                    {
                        "case_id": case["case_id"],
                        "mode": case["mode"],
                        "slits": case["slits"],
                        "seed": int(seed),
                        "status": "failed",
                        "error": str(error),
                        "metrics": {},
                        "stage_metrics": [],
                    }
                )

    aggregates = _aggregate_records(records, cases_by_id)
    if not aggregates:
        errors = sorted(
            {str(record["error"]) for record in records if record["error"]}
        )
        raise RuntimeError(f"all WP3 traces failed: {errors}")
    eligible_aggregates = [
        aggregate
        for aggregate in aggregates
        if int(aggregate["successful_seeds"]) == len(scan_config["seeds"])
    ]
    if not eligible_aggregates:
        raise RuntimeError(
            "no WP3 candidate completed every configured independent seed"
        )
    maximize = list(scan_config["pareto"]["maximize"])
    minimize = list(scan_config["pareto"]["minimize"])
    pareto_ids = _pareto_front(eligible_aggregates, maximize, minimize)
    selection = _diagnostic_selection(
        eligible_aggregates, pareto_ids, maximize, minimize
    )

    case_seed_csv = args.output_dir / "wp3_case_seed_metrics.csv"
    aggregate_json = args.output_dir / "wp3_aggregation.json"
    _write_case_seed_csv(case_seed_csv, records)
    plot_paths: list[str] = []
    if not args.no_plots:
        png_path, pdf_path = _make_plots(
            args.output_dir, eligible_aggregates, pareto_ids, selection
        )
        plot_paths = [str(png_path), str(pdf_path)]

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "legacy_WP3_slit_scan",
        "grant_activity": "A1.2",
        "validation_level": "simulation",
        "hardware_recommendation": False,
        "controlled_comparison": {
            "same_source_beam_reused_for_all_cases_within_each_seed": True,
            "independent_seeds": scan_config["seeds"],
            "source_beam_sha256_by_seed": source_fingerprints,
        },
        "scan_config": scan_config,
        "resolved_source_to_crystal_m": source_distance_m,
        "cases_generated_before_limit": len(generate_scan_cases(scan_config)),
        "cases_executed": len(cases),
        "successful_traces": sum(record["status"] == "ok" for record in records),
        "failed_traces": sum(record["status"] != "ok" for record in records),
        "source_metadata_by_seed": source_metadata_by_seed,
        "case_seed_records": records,
        "aggregates": aggregates,
        "selection_eligible_cases": len(eligible_aggregates),
        "pareto": {
            "maximize": maximize,
            "minimize": minimize,
            "case_ids": pareto_ids,
        },
        "diagnostic_selection": selection,
        "assumptions": [
            "Each slit is an ideal, perfectly absorbing rectangular aperture normal to the source-frame y axis.",
            "The slit mask changes ray status but does not add scatter, edge penetration or fluorescence.",
            "WP2 ray weights are interpreted as photons/mAs and retained for every stage metric.",
            "All cases within a seed duplicate one identical incident beam before masking.",
            "Independent seeds estimate Monte Carlo variation, not alignment or manufacturing tolerances.",
            "The incident-energy bandwidth is distinct from CZT fluorescence-energy resolution.",
            "Pareto and diagnostic selection results are simulation screening evidence, not hardware recommendations.",
        ],
        "outputs": {
            "case_seed_csv": str(case_seed_csv),
            "aggregation_json": str(aggregate_json),
            "plots": plot_paths,
        },
    }
    with aggregate_json.open("w", encoding="utf-8") as stream:
        json.dump(
            _json_ready(summary),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    bundled = load_json(DEFAULT_SCAN_CONFIG)
    parser = argparse.ArgumentParser(
        description=(
            "Apply configurable pre-crystal slits to one reused WP2 beam per "
            "seed and compare throughput, divergence, illumination, spot and bandwidth"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scan-config",
        type=Path,
        default=DEFAULT_SCAN_CONFIG,
        help="WP3 slit grid JSON configuration",
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
        help="WP1 crystal/geometry JSON configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory receiving CSV, aggregation JSON and diagnostic plots",
    )
    parser.add_argument(
        "--nrays",
        type=int,
        default=int(bundled["nrays_per_seed"]),
        help="incident rays generated for each independent seed",
    )
    parser.add_argument(
        "--seeds",
        type=parse_seed_list,
        default=list(bundled["seeds"]),
        metavar="SEED[,SEED...]",
        help="independent source seeds used for statistical aggregation",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="limit cases in controlled grid order; zero means all",
    )
    parser.add_argument(
        "--force-spectrum-cache",
        action="store_true",
        help="regenerate the SpekPy cache even when its configuration hash matches",
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
    if args.max_cases < 0:
        parser.error("--max-cases must be zero or positive")
    try:
        summary = run_scan(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    selection = summary["diagnostic_selection"]
    print(
        f"WP3 completed {summary['successful_traces']} successful traces "
        f"across {summary['cases_executed']} cases and "
        f"{len(summary['controlled_comparison']['independent_seeds'])} seeds."
    )
    print(
        f"Diagnostic selection: {selection['selected_case_id']} "
        f"({selection['status']})."
    )
    print(f"CSV: {summary['outputs']['case_seed_csv']}")
    print(f"Aggregation: {summary['outputs']['aggregation_json']}")


if __name__ == "__main__":
    main()
