#!/usr/bin/env python3
"""Unit and smoke tests for the internal WP5 Geant4 bridge and analysis."""

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

import h5py
import numpy as np


os.environ.setdefault("MPLBACKEND", "Agg")

SIMULATION_ROOT = Path(__file__).resolve().parents[1]
WP5_ROOT = SIMULATION_ROOT / "geant4" / "wp5_fluorescence"
PREPARE_PATH = WP5_ROOT / "prepare_phase_space.py"
ANALYZE_PATH = WP5_ROOT / "analyze_results.py"
SCAN_PATH = WP5_ROOT / "scan_detector.py"
CONFIG_PATH = SIMULATION_ROOT / "config" / "wp5_detector.json"
SCAN_CONFIG_PATH = SIMULATION_ROOT / "config" / "wp5_scan.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = load_module("prism_wp5_prepare", PREPARE_PATH)
ANALYZE = load_module("prism_wp5_analyze", ANALYZE_PATH)
SCAN = load_module("prism_wp5_scan", SCAN_PATH)


def read_prepared_rows(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    metadata: dict[str, str] = {}
    table_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith("#"):
            key, value = line[1:].strip().split("=", 1)
            metadata[key] = value
        else:
            table_lines.append(line)
    return metadata, list(csv.DictReader(table_lines))


class PreparePhaseSpaceTests(unittest.TestCase):
    def test_synthetic_fallback_is_explicit_and_normalized(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_prepare_") as temporary:
            output = Path(temporary) / "synthetic.csv"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PREPARE_PATH),
                    "--synthetic-monoenergetic",
                    "--events",
                    "32",
                    "--seed",
                    "77",
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metadata, rows = read_prepared_rows(output)
            self.assertEqual(metadata["schema"], "PRISM_WP5_PHASE_SPACE_V1")
            self.assertEqual(metadata["mode"], "synthetic_monoenergetic")
            self.assertEqual(float(metadata["normalization_weight_per_event"]), 1.0)
            self.assertEqual(len(rows), 32)
            self.assertTrue(all(float(row["energy_keV"]) == 25.52 for row in rows))
            self.assertTrue(all(float(row["unit_weight"]) == 1.0 for row in rows))
            self.assertTrue(all(int(row["source_row"]) == -1 for row in rows))
            self.assertTrue(output.with_suffix(".metadata.json").is_file())
            self.assertFalse(
                output.with_name(output.name + ".incomplete").exists()
            )
            self.assertFalse(
                output.with_suffix(".metadata.json")
                .with_name(output.with_suffix(".metadata.json").name + ".incomplete")
                .exists()
            )

    def test_hdf5_import_rejects_lost_rows_and_resamples_by_weight(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_hdf5_") as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "phase_space.h5"
            with h5py.File(source, "w") as handle:
                handle.attrs["schema"] = "PRISM_SHADOW4_PHASE_SPACE_V1"
                handle.attrs["weight_unit"] = "photons/mAs"
                handle.attrs["downstream_wp5_design_input_approved"] = True
                group = handle.create_group("sample")
                group["x_m"] = np.array([-1e-3, 0.0, 1e-3])
                group["y_m"] = np.zeros(3)
                group["z_m"] = np.array([0.0, 5e-3, 1e-3])
                group["dx"] = np.array([0.0, 0.0, 0.1])
                group["dy"] = np.array([1.0, 1.0, 0.995])
                group["dz"] = np.zeros(3)
                group["energy_keV"] = np.array([25.4, 25.5, 25.6])
                group["weight"] = np.array([0.1, 100.0, 0.9])
                group["weight"].attrs["units"] = "photons/mAs"
                group["status"] = np.array([1.0, -1.0, 1.0])

            prepared, metadata = PREPARE.prepare_from_hdf5(
                source, "sample", events=400, seed=91
            )
            self.assertEqual(metadata["valid_rows"], 2)
            self.assertAlmostEqual(metadata["input_valid_weight_sum"], 1.0)
            self.assertAlmostEqual(
                metadata["normalization_weight_per_event"], 1.0 / 400.0
            )
            self.assertEqual(set(np.unique(prepared["source_row"])), {0, 2})
            self.assertGreater(np.count_nonzero(prepared["source_row"] == 2), 320)
            norms = np.sqrt(
                prepared["dx"] ** 2
                + prepared["dy"] ** 2
                + prepared["dz"] ** 2
            )
            self.assertTrue(np.allclose(norms, 1.0))

    def test_hdf5_import_requires_explicit_override_for_wp4_diagnostic(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_gate_") as temporary:
            source = Path(temporary) / "diagnostic.h5"
            with h5py.File(source, "w") as handle:
                handle.attrs["schema"] = "PRISM_SHADOW4_PHASE_SPACE_V1"
                handle.attrs["weight_unit"] = "photons/mAs"
                handle.attrs["downstream_wp5_design_input_approved"] = False
                group = handle.create_group("sample")
                group["x_m"] = np.zeros(2)
                group["y_m"] = np.zeros(2)
                group["z_m"] = np.zeros(2)
                group["dx"] = np.zeros(2)
                group["dy"] = np.ones(2)
                group["dz"] = np.zeros(2)
                group["energy_keV"] = np.full(2, 25.52)
                group["weight"] = np.ones(2)
                group["weight"].attrs["units"] = "photons/mAs"
                group["status"] = np.ones(2)

            with self.assertRaisesRegex(ValueError, "infeasible diagnostic"):
                PREPARE.prepare_from_hdf5(
                    source, "sample", events=8, seed=91
                )
            prepared, metadata = PREPARE.prepare_from_hdf5(
                source,
                "sample",
                events=8,
                seed=91,
                allow_diagnostic_input=True,
            )
            self.assertEqual(prepared["event_id"].size, 8)
            self.assertTrue(metadata["diagnostic_input_override"])

    def test_hdf5_import_rejects_missing_schema_units_and_approval(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_contract_") as temporary:
            source = Path(temporary) / "uncontracted.h5"
            with h5py.File(source, "w") as handle:
                group = handle.create_group("sample")
                group["x_m"] = np.zeros(2)
                group["y_m"] = np.zeros(2)
                group["z_m"] = np.zeros(2)
                group["dx"] = np.zeros(2)
                group["dy"] = np.ones(2)
                group["dz"] = np.zeros(2)
                group["energy_keV"] = np.full(2, 25.52)
                group["weight"] = np.ones(2)
                group["status"] = np.ones(2)

            with self.assertRaisesRegex(
                ValueError,
                "schema.*weight_unit.*downstream_wp5_design_input_approved",
            ):
                PREPARE.prepare_from_hdf5(
                    source, "sample", events=8, seed=91
                )
            _, metadata = PREPARE.prepare_from_hdf5(
                source,
                "sample",
                events=8,
                seed=91,
                allow_diagnostic_input=True,
            )
            validation = metadata["source_contract_validation"]
            self.assertFalse(validation["compliant"])
            self.assertGreaterEqual(len(validation["reasons"]), 4)
            self.assertTrue(metadata["diagnostic_input_override"])

    def test_prepare_help_shows_effective_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(PREPARE_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("(default: 10000)", completed.stdout)
        self.assertIn("(default: 20260728)", completed.stdout)
        self.assertIn("wp4_phase_space.h5", completed.stdout)


class AnalyzeResultsTests(unittest.TestCase):
    @staticmethod
    def write_raw_fixture(
        path: Path, stored_smeared: list[float] | None = None
    ) -> None:
        fields = [
            "event_id",
            "phase_event_id",
            "source_row",
            "source_weight",
            "normalization_weight",
            "x_mm",
            "y_mm",
            "z_mm",
            "dx",
            "dy",
            "dz",
            "source_energy_keV",
            "edep_total_keV",
            "edep_primary_keV",
            "edep_secondary_keV",
            "edep_gamma_keV",
            "edep_electron_keV",
            "edep_other_keV",
            "smeared_edep_keV",
            "secondary_gamma_created",
            "ag_ka_created",
            "ag_kb_created",
            "secondary_gamma_entered_czt",
            "ag_ka_entered_czt",
            "ag_kb_entered_czt",
            "entered_gamma_energy_sum_keV",
        ]
        energies = [0.0, 22.1, 24.9, 10.0]
        if stored_smeared is None:
            stored_smeared = energies
        if len(stored_smeared) != len(energies):
            raise ValueError("stored_smeared must contain four values")
        with path.open("w", newline="", encoding="utf-8") as stream:
            stream.write("# schema=PRISM_WP5_RAW_V1\n")
            stream.write("# detector_width_mm=20\n")
            stream.write("# detector_height_mm=20\n")
            stream.write("# detector_distance_mm=50\n")
            stream.write("# detector_angle_deg=90\n")
            stream.write("# source.normalization_unit=relative photons\n")
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for event_id, (energy, smeared_energy) in enumerate(
                zip(energies, stored_smeared, strict=True)
            ):
                writer.writerow(
                    {
                        "event_id": event_id,
                        "phase_event_id": event_id,
                        "source_row": event_id,
                        "source_weight": 1.0,
                        "normalization_weight": 2.0,
                        "x_mm": 0.0,
                        "y_mm": 0.0,
                        "z_mm": 0.0,
                        "dx": 0.0,
                        "dy": 1.0,
                        "dz": 0.0,
                        "source_energy_keV": 25.52,
                        "edep_total_keV": energy,
                        "edep_primary_keV": 0.0,
                        "edep_secondary_keV": energy,
                        "edep_gamma_keV": 0.0,
                        "edep_electron_keV": energy,
                        "edep_other_keV": 0.0,
                        "smeared_edep_keV": smeared_energy,
                        "secondary_gamma_created": int(event_id > 0),
                        "ag_ka_created": int(event_id == 1),
                        "ag_kb_created": int(event_id == 2),
                        "secondary_gamma_entered_czt": int(event_id in (1, 2)),
                        "ag_ka_entered_czt": int(event_id == 1),
                        "ag_kb_entered_czt": int(event_id == 2),
                        "entered_gamma_energy_sum_keV": (
                            energy if event_id in (1, 2) else 0.0
                        ),
                    }
                )

    def test_analysis_writes_summary_and_both_plot_formats(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_analysis_") as temporary:
            temporary_path = Path(temporary)
            raw = temporary_path / "events.csv"
            output = temporary_path / "analysis"
            self.write_raw_fixture(raw, stored_smeared=[0.0, 0.0, 0.0, 22.1])
            environment = os.environ.copy()
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(temporary_path / "matplotlib")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ANALYZE_PATH),
                    "--input",
                    str(raw),
                    "--output-dir",
                    str(output),
                    "--prefix",
                    "fixture",
                    "--resolution-noise-fwhm-keV",
                    "0",
                    "--resolution-fraction-fwhm",
                    "0",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=60,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary_path = output / "fixture_summary.json"
            self.assertTrue(summary_path.is_file())
            self.assertGreater((output / "fixture_spectrum.png").stat().st_size, 10_000)
            self.assertGreater((output / "fixture_spectrum.pdf").stat().st_size, 5_000)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["events"], 4)
            self.assertEqual(summary["roi"]["ag_kalpha_events"], 1)
            self.assertEqual(summary["roi"]["ag_kbeta_events"], 0)
            self.assertEqual(
                summary["response_model"]["mode"], "stored_cpp_response"
            )
            self.assertEqual(
                summary["response_model"]["source_column"],
                "smeared_edep_keV",
            )

    def test_explicit_resmear_uses_raw_deposition_and_cli_response(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_resmear_") as temporary:
            temporary_path = Path(temporary)
            raw = temporary_path / "events.csv"
            output = temporary_path / "analysis"
            self.write_raw_fixture(raw, stored_smeared=[0.0, 0.0, 0.0, 0.0])
            environment = os.environ.copy()
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(temporary_path / "matplotlib")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ANALYZE_PATH),
                    "--input",
                    str(raw),
                    "--output-dir",
                    str(output),
                    "--prefix",
                    "resmeared",
                    "--resmear",
                    "--resolution-noise-fwhm-keV",
                    "0",
                    "--resolution-fraction-fwhm",
                    "0",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=60,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads(
                (output / "resmeared_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["roi"]["ag_kalpha_events"], 1)
            self.assertEqual(summary["roi"]["ag_kbeta_events"], 1)
            self.assertEqual(
                summary["response_model"]["mode"], "python_resmear"
            )
            self.assertEqual(
                summary["response_model"]["source_column"], "edep_total_keV"
            )
            self.assertEqual(summary["detection"]["smeared_detected_events"], 3)
            self.assertAlmostEqual(
                summary["normalization"]["represented_input_weight"], 8.0
            )

    def test_rectangle_solid_angle_is_bounded(self):
        solid_angle = ANALYZE.rectangular_solid_angle_sr(20.0, 20.0, 50.0)
        self.assertGreater(solid_angle, 0.0)
        self.assertLess(solid_angle, 4.0 * math.pi)
        self.assertAlmostEqual(solid_angle, 0.1538841096293133, places=12)

    def test_analysis_help_shows_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(ANALYZE_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("(default: 300)", completed.stdout)
        self.assertIn("(default: 0.8)", completed.stdout)
        self.assertIn("(default: 20260728)", completed.stdout)

    def test_raw_consumers_reject_missing_event_schema(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_raw_schema_") as temporary:
            raw = Path(temporary) / "events.csv"
            self.write_raw_fixture(raw)
            lines = raw.read_text(encoding="utf-8").splitlines()
            raw.write_text(
                "\n".join(
                    line
                    for line in lines
                    if not line.startswith("# schema=")
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "schema=PRISM_WP5_RAW_V1"
            ):
                ANALYZE.read_metadata_and_rows(raw)
            with self.assertRaisesRegex(
                ValueError, "schema=PRISM_WP5_RAW_V1"
            ):
                SCAN.read_raw_event_csv(raw)


class DetectorScanTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(SCAN_CONFIG_PATH.read_text(encoding="utf-8"))
        SCAN.validate_scan_config(self.config)

    def test_grid_enumeration_and_geometric_solid_angle(self):
        cases = SCAN.enumerate_cases(self.config)
        self.assertEqual(len(cases), 3 * 2 * 2 * 2 * 2)
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        first = cases[0]
        self.assertEqual(first["case_id"], "a00_d00_w00_h00_t00")
        self.assertGreater(first["geometric_solid_angle_sr"], 0.0)
        self.assertLess(first["geometric_solid_angle_sr"], 4.0 * math.pi)
        self.assertAlmostEqual(
            first["solid_angle_fraction_4pi"],
            first["geometric_solid_angle_sr"] / (4.0 * math.pi),
        )
        self.assertAlmostEqual(first["detector_active_volume_cm3"], 0.1)

    def test_raw_csv_parser_and_weighted_metrics(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_scan_metrics_") as temporary:
            raw = Path(temporary) / "raw.csv"
            AnalyzeResultsTests.write_raw_fixture(raw)
            metadata, arrays = SCAN.read_raw_event_csv(raw)
            metrics = SCAN.event_metrics(
                arrays,
                SCAN.enumerate_cases(self.config)[0],
                self.config["response"],
            )

        self.assertEqual(metadata["schema"], "PRISM_WP5_RAW_V1")
        self.assertEqual(metrics["events"], 4)
        self.assertAlmostEqual(metrics["incident_weight"], 8.0)
        self.assertAlmostEqual(metrics["weighted_total_deposited_keV"], 114.0)
        self.assertAlmostEqual(
            metrics["weighted_mean_deposited_keV_per_incident"], 14.25
        )
        self.assertAlmostEqual(metrics["detection_weight_fraction_proxy"], 0.75)
        self.assertAlmostEqual(metrics["ag_kalpha_entry_weight"], 2.0)
        self.assertAlmostEqual(metrics["ag_kbeta_entry_weight"], 2.0)
        self.assertAlmostEqual(
            metrics["ag_kalpha_entry_weight_per_incident"], 0.25
        )
        self.assertAlmostEqual(
            metrics["ag_kbeta_entry_weight_per_incident"], 0.25
        )
        self.assertAlmostEqual(
            metrics["fluorescence_roi_weight_fraction_proxy"], 0.5
        )
        self.assertAlmostEqual(
            metrics["background_weight_fraction_of_incident_proxy"], 0.25
        )
        self.assertEqual(metrics["ag_kalpha_entries_count"], 1)
        self.assertEqual(metrics["ag_kbeta_entries_count"], 1)
        self.assertEqual(metrics["fluorescence_roi_events_count"], 2)

    def test_prepared_input_evidence_distinguishes_approved_and_synthetic(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_evidence_") as temporary:
            temporary_path = Path(temporary)
            approved = temporary_path / "approved.csv"
            approved.write_text(
                "# schema=PRISM_WP5_PHASE_SPACE_V1\n"
                "# mode=weighted_hdf5_resample\n"
                "# source_downstream_wp5_design_input_approved=True\n"
                "# diagnostic_input_override=False\n"
                "# requested_events=100000\n"
                '# source_contract_validation={"compliant":true,"reasons":[]}\n'
                "event_id,x_mm,y_mm,z_mm,dx,dy,dz,energy_keV,"
                "unit_weight,source_row,source_weight\n",
                encoding="utf-8",
            )
            approved_evidence = SCAN.prepared_input_evidence(approved)
            self.assertTrue(approved_evidence["screening_input_eligible"])
            self.assertEqual(approved_evidence["reasons"], [])

            synthetic = temporary_path / "synthetic.csv"
            prepared, metadata = PREPARE.prepare_synthetic(
                events=4,
                seed=17,
                energy_keV=25.52,
                sigma_x_mm=0.1,
                sigma_z_mm=0.1,
                sigma_divergence_rad=0.0,
            )
            PREPARE.write_prepared_csv(synthetic, prepared, metadata)
            synthetic_evidence = SCAN.prepared_input_evidence(synthetic)
            self.assertFalse(synthetic_evidence["screening_input_eligible"])
            self.assertEqual(
                synthetic_evidence["mode"], "synthetic_monoenergetic"
            )
            self.assertIn(
                "not an approved weighted S4 resample",
                synthetic_evidence["reasons"][0],
            )

    def test_pareto_and_conditional_selection(self):
        objectives = [
            *self.config["selection"]["maximize"],
            *self.config["selection"]["minimize"],
        ]

        def aggregate(case_id, maximize_value, background, volume):
            values = {
                "ag_kalpha_entry_weight_per_incident": maximize_value,
                "ag_kbeta_entry_weight_per_incident": maximize_value,
                "fluorescence_roi_weight_fraction_proxy": maximize_value,
                "background_weight_fraction_of_incident_proxy": background,
                "detector_active_volume_cm3": volume,
            }
            row = {
                "case_id": case_id,
                "eligible_for_selection": True,
            }
            for metric in objectives:
                row[f"{metric}_mean"] = values[metric]
                row[f"{metric}_std"] = 0.0
            return row

        aggregates = [
            aggregate("inferior", 0.10, 0.20, 1.0),
            aggregate("dominant", 0.20, 0.10, 0.5),
        ]
        selection = SCAN.select_candidate(aggregates, self.config["selection"])
        self.assertEqual(selection["selected_case_id"], "dominant")
        self.assertEqual(selection["pareto_case_ids"], ["dominant"])
        self.assertEqual(selection["status"], SCAN.SELECTION_STATUS)
        self.assertIn("not an approved", selection["evidence_boundary"])

    def test_json_and_csv_serialization_are_strict(self):
        with tempfile.TemporaryDirectory(prefix="prism_wp5_scan_strict_") as temporary:
            temporary_path = Path(temporary)
            json_path = temporary_path / "strict.json"
            csv_path = temporary_path / "strict.csv"
            SCAN.write_strict_json(
                json_path,
                {"finite": 1.25, "nonfinite": math.nan, "nested": [math.inf]},
            )
            SCAN.write_rows_csv(
                csv_path,
                [{"finite": 1.25, "nonfinite": math.nan, "missing": None}],
            )
            document = json.loads(
                json_path.read_text(encoding="utf-8"),
                parse_constant=lambda value: self.fail(
                    f"non-standard JSON constant: {value}"
                ),
            )
            with csv_path.open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(document["finite"], 1.25)
        self.assertIsNone(document["nonfinite"])
        self.assertEqual(document["nested"], [None])
        self.assertEqual(rows[0]["nonfinite"], "")
        self.assertEqual(rows[0]["missing"], "")

    def test_scan_help_shows_effective_defaults(self):
        completed = subprocess.run(
            [sys.executable, str(SCAN_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("wp5_scan.json", completed.stdout)
        self.assertIn("(default: 0)", completed.stdout)
        self.assertIn("20260728", completed.stdout)
        self.assertIn("--max-cases", completed.stdout)

    def test_real_geant4_single_case_smoke_when_binary_is_supplied(self):
        binary_text = os.environ.get("PRISM_WP5_BINARY")
        if not binary_text:
            self.skipTest("set PRISM_WP5_BINARY to run the Geant4 scan smoke test")
        binary = Path(binary_text)
        self.assertTrue(binary.is_file(), binary)
        with tempfile.TemporaryDirectory(prefix="prism_wp5_scan_smoke_") as temporary:
            temporary_path = Path(temporary)
            prepared = temporary_path / "phase_space.csv"
            output = temporary_path / "scan"
            environment = os.environ.copy()
            environment["MPLBACKEND"] = "Agg"
            environment["MPLCONFIGDIR"] = str(temporary_path / "matplotlib")
            prepare = subprocess.run(
                [
                    sys.executable,
                    str(PREPARE_PATH),
                    "--synthetic-monoenergetic",
                    "--synthetic-energy-keV",
                    "30",
                    "--events",
                    "128",
                    "--seed",
                    "19",
                    "--output",
                    str(prepared),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCAN_PATH),
                    "--binary",
                    str(binary),
                    "--input",
                    str(prepared),
                    "--output-dir",
                    str(output),
                    "--events",
                    "128",
                    "--seeds",
                    "23",
                    "--max-cases",
                    "1",
                    "--no-plots",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary_path = output / "wp5_detector_scan_summary.json"
            summary = json.loads(
                summary_path.read_text(encoding="utf-8"),
                parse_constant=lambda value: self.fail(
                    f"non-standard JSON constant: {value}"
                ),
            )
            self.assertTrue(
                (output / "wp5_detector_scan_runs.csv").is_file()
            )
            self.assertTrue(
                (output / "wp5_detector_scan_aggregates.csv").is_file()
            )

        self.assertEqual(summary["status"], SCAN.SOFTWARE_SMOKE_STATUS)
        self.assertTrue(summary["software_smoke_or_partial_scan"])
        self.assertTrue(summary["case_limit_applied"])
        self.assertFalse(summary["independent_seed_gate_satisfied"])
        self.assertTrue(summary["event_limit_applied"])
        self.assertFalse(summary["prepared_events_gate_satisfied"])
        self.assertFalse(
            summary["input_evidence"]["screening_input_eligible"]
        )
        self.assertEqual(
            summary["input_evidence"]["mode"], "synthetic_monoenergetic"
        )
        self.assertTrue(
            any(
                "input phase space" in reason
                for reason in summary["software_smoke_reasons"]
            )
        )
        self.assertEqual(summary["cases_generated"], 48)
        self.assertEqual(summary["cases_executed"], 1)
        self.assertEqual(summary["cases_requested"], 1)
        self.assertEqual(summary["successful_runs"], 1)
        self.assertEqual(summary["failed_runs"], 0)
        self.assertEqual(summary["completed_cases"], 1)
        self.assertEqual(summary["statistics_eligible_cases"], 0)
        self.assertEqual(summary["eligible_cases"], 0)
        self.assertEqual(
            summary["selection"]["selected_case_id"],
            "a00_d00_w00_h00_t00",
        )


class InterfaceConsistencyTests(unittest.TestCase):
    def test_reference_config_matches_documented_geometry(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["sample"]["material"], "Ag")
        self.assertEqual(config["detector"]["material"], "Cd0.9Zn0.1Te")
        self.assertEqual(config["detector"]["angle_deg"], 90.0)
        self.assertTrue(config["physics"]["fluorescence"])
        self.assertTrue(config["physics"]["auger"])
        self.assertTrue(config["physics"]["pixe"])

    def test_compiled_help_when_binary_is_supplied(self):
        binary_text = os.environ.get("PRISM_WP5_BINARY")
        if not binary_text:
            self.skipTest("set PRISM_WP5_BINARY to validate a compiled executable")
        binary = Path(binary_text)
        self.assertTrue(binary.is_file(), binary)
        completed = subprocess.run(
            [str(binary), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--detector-angle-deg", completed.stdout)
        self.assertIn("default: 90", completed.stdout)
        self.assertIn("--resolution-noise-fwhm-keV", completed.stdout)
        self.assertIn("default: 0.8", completed.stdout)

    def test_compiled_binary_rejects_uncontracted_csv_when_supplied(self):
        binary_text = os.environ.get("PRISM_WP5_BINARY")
        if not binary_text:
            self.skipTest("set PRISM_WP5_BINARY to validate a compiled executable")
        binary = Path(binary_text)
        self.assertTrue(binary.is_file(), binary)
        with tempfile.TemporaryDirectory(prefix="prism_wp5_schema_") as temporary:
            temporary_path = Path(temporary)
            phase_space = temporary_path / "uncontracted.csv"
            phase_space.write_text(
                "event_id,x_mm,y_mm,z_mm,dx,dy,dz,energy_keV\n"
                "0,0,0,0,0,1,0,25.52\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    str(binary),
                    "--input",
                    str(phase_space),
                    "--output",
                    str(temporary_path / "events.csv"),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "schema=PRISM_WP5_PHASE_SPACE_V1",
            completed.stderr + completed.stdout,
        )

    def test_compiled_subset_preserves_prepared_total_weight_when_supplied(self):
        binary_text = os.environ.get("PRISM_WP5_BINARY")
        if not binary_text:
            self.skipTest("set PRISM_WP5_BINARY to validate a compiled executable")
        binary = Path(binary_text)
        self.assertTrue(binary.is_file(), binary)
        with tempfile.TemporaryDirectory(prefix="prism_wp5_subset_") as temporary:
            temporary_path = Path(temporary)
            phase_space = temporary_path / "prepared.csv"
            raw = temporary_path / "events.csv"
            prepared, metadata = PREPARE.prepare_synthetic(
                events=8,
                seed=17,
                energy_keV=25.52,
                sigma_x_mm=0.1,
                sigma_z_mm=0.1,
                sigma_divergence_rad=0.0,
            )
            PREPARE.write_prepared_csv(phase_space, prepared, metadata)
            completed = subprocess.run(
                [
                    str(binary),
                    "--input",
                    str(phase_space),
                    "--output",
                    str(raw),
                    "--events",
                    "2",
                    "--seed",
                    "29",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            raw_metadata, arrays = ANALYZE.read_metadata_and_rows(raw)
        self.assertEqual(raw_metadata["prepared_events_available"], "8")
        self.assertEqual(
            raw_metadata["normalization_rescaled_for_event_subset"], "true"
        )
        self.assertTrue(
            np.allclose(arrays["normalization_weight"], 4.0)
        )
        self.assertAlmostEqual(
            float(np.sum(arrays["normalization_weight"])), 8.0
        )

    def test_compiled_binary_rejects_truncated_prepared_csv_when_supplied(self):
        binary_text = os.environ.get("PRISM_WP5_BINARY")
        if not binary_text:
            self.skipTest("set PRISM_WP5_BINARY to validate a compiled executable")
        binary = Path(binary_text)
        self.assertTrue(binary.is_file(), binary)
        with tempfile.TemporaryDirectory(prefix="prism_wp5_truncated_") as temporary:
            temporary_path = Path(temporary)
            phase_space = temporary_path / "prepared.csv"
            raw = temporary_path / "events.csv"
            prepared, metadata = PREPARE.prepare_synthetic(
                events=8,
                seed=17,
                energy_keV=25.52,
                sigma_x_mm=0.1,
                sigma_z_mm=0.1,
                sigma_divergence_rad=0.0,
            )
            PREPARE.write_prepared_csv(phase_space, prepared, metadata)
            lines = phase_space.read_text(encoding="utf-8").splitlines()
            header_index = next(
                index
                for index, line in enumerate(lines)
                if not line.startswith("#")
            )
            phase_space.write_text(
                "\n".join(
                    [
                        *lines[: header_index + 1],
                        *lines[header_index + 1 : header_index + 3],
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    str(binary),
                    "--input",
                    str(phase_space),
                    "--output",
                    str(raw),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "requested_events metadata (8) does not match",
            completed.stderr + completed.stdout,
        )


if __name__ == "__main__":
    unittest.main()
