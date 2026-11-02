#!/usr/bin/env python3
"""Unit and smoke tests for the legacy WP3 two-slit scan."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from shadow4.beam.s4_beam import S4Beam


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SHADOW_DIRECTORY = SIMULATION_ROOT / "shadow4"
SCRIPT_PATH = SHADOW_DIRECTORY / "wp3_slit_scan.py"
CONFIG_PATH = SIMULATION_ROOT / "config" / "wp3_slits.json"
if str(SHADOW_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SHADOW_DIRECTORY))
SPEC = importlib.util.spec_from_file_location("prism_wp3", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
WP3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WP3)


def pencil_beam_with_sagittal_slopes() -> S4Beam:
    beam = S4Beam.initialize_as_pencil(N=5)
    dx = np.asarray([-0.10, -0.04, 0.0, 0.04, 0.10])
    beam.set_column(4, dx)
    beam.set_column(5, np.sqrt(1.0 - dx**2))
    beam.set_column(6, np.zeros(dx.size))
    return beam


def rectangular_slit(
    name: str, distance_m: float, width_m: float
) -> dict[str, float | str]:
    return {
        "name": name,
        "distance_from_source_m": distance_m,
        "width_x_m": width_m,
        "height_z_m": 1.0,
        "center_x_m": 0.0,
        "center_z_m": 0.0,
    }


class SlitMaskTests(unittest.TestCase):
    def test_projection_mask_is_non_mutating_and_accounts_each_stage(self):
        source = pencil_beam_with_sagittal_slopes()
        masked, stages = WP3.apply_slit_sequence(
            source,
            [
                rectangular_slit("wide", 1.0, 0.10),
                rectangular_slit("narrow", 2.0, 0.02),
            ],
        )

        self.assertTrue(np.all(source.get_column(10) > 0.0))
        self.assertEqual(np.count_nonzero(masked.get_column(10) > 0.0), 1)
        self.assertEqual([stage["input_rays"] for stage in stages], [5, 3])
        self.assertEqual([stage["passed_rays"] for stage in stages], [3, 1])
        self.assertEqual([stage["blocked_rays"] for stage in stages], [2, 2])
        self.assertEqual(
            [stage["passed_photons_per_mAs"] for stage in stages],
            [3.0, 1.0],
        )
        self.assertAlmostEqual(stages[0]["stage_transmission_fraction"], 3.0 / 5.0)
        self.assertAlmostEqual(stages[1]["stage_transmission_fraction"], 1.0 / 3.0)
        self.assertAlmostEqual(stages[1]["cumulative_transmission_fraction"], 1.0 / 5.0)

    def test_nested_apertures_never_restore_a_lost_ray(self):
        source = pencil_beam_with_sagittal_slopes()
        wide, _ = WP3.apply_slit_sequence(
            source, [rectangular_slit("wide", 1.0, 0.10)]
        )
        nested, _ = WP3.apply_slit_sequence(
            source,
            [
                rectangular_slit("wide", 1.0, 0.10),
                rectangular_slit("narrow", 2.0, 0.02),
            ],
        )
        wide_alive = wide.get_column(10) > 0.0
        nested_alive = nested.get_column(10) > 0.0
        self.assertTrue(np.all(~nested_alive | wide_alive))

    def test_unordered_slits_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "downstream-ordered"):
            WP3.apply_slit_sequence(
                pencil_beam_with_sagittal_slopes(),
                [
                    rectangular_slit("downstream", 2.0, 0.10),
                    rectangular_slit("upstream", 1.0, 0.10),
                ],
            )


class ScanGridTests(unittest.TestCase):
    def test_grid_contains_open_single_two_slit_and_position_variants(self):
        config = WP3.load_json(CONFIG_PATH)
        WP3.validate_scan_config(config)
        cases = WP3.generate_scan_cases(config)
        modes = [case["mode"] for case in cases]
        self.assertEqual(modes.count("open"), 1)
        self.assertIn("single", modes)
        self.assertIn("two", modes)

        single_first = [
            case
            for case in cases
            if case["mode"] == "single"
            and case["slits"][0]["name"] == "slit_1_source"
        ]
        single_second = [
            case
            for case in cases
            if case["mode"] == "single"
            and case["slits"][0]["name"] == "slit_2_precrystal"
        ]
        self.assertGreaterEqual(
            len(
                {
                    case["slits"][0]["distance_from_source_m"]
                    for case in single_first
                }
            ),
            2,
        )
        self.assertGreaterEqual(
            len(
                {
                    case["slits"][0]["distance_from_source_m"]
                    for case in single_second
                }
            ),
            2,
        )
        two_position_pairs = {
            tuple(slit["distance_from_source_m"] for slit in case["slits"])
            for case in cases
            if case["mode"] == "two"
        }
        self.assertGreaterEqual(len(two_position_pairs), 4)
        self.assertEqual(len(cases), 49)
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))


class CommandLineTests(unittest.TestCase):
    def test_help_displays_effective_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        compact = "".join(completed.stdout.split())
        self.assertIn("wp3_slits.json", compact)
        self.assertIn("(default:20000)", compact)
        self.assertIn("(default:0)", compact)
        self.assertIn("20260728", compact)

    def test_two_seed_small_scan_writes_csv_and_aggregation(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp3_test_") as temporary:
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
                "--seeds",
                "20260728,20260729",
                "--max-cases",
                "2",
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
                timeout=240,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            csv_path = output_dir / "wp3_case_seed_metrics.csv"
            summary_path = output_dir / "wp3_aggregation.json"
            self.assertTrue(csv_path.is_file())
            self.assertTrue(summary_path.is_file())
            with csv_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["status"] == "ok" for row in rows))
            self.assertIn("sample_photons_per_mAs", rows[0])
            self.assertIn("slit_transmission_fraction", rows[0])

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["validation_level"], "simulation")
            self.assertFalse(summary["hardware_recommendation"])
            self.assertEqual(summary["cases_executed"], 2)
            self.assertEqual(summary["successful_traces"], 4)
            self.assertEqual(
                len(
                    summary["controlled_comparison"][
                        "source_beam_sha256_by_seed"
                    ]
                ),
                2,
            )
            self.assertTrue(
                summary["controlled_comparison"][
                    "same_source_beam_reused_for_all_cases_within_each_seed"
                ]
            )
            self.assertEqual(
                summary["diagnostic_selection"]["hardware_recommendation"],
                False,
            )
            self.assertEqual(
                summary["diagnostic_selection"]["status"],
                "simulation_diagnostic_not_hardware_recommendation",
            )
            self.assertFalse((output_dir / "wp3_diagnostics.png").exists())
            self.assertFalse((output_dir / "wp3_diagnostics.pdf").exists())

    def test_scan_rejects_wp2_reference_energy_mismatch_before_tracing(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp3_energy_") as temporary:
            temporary_path = Path(temporary)
            tube_config_path = temporary_path / "tube.json"
            tube_config = WP3.load_json(
                SIMULATION_ROOT / "config" / "wp2_tube_source.json"
            )
            tube_config["source_phase_space"]["reference_energy_keV"] = 25.51
            tube_config_path.write_text(
                json.dumps(tube_config, allow_nan=False),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tube-config",
                    str(tube_config_path),
                    "--nrays",
                    "100",
                    "--seeds",
                    "71,72",
                    "--max-cases",
                    "1",
                    "--output-dir",
                    str(temporary_path / "results"),
                    "--no-plots",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(
                "WP2 source_phase_space.reference_energy_keV and "
                "WP3 reference_energy_keV must match",
                completed.stderr,
            )


if __name__ == "__main__":
    unittest.main()
