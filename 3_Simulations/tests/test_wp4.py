#!/usr/bin/env python3
"""Unit and smoke tests for the WP4 end-to-end screening stage."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import h5py
import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SIMULATION_ROOT / "shadow4" / "wp4_end_to_end.py"
SPEC = importlib.util.spec_from_file_location("prism_wp4", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
WP4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WP4)


class ConfigurationTests(unittest.TestCase):
    def test_bundled_grid_is_valid_and_enumerates_expected_cases(self):
        scan = WP4.load_json(WP4.DEFAULT_SCAN_CONFIG)
        geometry = WP4.load_json(WP4.DEFAULT_GEOMETRY_CONFIG)
        WP4.validate_scan_config(scan)
        cases = WP4.enumerate_cases(scan, geometry)
        expected = (
            len(scan["geometry_grid"]["crystal_radius_m"])
            * len(
                scan["geometry_grid"][
                    "source_distance_scale_of_symmetric_arm"
                ]
            )
            * len(
                scan["geometry_grid"][
                    "sample_distance_scale_of_paraxial_image"
                ]
            )
            * len(scan["slit_designs"])
        )
        self.assertEqual(len(cases), expected)
        self.assertEqual(len({case["case_id"] for case in cases}), expected)
        for case in cases:
            positions = [
                slit["distance_from_source_m"] for slit in case["slits"]
            ]
            self.assertEqual(positions, sorted(positions))
            self.assertTrue(
                all(
                    0.0 < position < case["source_distance_m"]
                    for position in positions
                )
            )

    def test_pareto_front_and_feasible_selection_are_deterministic(self):
        aggregates = [
            {
                "case_id": "flux",
                "successful_seeds": 3,
                "sample_photons_per_mAs_mean": 100.0,
                "sample_photons_per_mAs_std": 1.0,
                "incident_energy_resolution_fwhm_eV_mean": 12.0,
                "incident_energy_resolution_fwhm_eV_std": 0.2,
                "energy_window_edge_weight_fraction_mean": 0.0,
                "sample_fwhm_x_m_mean": 4.0e-4,
                "sample_fwhm_x_m_std": 1.0e-5,
                "effective_weighted_rays_mean": 100.0,
                "resolution_peak_effective_rays_min": 100.0,
                "resolution_peak_energy_eV_std": 0.1,
                "resolution_peak_offset_eV_mean": 0.2,
                "resolution_fwhm_cv": 0.02,
            },
            {
                "case_id": "balanced",
                "successful_seeds": 3,
                "sample_photons_per_mAs_mean": 80.0,
                "sample_photons_per_mAs_std": 1.0,
                "incident_energy_resolution_fwhm_eV_mean": 8.0,
                "incident_energy_resolution_fwhm_eV_std": 0.1,
                "energy_window_edge_weight_fraction_mean": 0.0,
                "sample_fwhm_x_m_mean": 3.0e-4,
                "sample_fwhm_x_m_std": 1.0e-5,
                "effective_weighted_rays_mean": 100.0,
                "resolution_peak_effective_rays_min": 100.0,
                "resolution_peak_energy_eV_std": 0.1,
                "resolution_peak_offset_eV_mean": 0.2,
                "resolution_fwhm_cv": 0.02,
            },
            {
                "case_id": "dominated",
                "successful_seeds": 3,
                "sample_photons_per_mAs_mean": 70.0,
                "sample_photons_per_mAs_std": 1.0,
                "incident_energy_resolution_fwhm_eV_mean": 9.0,
                "incident_energy_resolution_fwhm_eV_std": 0.1,
                "energy_window_edge_weight_fraction_mean": 0.0,
                "sample_fwhm_x_m_mean": 3.5e-4,
                "sample_fwhm_x_m_std": 1.0e-5,
                "effective_weighted_rays_mean": 100.0,
                "resolution_peak_effective_rays_min": 100.0,
                "resolution_peak_energy_eV_std": 0.1,
                "resolution_peak_offset_eV_mean": 0.2,
                "resolution_fwhm_cv": 0.02,
            },
        ]
        selection_config = WP4.load_json(WP4.DEFAULT_SCAN_CONFIG)["selection"]
        selection = WP4.select_candidate(aggregates, selection_config)
        self.assertEqual(
            set(selection["pareto_case_ids"]), {"flux", "balanced"}
        )
        self.assertEqual(selection["selected_case_id"], "balanced")
        self.assertTrue(selection["constraints_satisfied"])
        self.assertEqual(
            selection["status"],
            "simulation_candidate_not_an_approved_design_freeze",
        )

    def test_bundled_wp4_uses_finite_crystal_thickness(self):
        geometry = WP4.load_json(WP4.DEFAULT_GEOMETRY_CONFIG)
        self.assertFalse(
            geometry["crystal"]["use_thick_crystal_approximation"]
        )

    def test_selection_contract_rejects_missing_gate_and_negative_penalty(self):
        scan = WP4.load_json(WP4.DEFAULT_SCAN_CONFIG)
        del scan["selection"]["constraints"]["resolution_fwhm_cv_max"]
        with self.assertRaisesRegex(ValueError, "constraints must contain exactly"):
            WP4.validate_scan_config(scan)

        scan = WP4.load_json(WP4.DEFAULT_SCAN_CONFIG)
        scan["selection"]["robustness_cv_penalty"] = -0.1
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            WP4.validate_scan_config(scan)

    def test_half_maximum_response_uses_interpolated_crossings(self):
        energy_eV = np.arange(25_500.0, 25_541.0, 0.5)
        sigma_eV = 4.0
        response = np.exp(
            -0.5 * ((energy_eV - 25_520.0) / sigma_eV) ** 2
        )
        metrics = WP4.half_maximum_response_metrics(
            energy_eV, response
        )
        self.assertTrue(metrics["resolved"])
        self.assertAlmostEqual(
            metrics["incident_energy_resolution_fwhm_eV"],
            2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma_eV,
            delta=0.02,
        )

    def test_resolution_plot_writes_both_formats_and_calls_show(self):
        energy_eV = np.arange(25_500.0, 25_541.0, 0.5)
        records = []
        for seed, shift in ((11, -0.1), (12, 0.1)):
            response = np.exp(
                -0.5 * ((energy_eV - 25_520.0 - shift) / 4.0) ** 2
            )
            records.extend(
                {
                    "case_id": "candidate",
                    "seed": seed,
                    "energy_eV": float(energy),
                    "transmission_fraction": float(value),
                    "status": "ok",
                }
                for energy, value in zip(energy_eV, response)
            )
        with tempfile.TemporaryDirectory(prefix="prism_wp4_plot_") as temporary:
            with mock.patch.object(WP4.plt, "show") as show:
                png, pdf = WP4.make_resolution_plot(
                    Path(temporary), "candidate", records
                )
            show.assert_called_once()
            self.assertGreater(png.stat().st_size, 10_000)
            self.assertGreater(pdf.stat().st_size, 5_000)

    def test_batched_monoenergetic_response_matches_individual_traces(self):
        source_config = WP4.load_json(WP4.wp1.DEFAULT_SOURCE_CONFIG)
        source_config["nrays"] = 200
        source_config["seed"] = 919
        source_config["sigma_x_m"] = 25.0e-6
        source_config["sigma_z_m"] = 25.0e-6
        probe = WP4.wp1.build_source(source_config).get_beam()
        scan = WP4.load_json(WP4.DEFAULT_SCAN_CONFIG)
        geometry = WP4.load_json(WP4.DEFAULT_GEOMETRY_CONFIG)
        case = WP4.enumerate_cases(scan, geometry)[0]
        energies = np.asarray([25_518.0, 25_520.0, 25_522.0])
        batched = WP4.monoenergetic_transmission_batch(
            probe,
            case,
            float(scan["reference_energy_keV"]),
            energies,
            verbose_shadow4=False,
        )
        individual = [
            WP4.monoenergetic_transmission_point(
                probe,
                case,
                float(scan["reference_energy_keV"]),
                float(energy),
                verbose_shadow4=False,
            )
            for energy in energies
        ]
        self.assertTrue(np.allclose(batched, individual, rtol=1.0e-12))


class CommandLineTests(unittest.TestCase):
    def test_help_shows_effective_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        normalized = " ".join(completed.stdout.split())
        self.assertIn("100000", normalized)
        self.assertIn("5000", normalized)
        self.assertIn("20260728", normalized)
        self.assertIn("wp4_optimization.json", normalized)

    def test_small_end_to_end_scan_exports_wp5_phase_space(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp4_test_") as temporary:
            temporary_path = Path(temporary)
            output_dir = temporary_path / "results"
            output_dir.mkdir()
            stale_phase_space = output_dir / "wp4_phase_space.h5"
            stale_sample_csv = output_dir / "wp4_sample_phase_space.csv"
            stale_phase_space.write_bytes(b"stale feasible artifact")
            stale_sample_csv.write_text("stale feasible artifact\n", encoding="utf-8")
            environment = os.environ.copy()
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(temporary_path / "matplotlib")
            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--nrays",
                "4000",
                "--seeds",
                "71",
                "--max-cases",
                "2",
                "--resolution-nrays",
                "500",
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
                timeout=180,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary_path = output_dir / "wp4_summary.json"
            candidate_path = output_dir / "wp4_candidate_design.json"
            self.assertTrue(summary_path.is_file())
            self.assertTrue(candidate_path.is_file())
            summary = json.loads(
                summary_path.read_text(encoding="utf-8"),
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-standard JSON constant {value}")
                ),
            )
            self.assertEqual(summary["stage"], "WP4_end_to_end")
            self.assertEqual(summary["cases_requested"], 2)
            self.assertEqual(summary["failed_traces"], 0)
            self.assertEqual(
                summary["selection"]["status"],
                "software_smoke_or_partial_scan_not_for_wp5_design_input",
            )
            self.assertFalse(summary["selection"]["constraints_satisfied"])
            self.assertTrue(summary["case_limit_applied"])
            self.assertEqual(summary["cases_generated"], 40)
            self.assertEqual(summary["cases_executed"], 2)
            self.assertFalse(stale_phase_space.exists())
            self.assertFalse(stale_sample_csv.exists())
            self.assertCountEqual(
                summary["removed_stale_alternate_outputs"],
                [str(stale_phase_space), str(stale_sample_csv)],
            )
            self.assertIsNone(
                summary["outputs"]["phase_space_hdf5_for_wp5"]
            )
            phase_space_path = Path(
                summary["outputs"]["diagnostic_phase_space_hdf5"]
            )
            self.assertTrue(phase_space_path.is_file())
            with h5py.File(phase_space_path) as phase_space:
                self.assertEqual(
                    phase_space.attrs["schema"],
                    "PRISM_SHADOW4_PHASE_SPACE_V1",
                )
                self.assertEqual(
                    phase_space.attrs["producer"], "wp4_end_to_end.py"
                )
                self.assertIn("sample", phase_space)
                sample = phase_space["sample"]
                self.assertGreater(sample["energy_keV"].shape[0], 0)
                self.assertEqual(sample["weight"].attrs["units"], "photons/mAs")
                status = sample["status"][:]
                weight = sample["weight"][:]
                energy = sample["energy_keV"][:]
                usable = (
                    (status > 0.0)
                    & (weight > 0.0)
                    & np.isfinite(weight)
                    & np.isfinite(energy)
                )
                self.assertGreater(np.count_nonzero(usable), 1)
                self.assertGreater(float(np.sum(weight[usable])), 0.0)

    def test_failed_rerun_invalidates_previous_wp5_handoff(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp4_invalidate_") as temporary:
            temporary_path = Path(temporary)
            output_dir = temporary_path / "results"
            output_dir.mkdir()
            stale_phase_space = output_dir / "wp4_phase_space.h5"
            stale_sample_csv = output_dir / "wp4_sample_phase_space.csv"
            stale_phase_space.write_bytes(b"stale feasible artifact")
            stale_sample_csv.write_text(
                "stale feasible artifact\n", encoding="utf-8"
            )
            tube_config = WP4.load_json(
                SIMULATION_ROOT / "config" / "wp2_tube_source.json"
            )
            tube_config["spekpy"]["kvp"] = 20.0
            tube_config_path = temporary_path / "invalid_tube.json"
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
                    "71",
                    "--max-cases",
                    "1",
                    "--resolution-nrays",
                    "100",
                    "--output-dir",
                    str(output_dir),
                    "--no-plots",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(stale_phase_space.exists())
            self.assertFalse(stale_sample_csv.exists())
            self.assertFalse(
                (output_dir / "wp4_phase_space.h5.incomplete").exists()
            )


if __name__ == "__main__":
    unittest.main()
