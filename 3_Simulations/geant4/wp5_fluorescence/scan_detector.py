#!/usr/bin/env python3
"""Scan the conditional PRISM WP5 CZT geometry with independent Geant4 seeds."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = SIMULATION_ROOT / "config" / "wp5_scan.json"
DEFAULT_INPUT = SIMULATION_ROOT / "results" / "wp5" / "wp5_phase_space.csv"
DEFAULT_OUTPUT_DIR = SIMULATION_ROOT / "results" / "wp5" / "detector_scan"
DEFAULT_BINARY = os.environ.get("PRISM_WP5_BINARY", "prism_wp5")
PREPARED_PHASE_SPACE_SCHEMA = "PRISM_WP5_PHASE_SPACE_V1"
RAW_EVENT_SCHEMA = "PRISM_WP5_RAW_V1"
SELECTION_STATUS = "conditional_simulation_diagnostic_not_approved_hardware"
SOFTWARE_SMOKE_STATUS = (
    "software_smoke_or_partial_detector_scan_not_for_screening_claims"
)
INSUFFICIENT_STATISTICS_STATUS = (
    "conditional_detector_scan_insufficient_statistics_not_for_screening_claims"
)

GEOMETRY_KEYS = (
    "angle_deg",
    "distance_mm",
    "width_mm",
    "height_mm",
    "thickness_mm",
)

METRIC_KEYS = (
    "incident_weight",
    "weighted_total_deposited_keV",
    "weighted_mean_deposited_keV_per_incident",
    "raw_detection_weight_fraction_proxy",
    "detection_weight_fraction_proxy",
    "ag_kalpha_entry_weight",
    "ag_kbeta_entry_weight",
    "ag_kalpha_entries_count",
    "ag_kbeta_entries_count",
    "fluorescence_roi_events_count",
    "ag_kalpha_entry_weight_per_incident",
    "ag_kbeta_entry_weight_per_incident",
    "ag_kalpha_roi_weight_fraction_proxy",
    "ag_kbeta_roi_weight_fraction_proxy",
    "fluorescence_roi_weight_fraction_proxy",
    "background_weight_fraction_of_incident_proxy",
    "secondary_gamma_entry_weight_per_incident",
    "ag_kalpha_entry_efficiency_given_created_proxy",
    "ag_kbeta_entry_efficiency_given_created_proxy",
    "geometric_solid_angle_sr",
    "solid_angle_fraction_4pi",
    "detector_active_volume_cm3",
    "wall_time_s",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError(f"configuration root must be an object: {path}")
    return document


def finite_number(
    value: Any,
    label: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    if positive and result <= 0.0:
        raise ValueError(f"{label} must be positive")
    if nonnegative and result < 0.0:
        raise ValueError(f"{label} cannot be negative")
    return result


def validate_scan_config(config: Mapping[str, Any]) -> None:
    events = config.get("events")
    if isinstance(events, bool) or not isinstance(events, int) or events < 0:
        raise ValueError("events must be a non-negative integer; zero means all input rows")
    seeds = config.get("seeds")
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(
            isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0
            for seed in seeds
        )
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("seeds must be distinct positive integers")

    grid = config.get("geometry_grid")
    if not isinstance(grid, Mapping) or set(grid) != set(GEOMETRY_KEYS):
        raise ValueError(f"geometry_grid must contain exactly {list(GEOMETRY_KEYS)}")
    for key in GEOMETRY_KEYS:
        values = grid[key]
        if not isinstance(values, list) or not values:
            raise ValueError(f"geometry_grid.{key} must be a non-empty list")
        numeric = [
            finite_number(value, f"geometry_grid.{key}", positive=key != "angle_deg")
            for value in values
        ]
        if key == "angle_deg" and any(not 0.0 <= value <= 180.0 for value in numeric):
            raise ValueError("detector angles must lie in [0, 180] degrees")
        if len(set(numeric)) != len(numeric):
            raise ValueError(f"geometry_grid.{key} values must be unique")

    fixed = config.get("fixed_geometry")
    required_fixed = {
        "sample_width_mm",
        "sample_height_mm",
        "sample_thickness_mm",
        "czt_density_g_cm3",
        "world_half_size_mm",
        "production_cut_um",
    }
    if not isinstance(fixed, Mapping) or set(fixed) != required_fixed:
        raise ValueError(f"fixed_geometry must contain exactly {sorted(required_fixed)}")
    for key, value in fixed.items():
        finite_number(value, f"fixed_geometry.{key}", positive=True)

    response = config.get("response")
    required_response = {
        "noise_fwhm_keV",
        "fractional_fwhm",
        "detection_threshold_keV",
        "ag_kalpha_roi_keV",
        "ag_kbeta_roi_keV",
    }
    if not isinstance(response, Mapping) or set(response) != required_response:
        raise ValueError(f"response must contain exactly {sorted(required_response)}")
    for key in (
        "noise_fwhm_keV",
        "fractional_fwhm",
        "detection_threshold_keV",
    ):
        finite_number(response[key], f"response.{key}", nonnegative=True)
    roi_values: list[tuple[float, float]] = []
    for key in ("ag_kalpha_roi_keV", "ag_kbeta_roi_keV"):
        roi = response[key]
        if not isinstance(roi, list) or len(roi) != 2:
            raise ValueError(f"response.{key} must be [minimum, maximum]")
        lower = finite_number(roi[0], f"response.{key}[0]", positive=True)
        upper = finite_number(roi[1], f"response.{key}[1]", positive=True)
        if lower >= upper:
            raise ValueError(f"response.{key} minimum must be below maximum")
        roi_values.append((lower, upper))
    if roi_values[0][1] > roi_values[1][0]:
        raise ValueError("Ag K-alpha and K-beta ROIs cannot overlap")

    statistics = config.get("screening_statistics")
    required_statistics = {
        "prepared_events_min",
        "ag_kalpha_entries_per_seed_min",
        "ag_kbeta_entries_per_seed_min",
        "fluorescence_roi_events_per_seed_min",
    }
    if not isinstance(statistics, Mapping) or set(statistics) != required_statistics:
        raise ValueError(
            "screening_statistics must contain exactly "
            f"{sorted(required_statistics)}"
        )
    for key, value in statistics.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(
                f"screening_statistics.{key} must be a positive integer"
            )

    selection = config.get("selection")
    if not isinstance(selection, Mapping):
        raise ValueError("selection must be an object")
    maximize = selection.get("maximize")
    minimize = selection.get("minimize")
    weights = selection.get("objective_weights")
    if (
        not isinstance(maximize, list)
        or not maximize
        or not isinstance(minimize, list)
        or not minimize
        or not isinstance(weights, Mapping)
    ):
        raise ValueError("selection requires non-empty maximize/minimize lists and weights")
    objectives = [*maximize, *minimize]
    if len(set(objectives)) != len(objectives):
        raise ValueError("selection objectives must be unique")
    if set(weights) != set(objectives):
        raise ValueError("objective_weights keys must exactly match selection objectives")
    if set(objectives).difference(METRIC_KEYS):
        raise ValueError("selection contains an unknown detector-scan metric")
    numeric_weights = [
        finite_number(value, f"selection.objective_weights.{key}", nonnegative=True)
        for key, value in weights.items()
    ]
    if not math.isclose(sum(numeric_weights), 1.0, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError("selection objective weights must sum to one")
    finite_number(
        selection.get("robustness_cv_penalty"),
        "selection.robustness_cv_penalty",
        nonnegative=True,
    )
    independent_seeds_min = selection.get("independent_seeds_min")
    if (
        isinstance(independent_seeds_min, bool)
        or not isinstance(independent_seeds_min, int)
        or independent_seeds_min < 2
    ):
        raise ValueError(
            "selection.independent_seeds_min must be an integer of at least two"
        )

    runtime = config.get("runtime")
    if not isinstance(runtime, Mapping) or set(runtime) != {"timeout_s"}:
        raise ValueError("runtime must contain exactly timeout_s")
    finite_number(runtime["timeout_s"], "runtime.timeout_s", positive=True)
    plots = config.get("plots")
    if not isinstance(plots, Mapping) or set(plots) != {"marker_size", "dpi"}:
        raise ValueError("plots must contain exactly marker_size and dpi")
    finite_number(plots["marker_size"], "plots.marker_size", positive=True)
    finite_number(plots["dpi"], "plots.dpi", positive=True)


def parse_seed_list(value: str) -> list[int]:
    try:
        seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from error
    if not seeds or any(seed <= 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise argparse.ArgumentTypeError("seeds must be distinct positive integers")
    return seeds


def _metadata_boolean(metadata: Mapping[str, str], key: str) -> bool | None:
    value = metadata.get(key)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def prepared_input_evidence(path: Path) -> dict[str, Any]:
    """Classify whether a prepared CSV can support conditional screening."""
    metadata: dict[str, str] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.startswith("#"):
                break
            comment = line[1:].strip()
            if "=" in comment:
                key, value = comment.split("=", 1)
                metadata[key.strip()] = value.strip()
    if metadata.get("schema") != PREPARED_PHASE_SPACE_SCHEMA:
        raise ValueError(
            "prepared phase-space CSV must declare "
            f"schema={PREPARED_PHASE_SPACE_SCHEMA}"
        )

    mode = metadata.get("mode", "missing")
    requested_events: int | None = None
    encoded_requested_events = metadata.get("requested_events")
    if encoded_requested_events is not None:
        try:
            requested_events = int(encoded_requested_events)
        except ValueError:
            requested_events = None
        if requested_events is not None and requested_events < 1:
            requested_events = None
    approval = _metadata_boolean(
        metadata, "source_downstream_wp5_design_input_approved"
    )
    diagnostic_override = _metadata_boolean(
        metadata, "diagnostic_input_override"
    )
    contract_compliant: bool | None = None
    encoded_contract = metadata.get("source_contract_validation")
    if encoded_contract is not None:
        try:
            decoded_contract = json.loads(encoded_contract)
        except json.JSONDecodeError:
            decoded_contract = None
        if isinstance(decoded_contract, Mapping) and isinstance(
            decoded_contract.get("compliant"), bool
        ):
            contract_compliant = bool(decoded_contract["compliant"])

    reasons: list[str] = []
    if mode != "weighted_hdf5_resample":
        reasons.append(
            f"prepared input mode {mode!r} is not an approved weighted S4 resample"
        )
    else:
        if approval is not True:
            reasons.append(
                "source_downstream_wp5_design_input_approved is not explicitly true"
            )
        if diagnostic_override is not False:
            reasons.append(
                "diagnostic_input_override is not explicitly false"
            )
        if contract_compliant is not True:
            reasons.append(
                "source S4 contract validation is not explicitly compliant"
            )
    if requested_events is None:
        reasons.append("requested_events metadata is missing or invalid")
    return {
        "mode": mode,
        "requested_events": requested_events,
        "source_downstream_wp5_design_input_approved": approval,
        "diagnostic_input_override": diagnostic_override,
        "source_contract_compliant": contract_compliant,
        "screening_input_eligible": not reasons,
        "reasons": reasons,
    }


def case_identifier(indices: Sequence[int]) -> str:
    return (
        f"a{indices[0]:02d}_d{indices[1]:02d}_w{indices[2]:02d}_"
        f"h{indices[3]:02d}_t{indices[4]:02d}"
    )


def enumerate_cases(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    grid = config["geometry_grid"]
    indexed = [list(enumerate(grid[key])) for key in GEOMETRY_KEYS]
    cases: list[dict[str, Any]] = []
    for combination in product(*indexed):
        indices = [item[0] for item in combination]
        values = [float(item[1]) for item in combination]
        case = {"case_id": case_identifier(indices)}
        case.update(dict(zip(GEOMETRY_KEYS, values)))
        case["detector_active_volume_cm3"] = (
            case["width_mm"] * case["height_mm"] * case["thickness_mm"] / 1000.0
        )
        case["geometric_solid_angle_sr"] = rectangular_solid_angle_sr(
            case["width_mm"], case["height_mm"], case["distance_mm"]
        )
        case["solid_angle_fraction_4pi"] = (
            case["geometric_solid_angle_sr"] / (4.0 * math.pi)
        )
        cases.append(case)
    return cases


def rectangular_solid_angle_sr(
    width_mm: float, height_mm: float, distance_mm: float
) -> float:
    if min(width_mm, height_mm, distance_mm) <= 0.0:
        raise ValueError("detector width, height, and distance must be positive")
    half_width = 0.5 * width_mm
    half_height = 0.5 * height_mm
    denominator = distance_mm * math.sqrt(
        distance_mm**2 + half_width**2 + half_height**2
    )
    return 4.0 * math.atan2(half_width * half_height, denominator)


def read_raw_event_csv(path: Path) -> tuple[dict[str, str], dict[str, np.ndarray]]:
    metadata: dict[str, str] = {}
    table_lines: list[str] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#"):
                comment = line[1:].strip()
                if "=" in comment:
                    key, value = comment.split("=", 1)
                    metadata[key.strip()] = value.strip()
            elif line.strip():
                table_lines.append(line)
    if not table_lines:
        raise ValueError(f"raw event CSV has no table: {path}")
    if metadata.get("schema") != RAW_EVENT_SCHEMA:
        raise ValueError(
            f"raw event CSV must declare schema={RAW_EVENT_SCHEMA}"
        )
    reader = csv.DictReader(table_lines)
    if reader.fieldnames is None:
        raise ValueError("raw event CSV has no header")
    required = {
        "normalization_weight",
        "edep_total_keV",
        "smeared_edep_keV",
        "secondary_gamma_created",
        "ag_ka_created",
        "ag_kb_created",
        "secondary_gamma_entered_czt",
        "ag_ka_entered_czt",
        "ag_kb_entered_czt",
    }
    missing = sorted(required.difference(reader.fieldnames))
    if missing:
        raise ValueError(f"raw event CSV is missing columns: {', '.join(missing)}")
    rows = list(reader)
    if not rows:
        raise ValueError("raw event CSV contains no event rows")
    arrays: dict[str, np.ndarray] = {}
    for field in required:
        try:
            arrays[field] = np.asarray(
                [float(row[field]) for row in rows], dtype=float
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"raw event column {field!r} is not numeric") from error
        if not np.all(np.isfinite(arrays[field])):
            raise ValueError(f"raw event column {field!r} contains non-finite data")
    if np.any(arrays["normalization_weight"] <= 0.0):
        raise ValueError("normalization_weight must be positive")
    for field in required.difference({"normalization_weight"}):
        if np.any(arrays[field] < 0.0):
            raise ValueError(f"raw event column {field!r} cannot be negative")
    return metadata, arrays


def weighted_sum(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights, dtype=np.float64))


def event_metrics(
    arrays: Mapping[str, np.ndarray],
    case: Mapping[str, Any],
    response: Mapping[str, Any],
) -> dict[str, float | int | None]:
    weights = arrays["normalization_weight"]
    raw = arrays["edep_total_keV"]
    smeared = arrays["smeared_edep_keV"]
    incident_weight = float(np.sum(weights, dtype=np.float64))
    if not math.isfinite(incident_weight) or incident_weight <= 0.0:
        raise ValueError("raw event table has non-positive represented input weight")

    threshold = float(response["detection_threshold_keV"])
    ka_min, ka_max = (float(value) for value in response["ag_kalpha_roi_keV"])
    kb_min, kb_max = (float(value) for value in response["ag_kbeta_roi_keV"])
    raw_detected = raw >= threshold
    detected = smeared >= threshold
    ka_roi = (smeared >= ka_min) & (smeared < ka_max)
    kb_roi = (smeared >= kb_min) & (smeared < kb_max)
    fluorescence_roi = ka_roi | kb_roi
    background = detected & ~fluorescence_roi

    created_ka_weight = weighted_sum(arrays["ag_ka_created"], weights)
    created_kb_weight = weighted_sum(arrays["ag_kb_created"], weights)
    entered_ka_weight = weighted_sum(arrays["ag_ka_entered_czt"], weights)
    entered_kb_weight = weighted_sum(arrays["ag_kb_entered_czt"], weights)
    entered_secondary_weight = weighted_sum(
        arrays["secondary_gamma_entered_czt"], weights
    )

    def weighted_fraction(mask: np.ndarray) -> float:
        return float(np.sum(weights[mask], dtype=np.float64) / incident_weight)

    return {
        "events": int(raw.size),
        "incident_weight": incident_weight,
        "weighted_total_deposited_keV": weighted_sum(raw, weights),
        "weighted_mean_deposited_keV_per_incident": weighted_sum(raw, weights)
        / incident_weight,
        "raw_detection_weight_fraction_proxy": weighted_fraction(raw_detected),
        "detection_weight_fraction_proxy": weighted_fraction(detected),
        "ag_kalpha_entry_weight": entered_ka_weight,
        "ag_kbeta_entry_weight": entered_kb_weight,
        "ag_kalpha_entries_count": int(
            np.rint(np.sum(arrays["ag_ka_entered_czt"], dtype=np.float64))
        ),
        "ag_kbeta_entries_count": int(
            np.rint(np.sum(arrays["ag_kb_entered_czt"], dtype=np.float64))
        ),
        "fluorescence_roi_events_count": int(
            np.count_nonzero(fluorescence_roi)
        ),
        "ag_kalpha_entry_weight_per_incident": entered_ka_weight / incident_weight,
        "ag_kbeta_entry_weight_per_incident": entered_kb_weight / incident_weight,
        "ag_kalpha_roi_weight_fraction_proxy": weighted_fraction(ka_roi),
        "ag_kbeta_roi_weight_fraction_proxy": weighted_fraction(kb_roi),
        "fluorescence_roi_weight_fraction_proxy": weighted_fraction(
            fluorescence_roi
        ),
        "background_weight_fraction_of_incident_proxy": weighted_fraction(
            background
        ),
        "secondary_gamma_entry_weight_per_incident": entered_secondary_weight
        / incident_weight,
        "ag_kalpha_entry_efficiency_given_created_proxy": (
            entered_ka_weight / created_ka_weight
            if created_ka_weight > 0.0
            else None
        ),
        "ag_kbeta_entry_efficiency_given_created_proxy": (
            entered_kb_weight / created_kb_weight
            if created_kb_weight > 0.0
            else None
        ),
        "geometric_solid_angle_sr": float(case["geometric_solid_angle_sr"]),
        "solid_angle_fraction_4pi": float(case["solid_angle_fraction_4pi"]),
        "detector_active_volume_cm3": float(case["detector_active_volume_cm3"]),
    }


def build_geant4_command(
    binary: str,
    input_csv: Path,
    output_csv: Path,
    case: Mapping[str, Any],
    seed: int,
    events: int,
    config: Mapping[str, Any],
) -> list[str]:
    fixed = config["fixed_geometry"]
    response = config["response"]
    return [
        binary,
        "--input",
        str(input_csv),
        "--output",
        str(output_csv),
        "--events",
        str(events),
        "--seed",
        str(seed),
        "--sample-width-mm",
        str(fixed["sample_width_mm"]),
        "--sample-height-mm",
        str(fixed["sample_height_mm"]),
        "--sample-thickness-mm",
        str(fixed["sample_thickness_mm"]),
        "--detector-distance-mm",
        str(case["distance_mm"]),
        "--detector-angle-deg",
        str(case["angle_deg"]),
        "--detector-width-mm",
        str(case["width_mm"]),
        "--detector-height-mm",
        str(case["height_mm"]),
        "--detector-thickness-mm",
        str(case["thickness_mm"]),
        "--czt-density-g-cm3",
        str(fixed["czt_density_g_cm3"]),
        "--world-half-size-mm",
        str(fixed["world_half_size_mm"]),
        "--production-cut-um",
        str(fixed["production_cut_um"]),
        "--resolution-noise-fwhm-keV",
        str(response["noise_fwhm_keV"]),
        "--resolution-fraction-fwhm",
        str(response["fractional_fwhm"]),
    ]


def run_case_seed(
    binary: str,
    input_csv: Path,
    raw_path: Path,
    case: Mapping[str, Any],
    seed: int,
    events: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    command = build_geant4_command(
        binary, input_csv, raw_path, case, seed, events, config
    )
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=float(config["runtime"]["timeout_s"]),
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(
            f"Geant4 exited {completed.returncode}: {detail[-2000:]}"
        )
    _, arrays = read_raw_event_csv(raw_path)
    metrics = event_metrics(arrays, case, config["response"])
    statistics = config["screening_statistics"]
    statistics_failures: list[str] = []
    for metric, threshold_key in (
        ("ag_kalpha_entries_count", "ag_kalpha_entries_per_seed_min"),
        ("ag_kbeta_entries_count", "ag_kbeta_entries_per_seed_min"),
        (
            "fluorescence_roi_events_count",
            "fluorescence_roi_events_per_seed_min",
        ),
    ):
        if int(metrics[metric]) < int(statistics[threshold_key]):
            statistics_failures.append(
                f"{metric}={metrics[metric]} < {statistics[threshold_key]}"
            )
    metrics["statistics_gate_satisfied"] = not statistics_failures
    metrics["statistics_gate_failures"] = "; ".join(statistics_failures)
    metrics["wall_time_s"] = elapsed
    return {
        "case_id": case["case_id"],
        "seed": seed,
        **{key: case[key] for key in GEOMETRY_KEYS},
        "status": "ok",
        "error": "",
        **metrics,
    }


def aggregate_runs(
    runs: Sequence[Mapping[str, Any]],
    cases_by_id: Mapping[str, Mapping[str, Any]],
    required_seed_count: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        if run.get("status") == "ok":
            grouped[str(run["case_id"])].append(run)
    aggregates: list[dict[str, Any]] = []
    for case_id, records in grouped.items():
        case = cases_by_id[case_id]
        aggregate: dict[str, Any] = {
            "case_id": case_id,
            **{key: case[key] for key in GEOMETRY_KEYS},
            "successful_seeds": len(records),
            "completed_all_configured_seeds": (
                len(records) == required_seed_count
            ),
            "statistics_gate_satisfied_all_seeds": (
                len(records) == required_seed_count
                and all(
                    bool(record.get("statistics_gate_satisfied"))
                    for record in records
                )
            ),
        }
        aggregate["eligible_for_diagnostic_selection"] = bool(
            aggregate["completed_all_configured_seeds"]
        )
        aggregate["eligible_for_selection"] = bool(
            aggregate["statistics_gate_satisfied_all_seeds"]
        )
        for metric in METRIC_KEYS:
            values = [
                float(record[metric])
                for record in records
                if record.get(metric) is not None
                and math.isfinite(float(record[metric]))
            ]
            aggregate[f"{metric}_mean"] = (
                float(np.mean(values)) if values else None
            )
            aggregate[f"{metric}_std"] = (
                float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            ) if values else None
        aggregates.append(aggregate)
    return aggregates


def dominates(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    maximize: Sequence[str],
    minimize: Sequence[str],
) -> bool:
    weakly_better = True
    strictly_better = False
    for metric in maximize:
        a = float(first[f"{metric}_mean"])
        b = float(second[f"{metric}_mean"])
        weakly_better &= a >= b
        strictly_better |= a > b
    for metric in minimize:
        a = float(first[f"{metric}_mean"])
        b = float(second[f"{metric}_mean"])
        weakly_better &= a <= b
        strictly_better |= a < b
    return weakly_better and strictly_better


def pareto_case_ids(
    aggregates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
) -> list[str]:
    maximize = selection["maximize"]
    minimize = selection["minimize"]
    return [
        str(candidate["case_id"])
        for candidate in aggregates
        if not any(
            dominates(other, candidate, maximize, minimize)
            for other in aggregates
            if other["case_id"] != candidate["case_id"]
        )
    ]


def normalized_benefit(values: np.ndarray, maximize: bool) -> np.ndarray:
    if not np.all(np.isfinite(values)):
        raise ValueError("selection objective contains non-finite aggregates")
    low = float(np.min(values))
    high = float(np.max(values))
    if math.isclose(low, high, rel_tol=0.0, abs_tol=1.0e-30):
        return np.full(values.shape, 0.5)
    normalized = (values - low) / (high - low)
    return normalized if maximize else 1.0 - normalized


def select_candidate(
    aggregates: list[dict[str, Any]],
    selection: Mapping[str, Any],
    *,
    eligibility_key: str = "eligible_for_selection",
) -> dict[str, Any]:
    eligible = [row for row in aggregates if row[eligibility_key]]
    if not eligible:
        raise RuntimeError("no detector case completed every configured seed")
    directions = {
        metric: True for metric in selection["maximize"]
    } | {metric: False for metric in selection["minimize"]}
    benefits: dict[str, np.ndarray] = {}
    for metric, maximize in directions.items():
        values = np.asarray(
            [row[f"{metric}_mean"] for row in eligible], dtype=float
        )
        benefits[metric] = normalized_benefit(values, maximize)

    weights = selection["objective_weights"]
    penalty_factor = float(selection["robustness_cv_penalty"])
    pareto_ids = set(pareto_case_ids(eligible, selection))
    for index, aggregate in enumerate(eligible):
        utility = sum(
            float(weights[metric]) * float(benefits[metric][index])
            for metric in directions
        )
        cvs: list[float] = []
        for metric in directions:
            mean = abs(float(aggregate[f"{metric}_mean"]))
            standard = aggregate[f"{metric}_std"]
            if mean > 0.0 and standard is not None:
                cvs.append(float(standard) / mean)
        penalty = penalty_factor * (sum(cvs) / len(cvs) if cvs else 0.0)
        aggregate["objective_utility"] = utility
        aggregate["robustness_penalty"] = penalty
        aggregate["selection_score"] = utility - penalty
        aggregate["pareto_optimal"] = aggregate["case_id"] in pareto_ids

    selected = max(
        eligible,
        key=lambda row: (float(row["selection_score"]), str(row["case_id"])),
    )
    return {
        "status": SELECTION_STATUS,
        "selected_case_id": selected["case_id"],
        "basis": (
            "highest configured normalized utility after multi-seed CV penalty; "
            "conditional on the supplied phase space and simplified CZT model"
        ),
        "pareto_case_ids": sorted(pareto_ids),
        "selected_metrics": selected,
        "evidence_boundary": (
            "This is a conditional simulation diagnostic. It is not an approved "
            "hardware recommendation, detector acceptance test, or procurement decision."
        ),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def write_strict_json(path: Path, document: Mapping[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(
            json_ready(document),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def write_rows_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty detector-scan CSV")
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


def make_plots(
    output_dir: Path,
    aggregates: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    plot_config: Mapping[str, Any],
) -> tuple[Path, Path]:
    eligibility_key = (
        "eligible_for_diagnostic_selection"
        if selection.get("selection_pool") == "completed_cases"
        else "eligible_for_selection"
    )
    eligible = [row for row in aggregates if row[eligibility_key]]
    selected_id = str(selection["selected_case_id"])
    software_smoke = selection.get("status") == SOFTWARE_SMOKE_STATUS
    selected = np.asarray(
        [str(row["case_id"]) == selected_id for row in eligible], dtype=bool
    )
    angle = np.asarray([row["angle_deg"] for row in eligible], dtype=float)
    distance = np.asarray([row["distance_mm"] for row in eligible], dtype=float)
    solid = np.asarray(
        [row["solid_angle_fraction_4pi_mean"] for row in eligible], dtype=float
    )
    ka_entry = np.asarray(
        [row["ag_kalpha_entry_weight_per_incident_mean"] for row in eligible],
        dtype=float,
    )
    roi = np.asarray(
        [row["fluorescence_roi_weight_fraction_proxy_mean"] for row in eligible],
        dtype=float,
    )
    background = np.asarray(
        [
            row["background_weight_fraction_of_incident_proxy_mean"]
            for row in eligible
        ],
        dtype=float,
    )
    active_volume = np.asarray(
        [row["detector_active_volume_cm3_mean"] for row in eligible], dtype=float
    )

    fig, axes = plt.subplots(2, 2, figsize=(12.2, 9.2))
    ax_angle, ax_solid, ax_pareto, ax_geometry = axes.flat
    marker_size = float(plot_config["marker_size"])

    scatter = ax_angle.scatter(
        angle,
        ka_entry,
        c=distance,
        s=marker_size,
        cmap="viridis",
        alpha=0.85,
    )
    fig.colorbar(scatter, ax=ax_angle, label="Detector distance [mm]")
    ax_angle.set(
        xlabel="Detector angle [deg]",
        ylabel="Weighted Ag K-alpha entries / incident weight",
        title="Angle and distance response",
    )

    ax_solid.scatter(
        solid,
        roi,
        c=active_volume,
        s=marker_size,
        cmap="plasma",
        alpha=0.85,
    )
    ax_solid.set(
        xlabel="Geometric solid-angle fraction of 4π",
        ylabel="Fluorescence-ROI weight fraction proxy",
        title="Geometric coverage and deposited-energy ROI",
    )

    ax_pareto.scatter(
        background,
        roi,
        c=solid,
        s=marker_size,
        cmap="cividis",
        alpha=0.85,
    )
    ax_pareto.set(
        xlabel="Background weight fraction proxy",
        ylabel="Fluorescence-ROI weight fraction proxy",
        title="Conditional signal–background trade-off",
    )

    width = np.asarray([row["width_mm"] for row in eligible], dtype=float)
    height = np.asarray([row["height_mm"] for row in eligible], dtype=float)
    score = np.asarray([row["selection_score"] for row in eligible], dtype=float)
    geometry_scatter = ax_geometry.scatter(
        width * height,
        distance,
        c=score,
        s=marker_size,
        cmap="coolwarm",
        alpha=0.85,
    )
    fig.colorbar(geometry_scatter, ax=ax_geometry, label="Selection score")
    ax_geometry.set(
        xlabel="CZT face area [mm²]",
        ylabel="Detector distance [mm]",
        title="Geometry and conditional utility",
    )

    for axis, xvalues, yvalues in (
        (ax_angle, angle, ka_entry),
        (ax_solid, solid, roi),
        (ax_pareto, background, roi),
        (ax_geometry, width * height, distance),
    ):
        axis.scatter(
            xvalues[selected],
            yvalues[selected],
            marker="*",
            s=260,
            facecolor="none",
            edgecolor="black",
            linewidth=1.5,
            label=(
                "selected software-smoke/partial-scan case"
                if software_smoke
                else "selected conditional diagnostic"
            ),
        )
        axis.grid(linestyle=":", alpha=0.45)
        axis.legend(fontsize=7)

    fig.suptitle(
        "WP5 detector software smoke / partial scan"
        if software_smoke
        else (
            "WP5 detector scan — conditional simulation diagnostic, "
            "not approved hardware"
        )
    )
    fig.tight_layout()
    png_path = output_dir / "wp5_detector_scan.png"
    pdf_path = output_dir / "wp5_detector_scan.pdf"
    fig.savefig(png_path, dpi=int(plot_config["dpi"]))
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


def resolve_binary(binary: str) -> str:
    candidate = Path(binary)
    if candidate.parent != Path(".") or candidate.is_absolute():
        if not candidate.is_file():
            raise ValueError(f"Geant4 binary not found: {candidate}")
        return str(candidate.resolve())
    resolved = shutil.which(binary)
    if resolved is None:
        raise ValueError(
            f"Geant4 binary {binary!r} was not found on PATH; pass --binary"
        )
    return resolved


def run_scan(args: argparse.Namespace) -> dict[str, Any]:
    config = load_json(args.scan_config)
    validate_scan_config(config)
    config["events"] = int(args.events)
    config["seeds"] = list(args.seeds)
    validate_scan_config(config)
    if not args.input.is_file():
        raise ValueError(f"prepared phase-space CSV not found: {args.input}")
    input_evidence = prepared_input_evidence(args.input)
    binary = resolve_binary(args.binary)

    cases = enumerate_cases(config)
    cases_generated = len(cases)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("--max-cases leaves no detector geometry")
    case_limit_applied = len(cases) < cases_generated
    independent_seed_gate_satisfied = (
        len(config["seeds"])
        >= int(config["selection"]["independent_seeds_min"])
    )
    event_limit_applied = int(config["events"]) > 0
    prepared_events_gate_satisfied = (
        input_evidence["requested_events"] is not None
        and int(input_evidence["requested_events"])
        >= int(config["screening_statistics"]["prepared_events_min"])
    )
    software_smoke_reasons: list[str] = []
    if case_limit_applied:
        software_smoke_reasons.append("configured geometry grid was truncated")
    if not independent_seed_gate_satisfied:
        software_smoke_reasons.append(
            "configured minimum independent-seed count was not met"
        )
    if event_limit_applied:
        software_smoke_reasons.append(
            "an explicit event limit reduced Monte Carlo statistics"
        )
    if not prepared_events_gate_satisfied:
        software_smoke_reasons.append(
            "prepared event count does not meet "
            f"screening_statistics.prepared_events_min="
            f"{config['screening_statistics']['prepared_events_min']}"
        )
    if not bool(input_evidence["screening_input_eligible"]):
        software_smoke_reasons.extend(
            f"input phase space: {reason}"
            for reason in input_evidence["reasons"]
        )
    software_smoke_or_partial_scan = bool(software_smoke_reasons)
    cases_by_id = {str(case["case_id"]): case for case in cases}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for case in cases:
        for seed in config["seeds"]:
            raw_path = raw_dir / f"{case['case_id']}_seed{seed}.csv"
            try:
                run = run_case_seed(
                    binary,
                    args.input,
                    raw_path,
                    case,
                    int(seed),
                    int(config["events"]),
                    config,
                )
                runs.append(run)
                if not args.keep_raw:
                    raw_path.unlink()
            except (
                OSError,
                ValueError,
                RuntimeError,
                subprocess.TimeoutExpired,
            ) as error:
                runs.append(
                    {
                        "case_id": case["case_id"],
                        "seed": seed,
                        **{key: case[key] for key in GEOMETRY_KEYS},
                        "status": "failed",
                        "error": str(error),
                    }
                )

    run_csv = args.output_dir / "wp5_detector_scan_runs.csv"
    aggregate_csv = args.output_dir / "wp5_detector_scan_aggregates.csv"
    summary_json = args.output_dir / "wp5_detector_scan_summary.json"
    write_rows_csv(run_csv, runs)
    aggregates = aggregate_runs(
        runs, cases_by_id, required_seed_count=len(config["seeds"])
    )
    completed = [
        row
        for row in aggregates
        if row["eligible_for_diagnostic_selection"]
    ]
    statistics_eligible = [
        row for row in aggregates if row["eligible_for_selection"]
    ]
    if not completed:
        raise RuntimeError("no detector geometry completed every configured seed")
    if statistics_eligible:
        selection = select_candidate(aggregates, config["selection"])
        selection["selection_pool"] = "statistics_eligible_cases"
    else:
        selection = select_candidate(
            aggregates,
            config["selection"],
            eligibility_key="eligible_for_diagnostic_selection",
        )
        selection["screening_status_without_statistics_gate"] = (
            selection["status"]
        )
        selection["selection_pool"] = "completed_cases"
        selection["status"] = INSUFFICIENT_STATISTICS_STATUS
        selection["basis"] = (
            "No detector geometry met the configured per-seed fluorescence "
            "count gates; the selected case is an insufficient-statistics "
            "diagnostic only."
        )
        selection["evidence_boundary"] = (
            "The configured Monte Carlo statistics are insufficient for "
            "conditional detector-screening claims. This is not an approved "
            "hardware recommendation, acceptance test, or procurement decision."
        )
    selection["full_configured_case_grid_executed"] = not case_limit_applied
    selection["independent_seed_gate_satisfied"] = (
        independent_seed_gate_satisfied
    )
    selection["all_prepared_events_requested"] = not event_limit_applied
    selection["prepared_events_gate_satisfied"] = (
        prepared_events_gate_satisfied
    )
    selection["screening_input_evidence_gate_satisfied"] = bool(
        input_evidence["screening_input_eligible"]
    )
    selection["software_smoke_reasons"] = software_smoke_reasons
    if software_smoke_or_partial_scan:
        selection["screening_status_without_completeness_gate"] = (
            selection["status"]
        )
        selection["status"] = SOFTWARE_SMOKE_STATUS
        selection["basis"] = (
            "Software smoke/partial detector scan because: "
            + "; ".join(software_smoke_reasons)
        )
        selection["evidence_boundary"] = (
            "This run validates software execution only. It is not a complete "
            "conditional detector screening, approved hardware recommendation, "
            "acceptance test, or procurement decision."
        )
    write_rows_csv(aggregate_csv, aggregates)

    plots: list[str] = []
    if not args.no_plots:
        png_path, pdf_path = make_plots(
            args.output_dir, aggregates, selection, config["plots"]
        )
        plots = [str(png_path), str(pdf_path)]

    summary: dict[str, Any] = {
        "schema": "PRISM_WP5_DETECTOR_SCAN_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": selection["status"],
        "input_phase_space_csv": str(args.input.resolve()),
        "input_evidence": input_evidence,
        "geant4_binary": binary,
        "scan_config": config,
        "cases_requested": len(cases),
        "cases_generated": cases_generated,
        "cases_executed": len(cases),
        "case_limit_applied": case_limit_applied,
        "max_cases_cli": int(args.max_cases),
        "event_limit_applied": event_limit_applied,
        "prepared_events_gate_satisfied": prepared_events_gate_satisfied,
        "independent_seed_gate_satisfied": independent_seed_gate_satisfied,
        "software_smoke_or_partial_scan": software_smoke_or_partial_scan,
        "software_smoke_reasons": software_smoke_reasons,
        "seeds": config["seeds"],
        "successful_runs": sum(run["status"] == "ok" for run in runs),
        "failed_runs": sum(run["status"] != "ok" for run in runs),
        "completed_cases": len(completed),
        "statistics_eligible_cases": len(statistics_eligible),
        "eligible_cases": len(statistics_eligible),
        "aggregates": aggregates,
        "selection": selection,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "matplotlib": getattr(plt.matplotlib, "__version__", "unknown"),
        },
        "interpretation": [
            "All efficiencies and rates are conditional proxies per represented input phase-space weight.",
            "Ag K-alpha/K-beta entry metrics count Geant4 secondary photons entering the CZT.",
            "Deposited-energy ROI and background metrics use the phenomenologically smeared CZT energy.",
            "The rectangular solid angle is an independent centred point-source estimate.",
            "The selection is not an approved detector design, acceptance test, or procurement recommendation.",
        ],
        "outputs": {
            "run_csv": str(run_csv),
            "aggregate_csv": str(aggregate_csv),
            "summary_json": str(summary_json),
            "plots": plots,
            "raw_directory": str(raw_dir) if args.keep_raw else None,
        },
    }
    write_strict_json(summary_json, summary)
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    bundled = load_json(DEFAULT_CONFIG)
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--binary",
        default=DEFAULT_BINARY,
        help="compiled prism_wp5 Geant4 executable",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="prepared unit-event phase-space CSV",
    )
    parser.add_argument(
        "--scan-config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="detector geometry grid and selection JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory receiving scan tables, summary, and plots",
    )
    parser.add_argument(
        "--events",
        type=int,
        default=int(bundled["events"]),
        help="events passed to each Geant4 run; zero uses all prepared rows",
    )
    parser.add_argument(
        "--seeds",
        type=parse_seed_list,
        default=list(bundled["seeds"]),
        metavar="SEED[,SEED...]",
        help="independent Geant4 seeds",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="limit geometries in configured order; zero means the full grid",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="retain each per-case Geant4 raw event CSV",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="skip PNG/PDF diagnostics for automated smoke tests",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.events < 0:
        parser.error("--events cannot be negative")
    if args.max_cases < 0:
        parser.error("--max-cases cannot be negative")
    try:
        summary = run_scan(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    selection = summary["selection"]
    print(
        f"Selected {selection['selected_case_id']} "
        f"({selection['status']})."
    )
    print(
        f"Completed {summary['successful_runs']} successful runs; "
        f"{summary['failed_runs']} failed."
    )
    print(f"Summary: {summary['outputs']['summary_json']}")


if __name__ == "__main__":
    main()
