#!/usr/bin/env python3
"""Analyze PRISM WP5 event data and plot the raw/smeared CZT response."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = SIMULATION_ROOT / "results" / "wp5" / "wp5_events.csv"
DEFAULT_OUTPUT_DIR = SIMULATION_ROOT / "results" / "wp5"
RAW_EVENT_SCHEMA = "PRISM_WP5_RAW_V1"
GAUSSIAN_FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))


def read_metadata_and_rows(path: Path) -> tuple[dict[str, str], dict[str, np.ndarray]]:
    metadata: dict[str, str] = {}
    data_lines: list[str] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#"):
                comment = line[1:].strip()
                if "=" in comment:
                    key, value = comment.split("=", 1)
                    metadata[key.strip()] = value.strip()
            elif line.strip():
                data_lines.append(line)
    if not data_lines:
        raise ValueError(f"event CSV contains no table: {path}")
    if metadata.get("schema") != RAW_EVENT_SCHEMA:
        raise ValueError(
            f"event CSV must declare schema={RAW_EVENT_SCHEMA}"
        )

    reader = csv.DictReader(data_lines)
    if reader.fieldnames is None:
        raise ValueError("event CSV has no header")
    required = {
        "event_id",
        "source_energy_keV",
        "normalization_weight",
        "edep_total_keV",
        "smeared_edep_keV",
        "edep_primary_keV",
        "edep_secondary_keV",
        "edep_gamma_keV",
        "edep_electron_keV",
        "secondary_gamma_created",
        "ag_ka_created",
        "ag_kb_created",
        "secondary_gamma_entered_czt",
        "ag_ka_entered_czt",
        "ag_kb_entered_czt",
    }
    missing = sorted(required.difference(reader.fieldnames))
    if missing:
        raise ValueError(f"event CSV is missing columns: {', '.join(missing)}")

    rows = list(reader)
    if not rows:
        raise ValueError("event CSV contains no events")
    arrays: dict[str, np.ndarray] = {}
    for field in reader.fieldnames:
        try:
            arrays[field] = np.asarray([float(row[field]) for row in rows], dtype=float)
        except (TypeError, ValueError):
            continue
    for field in required:
        if field not in arrays or not np.all(np.isfinite(arrays[field])):
            raise ValueError(f"event CSV column {field!r} is not finite numeric data")
    return metadata, arrays


def rectangular_solid_angle_sr(width_mm: float, height_mm: float, distance_mm: float) -> float:
    """Exact solid angle of a centred rectangle viewed normal to its face."""
    if min(width_mm, height_mm, distance_mm) <= 0.0:
        raise ValueError("detector dimensions and distance must be positive")
    a = 0.5 * width_mm
    b = 0.5 * height_mm
    return 4.0 * math.atan2(a * b, distance_mm * math.sqrt(distance_mm**2 + a**2 + b**2))


def metadata_float(
    metadata: dict[str, str], key: str, fallback: float | None = None
) -> float:
    if key not in metadata:
        if fallback is None:
            raise ValueError(f"event metadata is missing {key!r}")
        return fallback
    try:
        value = float(metadata[key])
    except ValueError as error:
        raise ValueError(f"event metadata {key!r} is not numeric") from error
    if not math.isfinite(value):
        raise ValueError(f"event metadata {key!r} is not finite")
    return value


def optional_metadata_float(
    metadata: dict[str, str], key: str, *, minimum: float = 0.0
) -> float | None:
    if key not in metadata:
        return None
    value = metadata_float(metadata, key)
    if value < minimum:
        raise ValueError(f"event metadata {key!r} must be >= {minimum:g}")
    return value


def optional_metadata_positive_int(
    metadata: dict[str, str], key: str
) -> int | None:
    if key not in metadata:
        return None
    try:
        value = int(metadata[key])
    except ValueError as error:
        raise ValueError(f"event metadata {key!r} is not an integer") from error
    if value <= 0:
        raise ValueError(f"event metadata {key!r} must be positive")
    return value


def roi_mask(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    return (values >= lower) & (values < upper)


def make_summary_and_plots(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    metadata, arrays = read_metadata_and_rows(args.input)
    raw = arrays["edep_total_keV"]
    weights = arrays["normalization_weight"]
    if np.any(weights <= 0.0):
        raise ValueError("normalization_weight must be positive for every event")

    if args.resmear:
        generator = np.random.default_rng(args.smear_seed)
        fwhm = np.sqrt(
            args.resolution_noise_fwhm_keV**2
            + (args.resolution_fraction_fwhm * raw) ** 2
        )
        smeared = np.zeros_like(raw)
        positive_deposition = raw > 0.0
        smeared[positive_deposition] = np.maximum(
            0.0,
            generator.normal(
                raw[positive_deposition],
                fwhm[positive_deposition] / GAUSSIAN_FWHM_FACTOR,
            ),
        )
        response_model: dict[str, Any] = {
            "mode": "python_resmear",
            "source_column": "edep_total_keV",
            "parameter_source": "analysis command-line arguments",
            "metadata_complete": True,
            "missing_metadata": [],
            "smear_seed": args.smear_seed,
            "noise_fwhm_keV": args.resolution_noise_fwhm_keV,
            "fractional_fwhm": args.resolution_fraction_fwhm,
            "formula": (
                "FWHM(E)=sqrt(noise_fwhm_keV^2+(fractional_fwhm*E)^2)"
            ),
        }
        smeared_label = "Python re-smeared response"
    else:
        smeared = arrays["smeared_edep_keV"]
        cpp_parameters: dict[str, float | int | None] = {
            "smear_seed": optional_metadata_positive_int(metadata, "seed"),
            "noise_fwhm_keV": optional_metadata_float(
                metadata, "resolution_noise_fwhm_keV"
            ),
            "fractional_fwhm": optional_metadata_float(
                metadata, "resolution_fraction_fwhm"
            ),
        }
        metadata_keys = {
            "smear_seed": "seed",
            "noise_fwhm_keV": "resolution_noise_fwhm_keV",
            "fractional_fwhm": "resolution_fraction_fwhm",
        }
        missing_metadata = [
            metadata_keys[name]
            for name, value in cpp_parameters.items()
            if value is None
        ]
        response_model = {
            "mode": "stored_cpp_response",
            "source_column": "smeared_edep_keV",
            "parameter_source": (
                "C++ event CSV metadata"
                if not missing_metadata
                else (
                    "C++ event CSV metadata is incomplete; the stored "
                    "smeared_edep_keV column remains authoritative"
                )
            ),
            "metadata_complete": not missing_metadata,
            "missing_metadata": missing_metadata,
            **cpp_parameters,
            "formula": (
                "FWHM(E)=sqrt(noise_fwhm_keV^2+(fractional_fwhm*E)^2)"
            ),
        }
        smeared_label = "Stored C++-smeared response"

    response_model["detection_threshold_keV"] = args.detection_threshold_keV

    raw_detected = raw >= args.detection_threshold_keV
    smeared_detected = smeared >= args.detection_threshold_keV
    ka = roi_mask(smeared, args.ka_min_keV, args.ka_max_keV)
    kb = roi_mask(smeared, args.kb_min_keV, args.kb_max_keV)
    fluorescence_roi = ka | kb
    background = smeared_detected & ~fluorescence_roi

    detector_width_mm = metadata_float(
        metadata, "detector_width_mm", args.detector_width_mm
    )
    detector_height_mm = metadata_float(
        metadata, "detector_height_mm", args.detector_height_mm
    )
    detector_distance_mm = metadata_float(
        metadata, "detector_distance_mm", args.detector_distance_mm
    )
    solid_angle_sr = rectangular_solid_angle_sr(
        detector_width_mm, detector_height_mm, detector_distance_mm
    )

    event_count = int(raw.size)
    represented_input_weight = float(weights.sum(dtype=np.float64))
    detected_weight = float(weights[smeared_detected].sum(dtype=np.float64))
    ka_weight = float(weights[ka].sum(dtype=np.float64))
    kb_weight = float(weights[kb].sum(dtype=np.float64))
    background_weight = float(weights[background].sum(dtype=np.float64))

    def count_sum(name: str) -> int:
        return int(np.rint(arrays[name].sum(dtype=np.float64)))

    summary: dict[str, Any] = {
        "schema": "PRISM_WP5_ANALYSIS_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_csv": str(args.input.resolve()),
        "events": event_count,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "matplotlib": getattr(plt.matplotlib, "__version__", "unknown"),
        },
        "response_model": response_model,
        "geometry": {
            "detector_width_mm": detector_width_mm,
            "detector_height_mm": detector_height_mm,
            "detector_distance_mm": detector_distance_mm,
            "detector_angle_deg": metadata_float(
                metadata, "detector_angle_deg", args.detector_angle_deg
            ),
            "solid_angle_sr": solid_angle_sr,
            "solid_angle_fraction_4pi": solid_angle_sr / (4.0 * math.pi),
            "solid_angle_assumption": (
                "centred point source and detector face normal to sample-detector axis"
            ),
        },
        "normalization": {
            "represented_input_weight": represented_input_weight,
            "mean_weight_per_event": float(weights.mean()),
            "unit": metadata.get(
                "source.normalization_unit",
                "input phase-space weight propagated per simulated event",
            ),
        },
        "detection": {
            "raw_detected_events": int(np.count_nonzero(raw_detected)),
            "raw_detection_efficiency": float(np.mean(raw_detected)),
            "smeared_detected_events": int(np.count_nonzero(smeared_detected)),
            "smeared_detection_efficiency": float(np.mean(smeared_detected)),
            "smeared_detected_weight": detected_weight,
            "mean_raw_edep_keV_all_events": float(raw.mean()),
            "mean_raw_edep_keV_detected": (
                float(raw[raw_detected].mean())
                if np.any(raw_detected)
                else None
            ),
        },
        "roi": {
            "ag_kalpha_keV": [args.ka_min_keV, args.ka_max_keV],
            "ag_kalpha_events": int(np.count_nonzero(ka)),
            "ag_kalpha_weight": ka_weight,
            "ag_kbeta_keV": [args.kb_min_keV, args.kb_max_keV],
            "ag_kbeta_events": int(np.count_nonzero(kb)),
            "ag_kbeta_weight": kb_weight,
            "background_detected_events": int(np.count_nonzero(background)),
            "background_weight": background_weight,
            "signal_to_background_weight_ratio": (
                (ka_weight + kb_weight) / background_weight
                if background_weight > 0.0
                else None
            ),
        },
        "secondary_photons": {
            "created_total": count_sum("secondary_gamma_created"),
            "created_ag_kalpha": count_sum("ag_ka_created"),
            "created_ag_kbeta": count_sum("ag_kb_created"),
            "entered_czt_total": count_sum("secondary_gamma_entered_czt"),
            "entered_czt_ag_kalpha": count_sum("ag_ka_entered_czt"),
            "entered_czt_ag_kbeta": count_sum("ag_kb_entered_czt"),
        },
        "energy_deposition_keV": {
            "total": float(arrays["edep_total_keV"].sum()),
            "primary_tracks": float(arrays["edep_primary_keV"].sum()),
            "secondary_tracks": float(arrays["edep_secondary_keV"].sum()),
            "gamma_tracks": float(arrays["edep_gamma_keV"].sum()),
            "electron_positron_tracks": float(arrays["edep_electron_keV"].sum()),
        },
        "simulation_metadata": metadata,
        "limitations": [
            "Efficiency is conditional on the prepared incident phase space.",
            "The CZT is a homogeneous active volume without contacts, charge transport, dead layers, pile-up, or thresholds beyond the analysis cut.",
            "The Gaussian resolution model is phenomenological and must be replaced or calibrated with detector data.",
            "Solid angle is a centred point-source estimate; the Monte Carlo geometry remains authoritative for finite samples.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.prefix}_summary.json"
    png_path = args.output_dir / f"{args.prefix}_spectrum.png"
    pdf_path = args.output_dir / f"{args.prefix}_spectrum.pdf"
    json_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    edges = np.linspace(args.energy_min_keV, args.energy_max_keV, args.bins + 1)
    detected_raw_values = raw[raw_detected]
    detected_smeared_values = smeared[smeared_detected]

    fig, (axis_full, axis_roi) = plt.subplots(2, 1, figsize=(10.5, 8.0))
    axis_full.hist(
        detected_raw_values,
        bins=edges,
        histtype="step",
        linewidth=1.4,
        label=f"Raw deposited energy ({detected_raw_values.size} detected)",
        color="#4c78a8",
    )
    axis_full.hist(
        detected_smeared_values,
        bins=edges,
        histtype="step",
        linewidth=1.4,
        label=smeared_label,
        color="#e45756",
    )
    axis_full.set(
        title="WP5 CZT energy response",
        xlabel="Deposited energy [keV]",
        ylabel="Events / bin",
        xlim=(args.energy_min_keV, args.energy_max_keV),
    )
    axis_full.set_yscale("log")
    axis_full.legend()

    roi_min = max(args.energy_min_keV, args.ka_min_keV - 1.5)
    roi_max = min(args.energy_max_keV, args.kb_max_keV + 1.5)
    roi_edges = np.linspace(roi_min, roi_max, max(80, args.bins // 2) + 1)
    axis_roi.hist(
        detected_smeared_values,
        bins=roi_edges,
        histtype="stepfilled",
        alpha=0.35,
        color="#72b7b2",
        label=smeared_label,
    )
    axis_roi.axvspan(
        args.ka_min_keV,
        args.ka_max_keV,
        alpha=0.22,
        color="#54a24b",
        label="Ag K-alpha ROI",
    )
    axis_roi.axvspan(
        args.kb_min_keV,
        args.kb_max_keV,
        alpha=0.22,
        color="#f2cf5b",
        label="Ag K-beta ROI",
    )
    axis_roi.set(
        title="Ag fluorescence region",
        xlabel="Deposited energy [keV]",
        ylabel="Events / bin",
        xlim=(roi_min, roi_max),
    )
    axis_roi.legend(fontsize=8)

    for axis in (axis_full, axis_roi):
        axis.grid(linestyle=":", alpha=0.45)
    fig.suptitle(
        f"Ag sample -> CZT at {metadata_float(metadata, 'detector_angle_deg', args.detector_angle_deg):g} degrees; "
        f"{event_count} incident events"
    )
    fig.tight_layout()
    fig.savefig(png_path, dpi=250)
    fig.savefig(pdf_path)
    plt.show()
    plt.close(fig)
    return json_path, png_path, pdf_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT, help="raw prism_wp5 event CSV"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for summary and plots",
    )
    parser.add_argument("--prefix", default="wp5", help="output filename prefix")
    parser.add_argument("--bins", type=int, default=300, help="full-spectrum bins")
    parser.add_argument(
        "--energy-min-keV", type=float, default=0.0, help="plot lower bound"
    )
    parser.add_argument(
        "--energy-max-keV", type=float, default=30.0, help="plot upper bound"
    )
    parser.add_argument(
        "--detection-threshold-keV",
        type=float,
        default=0.5,
        help="minimum deposited energy counted as a detection",
    )
    parser.add_argument(
        "--resmear",
        action="store_true",
        help=(
            "ignore stored C++ smearing and explicitly re-smear edep_total_keV "
            "in Python"
        ),
    )
    parser.add_argument(
        "--resolution-noise-fwhm-keV",
        type=float,
        default=0.80,
        help="constant detector FWHM term used only with --resmear",
    )
    parser.add_argument(
        "--resolution-fraction-fwhm",
        type=float,
        default=0.020,
        help="fractional detector FWHM term used only with --resmear",
    )
    parser.add_argument(
        "--smear-seed",
        type=int,
        default=20260728,
        help="Python response-smearing seed used only with --resmear",
    )
    parser.add_argument(
        "--ka-min-keV", type=float, default=21.60, help="Ag K-alpha ROI lower edge"
    )
    parser.add_argument(
        "--ka-max-keV", type=float, default=22.50, help="Ag K-alpha ROI upper edge"
    )
    parser.add_argument(
        "--kb-min-keV", type=float, default=24.45, help="Ag K-beta ROI lower edge"
    )
    parser.add_argument(
        "--kb-max-keV", type=float, default=25.25, help="Ag K-beta ROI upper edge"
    )
    parser.add_argument(
        "--detector-width-mm",
        type=float,
        default=20.0,
        help="fallback width if raw metadata is absent",
    )
    parser.add_argument(
        "--detector-height-mm",
        type=float,
        default=20.0,
        help="fallback height if raw metadata is absent",
    )
    parser.add_argument(
        "--detector-distance-mm",
        type=float,
        default=50.0,
        help="fallback distance if raw metadata is absent",
    )
    parser.add_argument(
        "--detector-angle-deg",
        type=float,
        default=90.0,
        help="fallback detector angle if raw metadata is absent",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"raw event CSV not found: {args.input}")
    if args.bins < 20:
        parser.error("--bins must be at least 20")
    if args.energy_min_keV < 0.0 or args.energy_min_keV >= args.energy_max_keV:
        parser.error("energy plot bounds must satisfy 0 <= min < max")
    if args.detection_threshold_keV < 0.0:
        parser.error("--detection-threshold-keV cannot be negative")
    if args.resmear:
        if (
            args.resolution_noise_fwhm_keV < 0.0
            or args.resolution_fraction_fwhm < 0.0
        ):
            parser.error("resolution terms cannot be negative")
        if args.smear_seed <= 0:
            parser.error("--smear-seed must be positive")
    if not (
        args.ka_min_keV < args.ka_max_keV <= args.kb_min_keV < args.kb_max_keV
    ):
        parser.error("Ag K-alpha and K-beta ROI bounds are invalid or overlap")

    try:
        json_path, png_path, pdf_path = make_summary_and_plots(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Summary: {json_path}")
    print(f"Spectrum: {png_path}")
    print(f"Spectrum: {pdf_path}")


if __name__ == "__main__":
    main()
