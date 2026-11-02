#!/usr/bin/env python3
"""Prepare a unit-event CSV for the PRISM WP5 Geant4 fluorescence model."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = SIMULATION_ROOT / "results" / "wp4" / "wp4_phase_space.h5"
DEFAULT_OUTPUT = SIMULATION_ROOT / "results" / "wp5" / "wp5_phase_space.csv"
SCHEMA = "PRISM_WP5_PHASE_SPACE_V1"
S4_PHASE_SPACE_SCHEMA = "PRISM_SHADOW4_PHASE_SPACE_V1"
S4_WEIGHT_UNIT = "photons/mAs"
CSV_FIELDS = [
    "event_id",
    "x_mm",
    "y_mm",
    "z_mm",
    "dx",
    "dy",
    "dz",
    "energy_keV",
    "unit_weight",
    "source_row",
    "source_weight",
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _compact_metadata_value(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    return text


def _required_arrays(group: h5py.Group) -> dict[str, np.ndarray]:
    required = (
        "x_m",
        "y_m",
        "z_m",
        "dx",
        "dy",
        "dz",
        "energy_keV",
        "weight",
        "status",
    )
    missing = [name for name in required if name not in group]
    if missing:
        raise ValueError(
            f"HDF5 group {group.name!r} is missing datasets: {', '.join(missing)}"
        )
    arrays = {name: np.asarray(group[name][...]) for name in required}
    lengths = {array.shape[0] for array in arrays.values() if array.ndim == 1}
    if any(array.ndim != 1 for array in arrays.values()) or len(lengths) != 1:
        raise ValueError("all required phase-space datasets must be 1D and equal-length")
    return arrays


def _valid_mask(arrays: dict[str, np.ndarray]) -> np.ndarray:
    mask = np.asarray(arrays["status"] > 0, dtype=bool)
    for name in (
        "x_m",
        "y_m",
        "z_m",
        "dx",
        "dy",
        "dz",
        "energy_keV",
        "weight",
    ):
        mask &= np.isfinite(arrays[name])
    mask &= arrays["energy_keV"] > 0.0
    mask &= arrays["weight"] > 0.0
    direction_norm = np.sqrt(
        arrays["dx"] ** 2 + arrays["dy"] ** 2 + arrays["dz"] ** 2
    )
    mask &= np.isfinite(direction_norm) & (direction_norm > 0.0)
    return mask


def _validate_s4_input_contract(
    root_attributes: dict[str, Any],
    group: h5py.Group,
) -> tuple[list[str], bool | None, str | None]:
    """Validate the exact S4 contract required for a WP5 design input."""
    reasons: list[str] = []
    if group.name != "/sample":
        reasons.append(
            f"selected group is {group.name!r}, expected the S4 group '/sample'"
        )

    root_schema = root_attributes.get("schema")
    if root_schema != S4_PHASE_SPACE_SCHEMA:
        reasons.append(
            "root attribute 'schema' is "
            f"{root_schema!r}, expected {S4_PHASE_SPACE_SCHEMA!r}"
        )

    root_weight_unit = root_attributes.get("weight_unit")
    if root_weight_unit != S4_WEIGHT_UNIT:
        reasons.append(
            "root attribute 'weight_unit' is "
            f"{root_weight_unit!r}, expected {S4_WEIGHT_UNIT!r}"
        )

    weight_unit = _jsonable(group["weight"].attrs.get("units"))
    if weight_unit != S4_WEIGHT_UNIT:
        reasons.append(
            f"dataset {group.name}/weight attribute 'units' is "
            f"{weight_unit!r}, expected {S4_WEIGHT_UNIT!r}"
        )

    approval: bool | None = None
    approval_source: str | None = None
    if "downstream_wp5_design_input_approved" in root_attributes:
        approval_source = "root_attribute"
        candidate = root_attributes["downstream_wp5_design_input_approved"]
        if isinstance(candidate, bool):
            approval = candidate
        else:
            reasons.append(
                "root attribute 'downstream_wp5_design_input_approved' must "
                f"be a JSON-compatible boolean, got {candidate!r}"
            )
    else:
        encoded_metadata = root_attributes.get("metadata_json")
        if isinstance(encoded_metadata, str):
            try:
                decoded_metadata = json.loads(encoded_metadata)
            except json.JSONDecodeError as error:
                reasons.append(
                    "root approval attribute is absent and 'metadata_json' "
                    f"cannot be decoded: {error.msg}"
                )
            else:
                if isinstance(decoded_metadata, dict) and (
                    "downstream_wp5_design_input_approved" in decoded_metadata
                ):
                    approval_source = "metadata_json"
                    candidate = decoded_metadata[
                        "downstream_wp5_design_input_approved"
                    ]
                    if isinstance(candidate, bool):
                        approval = candidate
                    else:
                        reasons.append(
                            "metadata_json field "
                            "'downstream_wp5_design_input_approved' must be "
                            f"a boolean, got {candidate!r}"
                        )
                else:
                    reasons.append(
                        "root approval attribute is absent and metadata_json "
                        "does not contain an explicit "
                        "'downstream_wp5_design_input_approved' boolean"
                    )
        else:
            reasons.append(
                "root attribute 'downstream_wp5_design_input_approved' is "
                "absent and no metadata_json fallback supplies it"
            )

    if approval is False:
        reasons.append(
            "downstream_wp5_design_input_approved is explicitly false"
        )
    elif approval is None and not any(
        "downstream_wp5_design_input_approved" in reason
        or "root approval attribute" in reason
        for reason in reasons
    ):
        reasons.append(
            "downstream_wp5_design_input_approved is not explicitly true"
        )
    return reasons, approval, approval_source


def prepare_from_hdf5(
    path: Path,
    group_name: str,
    events: int,
    seed: int,
    *,
    allow_diagnostic_input: bool = False,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Load and weighted-resample a WP1/WP4 sample phase space."""
    with h5py.File(path, "r") as handle:
        if group_name not in handle:
            raise ValueError(
                f"HDF5 file has no group {group_name!r}; available: "
                f"{', '.join(handle.keys())}"
            )
        group = handle[group_name]
        if not isinstance(group, h5py.Group):
            raise ValueError(f"HDF5 object {group_name!r} is not a group")
        arrays = _required_arrays(group)
        root_attributes = {
            str(key): _jsonable(value) for key, value in handle.attrs.items()
        }
        group_attributes = {
            str(key): _jsonable(value) for key, value in group.attrs.items()
        }
        contract_reasons, downstream_approved, approval_source = (
            _validate_s4_input_contract(root_attributes, group)
        )
        if contract_reasons and not allow_diagnostic_input:
            raise ValueError(
                "input is not an approved S4/WP5 design input (infeasible "
                "diagnostic or contract mismatch): "
                + "; ".join(contract_reasons)
                + "; pass --allow-diagnostic-input only for explicit "
                "pipeline diagnostics"
            )

    mask = _valid_mask(arrays)
    valid_indices = np.flatnonzero(mask)
    if valid_indices.size == 0:
        raise ValueError("no finite status>0 rows with positive energy and weight")
    valid_weights = np.asarray(arrays["weight"][valid_indices], dtype=float)
    total_weight = float(valid_weights.sum(dtype=np.float64))
    probabilities = valid_weights / total_weight
    generator = np.random.default_rng(seed)
    selected = generator.choice(
        valid_indices, size=events, replace=True, p=probabilities
    )

    dx = np.asarray(arrays["dx"][selected], dtype=float)
    dy = np.asarray(arrays["dy"][selected], dtype=float)
    dz = np.asarray(arrays["dz"][selected], dtype=float)
    norm = np.sqrt(dx**2 + dy**2 + dz**2)
    prepared = {
        "event_id": np.arange(events, dtype=np.int64),
        "x_mm": 1.0e3 * np.asarray(arrays["x_m"][selected], dtype=float),
        "y_mm": 1.0e3 * np.asarray(arrays["y_m"][selected], dtype=float),
        "z_mm": 1.0e3 * np.asarray(arrays["z_m"][selected], dtype=float),
        "dx": dx / norm,
        "dy": dy / norm,
        "dz": dz / norm,
        "energy_keV": np.asarray(arrays["energy_keV"][selected], dtype=float),
        "unit_weight": np.ones(events, dtype=float),
        "source_row": selected.astype(np.int64),
        "source_weight": np.asarray(arrays["weight"][selected], dtype=float),
    }
    metadata: dict[str, Any] = {
        "schema": SCHEMA,
        "mode": "weighted_hdf5_resample",
        "source_path": str(path.resolve()),
        "source_group": group_name,
        "resample_seed": seed,
        "requested_events": events,
        "input_rows": int(arrays["weight"].size),
        "valid_rows": int(valid_indices.size),
        "input_valid_weight_sum": total_weight,
        "normalization_weight_per_event": total_weight / events,
        "normalization_unit": (
            "input phase-space weight per simulated Geant4 event"
        ),
        "source_root_attributes": root_attributes,
        "source_group_attributes": group_attributes,
        "source_downstream_wp5_design_input_approved": downstream_approved,
        "source_contract_expected": {
            "root_schema": S4_PHASE_SPACE_SCHEMA,
            "root_weight_unit": S4_WEIGHT_UNIT,
            "sample_weight_unit": S4_WEIGHT_UNIT,
            "downstream_wp5_design_input_approved": True,
        },
        "source_contract_validation": {
            "compliant": not contract_reasons,
            "approval_source": approval_source,
            "reasons": contract_reasons,
        },
        "diagnostic_input_override": bool(
            contract_reasons and allow_diagnostic_input
        ),
        "diagnostic_input_override_reasons": (
            contract_reasons if allow_diagnostic_input else []
        ),
    }
    return prepared, metadata


def prepare_synthetic(
    events: int,
    seed: int,
    energy_keV: float,
    sigma_x_mm: float,
    sigma_z_mm: float,
    sigma_divergence_rad: float,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Create an explicit monoenergetic fallback for tests and diagnostics."""
    generator = np.random.default_rng(seed)
    dx = generator.normal(0.0, sigma_divergence_rad, events)
    dz = generator.normal(0.0, sigma_divergence_rad, events)
    transverse_squared = dx**2 + dz**2
    if np.any(transverse_squared >= 1.0):
        raise ValueError(
            "synthetic angular draw is unphysical; reduce divergence or change seed"
        )
    dy = np.sqrt(1.0 - transverse_squared)
    prepared = {
        "event_id": np.arange(events, dtype=np.int64),
        "x_mm": generator.normal(0.0, sigma_x_mm, events),
        "y_mm": np.zeros(events, dtype=float),
        "z_mm": generator.normal(0.0, sigma_z_mm, events),
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "energy_keV": np.full(events, energy_keV, dtype=float),
        "unit_weight": np.ones(events, dtype=float),
        "source_row": np.full(events, -1, dtype=np.int64),
        "source_weight": np.ones(events, dtype=float),
    }
    metadata: dict[str, Any] = {
        "schema": SCHEMA,
        "mode": "synthetic_monoenergetic",
        "source_path": "synthetic",
        "source_group": "none",
        "resample_seed": seed,
        "requested_events": events,
        "input_rows": events,
        "valid_rows": events,
        "input_valid_weight_sum": float(events),
        "normalization_weight_per_event": 1.0,
        "normalization_unit": "synthetic unit photon per simulated event",
        "synthetic_energy_keV": energy_keV,
        "synthetic_sigma_x_mm": sigma_x_mm,
        "synthetic_sigma_z_mm": sigma_z_mm,
        "synthetic_sigma_divergence_rad": sigma_divergence_rad,
        "assumption": (
            "Synthetic input is a software smoke-test fallback, not a WP4 "
            "absolute-flux prediction."
        ),
    }
    return prepared, metadata


def write_prepared_csv(
    path: Path, prepared: dict[str, np.ndarray], metadata: dict[str, Any]
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = path.with_suffix(".metadata.json")
    incomplete_path = path.with_name(path.name + ".incomplete")
    incomplete_metadata_path = metadata_path.with_name(
        metadata_path.name + ".incomplete"
    )
    for target in (
        path,
        metadata_path,
        incomplete_path,
        incomplete_metadata_path,
    ):
        if target.is_dir():
            raise IsADirectoryError(
                f"refusing to replace prepared phase-space directory: {target}"
            )
    for target in (
        path,
        metadata_path,
        incomplete_path,
        incomplete_metadata_path,
    ):
        if target.exists() or target.is_symlink():
            target.unlink()
    enriched = {
        **metadata,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "h5py": h5py.__version__,
        "coordinate_convention": (
            "x/z transverse at sample plane; +y follows incident central ray; "
            "positions in mm, energy in keV"
        ),
        "weight_interpretation": (
            "Rows are sampled proportional to source_weight and transported "
            "as unit Geant4 events; multiply event tallies by "
            "normalization_weight_per_event."
        ),
    }
    with incomplete_path.open("w", newline="", encoding="utf-8") as stream:
        for key, value in enriched.items():
            serialized = (
                json.dumps(value, sort_keys=True, separators=(",", ":"))
                if isinstance(value, (dict, list))
                else _compact_metadata_value(value)
            )
            stream.write(f"# {key}={serialized}\n")
        writer = csv.DictWriter(
            stream, fieldnames=CSV_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        number = len(prepared["event_id"])
        for index in range(number):
            writer.writerow(
                {
                    field: (
                        int(prepared[field][index])
                        if field in {"event_id", "source_row"}
                        else f"{float(prepared[field][index]):.12g}"
                    )
                    for field in CSV_FIELDS
                }
            )

    incomplete_metadata_path.write_text(
        json.dumps(
            enriched,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    incomplete_metadata_path.replace(metadata_path)
    incomplete_path.replace(path)
    return metadata_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="WP4/WP1-style HDF5 phase-space file",
    )
    parser.add_argument(
        "--group",
        default="sample",
        help="HDF5 group containing the sample-plane datasets",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="unit-event CSV consumed by prism_wp5",
    )
    parser.add_argument(
        "--events",
        type=int,
        default=10_000,
        help="number of weighted-resampled Geant4 primary events",
    )
    parser.add_argument(
        "--seed", type=int, default=20260728, help="NumPy resampling seed"
    )
    parser.add_argument(
        "--synthetic-monoenergetic",
        action="store_true",
        help="explicitly use the software-test fallback instead of HDF5 input",
    )
    parser.add_argument(
        "--allow-diagnostic-input",
        action="store_true",
        help=(
            "allow an infeasible or non-S4-compliant phase space (including "
            "WP1/arbitrary input); intended only for software-pipeline "
            "diagnostics"
        ),
    )
    parser.add_argument(
        "--synthetic-energy-keV",
        type=float,
        default=25.52,
        help="synthetic primary energy",
    )
    parser.add_argument(
        "--synthetic-sigma-x-mm",
        type=float,
        default=0.10,
        help="synthetic Gaussian source sigma along x",
    )
    parser.add_argument(
        "--synthetic-sigma-z-mm",
        type=float,
        default=0.10,
        help="synthetic Gaussian source sigma along z",
    )
    parser.add_argument(
        "--synthetic-sigma-divergence-rad",
        type=float,
        default=0.0,
        help="synthetic Gaussian sigma for dx and dz",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.events <= 0:
        raise SystemExit("--events must be positive")
    if args.seed <= 0:
        raise SystemExit("--seed must be positive")
    for name in (
        "synthetic_energy_keV",
        "synthetic_sigma_x_mm",
        "synthetic_sigma_z_mm",
    ):
        if getattr(args, name) <= 0.0:
            raise SystemExit(f"--{name.replace('_', '-')} must be positive")
    if not 0.0 <= args.synthetic_sigma_divergence_rad < 0.25:
        raise SystemExit("--synthetic-sigma-divergence-rad must lie in [0, 0.25)")

    try:
        if args.synthetic_monoenergetic:
            prepared, metadata = prepare_synthetic(
                events=args.events,
                seed=args.seed,
                energy_keV=args.synthetic_energy_keV,
                sigma_x_mm=args.synthetic_sigma_x_mm,
                sigma_z_mm=args.synthetic_sigma_z_mm,
                sigma_divergence_rad=args.synthetic_sigma_divergence_rad,
            )
        else:
            if not args.input.is_file():
                raise ValueError(
                    f"phase-space file not found: {args.input}; pass a valid "
                    "WP4/WP1 HDF5 file or explicitly use "
                    "--synthetic-monoenergetic"
                )
            prepared, metadata = prepare_from_hdf5(
                path=args.input,
                group_name=args.group,
                events=args.events,
                seed=args.seed,
                allow_diagnostic_input=args.allow_diagnostic_input,
            )
        metadata_path = write_prepared_csv(args.output, prepared, metadata)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Prepared {args.events} unit events: {args.output}")
    print(
        "Normalization per event: "
        f"{metadata['normalization_weight_per_event']:.12g} "
        f"({metadata['normalization_unit']})"
    )
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
