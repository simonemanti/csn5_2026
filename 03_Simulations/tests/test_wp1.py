#!/usr/bin/env python3
"""Unit and smoke tests for the WP1 monoenergetic SHADOW4 baseline."""

from __future__ import annotations

import importlib.util
import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import h5py
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SIMULATION_ROOT / "shadow4" / "wp1_monoenergetic.py"
OWS_PATH = SIMULATION_ROOT / "oasys" / "wp1_monoenergetic.ows"
SPEC = importlib.util.spec_from_file_location("oltre_wp1", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
WP1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WP1)


class GeometryTests(unittest.TestCase):
    def test_symmetric_von_hamos_geometry_satisfies_sagittal_equation(self):
        radius_m = 0.25
        angle_rad = math.radians(29.0)
        arm_m = WP1.von_hamos_symmetric_arm_m(radius_m, angle_rad)
        image_m = WP1.sagittal_image_distance_m(arm_m, radius_m, angle_rad)
        self.assertAlmostEqual(arm_m, image_m, places=13)
        self.assertAlmostEqual(arm_m, radius_m / math.sin(angle_rad), places=13)

    def test_weighted_focus_recovers_crossing_plane(self):
        rng = np.random.default_rng(17)
        number = 2000
        expected_focus_m = 0.42
        slopes = rng.normal(0.0, 0.02, number)
        intercepts = -expected_focus_m * slopes + rng.normal(0.0, 2.0e-6, number)
        arrays = {
            "x_m": intercepts,
            "y_m": np.zeros(number),
            "z_m": np.zeros(number),
            "dx": slopes / np.sqrt(1.0 + slopes**2),
            "dy": 1.0 / np.sqrt(1.0 + slopes**2),
            "dz": np.zeros(number),
            "weight": np.linspace(0.1, 1.0, number),
            "status": np.ones(number, dtype=np.int16),
        }
        mask = WP1.usable_mask(arrays)
        recovered_m = WP1.weighted_sagittal_focus_m(arrays, mask)
        self.assertAlmostEqual(recovered_m, expected_focus_m, delta=2.0e-5)

    def test_missing_distance_key_is_rejected_during_validation(self):
        config = WP1.load_json(WP1.DEFAULT_GEOMETRY_CONFIG)
        del config["distances"]["source_to_crystal_m"]
        with self.assertRaisesRegex(ValueError, "source_to_crystal_m"):
            WP1.validate_geometry_config(config)

    def test_central_layout_is_symmetric_and_has_correct_deflection(self):
        theta = math.radians(29.0)
        layout = WP1.central_layout_coordinates(0.50, 0.52, theta)
        incident = layout["incident_direction"]
        outgoing = layout["outgoing_direction"]
        source = layout["source_m"]
        sample = layout["sample_m"]

        self.assertTrue(np.allclose(-source / 0.50, incident))
        self.assertTrue(np.allclose(sample / 0.52, outgoing))
        self.assertAlmostEqual(np.linalg.norm(incident), 1.0, places=14)
        self.assertAlmostEqual(np.linalg.norm(outgoing), 1.0, places=14)
        self.assertAlmostEqual(
            math.acos(float(np.dot(incident, outgoing))), 2.0 * theta, places=14
        )

    def test_geometry_plot_writes_png_and_pdf(self):
        with tempfile.TemporaryDirectory(prefix="oltre_wp1_geometry_") as temporary:
            output_dir = Path(temporary)
            config = WP1.load_json(WP1.DEFAULT_GEOMETRY_CONFIG)["crystal"]
            png_path, pdf_path = WP1.make_geometry_plots(
                output_dir,
                config,
                source_distance_m=0.50,
                sample_distance_m=0.52,
                focus_distance_m=0.51,
                bragg_angle_rad=math.radians(29.0),
                crystal_label="Ge(880)",
                energy_keV=25.52,
            )
            self.assertTrue(png_path.is_file())
            self.assertTrue(pdf_path.is_file())
            self.assertGreater(png_path.stat().st_size, 10_000)
            self.assertGreater(pdf_path.stat().st_size, 10_000)


class CommandLineSmokeTest(unittest.TestCase):
    def test_help_reports_effective_bundled_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("bundled value 100000", completed.stdout)
        self.assertIn("bundled value 20260720", completed.stdout)
        self.assertIn("bundled value 25.52", completed.stdout)
        self.assertIn("bundled value 101", completed.stdout)
        self.assertNotIn("default: None", completed.stdout)

    def test_small_trace_writes_reusable_outputs(self):
        with tempfile.TemporaryDirectory(prefix="oltre_wp1_test_") as temporary:
            temporary_path = Path(temporary)
            output_dir = temporary_path / "results"
            environment = os.environ.copy()
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(temporary_path / "matplotlib")
            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--nrays",
                "2000",
                "--focal-scan-points",
                "11",
                "--output-dir",
                str(output_dir),
                "--no-plots",
            ]
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=90,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary_path = output_dir / "wp1_summary.json"
            phase_space_path = output_dir / "wp1_phase_space.h5"
            focus_path = output_dir / "wp1_focal_scan.csv"
            self.assertTrue(summary_path.is_file())
            self.assertTrue(phase_space_path.is_file())
            self.assertTrue(focus_path.is_file())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            accepted = summary["acceptance"]["weighted_accepted_fraction"]
            rejected = summary["acceptance"]["weighted_rejected_fraction"]
            exclusive = [
                summary["acceptance"]["exclusive_geometric_miss_fraction"],
                summary["acceptance"][
                    "exclusive_diffraction_loss_after_intercept_fraction"
                ],
                summary["acceptance"]["exclusive_reflected_fraction"],
            ]
            self.assertGreater(accepted, 0.0)
            self.assertAlmostEqual(accepted + rejected, 1.0, places=12)
            self.assertAlmostEqual(sum(exclusive), 1.0, places=12)
            self.assertTrue(summary["focus"]["inside_configured_scan"])
            self.assertEqual(
                summary["outputs"]["summary_json"], str(summary_path)
            )

            with focus_path.open(newline="", encoding="utf-8") as stream:
                focus_rows = list(csv.DictReader(stream))
            self.assertEqual(len(focus_rows), 11)

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
                    phase_space.attrs["schema"], "OLTRE_SHADOW4_PHASE_SPACE_V1"
                )
                self.assertIn("sample_plane_distance_from_crystal_m", phase_space.attrs)
                metadata = json.loads(phase_space.attrs["metadata_json"])
                self.assertIn("resolved_geometry", metadata)
                for group_name in ("crystal_footprint", "post_crystal", "sample"):
                    group = phase_space[group_name]
                    self.assertEqual(set(group), required_fields)
                    self.assertEqual(group["x_m"].shape, (2000,))
                    self.assertTrue(np.all(np.isfinite(group["energy_keV"][:])))
                    self.assertTrue(np.all(np.isfinite(group["weight"][:])))
                self.assertTrue(
                    np.allclose(phase_space["sample"]["y_m"][:], 0.0)
                )
                self.assertIn(
                    "plane_distance_from_crystal_m", phase_space["sample"].attrs
                )


class OasysWorkflowTests(unittest.TestCase):
    def test_workflow_has_expected_nodes_links_and_wp1_values(self):
        root = ET.parse(OWS_PATH).getroot()
        nodes = root.findall("./nodes/node")
        links = root.findall("./links/link")
        properties = {
            item.attrib["node_id"]: item.text
            for item in root.findall("./node_properties/properties")
        }

        self.assertEqual(root.attrib["version"], "2.0")
        self.assertEqual(len(nodes), 5)
        self.assertEqual(len(links), 4)
        self.assertTrue(
            all(node.attrib["project_name"] == "OASYS2-SHADOW4" for node in nodes)
        )
        self.assertIn("'single_line_value': 25520.0", properties["0"])
        self.assertIn("'user_defined_h': 8", properties["1"])
        self.assertIn("'user_defined_k': 8", properties["1"])
        self.assertIn("'user_defined_l': 0", properties["1"])
        self.assertIn("'spherical_radius': 0.25", properties["1"])
        self.assertIn("'cylinder_orientation': 1", properties["1"])

    def test_ows_validator_help_displays_default_workflow(self):
        validator = SIMULATION_ROOT / "oasys" / "validate_wp1_ows.py"
        completed = subprocess.run(
            [sys.executable, str(validator), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("wp1_monoenergetic.ows", "".join(completed.stdout.split()))


if __name__ == "__main__":
    unittest.main()
