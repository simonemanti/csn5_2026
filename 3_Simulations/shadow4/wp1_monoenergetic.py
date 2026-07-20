#!/usr/bin/env python3
"""WP1 monoenergetic SHADOW4 trace for a Ge(880) Von Hamos optic.

The local SHADOW4 convention is used throughout: X is sagittal, Y follows the
central ray, and Z is tangential.  The post-crystal and sample phase spaces are
stored in the coordinate system of the reflected central ray.

This is a geometry baseline, not yet a realistic tube or bent-crystal model.
The crystal is a cylindrically curved perfect crystal whose local planes are
parallel to its surface.  Bending strain, fabrication tolerances, slits, air,
and a polychromatic source are deliberately left for later work packages.
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
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import shadow4  # noqa: F401 -- fail early outside the requested environment
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


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_CONFIG = SIMULATION_ROOT / "config" / "wp1_source.json"
DEFAULT_GEOMETRY_CONFIG = SIMULATION_ROOT / "config" / "wp1_geometry.json"
DEFAULT_OUTPUT_DIR = SIMULATION_ROOT / "results" / "wp1"
GAUSSIAN_FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))


def package_version(distribution: str) -> str:
    """Return an installed distribution version without making it mandatory."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError(f"configuration root must be an object: {path}")
    return document


def stable_config_hash(*documents: dict[str, Any]) -> str:
    payload = json.dumps(documents, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_number(
    mapping: dict[str, Any], key: str, *, positive: bool = False
) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key!r} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{key!r} must be finite")
    if positive and value <= 0.0:
        raise ValueError(f"{key!r} must be positive")
    return value


def validate_source_config(config: dict[str, Any]) -> None:
    nrays = config.get("nrays")
    seed = config.get("seed")
    if isinstance(nrays, bool) or not isinstance(nrays, int) or nrays < 100:
        raise ValueError("'nrays' must be an integer of at least 100")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 1:
        raise ValueError("'seed' must be a positive integer")
    require_number(config, "energy_keV", positive=True)

    spatial = str(config.get("spatial_distribution", "")).lower()
    if spatial == "gaussian":
        require_number(config, "sigma_x_m", positive=True)
        require_number(config, "sigma_z_m", positive=True)
    elif spatial == "rectangle":
        require_number(config, "width_x_m", positive=True)
        require_number(config, "height_z_m", positive=True)
    elif spatial != "point":
        raise ValueError(
            "'spatial_distribution' must be point, gaussian, or rectangle"
        )

    angular = str(config.get("angular_distribution", "")).lower()
    if angular == "flat":
        hmin = require_number(config, "horizontal_angle_min_rad")
        hmax = require_number(config, "horizontal_angle_max_rad")
        vmin = require_number(config, "vertical_angle_min_rad")
        vmax = require_number(config, "vertical_angle_max_rad")
        if hmin >= hmax or vmin >= vmax:
            raise ValueError("each angular minimum must be below its maximum")
        if max(abs(hmin), abs(hmax), abs(vmin), abs(vmax)) >= 1.0:
            raise ValueError("source half-angles must be below 1 rad for WP1")
    elif angular == "gaussian":
        require_number(config, "sigma_horizontal_angle_rad", positive=True)
        require_number(config, "sigma_vertical_angle_rad", positive=True)
    elif angular != "collimated":
        raise ValueError(
            "'angular_distribution' must be flat, gaussian, or collimated"
        )

    polarization = require_number(config, "polarization_degree")
    if not 0.0 <= polarization <= 1.0:
        raise ValueError("'polarization_degree' must lie in [0, 1]")


def validate_geometry_config(config: dict[str, Any]) -> None:
    crystal = config.get("crystal")
    distances = config.get("distances")
    focus_scan = config.get("focus_scan")
    plots = config.get("plots")
    if not all(isinstance(item, dict) for item in (crystal, distances, focus_scan, plots)):
        raise ValueError("geometry config requires crystal, distances, focus_scan, and plots objects")

    hkl = crystal.get("miller_indices")
    if (
        not isinstance(hkl, list)
        or len(hkl) != 3
        or any(isinstance(v, bool) or not isinstance(v, int) for v in hkl)
        or hkl == [0, 0, 0]
    ):
        raise ValueError("'miller_indices' must contain three integers other than (000)")
    if str(crystal.get("material", "")) != "Ge":
        raise ValueError("WP1 currently validates only the configured Ge crystal")
    for key in (
        "thickness_m",
        "radius_m",
        "width_sagittal_m",
        "length_tangential_m",
    ):
        require_number(crystal, key, positive=True)
    require_number(crystal, "asymmetry_angle_rad")
    if crystal.get("curvature_direction") != "sagittal":
        raise ValueError("Von Hamos WP1 requires sagittal cylindrical curvature")
    if crystal.get("convexity") != "downward":
        raise ValueError("this verified SHADOW4 layout requires downward convexity")
    if crystal.get("material_constants_library") != "xraylib":
        raise ValueError("WP1 currently supports the xraylib crystal library")
    if not isinstance(crystal.get("use_thick_crystal_approximation"), bool):
        raise ValueError("'use_thick_crystal_approximation' must be boolean")

    for key in ("source_to_crystal_m", "crystal_to_sample_m"):
        if key not in distances:
            raise ValueError(f"distances config is missing {key!r}")
        value = distances.get(key)
        if value is not None:
            require_number(distances, key, positive=True)

    minimum_factor = require_number(
        focus_scan, "minimum_distance_factor", positive=True
    )
    maximum_factor = require_number(
        focus_scan, "maximum_distance_factor", positive=True
    )
    if minimum_factor >= maximum_factor:
        raise ValueError("focus-scan minimum factor must be below maximum factor")
    points = focus_scan.get("points")
    if isinstance(points, bool) or not isinstance(points, int) or points < 5:
        raise ValueError("focus-scan 'points' must be an integer of at least 5")
    bins = plots.get("bins")
    scatter = plots.get("maximum_scatter_rays")
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 20:
        raise ValueError("plot 'bins' must be an integer of at least 20")
    if isinstance(scatter, bool) or not isinstance(scatter, int) or scatter < 100:
        raise ValueError("'maximum_scatter_rays' must be an integer of at least 100")


def diffraction_setup(
    crystal_config: dict[str, Any],
) -> DiffractionSetupXraylib:
    h, k, l = crystal_config["miller_indices"]
    return DiffractionSetupXraylib(
        geometry_type=BraggDiffraction(),
        crystal_name=crystal_config["material"],
        thickness=float(crystal_config["thickness_m"]),
        miller_h=h,
        miller_k=k,
        miller_l=l,
        asymmetry_angle=float(crystal_config["asymmetry_angle_rad"]),
        azimuthal_angle=0.0,
    )


def corrected_bragg_angle_rad(
    crystal_config: dict[str, Any], energy_ev: float
) -> float:
    angle = diffraction_setup(crystal_config).angleBraggCorrected(energy_ev)
    return float(np.asarray(angle).reshape(-1)[0])


def von_hamos_symmetric_arm_m(radius_m: float, bragg_angle_rad: float) -> float:
    """Straight source-crystal or crystal-image arm for symmetric Von Hamos."""
    sine = math.sin(bragg_angle_rad)
    if radius_m <= 0.0 or sine <= 0.0:
        raise ValueError("radius and Bragg-angle sine must be positive")
    return radius_m / sine


def sagittal_image_distance_m(
    source_distance_m: float, radius_m: float, bragg_angle_rad: float
) -> float:
    """Image distance from 1/p + 1/q = 2 sin(theta_B) / R."""
    denominator = 2.0 * math.sin(bragg_angle_rad) / radius_m - 1.0 / source_distance_m
    if denominator <= 0.0:
        raise ValueError(
            "configured source distance gives no positive sagittal image distance"
        )
    return 1.0 / denominator


def build_source(config: dict[str, Any]) -> SourceGeometrical:
    source = SourceGeometrical(
        name="WP1 monoenergetic source",
        nrays=int(config["nrays"]),
        seed=int(config["seed"]),
    )

    spatial = str(config["spatial_distribution"]).lower()
    if spatial == "point":
        source.set_spatial_type_point()
    elif spatial == "gaussian":
        source.set_spatial_type_gaussian(
            sigma_h=float(config["sigma_x_m"]),
            sigma_v=float(config["sigma_z_m"]),
        )
    else:
        source.set_spatial_type_rectangle(
            width=float(config["width_x_m"]),
            height=float(config["height_z_m"]),
        )
    source.set_depth_distribution_off()

    angular = str(config["angular_distribution"]).lower()
    if angular == "flat":
        source.set_angular_distribution_flat(
            hdiv1=float(config["horizontal_angle_min_rad"]),
            hdiv2=float(config["horizontal_angle_max_rad"]),
            vdiv1=float(config["vertical_angle_min_rad"]),
            vdiv2=float(config["vertical_angle_max_rad"]),
        )
    elif angular == "gaussian":
        source.set_angular_distribution_gaussian(
            sigdix=float(config["sigma_horizontal_angle_rad"]),
            sigdiz=float(config["sigma_vertical_angle_rad"]),
        )
    else:
        source.set_angular_distribution_collimated()

    source.set_energy_distribution_singleline(
        1000.0 * float(config["energy_keV"]), unit="eV"
    )
    source.set_polarization(
        polarization_degree=float(config["polarization_degree"]),
        phase_diff=0.0,
        coherent_beam=0,
    )
    return source


def build_crystal(
    config: dict[str, Any], energy_ev: float
) -> S4SphereCrystal:
    h, k, l = config["miller_indices"]
    half_width = 0.5 * float(config["width_sagittal_m"])
    half_length = 0.5 * float(config["length_tangential_m"])
    boundary = Rectangle(
        x_left=-half_width,
        x_right=half_width,
        y_bottom=-half_length,
        y_top=half_length,
    )
    return S4SphereCrystal(
        name=f"{config['material']}({h}{k}{l}) Von Hamos crystal",
        boundary_shape=boundary,
        material=str(config["material"]),
        miller_index_h=h,
        miller_index_k=k,
        miller_index_l=l,
        asymmetry_angle=float(config["asymmetry_angle_rad"]),
        is_thick=int(config["use_thick_crystal_approximation"]),
        thickness=float(config["thickness_m"]),
        f_central=True,
        f_phot_cent=0,
        phot_cent=energy_ev,
        file_refl="",
        f_bragg_a=bool(float(config["asymmetry_angle_rad"])),
        f_ext=0,
        material_constants_library_flag=0,
        radius=float(config["radius_m"]),
        is_cylinder=True,
        cylinder_direction=Direction.SAGITTAL,
        convexity=Convexity.DOWNWARD,
    )


def trace_crystal(
    source_config: dict[str, Any],
    geometry_config: dict[str, Any],
    source_distance_m: float,
    *,
    verbose_shadow4: bool,
) -> tuple[S4Beam, S4Beam, S4Beam, ElementCoordinates]:
    source = build_source(source_config)
    incident_beam = source.get_beam()
    energy_ev = 1000.0 * float(source_config["energy_keV"])
    crystal = build_crystal(geometry_config["crystal"], energy_ev)
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
        input_beam=incident_beam,
    )
    if verbose_shadow4:
        post_crystal, footprint = element.trace_beam()
    else:
        # SHADOW4 0.1.78 emits unconditional per-trace diagnostics.  Keep the
        # normal CLI concise while retaining --verbose-shadow4 for debugging.
        with contextlib.redirect_stdout(io.StringIO()):
            post_crystal, footprint = element.trace_beam()
    return incident_beam, footprint, post_crystal, coordinates


def beam_arrays(beam: S4Beam) -> dict[str, np.ndarray]:
    return {
        "x_m": beam.get_column(1),
        "y_m": beam.get_column(2),
        "z_m": beam.get_column(3),
        "dx": beam.get_column(4),
        "dy": beam.get_column(5),
        "dz": beam.get_column(6),
        "energy_keV": 1.0e-3 * beam.get_column(26),
        "weight": beam.get_column(23),
        # SHADOW flags are floating point and some loss codes are small
        # negative values.  Preserve them instead of truncating to integers.
        "status": beam.get_column(10),
        "ray_id": beam.get_column(12).astype(np.int64),
    }


def usable_mask(arrays: dict[str, np.ndarray]) -> np.ndarray:
    mask = arrays["status"] > 0
    for name in ("x_m", "y_m", "z_m", "dx", "dy", "dz", "weight"):
        mask &= np.isfinite(arrays[name])
    mask &= arrays["weight"] > 0.0
    mask &= np.abs(arrays["dy"]) > 1.0e-15
    return mask


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("no positive finite reflected weight is available")
    return float(np.sum(weights * values) / total)


def weighted_variance(values: np.ndarray, weights: np.ndarray) -> float:
    mean = weighted_mean(values, weights)
    variance = weighted_mean((values - mean) ** 2, weights)
    return max(variance, 0.0)


def weighted_covariance(
    first: np.ndarray, second: np.ndarray, weights: np.ndarray
) -> float:
    first_mean = weighted_mean(first, weights)
    second_mean = weighted_mean(second, weights)
    return weighted_mean(
        (first - first_mean) * (second - second_mean), weights
    )


def reflected_weight_statistics(weights: np.ndarray) -> dict[str, float | int | str]:
    finite_weights = weights[np.isfinite(weights) & (weights > 0.0)]
    total = float(np.sum(finite_weights))
    if finite_weights.size == 0 or total <= 0.0:
        raise ValueError("no positive reflected weights are available")
    descending = np.sort(finite_weights)[::-1]
    cumulative = np.cumsum(descending) / total
    effective = total**2 / float(np.sum(finite_weights**2))
    return {
        "positive_weight_rows": int(finite_weights.size),
        "effective_reflected_rays": effective,
        "rows_carrying_50_percent_of_weight": int(
            np.searchsorted(cumulative, 0.5) + 1
        ),
        "rows_carrying_90_percent_of_weight": int(
            np.searchsorted(cumulative, 0.9) + 1
        ),
        "largest_single_ray_weight_fraction": float(descending[0] / total),
        "interpretation": (
            "Single-seed Monte Carlo diagnostic; repeat seeds before claiming "
            "sub-millimetre focal shifts."
        ),
    }


def projected_coordinates(
    arrays: dict[str, np.ndarray], distance_m: float, mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = (distance_m - arrays["y_m"][mask]) / arrays["dy"][mask]
    x_m = arrays["x_m"][mask] + path * arrays["dx"][mask]
    z_m = arrays["z_m"][mask] + path * arrays["dz"][mask]
    return x_m, z_m, arrays["weight"][mask]


def spot_metrics(
    arrays: dict[str, np.ndarray], distance_m: float, mask: np.ndarray
) -> dict[str, float]:
    x_m, z_m, weights = projected_coordinates(arrays, distance_m, mask)
    sigma_x_m = math.sqrt(weighted_variance(x_m, weights))
    sigma_z_m = math.sqrt(weighted_variance(z_m, weights))
    total_weight = float(np.sum(weights))
    effective_rays = total_weight**2 / float(np.sum(weights**2))
    return {
        "distance_m": float(distance_m),
        "centroid_x_m": weighted_mean(x_m, weights),
        "centroid_z_m": weighted_mean(z_m, weights),
        "sigma_x_m": sigma_x_m,
        "sigma_z_m": sigma_z_m,
        "gaussian_equivalent_fwhm_x_m": GAUSSIAN_FWHM_FACTOR * sigma_x_m,
        "gaussian_equivalent_fwhm_z_m": GAUSSIAN_FWHM_FACTOR * sigma_z_m,
        "total_weight": total_weight,
        "effective_weighted_rays": effective_rays,
    }


def weighted_sagittal_focus_m(
    arrays: dict[str, np.ndarray], mask: np.ndarray
) -> float:
    """Return the plane minimizing weighted sagittal RMS width exactly."""
    weights = arrays["weight"][mask]
    slopes = arrays["dx"][mask] / arrays["dy"][mask]
    intercepts = arrays["x_m"][mask] - arrays["y_m"][mask] * slopes
    slope_variance = weighted_variance(slopes, weights)
    if slope_variance <= 0.0:
        raise ValueError("the reflected beam has no sagittal angular spread")
    return -weighted_covariance(intercepts, slopes, weights) / slope_variance


def make_focus_scan(
    arrays: dict[str, np.ndarray],
    mask: np.ndarray,
    center_distance_m: float,
    scan_config: dict[str, Any],
) -> list[dict[str, float]]:
    distances = np.linspace(
        float(scan_config["minimum_distance_factor"]) * center_distance_m,
        float(scan_config["maximum_distance_factor"]) * center_distance_m,
        int(scan_config["points"]),
    )
    return [spot_metrics(arrays, float(distance), mask) for distance in distances]


def acceptance_metrics(
    incident: S4Beam, footprint: S4Beam, post_crystal: S4Beam
) -> dict[str, float | int]:
    incident_arrays = beam_arrays(incident)
    footprint_arrays = beam_arrays(footprint)
    post_arrays = beam_arrays(post_crystal)
    input_mask = (
        (incident_arrays["status"] > 0)
        & np.isfinite(incident_arrays["weight"])
        & (incident_arrays["weight"] > 0.0)
    )
    geometric_mask = footprint_arrays["status"] > 0
    reflected_mask = usable_mask(post_arrays)
    input_weight = float(np.sum(incident_arrays["weight"][input_mask]))
    accepted_weight = float(np.sum(post_arrays["weight"][reflected_mask]))
    geometric_count = int(np.count_nonzero(geometric_mask))
    total_rays = int(incident_arrays["status"].size)
    geometric_input_weight = float(
        np.sum(incident_arrays["weight"][geometric_mask])
    )
    geometric_fraction = geometric_count / total_rays
    geometric_weight_fraction = geometric_input_weight / input_weight
    accepted_fraction = accepted_weight / input_weight
    rejected_fraction = 1.0 - accepted_fraction
    if not 0.0 <= accepted_fraction <= 1.0 + 1.0e-12:
        raise RuntimeError("unphysical weighted crystal acceptance outside [0, 1]")
    if accepted_fraction > geometric_weight_fraction + 1.0e-12:
        raise RuntimeError("reflected weight exceeds geometrically intercepted weight")
    return {
        "launched_rays": total_rays,
        "geometrically_intercepted_rays": geometric_count,
        "geometrically_rejected_rays": total_rays - geometric_count,
        "geometric_intercepted_fraction": geometric_fraction,
        "geometric_rejected_fraction": 1.0 - geometric_fraction,
        "geometrically_intercepted_incident_weight": geometric_input_weight,
        "geometrically_intercepted_weight_fraction": geometric_weight_fraction,
        "exclusive_geometric_miss_fraction": 1.0 - geometric_weight_fraction,
        "exclusive_diffraction_loss_after_intercept_fraction": (
            geometric_weight_fraction - accepted_fraction
        ),
        "exclusive_reflected_fraction": accepted_fraction,
        "incident_weight": input_weight,
        "accepted_reflected_weight": accepted_weight,
        "weighted_accepted_fraction": accepted_fraction,
        "weighted_rejected_fraction": rejected_fraction,
        "mean_reflectivity_for_geometrically_intercepted_rays": (
            accepted_weight / geometric_input_weight
            if geometric_input_weight > 0.0
            else 0.0
        ),
    }


def footprint_metrics(footprint: S4Beam) -> dict[str, float]:
    arrays = beam_arrays(footprint)
    geometric_mask = (
        (arrays["status"] > 0)
        & np.isfinite(arrays["x_m"])
        & np.isfinite(arrays["y_m"])
    )
    weights = np.where(
        np.isfinite(arrays["weight"]) & (arrays["weight"] > 0.0),
        arrays["weight"],
        0.0,
    )
    weighted_mask = geometric_mask & (weights > 0.0)
    return {
        "geometric_centroid_sagittal_x_m": float(
            np.mean(arrays["x_m"][geometric_mask])
        ),
        "geometric_centroid_tangential_y_m": float(
            np.mean(arrays["y_m"][geometric_mask])
        ),
        "geometric_sigma_sagittal_x_m": float(
            np.std(arrays["x_m"][geometric_mask])
        ),
        "geometric_sigma_tangential_y_m": float(
            np.std(arrays["y_m"][geometric_mask])
        ),
        "geometric_minimum_sagittal_x_m": float(
            np.min(arrays["x_m"][geometric_mask])
        ),
        "geometric_maximum_sagittal_x_m": float(
            np.max(arrays["x_m"][geometric_mask])
        ),
        "geometric_minimum_tangential_y_m": float(
            np.min(arrays["y_m"][geometric_mask])
        ),
        "geometric_maximum_tangential_y_m": float(
            np.max(arrays["y_m"][geometric_mask])
        ),
        "reflected_weighted_centroid_sagittal_x_m": weighted_mean(
            arrays["x_m"][weighted_mask], weights[weighted_mask]
        ),
        "reflected_weighted_centroid_tangential_y_m": weighted_mean(
            arrays["y_m"][weighted_mask], weights[weighted_mask]
        ),
        "reflected_weighted_sigma_sagittal_x_m": math.sqrt(
            weighted_variance(
                arrays["x_m"][weighted_mask], weights[weighted_mask]
            )
        ),
        "reflected_weighted_sigma_tangential_y_m": math.sqrt(
            weighted_variance(
                arrays["y_m"][weighted_mask], weights[weighted_mask]
            )
        ),
    }


def propagate_beam(beam: S4Beam, distance_m: float) -> S4Beam:
    propagated = beam.duplicate()
    propagated.retrace(distance_m, resetY=True)
    return propagated


def write_hdf5_group(
    handle: h5py.File,
    name: str,
    beam: S4Beam,
    description: str,
    coordinate_system: str,
    plane_distance_from_crystal_m: float | None,
) -> None:
    group = handle.create_group(name)
    group.attrs["description"] = description
    group.attrs["coordinate_system"] = coordinate_system
    group.attrs["recommended_selection"] = "status > 0 and weight > 0"
    group.attrs["weight_interpretation"] = (
        "Resample rows proportionally to weight; do not count each valid row equally."
    )
    if plane_distance_from_crystal_m is not None:
        group.attrs["plane_distance_from_crystal_m"] = plane_distance_from_crystal_m
    arrays = beam_arrays(beam)
    units = {
        "x_m": "m",
        "y_m": "m",
        "z_m": "m",
        "dx": "1",
        "dy": "1",
        "dz": "1",
        "energy_keV": "keV",
        "weight": "relative photon weight",
        "status": "1=valid, negative=lost",
        "ray_id": "1",
    }
    for field, values in arrays.items():
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
    footprint: S4Beam,
    post_crystal: S4Beam,
    sample: S4Beam,
    metadata: dict[str, Any],
) -> None:
    with h5py.File(output_path, "w") as handle:
        handle.attrs["schema"] = "OLTRE_SHADOW4_PHASE_SPACE_V1"
        handle.attrs["metadata_json"] = json.dumps(metadata, sort_keys=True)
        handle.attrs["weight_interpretation"] = (
            "For particle transport, select status > 0 and resample rows "
            "with probability proportional to weight."
        )
        resolved = metadata["resolved_geometry"]
        handle.attrs["energy_keV"] = metadata["source_config"]["energy_keV"]
        handle.attrs["corrected_bragg_angle_deg"] = resolved[
            "corrected_bragg_angle_deg"
        ]
        handle.attrs["source_to_crystal_m"] = resolved["source_to_crystal_m"]
        handle.attrs["sample_plane_distance_from_crystal_m"] = resolved[
            "configured_crystal_to_sample_m"
        ]
        handle.attrs["weighted_sagittal_focus_distance_m"] = resolved[
            "weighted_sagittal_focus_distance_m"
        ]
        write_hdf5_group(
            handle,
            "crystal_footprint",
            footprint,
            "Ray intercepts on the curved crystal after diffraction weighting.",
            "local crystal surface frame",
            None,
        )
        write_hdf5_group(
            handle,
            "post_crystal",
            post_crystal,
            "Rays at q=0 immediately after the crystal reference transformation.",
            "reflected central-ray frame",
            0.0,
        )
        write_hdf5_group(
            handle,
            "sample",
            sample,
            "Rays at the configured sample plane.",
            "reflected central-ray frame; sample plane is y=0",
            float(resolved["configured_crystal_to_sample_m"]),
        )


def save_focus_csv(path: Path, rows: list[dict[str, float]]) -> None:
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def finite_scatter_indices(
    mask: np.ndarray, maximum: int, seed: int
) -> np.ndarray:
    indices = np.flatnonzero(mask)
    if indices.size <= maximum:
        return indices
    generator = np.random.default_rng(seed)
    return np.sort(generator.choice(indices, size=maximum, replace=False))


def central_layout_coordinates(
    source_distance_m: float,
    sample_distance_m: float,
    bragg_angle_rad: float,
) -> dict[str, np.ndarray | float]:
    """Return central-ray geometry in the local crystal (x, y, z) frame.

    The crystal tangent plane is z=0 at its centre.  SHADOW4's aligned
    symmetric Bragg geometry places the source and reflected image on the same
    side of that plane.  Both arms lie in the y-z diffraction plane; x is the
    sagittal direction in which the cylindrical surface is curved.
    """
    if source_distance_m <= 0.0 or sample_distance_m <= 0.0:
        raise ValueError("source and sample distances must be positive")
    if not 0.0 < bragg_angle_rad < 0.5 * math.pi:
        raise ValueError("Bragg angle must lie between zero and pi/2")

    cosine = math.cos(bragg_angle_rad)
    sine = math.sin(bragg_angle_rad)
    incident_direction = np.array([0.0, cosine, -sine])
    outgoing_direction = np.array([0.0, cosine, sine])
    source = -source_distance_m * incident_direction
    crystal = np.zeros(3)
    sample = sample_distance_m * outgoing_direction
    surface_normal = np.array([0.0, 0.0, 1.0])
    return {
        "source_m": source,
        "crystal_m": crystal,
        "sample_m": sample,
        "incident_direction": incident_direction,
        "outgoing_direction": outgoing_direction,
        "surface_normal": surface_normal,
        "deflection_angle_rad": 2.0 * bragg_angle_rad,
    }


def make_geometry_plots(
    output_dir: Path,
    crystal_config: dict[str, Any],
    source_distance_m: float,
    sample_distance_m: float,
    focus_distance_m: float,
    bragg_angle_rad: float,
    crystal_label: str,
    energy_keV: float,
) -> tuple[Path, Path]:
    """Draw the central-ray layout and curved-crystal surface schematic."""
    import matplotlib.pyplot as plt

    layout = central_layout_coordinates(
        source_distance_m, sample_distance_m, bragg_angle_rad
    )
    source = np.asarray(layout["source_m"])
    crystal = np.asarray(layout["crystal_m"])
    sample = np.asarray(layout["sample_m"])
    outgoing = np.asarray(layout["outgoing_direction"])
    focus = focus_distance_m * outgoing

    radius_m = float(crystal_config["radius_m"])
    width_m = float(crystal_config["width_sagittal_m"])
    length_m = float(crystal_config["length_tangential_m"])
    half_width = 0.5 * width_m
    half_length = 0.5 * length_m

    fig = plt.figure(figsize=(15.0, 6.5))
    ax_layout = fig.add_subplot(1, 2, 1)
    ax_surface = fig.add_subplot(1, 2, 2, projection="3d")

    # Scattering plane: the crystal is at the origin of its local frame.
    ax_layout.plot(
        [source[1], crystal[1]], [source[2], crystal[2]],
        color="#4c78a8", lw=2.2, label="Incident central ray",
    )
    ax_layout.plot(
        [crystal[1], sample[1]], [crystal[2], sample[2]],
        color="#e45756", lw=2.2, label="Reflected central ray",
    )
    ax_layout.plot(
        [crystal[1], focus[1]], [crystal[2], focus[2]],
        color="#f2cf5b", lw=1.6, ls="--", label="Weighted sagittal focus",
    )
    tangent_half_length = max(half_length, 0.035 * (source_distance_m + sample_distance_m))
    ax_layout.plot(
        [-tangent_half_length, tangent_half_length], [0.0, 0.0],
        color="black", lw=4.0, solid_capstyle="round", label="Crystal tangent",
    )
    normal_length = 0.18 * max(source_distance_m, sample_distance_m)
    ax_layout.arrow(
        0.0, 0.0, 0.0, normal_length,
        width=0.0015 * normal_length, head_width=0.035 * normal_length,
        head_length=0.06 * normal_length, color="#54a24b",
        length_includes_head=True,
    )
    ax_layout.scatter(
        [source[1], crystal[1], sample[1]],
        [source[2], crystal[2], sample[2]],
        c=["#4c78a8", "black", "#e45756"], s=[65, 65, 65], zorder=5,
    )
    ax_layout.annotate("Source", (source[1], source[2]), xytext=(6, -18), textcoords="offset points")
    ax_layout.annotate("Crystal", (0.0, 0.0), xytext=(6, -18), textcoords="offset points")
    ax_layout.annotate("Sample", (sample[1], sample[2]), xytext=(6, -18), textcoords="offset points")
    ax_layout.annotate("Surface normal", (0.0, normal_length), xytext=(6, 0), textcoords="offset points")
    ax_layout.text(
        0.03, 0.97,
        rf"$\theta_B={math.degrees(bragg_angle_rad):.3f}^\circ$" "\n"
        rf"deflection $=2\theta_B={2.0 * math.degrees(bragg_angle_rad):.3f}^\circ$" "\n"
        f"p = {source_distance_m:.4f} m\nq = {sample_distance_m:.4f} m\n"
        f"weighted focus = {focus_distance_m:.4f} m",
        transform=ax_layout.transAxes, va="top",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9},
    )
    ax_layout.set(
        title="Central-ray layout in the diffraction plane",
        xlabel="Local crystal y [m]",
        ylabel="Local crystal z [m]",
    )
    ax_layout.set_aspect("equal", adjustable="datalim")
    ax_layout.grid(ls=":", alpha=0.45)
    ax_layout.legend(loc="lower right", fontsize=8)

    # The sagittally bent crystal is a cylindrical ribbon with its axis along y.
    x = np.linspace(-half_width, half_width, 121)
    y = np.linspace(-half_length, half_length, 31)
    xx, yy = np.meshgrid(x, y)
    zz_line = radius_m - np.sqrt(np.maximum(radius_m**2 - x**2, 0.0))
    zz = np.broadcast_to(zz_line, xx.shape)
    ax_surface.plot_surface(
        xx * 1.0e3, yy * 1.0e3, zz * 1.0e3,
        cmap="viridis", alpha=0.82, linewidth=0.15, edgecolor="black",
    )
    ax_surface.plot(
        x * 1.0e3, np.zeros_like(x), zz_line * 1.0e3,
        color="black", lw=2.2, label="Sagittal section",
    )
    ax_surface.set(
        title="Sagittally curved crystal (local surface)",
        xlabel="Sagittal x [mm]",
        ylabel="Tangential y [mm]",
        zlabel="Surface sag z [mm]",
    )
    ax_surface.text2D(
        0.03, 0.96,
        f"{crystal_label}\nR = {1.0e3 * radius_m:.1f} mm\n"
        f"size = {1.0e3 * width_m:.1f} × {1.0e3 * length_m:.1f} mm²",
        transform=ax_surface.transAxes, va="top",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9},
    )
    ax_surface.view_init(elev=24.0, azim=-58.0)
    ax_surface.set_box_aspect((max(width_m, 1e-9), max(length_m, 1e-9), max(float(np.ptp(zz_line)), 0.15 * width_m)))

    fig.suptitle(
        f"WP1 geometry: {energy_keV:g} keV {crystal_label} Von Hamos baseline",
        fontsize=14,
    )
    fig.text(
        0.5, 0.015,
        "Geometry schematic in the local crystal frame; dimensions are physical, rendering is not a mechanical CAD model.",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 0.95))
    png_path = output_dir / "wp1_geometry.png"
    pdf_path = output_dir / "wp1_geometry.pdf"
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


def make_plots(
    output_dir: Path,
    footprint: S4Beam,
    post_crystal: S4Beam,
    sample: S4Beam,
    focus_scan: list[dict[str, float]],
    focus_distance_m: float,
    acceptance: dict[str, float | int],
    plot_config: dict[str, Any],
    seed: int,
    energy_keV: float,
    crystal_label: str,
) -> tuple[Path, Path]:
    import matplotlib.pyplot as plt

    footprint_arrays = beam_arrays(footprint)
    post_arrays = beam_arrays(post_crystal)
    sample_arrays = beam_arrays(sample)
    max_scatter = int(plot_config["maximum_scatter_rays"])
    bins = int(plot_config["bins"])

    fig, axes = plt.subplots(2, 3, figsize=(15.0, 9.0))
    ax_footprint, ax_post, ax_direction, ax_focus, ax_sample, ax_acceptance = axes.flat

    footprint_mask = (
        (footprint_arrays["status"] > 0)
        & np.isfinite(footprint_arrays["x_m"])
        & np.isfinite(footprint_arrays["y_m"])
        & np.isfinite(footprint_arrays["weight"])
        & (footprint_arrays["weight"] > 0.0)
    )
    footprint_indices = finite_scatter_indices(footprint_mask, max_scatter, seed)
    footprint_colors = np.log10(
        np.maximum(footprint_arrays["weight"][footprint_indices], 1.0e-20)
    )
    scatter = ax_footprint.scatter(
        1.0e3 * footprint_arrays["x_m"][footprint_indices],
        1.0e3 * footprint_arrays["y_m"][footprint_indices],
        c=footprint_colors,
        s=2,
        cmap="viridis",
        rasterized=True,
    )
    fig.colorbar(scatter, ax=ax_footprint, label=r"$\log_{10}$(ray weight)")
    ax_footprint.set(
        title="Crystal footprint (color: reflected weight)",
        xlabel="Sagittal crystal coordinate x [mm]",
        ylabel="Tangential crystal coordinate y [mm]",
    )

    post_mask = usable_mask(post_arrays)
    post_indices = finite_scatter_indices(post_mask, max_scatter, seed + 1)
    post_colors = np.log10(np.maximum(post_arrays["weight"][post_indices], 1.0e-20))
    scatter = ax_post.scatter(
        1.0e3 * post_arrays["x_m"][post_indices],
        1.0e3 * post_arrays["z_m"][post_indices],
        c=post_colors,
        s=2,
        cmap="viridis",
        rasterized=True,
    )
    fig.colorbar(scatter, ax=ax_post, label=r"$\log_{10}$(ray weight)")
    ax_post.set(
        title="Ray distribution immediately after crystal",
        xlabel="x [mm]",
        ylabel="z [mm]",
    )

    angle_x_mrad = 1.0e3 * np.arctan2(
        post_arrays["dx"][post_indices], post_arrays["dy"][post_indices]
    )
    angle_z_mrad = 1.0e3 * np.arctan2(
        post_arrays["dz"][post_indices], post_arrays["dy"][post_indices]
    )
    scatter = ax_direction.scatter(
        angle_x_mrad,
        angle_z_mrad,
        c=post_colors,
        s=2,
        cmap="viridis",
        rasterized=True,
    )
    fig.colorbar(scatter, ax=ax_direction, label=r"$\log_{10}$(ray weight)")
    ax_direction.set(
        title="Reflected directions",
        xlabel=r"$\arctan(d_x/d_y)$ [mrad]",
        ylabel=r"$\arctan(d_z/d_y)$ [mrad]",
    )

    scan_distance_m = np.array([row["distance_m"] for row in focus_scan])
    scan_sigma_x_um = 1.0e6 * np.array([row["sigma_x_m"] for row in focus_scan])
    scan_sigma_z_um = 1.0e6 * np.array([row["sigma_z_m"] for row in focus_scan])
    ax_focus.plot(scan_distance_m, scan_sigma_x_um, label=r"$\sigma_x$ (sagittal)")
    ax_focus.plot(scan_distance_m, scan_sigma_z_um, label=r"$\sigma_z$ (tangential)")
    ax_focus.axvline(
        focus_distance_m,
        color="black",
        ls="--",
        lw=1.0,
        label=f"RMS focus = {focus_distance_m:.4f} m",
    )
    ax_focus.set(
        title="Longitudinal focal scan",
        xlabel="Distance after crystal [m]",
        ylabel="Weighted RMS spot size [µm]",
        yscale="log",
    )
    ax_focus.legend(fontsize=8)

    sample_mask = usable_mask(sample_arrays)
    sample_x_mm = 1.0e3 * sample_arrays["x_m"][sample_mask]
    sample_z_mm = 1.0e3 * sample_arrays["z_m"][sample_mask]
    sample_weights = sample_arrays["weight"][sample_mask]
    histogram, x_edges, z_edges = np.histogram2d(
        sample_x_mm,
        sample_z_mm,
        bins=bins,
        weights=sample_weights,
    )
    log_histogram = np.full_like(histogram, np.nan, dtype=float)
    positive = histogram > 0.0
    log_histogram[positive] = np.log10(histogram[positive])
    mesh = ax_sample.pcolormesh(
        x_edges,
        z_edges,
        log_histogram.T,
        cmap="magma",
        shading="auto",
        rasterized=True,
    )
    fig.colorbar(mesh, ax=ax_sample, label=r"$\log_{10}$(weighted counts/bin)")
    ax_sample.set(
        title="2D beam profile at sample (x focused only)",
        xlabel="x [mm]",
        ylabel="z [mm]",
    )

    labels = ["Geometric\nmiss", "Diffraction loss\nafter hit", "Reflected"]
    values = [
        float(acceptance["exclusive_geometric_miss_fraction"]),
        float(acceptance["exclusive_diffraction_loss_after_intercept_fraction"]),
        float(acceptance["exclusive_reflected_fraction"]),
    ]
    bars = ax_acceptance.bar(labels, values, color=["#9d9da0", "#e45756", "#54a24b"])
    for bar, value in zip(bars, values):
        ax_acceptance.text(
            bar.get_x() + 0.5 * bar.get_width(),
            min(value + 0.025, 1.035),
            f"{100.0 * value:.4g}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax_acceptance.set(
        title="Exclusive throughput accounting",
        ylabel="Fraction of launched photon weight",
        ylim=(0.0, 1.08),
    )

    for axis in axes.flat:
        axis.grid(ls=":", alpha=0.45)
    fig.suptitle(
        f"WP1: {energy_keV:g} keV {crystal_label} Von Hamos baseline",
        fontsize=14,
    )
    fig.tight_layout()
    png_path = output_dir / "wp1_diagnostics.png"
    pdf_path = output_dir / "wp1_diagnostics.pdf"
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


def run_simulation(args: argparse.Namespace) -> dict[str, Any]:
    source_config = load_json(args.source_config)
    geometry_config = load_json(args.geometry_config)
    if getattr(args, "nrays", None) is not None:
        source_config["nrays"] = args.nrays
    if getattr(args, "seed", None) is not None:
        source_config["seed"] = args.seed
    if getattr(args, "energy_keV", None) is not None:
        source_config["energy_keV"] = args.energy_keV
    if getattr(args, "focal_scan_points", None) is not None:
        geometry_config["focus_scan"]["points"] = args.focal_scan_points
    validate_source_config(source_config)
    validate_geometry_config(geometry_config)

    crystal_config = geometry_config["crystal"]
    distance_config = geometry_config["distances"]
    energy_ev = 1000.0 * float(source_config["energy_keV"])
    bragg_angle_rad = corrected_bragg_angle_rad(crystal_config, energy_ev)
    radius_m = float(crystal_config["radius_m"])
    symmetric_arm_m = von_hamos_symmetric_arm_m(radius_m, bragg_angle_rad)
    source_distance_m = (
        symmetric_arm_m
        if distance_config["source_to_crystal_m"] is None
        else float(distance_config["source_to_crystal_m"])
    )
    predicted_image_m = sagittal_image_distance_m(
        source_distance_m, radius_m, bragg_angle_rad
    )
    sample_distance_m = (
        predicted_image_m
        if distance_config["crystal_to_sample_m"] is None
        else float(distance_config["crystal_to_sample_m"])
    )

    incident, footprint, post_crystal, coordinates = trace_crystal(
        source_config,
        geometry_config,
        source_distance_m,
        verbose_shadow4=args.verbose_shadow4,
    )
    post_arrays = beam_arrays(post_crystal)
    reflected_mask = usable_mask(post_arrays)
    if np.count_nonzero(reflected_mask) < 10:
        raise RuntimeError("fewer than ten usable weighted rays leave the crystal")
    statistical_quality = reflected_weight_statistics(
        post_arrays["weight"][reflected_mask]
    )

    focus_distance_m = weighted_sagittal_focus_m(post_arrays, reflected_mask)
    focus_scan = make_focus_scan(
        post_arrays,
        reflected_mask,
        predicted_image_m,
        geometry_config["focus_scan"],
    )
    focus_metrics = spot_metrics(post_arrays, focus_distance_m, reflected_mask)
    sample_metrics = spot_metrics(post_arrays, sample_distance_m, reflected_mask)
    acceptance = acceptance_metrics(incident, footprint, post_crystal)
    footprint_summary = footprint_metrics(footprint)
    sample_beam = propagate_beam(post_crystal, sample_distance_m)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    phase_space_path = args.output_dir / "wp1_phase_space.h5"
    focus_csv_path = args.output_dir / "wp1_focal_scan.csv"
    summary_path = args.output_dir / "wp1_summary.json"
    save_focus_csv(focus_csv_path, focus_scan)

    aligned_incident, aligned_outgoing, aligned_azimuthal = coordinates.get_angles()
    crystal_label = (
        f"{crystal_config['material']}"
        f"({''.join(str(index) for index in crystal_config['miller_indices'])})"
    )
    resolved_geometry = {
        "crystal_label": crystal_label,
        "corrected_bragg_angle_deg": math.degrees(bragg_angle_rad),
        "central_deflection_angle_deg": 2.0 * math.degrees(bragg_angle_rad),
        "von_hamos_symmetric_arm_m": symmetric_arm_m,
        "source_to_crystal_m": source_distance_m,
        "paraxial_predicted_crystal_to_focus_m": predicted_image_m,
        "weighted_sagittal_focus_distance_m": focus_distance_m,
        "configured_crystal_to_sample_m": sample_distance_m,
        "sample_plane_orientation": (
            "perpendicular to the reflected central ray in the local output frame"
        ),
        "aligned_incident_angle_to_normal_deg": math.degrees(aligned_incident),
        "aligned_outgoing_angle_to_normal_deg": math.degrees(aligned_outgoing),
        "aligned_azimuthal_angle_deg": math.degrees(aligned_azimuthal),
    }
    software = {
        "python": platform.python_version(),
        "shadow4": package_version("shadow4"),
        "crystalpy": package_version("crystalpy"),
        "syned": package_version("syned"),
        "numpy": package_version("numpy"),
        "h5py": package_version("h5py"),
        "matplotlib": package_version("matplotlib"),
    }
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": [str(Path(sys.executable)), *sys.argv],
        "config_sha256": stable_config_hash(source_config, geometry_config),
        "source_config": source_config,
        "geometry_config": geometry_config,
        "resolved_geometry": resolved_geometry,
        "analysis": {
            "acceptance": acceptance,
            "focus": focus_metrics,
            "sample_spot": sample_metrics,
            "crystal_footprint": footprint_summary,
            "statistical_quality": statistical_quality,
        },
        "software": software,
        "coordinate_convention": {
            "source_and_output": "x=sagittal, y=central-ray axis, z=tangential",
            "crystal_footprint": "local curved-surface frame",
        },
    }
    save_phase_space(
        phase_space_path,
        footprint,
        post_crystal,
        sample_beam,
        metadata,
    )

    plot_files: list[str] = []
    if not args.no_plots:
        png_path, pdf_path = make_plots(
            args.output_dir,
            footprint,
            post_crystal,
            sample_beam,
            focus_scan,
            focus_distance_m,
            acceptance,
            geometry_config["plots"],
            int(source_config["seed"]),
            float(source_config["energy_keV"]),
            crystal_label,
        )
        geometry_png_path, geometry_pdf_path = make_geometry_plots(
            args.output_dir,
            crystal_config,
            source_distance_m,
            sample_distance_m,
            focus_distance_m,
            bragg_angle_rad,
            crystal_label,
            float(source_config["energy_keV"]),
        )
        plot_files = [
            str(png_path),
            str(pdf_path),
            str(geometry_png_path),
            str(geometry_pdf_path),
        ]

    summary: dict[str, Any] = {
        **metadata,
        "assumptions": [
            "The source is monoenergetic and has unit relative weight per launched ray.",
            f"The {crystal_label} crystal is symmetric, perfect, and cylindrically curved sagittally.",
            "Crystal planes remain locally parallel to the curved surface; bending strain is absent.",
            "Vacuum propagation is used; slits, windows, air, and absolute source flux are absent.",
            "Throughput fractions are conditional on the configured normalized source phase space.",
            "Only x is focused; z is the flat tangential direction in this Von Hamos model.",
            "With thick-crystal mode enabled, configured thickness is metadata rather than a scan variable.",
            "Valid phase-space rows must be sampled proportionally to weight for particle transport.",
        ],
        "geometry": resolved_geometry,
        "acceptance": acceptance,
        "crystal_footprint": footprint_summary,
        "statistical_quality": statistical_quality,
        "focus": {
            **focus_metrics,
            "metric": "plane minimizing intensity-weighted sagittal RMS sigma_x",
            "inside_configured_scan": bool(
                focus_scan[0]["distance_m"]
                <= focus_distance_m
                <= focus_scan[-1]["distance_m"]
            ),
            "difference_from_paraxial_prediction_m": (
                focus_distance_m - predicted_image_m
            ),
        },
        "sample_spot": {
            **sample_metrics,
            "focused_axis": "x (sagittal)",
            "unfocused_axis": "z (tangential)",
        },
        "outputs": {
            "summary_json": str(summary_path),
            "phase_space_hdf5": str(phase_space_path),
            "focal_scan_csv": str(focus_csv_path),
            "plots": plot_files,
        },
    }
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    bundled_source = load_json(DEFAULT_SOURCE_CONFIG)
    bundled_geometry = load_json(DEFAULT_GEOMETRY_CONFIG)
    parser = argparse.ArgumentParser(
        description=(
            "Trace a configurable monoenergetic source through a sagittally "
            "curved perfect Ge(880) crystal in symmetric Von Hamos geometry"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source-config",
        type=Path,
        default=DEFAULT_SOURCE_CONFIG,
        help="JSON source configuration",
    )
    parser.add_argument(
        "--geometry-config",
        type=Path,
        default=DEFAULT_GEOMETRY_CONFIG,
        help="JSON geometry configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for phase space, summary, CSV, and plots",
    )
    parser.add_argument(
        "--nrays",
        type=int,
        default=argparse.SUPPRESS,
        help=(
            "override the ray count; default: selected source config "
            f"(bundled value {bundled_source['nrays']})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=argparse.SUPPRESS,
        help=(
            "override the random seed; default: selected source config "
            f"(bundled value {bundled_source['seed']})"
        ),
    )
    parser.add_argument(
        "--energy-keV",
        type=float,
        default=argparse.SUPPRESS,
        help=(
            "override the monoenergetic photon energy in keV; default: "
            "selected source config "
            f"(bundled value {bundled_source['energy_keV']})"
        ),
    )
    parser.add_argument(
        "--focal-scan-points",
        type=int,
        default=argparse.SUPPRESS,
        help=(
            "override the number of longitudinal scan planes; default: "
            "selected geometry config "
            f"(bundled value {bundled_geometry['focus_scan']['points']})"
        ),
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="skip diagnostic plot creation (useful for automated tests)",
    )
    parser.add_argument(
        "--verbose-shadow4",
        action="store_true",
        help="show SHADOW4's low-level trace diagnostics",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    try:
        summary = run_simulation(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))

    geometry = summary["geometry"]
    acceptance = summary["acceptance"]
    focus = summary["focus"]
    spot = summary["sample_spot"]
    print(
        f"{geometry['crystal_label']}, "
        f"{summary['source_config']['energy_keV']:.6g} keV: "
        f"corrected Bragg angle = {geometry['corrected_bragg_angle_deg']:.6f} deg"
    )
    print(
        "Von Hamos arms: "
        f"source-crystal = {geometry['source_to_crystal_m']:.6f} m, "
        f"paraxial crystal-focus = "
        f"{geometry['paraxial_predicted_crystal_to_focus_m']:.6f} m"
    )
    print(
        "Configured phase-space throughput: "
        f"geometric = {100.0 * acceptance['geometric_intercepted_fraction']:.4f}%, "
        f"weighted reflected = {100.0 * acceptance['weighted_accepted_fraction']:.6f}%, "
        f"weighted rejected = {100.0 * acceptance['weighted_rejected_fraction']:.6f}%"
    )
    print(
        f"Weighted sagittal focus = {focus['distance_m']:.6f} m; "
        f"sigma_x = {1.0e6 * focus['sigma_x_m']:.3f} um; "
        f"N_eff = {focus['effective_weighted_rays']:.1f}"
    )
    print(
        f"Sample spot at {spot['distance_m']:.6f} m: "
        f"sigma_x = {1.0e6 * spot['sigma_x_m']:.3f} um, "
        f"sigma_z (unfocused) = {1.0e6 * spot['sigma_z_m']:.3f} um"
    )
    print("Saved:")
    print(f"  {summary['outputs']['summary_json']}")
    print(f"  {summary['outputs']['phase_space_hdf5']}")
    print(f"  {summary['outputs']['focal_scan_csv']}")
    for path in summary["outputs"]["plots"]:
        print(f"  {path}")


if __name__ == "__main__":
    main()
