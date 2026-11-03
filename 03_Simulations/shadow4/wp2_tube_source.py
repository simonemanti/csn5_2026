#!/usr/bin/env python3
"""WP2 realistic W-tube source and fixed-Ge(880) SHADOW4 trace.

SpekPy is evaluated on axis at a configurable reference distance and reference
exposure.  The cached complete spectrum is normalized to photons/cm2/mAs.
Only the explicit energy-importance window is sampled for ray tracing, while
both the complete-spectrum and traced-window fluences are retained.

The source model is deliberately factorized as
P(E, x, z, dx, dz) = P(E) P(x, z) P(dx, dz).  Within the small sampled angular
domain, the on-axis SpekPy radiant intensity is assumed uniform.  SHADOW4
samples direction cosines uniformly; ray amplitudes are therefore corrected by
1/dy and scaled so that column 23 is photons/mAs in the sampled solid angle.
Tube current and exposure time are reporting-only multipliers and never alter
the cached spectrum, sampled rays, or optical trace.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
from collections.abc import Mapping
from typing import Any
import warnings

import h5py
import numpy as np
import spekpy
from shadow4.beam.s4_beam import S4Beam
from shadow4.beamline.optical_elements.crystals.s4_sphere_crystal import (
    S4SphereCrystalElement,
)
from syned.beamline.element_coordinates import ElementCoordinates


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SHADOW4_DIR = Path(__file__).resolve().parent
if str(SHADOW4_DIR) not in sys.path:
    sys.path.insert(0, str(SHADOW4_DIR))
import wp1_monoenergetic as wp1  # noqa: E402


DEFAULT_TUBE_CONFIG = SIMULATION_ROOT / "config" / "wp2_tube_source.json"
DEFAULT_GEOMETRY_CONFIG = SIMULATION_ROOT / "config" / "wp1_geometry.json"
DEFAULT_OUTPUT_DIR = SIMULATION_ROOT / "results" / "wp2"
DEFAULT_CACHE_DIR = DEFAULT_OUTPUT_DIR / "cache"
PHASE_SPACE_SCHEMA = "PRISM_SHADOW4_PHASE_SPACE_V1"
ENERGY_SEED_OFFSET = 1_000_003
AMPLITUDE_COLUMNS = (7, 8, 9, 16, 17, 18)


@dataclass(frozen=True)
class TubeSpectrum:
    """Complete cached spectrum plus the configured traced-energy overlap."""

    energy_keV: np.ndarray
    differential_fluence_photons_cm2_keV_mAs: np.ndarray
    bin_fluence_photons_cm2_mAs: np.ndarray
    bin_lower_keV: np.ndarray
    bin_upper_keV: np.ndarray
    trace_overlap_keV: np.ndarray
    trace_bin_fluence_photons_cm2_mAs: np.ndarray
    operating_point: dict[str, Any]
    cache_key: str
    cache_path: Path
    cache_hit: bool
    importance_minimum_keV: float
    importance_maximum_keV: float

    @property
    def trace_mask(self) -> np.ndarray:
        return self.trace_overlap_keV > 0.0

    @property
    def total_fluence_photons_cm2_mAs(self) -> float:
        return float(np.sum(self.bin_fluence_photons_cm2_mAs))

    @property
    def traced_fluence_photons_cm2_mAs(self) -> float:
        return float(np.sum(self.trace_bin_fluence_photons_cm2_mAs))

    @property
    def traced_fraction_of_total_spectrum(self) -> float:
        return (
            self.traced_fluence_photons_cm2_mAs
            / self.total_fluence_photons_cm2_mAs
        )


@dataclass
class WP2Run:
    """Programmatic result from :func:`run_pipeline`."""

    summary: dict[str, Any]
    spectrum: TubeSpectrum
    source: S4Beam
    footprint: S4Beam
    post_crystal: S4Beam
    sample: S4Beam


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from *path*."""
    with path.open(encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError(f"configuration root must be an object: {path}")
    return document


def package_version(distribution: str) -> str:
    """Return an installed package version or ``unknown``."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _number(
    mapping: Mapping[str, Any],
    key: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key!r} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{key!r} must be finite")
    if positive and result <= 0.0:
        raise ValueError(f"{key!r} must be positive")
    if nonnegative and result < 0.0:
        raise ValueError(f"{key!r} must be nonnegative")
    return result


def validate_tube_config(config: Mapping[str, Any]) -> None:
    """Validate the complete WP2 source, reporting, and plotting configuration."""
    required_sections = (
        "spekpy",
        "source_phase_space",
        "energy_importance",
        "reporting",
        "plots",
    )
    sections: dict[str, Mapping[str, Any]] = {}
    for name in required_sections:
        section = config.get(name)
        if not isinstance(section, Mapping):
            raise ValueError(f"WP2 config requires a {name!r} object")
        sections[name] = section

    spectrum = sections["spekpy"]
    if spectrum.get("target") != "W":
        raise ValueError("WP2 currently supports only a W target")
    kvp = _number(spectrum, "kvp", positive=True)
    _number(spectrum, "anode_angle_deg", positive=True)
    _number(spectrum, "bin_width_keV", positive=True)
    _number(spectrum, "reference_distance_cm", positive=True)
    mas = _number(spectrum, "mas", positive=True)
    if not math.isclose(mas, 1.0, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(
            "WP2 cache must use mas=1.0; current and exposure are post-scaling only"
        )
    for key in ("x_cm", "y_cm"):
        _number(spectrum, key)
    for key in ("bremsstrahlung", "characteristic", "obliquity"):
        if not isinstance(spectrum.get(key), bool):
            raise ValueError(f"{key!r} must be boolean")
    for key in ("physics", "mu_data_source", "spekpy_version"):
        if not isinstance(spectrum.get(key), str) or not spectrum[key]:
            raise ValueError(f"{key!r} must be a non-empty string")
    installed_version = str(getattr(spekpy, "__version__", "unknown"))
    if spectrum["spekpy_version"] != installed_version:
        raise ValueError(
            "configured SpekPy version "
            f"{spectrum['spekpy_version']!r} does not match installed "
            f"{installed_version!r}"
        )
    filtration = spectrum.get("filtration")
    if not isinstance(filtration, list):
        raise ValueError("'filtration' must be a list")
    for index, item in enumerate(filtration):
        if not isinstance(item, Mapping):
            raise ValueError(f"filtration item {index} must be an object")
        if not isinstance(item.get("material"), str) or not item["material"]:
            raise ValueError(f"filtration item {index} requires a material")
        _number(item, "thickness_mm", positive=True)

    source = sections["source_phase_space"]
    nrays = source.get("nrays")
    seed = source.get("seed")
    if isinstance(nrays, bool) or not isinstance(nrays, int) or nrays < 100:
        raise ValueError("'nrays' must be an integer of at least 100")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 1:
        raise ValueError("'seed' must be a positive integer")
    reference_energy_keV = _number(
        source, "reference_energy_keV", positive=True
    )
    if reference_energy_keV >= kvp:
        raise ValueError("reference energy must be below the tube kVp")
    spatial = str(source.get("spatial_distribution", "")).lower()
    if spatial == "gaussian":
        _number(source, "sigma_x_m", positive=True)
        _number(source, "sigma_z_m", positive=True)
    elif spatial == "rectangle":
        _number(source, "width_x_m", positive=True)
        _number(source, "height_z_m", positive=True)
    elif spatial != "point":
        raise ValueError(
            "'spatial_distribution' must be point, gaussian, or rectangle"
        )
    if str(source.get("angular_distribution", "")).lower() != "flat":
        raise ValueError("WP2 normalization currently requires flat angular sampling")
    hmin = _number(source, "horizontal_angle_min_rad")
    hmax = _number(source, "horizontal_angle_max_rad")
    vmin = _number(source, "vertical_angle_min_rad")
    vmax = _number(source, "vertical_angle_max_rad")
    if hmin >= hmax or vmin >= vmax:
        raise ValueError("each angular minimum must be below its maximum")
    if max(
        hmin * hmin + vmin * vmin,
        hmin * hmin + vmax * vmax,
        hmax * hmax + vmin * vmin,
        hmax * hmax + vmax * vmax,
    ) >= 1.0:
        raise ValueError("sampled direction-cosine rectangle must lie in unit disk")
    polarization = _number(source, "polarization_degree")
    if not 0.0 <= polarization <= 1.0:
        raise ValueError("'polarization_degree' must lie in [0, 1]")

    importance = sections["energy_importance"]
    minimum_keV = _number(importance, "minimum_keV", positive=True)
    maximum_keV = _number(importance, "maximum_keV", positive=True)
    if minimum_keV >= maximum_keV:
        raise ValueError("energy-importance minimum must be below maximum")
    if maximum_keV > kvp:
        raise ValueError("energy-importance maximum cannot exceed tube kVp")
    if not minimum_keV <= reference_energy_keV <= maximum_keV:
        raise ValueError("reference energy must lie inside energy-importance window")

    reporting = sections["reporting"]
    _number(reporting, "current_mA", nonnegative=True)
    _number(reporting, "exposure_s", nonnegative=True)

    plots = sections["plots"]
    for key, minimum in (
        ("spectrum_bins", 20),
        ("profile_bins", 20),
        ("maximum_scatter_rays", 100),
    ):
        value = plots.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{key!r} must be an integer of at least {minimum}")


def _operating_point(config: Mapping[str, Any]) -> dict[str, Any]:
    spectrum = config["spekpy"]
    return {
        "target": spectrum["target"],
        "kvp": float(spectrum["kvp"]),
        "anode_angle_deg": float(spectrum["anode_angle_deg"]),
        "bin_width_keV": float(spectrum["bin_width_keV"]),
        "reference_distance_cm": float(spectrum["reference_distance_cm"]),
        "mas": float(spectrum["mas"]),
        "spekpy_version": str(spectrum["spekpy_version"]),
        "physics": str(spectrum["physics"]),
        "mu_data_source": str(spectrum["mu_data_source"]),
        "x_cm": float(spectrum["x_cm"]),
        "y_cm": float(spectrum["y_cm"]),
        "bremsstrahlung": bool(spectrum["bremsstrahlung"]),
        "characteristic": bool(spectrum["characteristic"]),
        "obliquity": bool(spectrum["obliquity"]),
        "filtration": [
            {
                "material": str(item["material"]),
                "thickness_mm": float(item["thickness_mm"]),
            }
            for item in spectrum["filtration"]
        ],
    }


def _cache_key(operating_point: Mapping[str, Any]) -> str:
    payload = json.dumps(
        operating_point, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generate_spectrum(
    operating_point: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model = spekpy.Spek(
        kvp=operating_point["kvp"],
        th=operating_point["anode_angle_deg"],
        dk=operating_point["bin_width_keV"],
        mu_data_source=operating_point["mu_data_source"],
        physics=operating_point["physics"],
        x=operating_point["x_cm"],
        y=operating_point["y_cm"],
        z=operating_point["reference_distance_cm"],
        mas=operating_point["mas"],
        brem=operating_point["bremsstrahlung"],
        char=operating_point["characteristic"],
        obli=operating_point["obliquity"],
        targ=operating_point["target"],
    )
    for item in operating_point["filtration"]:
        model.filter(item["material"], item["thickness_mm"])
    energy_keV, differential = model.get_spectrum(diff=True, flu=True)
    integrated_energy_keV, bin_fluence = model.get_spectrum(diff=False, flu=True)
    energy_keV = np.asarray(energy_keV, dtype=float)
    integrated_energy_keV = np.asarray(integrated_energy_keV, dtype=float)
    if not np.allclose(energy_keV, integrated_energy_keV):
        raise RuntimeError("SpekPy differential and integrated energy grids differ")
    reference_mas = float(operating_point["mas"])
    differential = np.asarray(differential, dtype=float) / reference_mas
    bin_fluence = np.asarray(bin_fluence, dtype=float) / reference_mas
    if (
        energy_keV.ndim != 1
        or energy_keV.size < 2
        or differential.shape != energy_keV.shape
        or bin_fluence.shape != energy_keV.shape
        or not np.all(np.isfinite(differential))
        or not np.all(np.isfinite(bin_fluence))
        or np.any(differential < 0.0)
        or np.any(bin_fluence < 0.0)
    ):
        raise RuntimeError("SpekPy returned an invalid spectrum")
    return energy_keV, differential, bin_fluence


def _write_spectrum_cache(
    path: Path,
    energy_keV: np.ndarray,
    differential: np.ndarray,
    bin_fluence: np.ndarray,
    operating_point: Mapping[str, Any],
    cache_key: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "cache_format": "PRISM_SPEKPY_SPECTRUM_V1",
        "cache_key": cache_key,
        "operating_point": operating_point,
        "normalization": "photons/cm2/mAs at the configured reference point",
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.stem}-",
            suffix=".npz",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
        np.savez_compressed(
            temporary_path,
            energy_keV=energy_keV,
            differential_fluence_photons_cm2_keV_mAs=differential,
            bin_fluence_photons_cm2_mAs=bin_fluence,
            metadata_json=np.asarray(
                json.dumps(metadata, sort_keys=True, allow_nan=False)
            ),
        )
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _read_spectrum_cache(
    path: Path,
    operating_point: Mapping[str, Any],
    cache_key: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            metadata = json.loads(str(archive["metadata_json"].item()))
            energy_keV = np.asarray(archive["energy_keV"], dtype=float)
            differential = np.asarray(
                archive["differential_fluence_photons_cm2_keV_mAs"],
                dtype=float,
            )
            bin_fluence = np.asarray(
                archive["bin_fluence_photons_cm2_mAs"], dtype=float
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid SpekPy cache {path}: {error}") from error
    if (
        metadata.get("cache_format") != "PRISM_SPEKPY_SPECTRUM_V1"
        or metadata.get("cache_key") != cache_key
        or metadata.get("operating_point") != operating_point
    ):
        raise RuntimeError(f"SpekPy cache metadata mismatch: {path}")
    if (
        energy_keV.ndim != 1
        or energy_keV.size < 2
        or differential.shape != energy_keV.shape
        or bin_fluence.shape != energy_keV.shape
    ):
        raise RuntimeError(f"SpekPy cache arrays have inconsistent shapes: {path}")
    return energy_keV, differential, bin_fluence


def load_or_generate_spectrum(
    tube_config: Mapping[str, Any],
    *,
    cache_dir: Path | None = None,
    force_regenerate: bool = False,
) -> TubeSpectrum:
    """Load or generate the complete 1 mAs SpekPy spectrum.

    The deterministic cache key covers the complete tube operating point:
    target, kVp, anode angle, filtration (including order), bin width,
    reference coordinates/distance, mAs, physics settings, emission flags, and
    exact SpekPy version.  The energy-importance window is deliberately not in
    the cache key because it is a downstream ray-sampling choice.
    """
    validate_tube_config(tube_config)
    operating_point = _operating_point(tube_config)
    cache_key = _cache_key(operating_point)
    resolved_cache_dir = (
        DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)
    )
    cache_path = resolved_cache_dir / f"spekpy_{cache_key[:20]}.npz"
    cache_hit = cache_path.is_file() and not force_regenerate
    if cache_hit:
        energy_keV, differential, bin_fluence = _read_spectrum_cache(
            cache_path, operating_point, cache_key
        )
    else:
        energy_keV, differential, bin_fluence = _generate_spectrum(
            operating_point
        )
        _write_spectrum_cache(
            cache_path,
            energy_keV,
            differential,
            bin_fluence,
            operating_point,
            cache_key,
        )

    bin_width_keV = float(operating_point["bin_width_keV"])
    lower = energy_keV - 0.5 * bin_width_keV
    upper = energy_keV + 0.5 * bin_width_keV
    importance = tube_config["energy_importance"]
    importance_minimum = float(importance["minimum_keV"])
    importance_maximum = float(importance["maximum_keV"])
    overlap = np.maximum(
        0.0,
        np.minimum(upper, importance_maximum)
        - np.maximum(lower, importance_minimum),
    )
    trace_bin_fluence = differential * overlap
    if not np.any(trace_bin_fluence > 0.0):
        raise ValueError("energy-importance window contains no SpekPy fluence")
    total = float(np.sum(bin_fluence))
    traced = float(np.sum(trace_bin_fluence))
    if not math.isfinite(total) or total <= 0.0 or traced <= 0.0:
        raise RuntimeError("SpekPy spectrum has no positive finite fluence")
    return TubeSpectrum(
        energy_keV=energy_keV,
        differential_fluence_photons_cm2_keV_mAs=differential,
        bin_fluence_photons_cm2_mAs=bin_fluence,
        bin_lower_keV=lower,
        bin_upper_keV=upper,
        trace_overlap_keV=overlap,
        trace_bin_fluence_photons_cm2_mAs=trace_bin_fluence,
        operating_point=operating_point,
        cache_key=cache_key,
        cache_path=cache_path,
        cache_hit=cache_hit,
        importance_minimum_keV=importance_minimum,
        importance_maximum_keV=importance_maximum,
    )


def rectangular_direction_cosine_solid_angle_sr(
    horizontal_minimum: float,
    horizontal_maximum: float,
    vertical_minimum: float,
    vertical_maximum: float,
    *,
    quadrature_order: int = 48,
) -> float:
    """Integrate ``d(dx)d(dz)/dy`` over a direction-cosine rectangle."""
    if horizontal_minimum >= horizontal_maximum:
        raise ValueError("horizontal direction-cosine limits are reversed")
    if vertical_minimum >= vertical_maximum:
        raise ValueError("vertical direction-cosine limits are reversed")
    nodes, weights = np.polynomial.legendre.leggauss(quadrature_order)
    horizontal = (
        0.5 * (horizontal_maximum - horizontal_minimum) * nodes
        + 0.5 * (horizontal_maximum + horizontal_minimum)
    )
    vertical = (
        0.5 * (vertical_maximum - vertical_minimum) * nodes
        + 0.5 * (vertical_maximum + vertical_minimum)
    )
    horizontal_weights = (
        0.5 * (horizontal_maximum - horizontal_minimum) * weights
    )
    vertical_weights = (
        0.5 * (vertical_maximum - vertical_minimum) * weights
    )
    squared = horizontal[:, None] ** 2 + vertical[None, :] ** 2
    if np.any(squared >= 1.0):
        raise ValueError("direction-cosine rectangle extends outside unit disk")
    integrand = 1.0 / np.sqrt(1.0 - squared)
    solid_angle = float(
        np.sum(
            integrand
            * horizontal_weights[:, None]
            * vertical_weights[None, :]
        )
    )
    if not math.isfinite(solid_angle) or solid_angle <= 0.0:
        raise RuntimeError("failed to calculate sampled solid angle")
    return solid_angle


def _wp1_source_config(
    source_config: Mapping[str, Any],
    *,
    nrays: int,
    seed: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "description": "WP2 factorized spatial/angular proposal",
        "nrays": nrays,
        "seed": seed,
        "energy_keV": float(source_config["reference_energy_keV"]),
        "spatial_distribution": str(source_config["spatial_distribution"]),
        "angular_distribution": "flat",
        "horizontal_angle_min_rad": float(
            source_config["horizontal_angle_min_rad"]
        ),
        "horizontal_angle_max_rad": float(
            source_config["horizontal_angle_max_rad"]
        ),
        "vertical_angle_min_rad": float(source_config["vertical_angle_min_rad"]),
        "vertical_angle_max_rad": float(source_config["vertical_angle_max_rad"]),
        "polarization_degree": float(source_config["polarization_degree"]),
    }
    spatial = result["spatial_distribution"].lower()
    if spatial == "gaussian":
        result["sigma_x_m"] = float(source_config["sigma_x_m"])
        result["sigma_z_m"] = float(source_config["sigma_z_m"])
    elif spatial == "rectangle":
        result["width_x_m"] = float(source_config["width_x_m"])
        result["height_z_m"] = float(source_config["height_z_m"])
    return result


def _scale_beam_amplitudes_to_weights(
    beam: S4Beam, target_weight_photons_mAs: np.ndarray
) -> None:
    current_weight = np.asarray(beam.get_column(23), dtype=float)
    target_weight = np.asarray(target_weight_photons_mAs, dtype=float)
    if current_weight.shape != target_weight.shape:
        raise ValueError("one target weight is required for each source ray")
    if (
        np.any(~np.isfinite(current_weight))
        or np.any(current_weight <= 0.0)
        or np.any(~np.isfinite(target_weight))
        or np.any(target_weight <= 0.0)
    ):
        raise ValueError("source and target ray weights must be positive and finite")
    amplitude_scale = np.sqrt(target_weight / current_weight)
    for column in AMPLITUDE_COLUMNS:
        beam.set_column(column, beam.get_column(column) * amplitude_scale)
    resolved_weight = np.asarray(beam.get_column(23), dtype=float)
    if not np.allclose(
        resolved_weight, target_weight, rtol=2.0e-13, atol=0.0
    ):
        raise RuntimeError("failed to encode photon weights in SHADOW4 amplitudes")


def build_polychromatic_source(
    tube_config: Mapping[str, Any],
    spectrum: TubeSpectrum,
    *,
    nrays: int | None = None,
    seed: int | None = None,
) -> tuple[S4Beam, dict[str, Any]]:
    """Build the factorized WP2 source with photon-normalized amplitudes.

    Returns ``(incident_beam, source_metadata)``.  The beam is a standard
    :class:`S4Beam`; energy is stored in the SHADOW photon-energy column and
    ``incident_beam.get_column(23)`` is photons/mAs for every row.  WP3 may
    duplicate this beam, apply aperture status masks, and pass the result to
    :func:`trace_incident_beam` without invoking SpekPy again.
    """
    validate_tube_config(tube_config)
    source_config = tube_config["source_phase_space"]
    effective_nrays = int(source_config["nrays"] if nrays is None else nrays)
    effective_seed = int(source_config["seed"] if seed is None else seed)
    if effective_nrays < 100:
        raise ValueError("nrays must be at least 100")
    if effective_seed < 1:
        raise ValueError("seed must be positive")
    wp1_source = _wp1_source_config(
        source_config, nrays=effective_nrays, seed=effective_seed
    )
    wp1.validate_source_config(wp1_source)
    beam = wp1.build_source(wp1_source).get_beam()

    trace_fluence = spectrum.trace_bin_fluence_photons_cm2_mAs
    positive_indices = np.flatnonzero(trace_fluence > 0.0)
    probability = trace_fluence[positive_indices]
    probability = probability / float(np.sum(probability))
    energy_seed = effective_seed + ENERGY_SEED_OFFSET
    generator = np.random.default_rng(energy_seed)
    sampled_indices = generator.choice(
        positive_indices, size=effective_nrays, replace=True, p=probability
    )
    sampled_lower = np.maximum(
        spectrum.bin_lower_keV[sampled_indices],
        spectrum.importance_minimum_keV,
    )
    sampled_upper = np.minimum(
        spectrum.bin_upper_keV[sampled_indices],
        spectrum.importance_maximum_keV,
    )
    sampled_energy_keV = generator.uniform(sampled_lower, sampled_upper)
    beam.set_photon_energy_eV(1000.0 * sampled_energy_keV)

    hmin = float(source_config["horizontal_angle_min_rad"])
    hmax = float(source_config["horizontal_angle_max_rad"])
    vmin = float(source_config["vertical_angle_min_rad"])
    vmax = float(source_config["vertical_angle_max_rad"])
    solid_angle_sr = rectangular_direction_cosine_solid_angle_sr(
        hmin, hmax, vmin, vmax
    )
    reference_distance_cm = float(
        spectrum.operating_point["reference_distance_cm"]
    )
    full_spectrum_photons_mAs = (
        spectrum.total_fluence_photons_cm2_mAs
        * reference_distance_cm**2
        * solid_angle_sr
    )
    traced_window_photons_mAs = (
        spectrum.traced_fluence_photons_cm2_mAs
        * reference_distance_cm**2
        * solid_angle_sr
    )

    dy = np.asarray(beam.get_column(5), dtype=float)
    if np.any(~np.isfinite(dy)) or np.any(dy <= 0.0):
        raise RuntimeError("source contains invalid forward direction cosines")
    angular_importance_correction = 1.0 / dy
    target_weights = (
        traced_window_photons_mAs
        * angular_importance_correction
        / float(np.sum(angular_importance_correction))
    )
    _scale_beam_amplitudes_to_weights(beam, target_weights)
    encoded_sum = float(np.sum(beam.get_column(23)))
    if not math.isclose(
        encoded_sum,
        traced_window_photons_mAs,
        rel_tol=2.0e-13,
        abs_tol=0.0,
    ):
        raise RuntimeError("source photon normalization invariant failed")

    metadata: dict[str, Any] = {
        "nrays": effective_nrays,
        "seed": effective_seed,
        "energy_seed": energy_seed,
        "factorization": "P(E) P(x,z) P(dx,dz)",
        "energy_sampling": (
            "piecewise-uniform within SpekPy bins, sampled in proportion to "
            "physical bin fluence inside the explicit importance window"
        ),
        "angular_sampling": (
            "uniform direction-cosine rectangle with 1/dy amplitude-weight "
            "correction for uniform radiant intensity per steradian"
        ),
        "sampled_solid_angle_sr": solid_angle_sr,
        "reference_distance_cm": reference_distance_cm,
        "complete_spectrum_fluence_photons_cm2_mAs": (
            spectrum.total_fluence_photons_cm2_mAs
        ),
        "traced_window_fluence_photons_cm2_mAs": (
            spectrum.traced_fluence_photons_cm2_mAs
        ),
        "complete_spectrum_photons_per_mAs_in_sampled_solid_angle": (
            full_spectrum_photons_mAs
        ),
        "traced_window_photons_per_mAs_in_sampled_solid_angle": (
            traced_window_photons_mAs
        ),
        "encoded_source_weight_sum_photons_per_mAs": encoded_sum,
        "weight_unit": "photons/mAs",
        "on_axis_uniformity_assumption": (
            "SpekPy fluence at configured x,y,z is converted to radiant "
            "intensity and treated as uniform across the sampled solid angle; "
            "heel-effect and energy-angle/position coupling are omitted."
        ),
    }
    return beam, metadata


def trace_incident_beam(
    incident_beam: S4Beam,
    geometry_config: Mapping[str, Any],
    *,
    reference_energy_keV: float,
    verbose_shadow4: bool = False,
) -> tuple[S4Beam, S4Beam, ElementCoordinates, dict[str, Any]]:
    """Trace an existing incident beam through the fixed WP1 Ge(880) optic.

    Returns exactly ``(footprint, post_crystal, coordinates,
    resolved_geometry)``.  ``incident_beam`` remains the caller-owned input.
    ``footprint`` is in the local crystal frame and ``post_crystal`` is at q=0
    in the reflected central-ray frame.  The minimum stable geometry keys are
    ``crystal_label``, ``reference_energy_keV``,
    ``corrected_bragg_angle_deg``, ``von_hamos_symmetric_arm_m``,
    ``source_to_crystal_m``, ``paraxial_predicted_crystal_to_focus_m``, and
    ``configured_crystal_to_sample_m``.
    """
    geometry = copy.deepcopy(dict(geometry_config))
    wp1.validate_geometry_config(geometry)
    if not math.isfinite(reference_energy_keV) or reference_energy_keV <= 0.0:
        raise ValueError("reference_energy_keV must be positive and finite")
    crystal_config = geometry["crystal"]
    distance_config = geometry["distances"]
    reference_energy_ev = 1000.0 * reference_energy_keV
    bragg_angle_rad = wp1.corrected_bragg_angle_rad(
        crystal_config, reference_energy_ev
    )
    radius_m = float(crystal_config["radius_m"])
    symmetric_arm_m = wp1.von_hamos_symmetric_arm_m(
        radius_m, bragg_angle_rad
    )
    source_distance_m = (
        symmetric_arm_m
        if distance_config["source_to_crystal_m"] is None
        else float(distance_config["source_to_crystal_m"])
    )
    predicted_image_m = wp1.sagittal_image_distance_m(
        source_distance_m, radius_m, bragg_angle_rad
    )
    sample_distance_m = (
        predicted_image_m
        if distance_config["crystal_to_sample_m"] is None
        else float(distance_config["crystal_to_sample_m"])
    )
    crystal = wp1.build_crystal(crystal_config, reference_energy_ev)
    coordinates = ElementCoordinates(
        p=source_distance_m,
        q=0.0,
        angle_radial=0.0,
        angle_azimuthal=0.0,
        angle_radial_out=None,
    )
    element = S4SphereCrystalElement(
        optical_element=crystal,
        coordinates=coordinates,
        input_beam=incident_beam.duplicate(),
    )
    if verbose_shadow4:
        post_crystal, footprint = element.trace_beam()
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            post_crystal, footprint = element.trace_beam()
    h, k, l = crystal_config["miller_indices"]
    crystal_label = f"{crystal_config['material']}({h}{k}{l})"
    aligned_incident, aligned_outgoing, aligned_azimuthal = (
        coordinates.get_angles()
    )
    resolved_geometry: dict[str, Any] = {
        "crystal_label": crystal_label,
        "reference_energy_keV": float(reference_energy_keV),
        "corrected_bragg_angle_deg": math.degrees(bragg_angle_rad),
        "central_deflection_angle_deg": 2.0 * math.degrees(bragg_angle_rad),
        "von_hamos_symmetric_arm_m": symmetric_arm_m,
        "source_to_crystal_m": source_distance_m,
        "paraxial_predicted_crystal_to_focus_m": predicted_image_m,
        "configured_crystal_to_sample_m": sample_distance_m,
        "aligned_incident_angle_to_normal_deg": math.degrees(aligned_incident),
        "aligned_outgoing_angle_to_normal_deg": math.degrees(aligned_outgoing),
        "aligned_azimuthal_angle_deg": math.degrees(aligned_azimuthal),
        "post_crystal_coordinate_system": "reflected central-ray frame at q=0",
    }
    return footprint, post_crystal, coordinates, resolved_geometry


def _spectrum_edges(spectrum: TubeSpectrum) -> np.ndarray:
    return np.concatenate(
        (spectrum.bin_lower_keV[:1], spectrum.bin_upper_keV)
    )


def _weighted_correlation(
    first: np.ndarray, second: np.ndarray, weights: np.ndarray
) -> float | None:
    first_variance = wp1.weighted_variance(first, weights)
    second_variance = wp1.weighted_variance(second, weights)
    if first_variance <= 0.0 or second_variance <= 0.0:
        return None
    return float(
        wp1.weighted_covariance(first, second, weights)
        / math.sqrt(first_variance * second_variance)
    )


def analyse_beams(
    source: S4Beam,
    footprint: S4Beam,
    post_crystal: S4Beam,
    sample: S4Beam,
    spectrum: TubeSpectrum,
    resolved_geometry: Mapping[str, Any],
) -> dict[str, Any]:
    """Analyse source/crystal/sample beams without writing files.

    The returned dictionary has a JSON-safe ``summary`` member and NumPy
    ``histograms`` used by CSV/plot writers.
    """
    source_arrays = wp1.beam_arrays(source)
    post_arrays = wp1.beam_arrays(post_crystal)
    sample_arrays = wp1.beam_arrays(sample)
    source_mask = wp1.usable_mask(source_arrays)
    post_mask = wp1.usable_mask(post_arrays)
    sample_mask = wp1.usable_mask(sample_arrays)
    if np.count_nonzero(source_mask) < 10:
        raise RuntimeError("fewer than ten usable source rays")
    if np.count_nonzero(post_mask) < 10:
        raise RuntimeError("fewer than ten usable weighted rays leave the crystal")
    if np.count_nonzero(sample_mask) < 10:
        raise RuntimeError("fewer than ten usable weighted rays reach the sample")

    edges = _spectrum_edges(spectrum)
    source_histogram, _ = np.histogram(
        source_arrays["energy_keV"][source_mask],
        bins=edges,
        weights=source_arrays["weight"][source_mask],
    )
    post_histogram, _ = np.histogram(
        post_arrays["energy_keV"][post_mask],
        bins=edges,
        weights=post_arrays["weight"][post_mask],
    )
    sample_histogram, _ = np.histogram(
        sample_arrays["energy_keV"][sample_mask],
        bins=edges,
        weights=sample_arrays["weight"][sample_mask],
    )
    sample_weights = sample_arrays["weight"][sample_mask]
    sample_energy = sample_arrays["energy_keV"][sample_mask]
    sample_x = sample_arrays["x_m"][sample_mask]
    sample_z = sample_arrays["z_m"][sample_mask]
    sample_spot = wp1.spot_metrics(sample_arrays, 0.0, sample_mask)
    sample_spot["distance_m"] = float(
        resolved_geometry["configured_crystal_to_sample_m"]
    )
    correlation_x = _weighted_correlation(
        sample_energy, sample_x, sample_weights
    )
    correlation_z = _weighted_correlation(
        sample_energy, sample_z, sample_weights
    )
    acceptance = wp1.acceptance_metrics(source, footprint, post_crystal)
    footprint_summary = wp1.footprint_metrics(footprint)
    summary: dict[str, Any] = {
        "acceptance": acceptance,
        "crystal_footprint": footprint_summary,
        "source": {
            "weighted_photons_per_mAs": float(
                np.sum(source_arrays["weight"][source_mask])
            ),
            "weighted_mean_energy_keV": wp1.weighted_mean(
                source_arrays["energy_keV"][source_mask],
                source_arrays["weight"][source_mask],
            ),
            "weighted_sigma_energy_keV": math.sqrt(
                wp1.weighted_variance(
                    source_arrays["energy_keV"][source_mask],
                    source_arrays["weight"][source_mask],
                )
            ),
        },
        "post_crystal": {
            "weighted_photons_per_mAs": float(
                np.sum(post_arrays["weight"][post_mask])
            ),
            "weighted_mean_energy_keV": wp1.weighted_mean(
                post_arrays["energy_keV"][post_mask],
                post_arrays["weight"][post_mask],
            ),
            "weighted_sigma_energy_keV": math.sqrt(
                wp1.weighted_variance(
                    post_arrays["energy_keV"][post_mask],
                    post_arrays["weight"][post_mask],
                )
            ),
        },
        "sample": {
            "weighted_photons_per_mAs": float(np.sum(sample_weights)),
            "weighted_mean_energy_keV": wp1.weighted_mean(
                sample_energy, sample_weights
            ),
            "weighted_sigma_energy_keV": math.sqrt(
                wp1.weighted_variance(sample_energy, sample_weights)
            ),
            "spot": sample_spot,
            "energy_position_correlation_x": correlation_x,
            "energy_position_correlation_z": correlation_z,
        },
    }
    return {
        "summary": summary,
        "histograms": {
            "source_photons_per_mAs": source_histogram,
            "post_crystal_photons_per_mAs": post_histogram,
            "sample_photons_per_mAs": sample_histogram,
        },
    }


def _write_hdf5_group(
    handle: h5py.File,
    name: str,
    beam: S4Beam,
    *,
    description: str,
    coordinate_system: str,
    plane_distance_from_crystal_m: float | None,
) -> None:
    group = handle.create_group(name)
    group.attrs["description"] = description
    group.attrs["coordinate_system"] = coordinate_system
    group.attrs["recommended_selection"] = "status > 0 and weight > 0"
    group.attrs["weight_interpretation"] = (
        "Photon-equivalent weight in photons/mAs; preserve or resample "
        "proportionally for particle transport."
    )
    if plane_distance_from_crystal_m is not None:
        group.attrs["plane_distance_from_crystal_m"] = float(
            plane_distance_from_crystal_m
        )
    units = {
        "x_m": "m",
        "y_m": "m",
        "z_m": "m",
        "dx": "1",
        "dy": "1",
        "dz": "1",
        "energy_keV": "keV",
        "weight": "photons/mAs",
        "status": "positive=valid, negative=lost",
        "ray_id": "1",
    }
    for field, values in wp1.beam_arrays(beam).items():
        dataset = group.create_dataset(
            field,
            data=values,
            compression="gzip",
            compression_opts=4,
            shuffle=True,
        )
        dataset.attrs["units"] = units[field]


def save_phase_space(
    output_path: Path,
    source: S4Beam,
    post_crystal: S4Beam,
    sample: S4Beam,
    metadata: Mapping[str, Any],
) -> None:
    """Write the WP2/WP4-compatible photon-normalized phase-space contract.

    Schema: ``PRISM_SHADOW4_PHASE_SPACE_V1``.  Groups are ``source``,
    ``post_crystal``, and ``sample``.  Every group contains
    ``x_m,y_m,z_m,dx,dy,dz,energy_keV,weight,status,ray_id``; weight is
    photons/mAs.  WP5 should select ``status > 0`` and ``weight > 0`` and
    preserve weights or resample rows proportionally to them.
    """
    resolved_geometry = metadata["geometry"]
    normalization = metadata["normalization"]
    with h5py.File(output_path, "w") as handle:
        handle.attrs["schema"] = PHASE_SPACE_SCHEMA
        handle.attrs["producer"] = str(
            metadata.get("producer", "wp2_tube_source.py")
        )
        handle.attrs["weight_unit"] = "photons/mAs"
        handle.attrs["recommended_selection"] = "status > 0 and weight > 0"
        handle.attrs["metadata_json"] = json.dumps(
            metadata, sort_keys=True, allow_nan=False
        )
        if "downstream_wp5_design_input_approved" in metadata:
            handle.attrs["downstream_wp5_design_input_approved"] = bool(
                metadata["downstream_wp5_design_input_approved"]
            )
        handle.attrs["sampled_solid_angle_sr"] = normalization[
            "sampled_solid_angle_sr"
        ]
        handle.attrs["energy_importance_minimum_keV"] = normalization[
            "energy_importance_minimum_keV"
        ]
        handle.attrs["energy_importance_maximum_keV"] = normalization[
            "energy_importance_maximum_keV"
        ]
        handle.attrs["sample_plane_distance_from_crystal_m"] = (
            resolved_geometry["configured_crystal_to_sample_m"]
        )
        _write_hdf5_group(
            handle,
            "source",
            source,
            description=str(
                metadata.get(
                    "source_group_description",
                    "Factorized W-tube source at the source plane.",
                )
            ),
            coordinate_system="incident central-ray frame at source plane",
            plane_distance_from_crystal_m=None,
        )
        _write_hdf5_group(
            handle,
            "post_crystal",
            post_crystal,
            description="Polychromatic rays immediately after the Ge(880) crystal.",
            coordinate_system="reflected central-ray frame at q=0",
            plane_distance_from_crystal_m=0.0,
        )
        _write_hdf5_group(
            handle,
            "sample",
            sample,
            description="Polychromatic rays at the configured sample plane.",
            coordinate_system="reflected central-ray frame; sample plane is y=0",
            plane_distance_from_crystal_m=resolved_geometry[
                "configured_crystal_to_sample_m"
            ],
        )


def save_spectrum_csv(
    output_path: Path,
    spectrum: TubeSpectrum,
    histograms: Mapping[str, np.ndarray],
    sampled_solid_angle_sr: float,
) -> None:
    """Save complete SpekPy spectrum and traced/post-crystal bin contents."""
    reference_distance_cm = float(
        spectrum.operating_point["reference_distance_cm"]
    )
    full_bin_photons = (
        spectrum.bin_fluence_photons_cm2_mAs
        * reference_distance_cm**2
        * sampled_solid_angle_sr
    )
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        fieldnames = (
            "energy_keV",
            "bin_lower_keV",
            "bin_upper_keV",
            "differential_fluence_photons_cm2_keV_mAs",
            "complete_bin_fluence_photons_cm2_mAs",
            "trace_overlap_keV",
            "trace_bin_fluence_photons_cm2_mAs",
            "complete_bin_photons_per_mAs_in_sampled_solid_angle",
            "sampled_source_photons_per_mAs",
            "post_crystal_photons_per_mAs",
            "sample_photons_per_mAs",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for index, energy in enumerate(spectrum.energy_keV):
            writer.writerow(
                {
                    "energy_keV": float(energy),
                    "bin_lower_keV": float(spectrum.bin_lower_keV[index]),
                    "bin_upper_keV": float(spectrum.bin_upper_keV[index]),
                    "differential_fluence_photons_cm2_keV_mAs": float(
                        spectrum.differential_fluence_photons_cm2_keV_mAs[
                            index
                        ]
                    ),
                    "complete_bin_fluence_photons_cm2_mAs": float(
                        spectrum.bin_fluence_photons_cm2_mAs[index]
                    ),
                    "trace_overlap_keV": float(
                        spectrum.trace_overlap_keV[index]
                    ),
                    "trace_bin_fluence_photons_cm2_mAs": float(
                        spectrum.trace_bin_fluence_photons_cm2_mAs[index]
                    ),
                    "complete_bin_photons_per_mAs_in_sampled_solid_angle": float(
                        full_bin_photons[index]
                    ),
                    "sampled_source_photons_per_mAs": float(
                        histograms["source_photons_per_mAs"][index]
                    ),
                    "post_crystal_photons_per_mAs": float(
                        histograms["post_crystal_photons_per_mAs"][index]
                    ),
                    "sample_photons_per_mAs": float(
                        histograms["sample_photons_per_mAs"][index]
                    ),
                }
            )


def _finite_scatter_indices(
    mask: np.ndarray, maximum: int, seed: int
) -> np.ndarray:
    indices = np.flatnonzero(mask)
    if indices.size <= maximum:
        return indices
    generator = np.random.default_rng(seed)
    return np.sort(generator.choice(indices, size=maximum, replace=False))


def make_diagnostic_plots(
    output_dir: Path,
    spectrum: TubeSpectrum,
    analysis: Mapping[str, Any],
    sample: S4Beam,
    plots_config: Mapping[str, Any],
    seed: int,
    sampled_solid_angle_sr: float,
) -> tuple[Path, Path]:
    """Create the WP2 diagnostic figure, save it, and call ``plt.show()``."""
    import matplotlib.pyplot as plt

    histograms = analysis["histograms"]
    sample_arrays = wp1.beam_arrays(sample)
    sample_mask = wp1.usable_mask(sample_arrays)
    reference_distance_cm = float(
        spectrum.operating_point["reference_distance_cm"]
    )
    complete_bin_photons = (
        spectrum.bin_fluence_photons_cm2_mAs
        * reference_distance_cm**2
        * sampled_solid_angle_sr
    )

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5))
    ax_spectrum, ax_compare, ax_profile, ax_correlation = axes.flat
    ax_spectrum.plot(
        spectrum.energy_keV,
        spectrum.differential_fluence_photons_cm2_keV_mAs,
        lw=0.9,
        color="#4c78a8",
    )
    ax_spectrum.axvspan(
        spectrum.importance_minimum_keV,
        spectrum.importance_maximum_keV,
        color="#f58518",
        alpha=0.2,
        label="ray-traced energy window",
    )
    ax_spectrum.set(
        title="Complete on-axis SpekPy W-tube spectrum",
        xlabel="Photon energy [keV]",
        ylabel=r"Fluence [photons cm$^{-2}$ keV$^{-1}$ mAs$^{-1}$]",
        yscale="log",
    )
    ax_spectrum.legend()

    ax_compare.step(
        spectrum.energy_keV,
        complete_bin_photons,
        where="mid",
        lw=0.8,
        label="complete source spectrum in sampled Ω",
    )
    ax_compare.step(
        spectrum.energy_keV,
        histograms["source_photons_per_mAs"],
        where="mid",
        lw=0.9,
        label="ray-traced source window",
    )
    ax_compare.step(
        spectrum.energy_keV,
        histograms["post_crystal_photons_per_mAs"],
        where="mid",
        lw=1.0,
        label="after Ge(880)",
    )
    ax_compare.set_xlim(
        spectrum.importance_minimum_keV - 0.25,
        spectrum.importance_maximum_keV + 0.25,
    )
    ax_compare.set(
        title="Source versus post-crystal spectrum",
        xlabel="Photon energy [keV]",
        ylabel="Photons/mAs per SpekPy bin",
        yscale="log",
    )
    ax_compare.legend(fontsize=8)

    x_mm = 1.0e3 * sample_arrays["x_m"][sample_mask]
    z_mm = 1.0e3 * sample_arrays["z_m"][sample_mask]
    sample_weights = sample_arrays["weight"][sample_mask]
    profile_bins = int(plots_config["profile_bins"])
    profile, x_edges, z_edges = np.histogram2d(
        x_mm, z_mm, bins=profile_bins, weights=sample_weights
    )
    log_profile = np.full_like(profile, np.nan, dtype=float)
    positive = profile > 0.0
    log_profile[positive] = np.log10(profile[positive])
    mesh = ax_profile.pcolormesh(
        x_edges,
        z_edges,
        log_profile.T,
        cmap="magma",
        shading="auto",
        rasterized=True,
    )
    fig.colorbar(mesh, ax=ax_profile, label=r"$\log_{10}$(photons/mAs/bin)")
    ax_profile.set(
        title="Photon-normalized profile at sample",
        xlabel="Sagittal x [mm]",
        ylabel="Tangential z [mm]",
    )

    scatter_indices = _finite_scatter_indices(
        sample_mask,
        int(plots_config["maximum_scatter_rays"]),
        seed,
    )
    scatter_weights = sample_arrays["weight"][scatter_indices]
    scatter = ax_correlation.scatter(
        sample_arrays["energy_keV"][scatter_indices],
        1.0e3 * sample_arrays["x_m"][scatter_indices],
        c=np.log10(np.maximum(scatter_weights, np.finfo(float).tiny)),
        s=4,
        cmap="viridis",
        rasterized=True,
    )
    fig.colorbar(scatter, ax=ax_correlation, label=r"$\log_{10}$(photons/mAs)")
    correlation = analysis["summary"]["sample"][
        "energy_position_correlation_x"
    ]
    correlation_label = "undefined" if correlation is None else f"{correlation:.4f}"
    ax_correlation.set(
        title=f"Energy-position correlation at sample (r = {correlation_label})",
        xlabel="Photon energy [keV]",
        ylabel="Sagittal x [mm]",
    )

    for axis in axes.flat:
        axis.grid(ls=":", alpha=0.4)
    fig.suptitle("WP2: physically normalized W-tube → Ge(880) trace", fontsize=14)
    fig.tight_layout()
    png_path = output_dir / "wp2_diagnostics.png"
    pdf_path = output_dir / "wp2_diagnostics.pdf"
    fig.savefig(png_path, dpi=250)
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


def scale_weight_for_exposure(
    photons_per_mAs: float | np.ndarray,
    current_mA: float,
    exposure_s: float,
) -> float | np.ndarray:
    """Post-scale photon weights by ``current_mA * exposure_s`` only."""
    if current_mA < 0.0 or exposure_s < 0.0:
        raise ValueError("current and exposure must be nonnegative")
    return photons_per_mAs * current_mA * exposure_s


def _normalization_summary(
    spectrum: TubeSpectrum,
    source_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "weight_unit": "photons/mAs",
        "sampled_solid_angle_sr": source_metadata["sampled_solid_angle_sr"],
        "reference_distance_cm": source_metadata["reference_distance_cm"],
        "energy_importance_minimum_keV": spectrum.importance_minimum_keV,
        "energy_importance_maximum_keV": spectrum.importance_maximum_keV,
        "complete_spectrum_fluence_photons_cm2_mAs": (
            spectrum.total_fluence_photons_cm2_mAs
        ),
        "traced_window_fluence_photons_cm2_mAs": (
            spectrum.traced_fluence_photons_cm2_mAs
        ),
        "traced_fraction_of_total_spectrum": (
            spectrum.traced_fraction_of_total_spectrum
        ),
        "complete_spectrum_photons_per_mAs_in_sampled_solid_angle": (
            source_metadata[
                "complete_spectrum_photons_per_mAs_in_sampled_solid_angle"
            ]
        ),
        "traced_window_photons_per_mAs_in_sampled_solid_angle": (
            source_metadata[
                "traced_window_photons_per_mAs_in_sampled_solid_angle"
            ]
        ),
        "source_weight_invariant": (
            "sum(source weight) equals traced-window photons/mAs in sampled Ω"
        ),
    }


def run_pipeline(
    tube_config: Mapping[str, Any],
    geometry_config: Mapping[str, Any],
    slit_config: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
    output_dir: Path | None = None,
    make_outputs: bool = True,
) -> WP2Run:
    """Run WP2 while preserving reusable source/trace interfaces.

    ``slit_config`` is reserved for the WP3 orchestrator and must be ``None`` in
    this WP2 driver.  WP3 should call :func:`load_or_generate_spectrum`,
    :func:`build_polychromatic_source`, apply aperture masks to a duplicate of
    the returned incident beam, and call :func:`trace_incident_beam`.

    Supported overrides are ``nrays``, ``seed``, ``current_mA``,
    ``exposure_s``, ``cache_dir``, ``force_spectrum_regeneration``,
    ``verbose_shadow4``, and ``make_plots``.
    """
    if slit_config is not None:
        raise ValueError(
            "WP2 does not apply slits; use the public source/trace functions in WP3"
        )
    config = copy.deepcopy(dict(tube_config))
    geometry = copy.deepcopy(dict(geometry_config))
    effective_overrides = {} if overrides is None else dict(overrides)
    allowed_overrides = {
        "nrays",
        "seed",
        "current_mA",
        "exposure_s",
        "cache_dir",
        "force_spectrum_regeneration",
        "verbose_shadow4",
        "make_plots",
    }
    unknown = sorted(set(effective_overrides) - allowed_overrides)
    if unknown:
        raise ValueError(f"unknown WP2 overrides: {', '.join(unknown)}")
    if "nrays" in effective_overrides:
        config["source_phase_space"]["nrays"] = int(
            effective_overrides["nrays"]
        )
    if "seed" in effective_overrides:
        config["source_phase_space"]["seed"] = int(effective_overrides["seed"])
    if "current_mA" in effective_overrides:
        config["reporting"]["current_mA"] = float(
            effective_overrides["current_mA"]
        )
    if "exposure_s" in effective_overrides:
        config["reporting"]["exposure_s"] = float(
            effective_overrides["exposure_s"]
        )
    validate_tube_config(config)

    resolved_output_dir = (
        DEFAULT_OUTPUT_DIR if output_dir is None else Path(output_dir)
    )
    cache_dir_value = effective_overrides.get("cache_dir")
    resolved_cache_dir = (
        resolved_output_dir / "cache"
        if cache_dir_value is None
        else Path(cache_dir_value)
    )
    spectrum = load_or_generate_spectrum(
        config,
        cache_dir=resolved_cache_dir,
        force_regenerate=bool(
            effective_overrides.get("force_spectrum_regeneration", False)
        ),
    )
    source, source_metadata = build_polychromatic_source(config, spectrum)
    source_config = config["source_phase_space"]
    footprint, post_crystal, _, resolved_geometry = trace_incident_beam(
        source,
        geometry,
        reference_energy_keV=float(source_config["reference_energy_keV"]),
        verbose_shadow4=bool(
            effective_overrides.get("verbose_shadow4", False)
        ),
    )
    sample = wp1.propagate_beam(
        post_crystal,
        float(resolved_geometry["configured_crystal_to_sample_m"]),
    )
    analysis = analyse_beams(
        source,
        footprint,
        post_crystal,
        sample,
        spectrum,
        resolved_geometry,
    )
    normalization = _normalization_summary(spectrum, source_metadata)
    reporting = config["reporting"]
    current_mA = float(reporting["current_mA"])
    exposure_s = float(reporting["exposure_s"])
    source_photons_mAs = analysis["summary"]["source"][
        "weighted_photons_per_mAs"
    ]
    post_photons_mAs = analysis["summary"]["post_crystal"][
        "weighted_photons_per_mAs"
    ]
    sample_photons_mAs = analysis["summary"]["sample"][
        "weighted_photons_per_mAs"
    ]
    summary: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": wp1.stable_config_hash(config, geometry),
        "tube_config": config,
        "geometry_config": geometry,
        "geometry": resolved_geometry,
        "spectrum_cache": {
            "path": str(spectrum.cache_path),
            "key": spectrum.cache_key,
            "hit": spectrum.cache_hit,
            "operating_point": spectrum.operating_point,
        },
        "source_sampling": source_metadata,
        "normalization": normalization,
        "analysis": analysis["summary"],
        "reporting_only_scaling": {
            "current_mA": current_mA,
            "exposure_s": exposure_s,
            "source_photons_per_s": source_photons_mAs * current_mA,
            "post_crystal_photons_per_s": post_photons_mAs * current_mA,
            "sample_photons_per_s": sample_photons_mAs * current_mA,
            "source_photons_in_exposure": float(
                scale_weight_for_exposure(
                    source_photons_mAs, current_mA, exposure_s
                )
            ),
            "post_crystal_photons_in_exposure": float(
                scale_weight_for_exposure(
                    post_photons_mAs, current_mA, exposure_s
                )
            ),
            "sample_photons_in_exposure": float(
                scale_weight_for_exposure(
                    sample_photons_mAs, current_mA, exposure_s
                )
            ),
            "invariant": (
                "current/exposure changes do not regenerate SpekPy or SHADOW4"
            ),
        },
        "software": {
            "python": platform.python_version(),
            "spekpy": package_version("spekpy"),
            "shadow4": package_version("shadow4"),
            "crystalpy": package_version("crystalpy"),
            "syned": package_version("syned"),
            "numpy": package_version("numpy"),
            "h5py": package_version("h5py"),
            "matplotlib": package_version("matplotlib"),
        },
        "assumptions": [
            "SpekPy fluence is evaluated on axis at the configured reference distance and 1 mAs.",
            "On-axis radiant intensity is uniform across the explicitly sampled small solid angle.",
            "Energy, source position, and direction are factorized; heel-effect coupling is omitted.",
            "Only the explicit energy-importance window is traced; complete-spectrum fluence is retained separately.",
            "The Ge(880) crystal and geometry are the unchanged WP1 perfect-crystal baseline.",
            "Vacuum propagation is used; windows/air beyond configured SpekPy filtration and all slits are absent.",
            "SHADOW4 column-23 weights are photons/mAs and already include diffraction after the crystal.",
            "Tube current and exposure are reporting-only multipliers; detector dead time and pile-up are absent.",
        ],
        "outputs": {
            "summary_json": None,
            "spectrum_csv": None,
            "phase_space_hdf5": None,
            "plots": [],
        },
    }

    if make_outputs:
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        spectrum_csv_path = resolved_output_dir / "wp2_spectrum.csv"
        phase_space_path = resolved_output_dir / "wp2_phase_space.h5"
        summary_path = resolved_output_dir / "wp2_summary.json"
        save_spectrum_csv(
            spectrum_csv_path,
            spectrum,
            analysis["histograms"],
            float(source_metadata["sampled_solid_angle_sr"]),
        )
        save_phase_space(
            phase_space_path,
            source,
            post_crystal,
            sample,
            summary,
        )
        plot_files: list[str] = []
        make_plots = bool(effective_overrides.get("make_plots", True))
        if make_plots:
            png_path, pdf_path = make_diagnostic_plots(
                resolved_output_dir,
                spectrum,
                analysis,
                sample,
                config["plots"],
                int(source_config["seed"]),
                float(source_metadata["sampled_solid_angle_sr"]),
            )
            plot_files = [str(png_path), str(pdf_path)]
        summary["outputs"] = {
            "summary_json": str(summary_path),
            "spectrum_csv": str(spectrum_csv_path),
            "phase_space_hdf5": str(phase_space_path),
            "plots": plot_files,
        }
        with summary_path.open("w", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")

    return WP2Run(
        summary=summary,
        spectrum=spectrum,
        source=source,
        footprint=footprint,
        post_crystal=post_crystal,
        sample=sample,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    bundled_config = load_json(DEFAULT_TUBE_CONFIG)
    bundled_spectrum = bundled_config["spekpy"]
    source = bundled_config["source_phase_space"]
    importance = bundled_config["energy_importance"]
    reporting = bundled_config["reporting"]
    filtration = ", ".join(
        f"{item['material']}:{item['thickness_mm']} mm"
        for item in bundled_spectrum["filtration"]
    ) or "none"
    parser = argparse.ArgumentParser(
        description=(
            "Generate/cache a realistic W-tube SpekPy spectrum, build a "
            "photon-normalized factorized source, and trace the fixed WP1 "
            "Ge(880) geometry"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Bundled physical defaults: "
            f"target={bundled_spectrum['target']}; "
            f"kVp={bundled_spectrum['kvp']}; "
            f"anode angle={bundled_spectrum['anode_angle_deg']} deg; "
            f"bin={bundled_spectrum['bin_width_keV']} keV; "
            f"reference distance={bundled_spectrum['reference_distance_cm']} cm; "
            f"mAs={bundled_spectrum['mas']}; "
            f"SpekPy={bundled_spectrum['spekpy_version']}; "
            f"filtration={filtration}; "
            f"reference energy={source['reference_energy_keV']} keV; "
            f"importance window={importance['minimum_keV']}-"
            f"{importance['maximum_keV']} keV."
        ),
    )
    parser.add_argument(
        "--tube-config",
        type=Path,
        default=DEFAULT_TUBE_CONFIG,
        help="WP2 JSON tube/source configuration",
    )
    parser.add_argument(
        "--geometry-config",
        type=Path,
        default=DEFAULT_GEOMETRY_CONFIG,
        help="WP1 JSON Ge(880) geometry configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for WP2 CSV, HDF5, JSON, cache, and plots",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="directory for operating-point-keyed SpekPy caches",
    )
    parser.add_argument(
        "--nrays",
        type=int,
        default=argparse.SUPPRESS,
        help=(
            "override ray count; default: selected tube config "
            f"(bundled value {source['nrays']})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=argparse.SUPPRESS,
        help=(
            "override source seed; default: selected tube config "
            f"(bundled value {source['seed']})"
        ),
    )
    parser.add_argument(
        "--current-mA",
        type=float,
        default=argparse.SUPPRESS,
        help=(
            "reporting-only tube current; default: selected tube config "
            f"(bundled value {reporting['current_mA']})"
        ),
    )
    parser.add_argument(
        "--exposure-s",
        type=float,
        default=argparse.SUPPRESS,
        help=(
            "reporting-only exposure; default: selected tube config "
            f"(bundled value {reporting['exposure_s']})"
        ),
    )
    parser.add_argument(
        "--force-spectrum-regeneration",
        action="store_true",
        help="regenerate and atomically replace the matching spectrum cache",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="skip PNG/PDF diagnostics (intended for automated tests)",
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
    overrides: dict[str, Any] = {
        "cache_dir": args.cache_dir,
        "force_spectrum_regeneration": args.force_spectrum_regeneration,
        "verbose_shadow4": args.verbose_shadow4,
        "make_plots": not args.no_plots,
    }
    for name in ("nrays", "seed", "current_mA", "exposure_s"):
        if hasattr(args, name):
            overrides[name] = getattr(args, name)
    try:
        run = run_pipeline(
            load_json(args.tube_config),
            load_json(args.geometry_config),
            overrides=overrides,
            output_dir=args.output_dir,
            make_outputs=True,
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
    ) as error:
        parser.error(str(error))

    summary = run.summary
    normalization = summary["normalization"]
    analysis = summary["analysis"]
    print(
        "SpekPy cache: "
        f"{'hit' if summary['spectrum_cache']['hit'] else 'generated'} "
        f"{summary['spectrum_cache']['path']}"
    )
    print(
        "Spectrum normalization: "
        f"complete={normalization['complete_spectrum_photons_per_mAs_in_sampled_solid_angle']:.6g} "
        "photons/mAs, "
        f"traced window={normalization['traced_window_photons_per_mAs_in_sampled_solid_angle']:.6g} "
        "photons/mAs"
    )
    print(
        "Weighted trace: "
        f"source={analysis['source']['weighted_photons_per_mAs']:.6g}, "
        f"post-crystal={analysis['post_crystal']['weighted_photons_per_mAs']:.6g}, "
        f"sample={analysis['sample']['weighted_photons_per_mAs']:.6g} photons/mAs"
    )
    print("Saved:")
    for key in ("summary_json", "spectrum_csv", "phase_space_hdf5"):
        print(f"  {summary['outputs'][key]}")
    for path in summary["outputs"]["plots"]:
        print(f"  {path}")


if __name__ == "__main__":
    main()
