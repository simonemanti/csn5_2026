#!/usr/bin/env python3
"""Tests for the photon-normalized WP2 SpekPy/SHADOW4 pipeline."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import h5py
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SIMULATION_ROOT / "shadow4" / "wp2_tube_source.py"
SPEC = importlib.util.spec_from_file_location("prism_wp2", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
WP2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = WP2
SPEC.loader.exec_module(WP2)


class SpectrumAndSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="prism_wp2_cache_")
        cls.cache_dir = Path(cls.temporary.name)
        cls.config = WP2.load_json(WP2.DEFAULT_TUBE_CONFIG)
        cls.spectrum = WP2.load_or_generate_spectrum(
            cls.config, cache_dir=cls.cache_dir
        )
        cls.cache_mtime_ns = cls.spectrum.cache_path.stat().st_mtime_ns

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_cache_key_and_reuse_are_deterministic(self):
        self.assertFalse(self.spectrum.cache_hit)
        second = WP2.load_or_generate_spectrum(
            self.config, cache_dir=self.cache_dir
        )
        self.assertTrue(second.cache_hit)
        self.assertEqual(second.cache_key, self.spectrum.cache_key)
        self.assertEqual(second.cache_path, self.spectrum.cache_path)
        self.assertEqual(second.cache_path.stat().st_mtime_ns, self.cache_mtime_ns)
        self.assertTrue(np.array_equal(second.energy_keV, self.spectrum.energy_keV))
        self.assertTrue(
            np.array_equal(
                second.differential_fluence_photons_cm2_keV_mAs,
                self.spectrum.differential_fluence_photons_cm2_keV_mAs,
            )
        )
        self.assertEqual(
            second.operating_point["spekpy_version"],
            self.config["spekpy"]["spekpy_version"],
        )

    def test_source_weights_and_energy_window_preserve_normalization(self):
        beam, metadata = WP2.build_polychromatic_source(
            self.config, self.spectrum, nrays=2000, seed=314159
        )
        energy_keV = beam.get_column(26) * 1.0e-3
        weights = beam.get_column(23)
        target = metadata[
            "traced_window_photons_per_mAs_in_sampled_solid_angle"
        ]
        self.assertTrue(
            np.all(energy_keV >= self.spectrum.importance_minimum_keV)
        )
        self.assertTrue(
            np.all(energy_keV <= self.spectrum.importance_maximum_keV)
        )
        self.assertTrue(np.all(weights > 0.0))
        self.assertTrue(
            math.isclose(
                float(np.sum(weights)), target, rel_tol=2.0e-13, abs_tol=0.0
            )
        )
        self.assertLess(
            metadata["traced_window_fluence_photons_cm2_mAs"],
            metadata["complete_spectrum_fluence_photons_cm2_mAs"],
        )
        repeat, repeat_metadata = WP2.build_polychromatic_source(
            self.config, self.spectrum, nrays=2000, seed=314159
        )
        self.assertTrue(np.array_equal(beam.rays, repeat.rays))
        self.assertEqual(metadata, repeat_metadata)

    def test_current_and_exposure_are_post_scaling_only(self):
        changed_reporting = copy.deepcopy(self.config)
        changed_reporting["reporting"]["current_mA"] = 7.5
        changed_reporting["reporting"]["exposure_s"] = 12.0
        same_cache = WP2.load_or_generate_spectrum(
            changed_reporting, cache_dir=self.cache_dir
        )
        self.assertEqual(same_cache.cache_key, self.spectrum.cache_key)
        self.assertEqual(same_cache.cache_path, self.spectrum.cache_path)
        self.assertTrue(same_cache.cache_hit)
        original_beam, _ = WP2.build_polychromatic_source(
            self.config, self.spectrum, nrays=500, seed=23
        )
        changed_beam, _ = WP2.build_polychromatic_source(
            changed_reporting, same_cache, nrays=500, seed=23
        )
        self.assertTrue(np.array_equal(original_beam.rays, changed_beam.rays))
        value = 13.0
        self.assertEqual(
            WP2.scale_weight_for_exposure(value, 7.5, 12.0),
            value * 7.5 * 12.0,
        )

    def test_solid_angle_matches_small_angle_limit(self):
        source = self.config["source_phase_space"]
        exact = WP2.rectangular_direction_cosine_solid_angle_sr(
            source["horizontal_angle_min_rad"],
            source["horizontal_angle_max_rad"],
            source["vertical_angle_min_rad"],
            source["vertical_angle_max_rad"],
        )
        rectangle = (
            source["horizontal_angle_max_rad"]
            - source["horizontal_angle_min_rad"]
        ) * (
            source["vertical_angle_max_rad"]
            - source["vertical_angle_min_rad"]
        )
        self.assertGreater(exact, rectangle)
        self.assertLess((exact - rectangle) / rectangle, 0.002)


class CommandLineTests(unittest.TestCase):
    def test_help_reports_effective_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        compact = " ".join(completed.stdout.split())
        for expected in (
            "wp2_tube_source.json",
            "wp1_geometry.json",
            "bundled value 100000",
            "bundled value 20260728",
            "bundled value 1.0",
            "target=W",
            "kVp=60.0",
            "anode angle=12.0 deg",
            "bin=0.02 keV",
            "reference distance=100.0 cm",
            "SpekPy=2.5.4",
            "reference energy=25.52 keV",
            "importance window=24.5-26.5 keV",
            "default: False",
        ):
            self.assertIn(expected, compact)
        self.assertNotIn("default: None", completed.stdout)

    def test_two_thousand_ray_smoke_writes_reusable_outputs(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp2_smoke_") as temporary:
            root = Path(temporary)
            output_dir = root / "results"
            cache_dir = root / "cache"
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(root / "matplotlib")
            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--nrays",
                "2000",
                "--output-dir",
                str(output_dir),
                "--cache-dir",
                str(cache_dir),
                "--no-plots",
            ]
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary_path = output_dir / "wp2_summary.json"
            spectrum_path = output_dir / "wp2_spectrum.csv"
            phase_space_path = output_dir / "wp2_phase_space.h5"
            self.assertTrue(summary_path.is_file())
            self.assertTrue(spectrum_path.is_file())
            self.assertTrue(phase_space_path.is_file())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            target = summary["normalization"][
                "traced_window_photons_per_mAs_in_sampled_solid_angle"
            ]
            source_weight = summary["analysis"]["source"][
                "weighted_photons_per_mAs"
            ]
            post_weight = summary["analysis"]["post_crystal"][
                "weighted_photons_per_mAs"
            ]
            sample_weight = summary["analysis"]["sample"][
                "weighted_photons_per_mAs"
            ]
            self.assertTrue(
                math.isclose(source_weight, target, rel_tol=2.0e-13, abs_tol=0.0)
            )
            self.assertGreater(post_weight, 0.0)
            self.assertLess(post_weight, source_weight)
            self.assertTrue(
                math.isclose(sample_weight, post_weight, rel_tol=2.0e-13)
            )
            self.assertEqual(summary["outputs"]["plots"], [])
            self.assertEqual(
                summary["spectrum_cache"]["operating_point"]["mas"], 1.0
            )

            required_fields = {
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
            }
            with h5py.File(phase_space_path) as phase_space:
                self.assertEqual(
                    phase_space.attrs["schema"], WP2.PHASE_SPACE_SCHEMA
                )
                self.assertEqual(phase_space.attrs["weight_unit"], "photons/mAs")
                self.assertEqual(
                    set(phase_space), {"source", "post_crystal", "sample"}
                )
                for group_name in ("source", "post_crystal", "sample"):
                    group = phase_space[group_name]
                    self.assertEqual(set(group), required_fields)
                    self.assertEqual(group["x_m"].shape, (2000,))
                    self.assertEqual(group["weight"].attrs["units"], "photons/mAs")
                    self.assertEqual(
                        group.attrs["recommended_selection"],
                        "status > 0 and weight > 0",
                    )
                self.assertIn(
                    "plane_distance_from_crystal_m",
                    phase_space["sample"].attrs,
                )
                self.assertTrue(
                    np.allclose(phase_space["sample"]["y_m"][:], 0.0)
                )
                self.assertTrue(
                    math.isclose(
                        float(np.sum(phase_space["source"]["weight"][:])),
                        target,
                        rel_tol=2.0e-13,
                    )
                )


if __name__ == "__main__":
    unittest.main()
