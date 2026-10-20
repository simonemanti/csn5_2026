from __future__ import annotations

import ast
import importlib.util
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import xraylib


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "photon_budget.py"
CONFIG = ROOT / "config" / "baseline.json"
SPEC = importlib.util.spec_from_file_location("prism_photon_budget", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PB)


class AnalyticPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = PB.load_config(CONFIG)

    def test_kramers_spectrum_conserves_assumed_xray_power(self) -> None:
        voltage = 60.0
        power = 500.0
        z = 74
        coefficient = 9e-10
        energies = np.linspace(1e-5, voltage, 1_000_001)
        rates = np.asarray(
            [
                PB.kramers_spectral_photon_rate_per_keV(
                    energy, voltage, power, z, coefficient
                )[0]
                for energy in energies
            ]
        )
        integrated_power = np.trapezoid(rates * energies, energies) * PB.KEV_TO_J
        _, _, expected_power = PB.kramers_spectral_photon_rate_per_keV(
            25.52, voltage, power, z, coefficient
        )
        self.assertAlmostEqual(integrated_power / expected_power, 1.0, places=6)

    def test_kramers_has_no_photons_at_or_above_tube_voltage(self) -> None:
        for energy in (60.0, 61.0):
            result = PB.kramers_spectral_photon_rate_per_keV(
                energy, 60.0, 500.0, 74, 9e-10
            )
            self.assertEqual(result, (0.0, 0.0, 0.0))

    def test_rectangular_solid_angle_has_correct_limits(self) -> None:
        tiny = PB.rectangular_solid_angle_sr(1.0, 1.0, 1000.0)
        self.assertAlmostEqual(tiny, 1e-6, delta=1e-12)
        near = PB.rectangular_solid_angle_sr(1000.0, 1000.0, 1e-3)
        self.assertAlmostEqual(near, 2.0 * math.pi, delta=2e-5)

    def test_fluorescence_is_zero_below_edge_and_bounded_above(self) -> None:
        edge = xraylib.EdgeEnergy(
            xraylib.SymbolToAtomicNumber("Ag"), xraylib.K_SHELL
        )
        below, below_rows = PB.slab_fluorescence_probability(
            edge - 0.001, self.config["sample"]
        )
        above, rows = PB.slab_fluorescence_probability(
            edge + 0.006, self.config["sample"]
        )
        self.assertEqual(below, 0.0)
        self.assertEqual(below_rows, [])
        self.assertGreater(above, 0.0)
        self.assertLessEqual(above, 1.0)
        self.assertEqual({row["line"] for row in rows}, {"KA1", "KA2"})
        self.assertTrue(
            all(0.0 < row["escape_probability_per_incident_photon"] < 1.0 for row in rows)
        )

    def test_czt_efficiency_is_physical_and_high_at_ag_kalpha(self) -> None:
        efficiency = PB.czt_intrinsic_efficiency(22.1, 5.8, 2.0)
        self.assertGreater(efficiency, 0.99)
        self.assertLessEqual(efficiency, 1.0)

    def test_signal_time_scales_inversely_with_rate(self) -> None:
        first = PB.signal_time_h(1.0, 101, 20.0, 1.0)
        second = PB.signal_time_h(2.0, 101, 20.0, 1.0)
        self.assertAlmostEqual(first / second, 2.0)


class Shadow4IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = PB.load_config(CONFIG)

    def test_small_shadow4_trace_reproduces_baseline_order_of_magnitude(self) -> None:
        row = PB.trace_optics_once(self.config, nrays=20_000, seed=12345)
        self.assertGreater(row["throughput"], 0.002)
        self.assertLess(row["throughput"], 0.007)
        self.assertGreater(row["geometric_intercept_fraction"], 0.5)
        self.assertLess(row["geometric_intercept_fraction"], 0.8)
        self.assertGreater(row["sample_gaussian_equivalent_fwhm_x_mm"], 0.1)
        self.assertLess(row["sample_gaussian_equivalent_fwhm_x_mm"], 0.5)

    def test_end_to_end_smoke_writes_reusable_outputs(self) -> None:
        old_backend = os.environ.get("MPLBACKEND")
        os.environ["MPLBACKEND"] = "Agg"
        try:
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                summary = PB.run(
                    CONFIG,
                    output,
                    nrays_override=5_000,
                    seeds_override=[24680],
                    make_plots=False,
                )
                expected = {
                    "photon_budget_summary.json",
                    "shadow4_seed_results.csv",
                    "source_scenarios.csv",
                    "budget_stages.csv",
                    "proposal_numbers.md",
                }
                self.assertEqual(expected, {path.name for path in output.iterdir()})
                stored = json.loads(
                    (output / "photon_budget_summary.json").read_text(encoding="utf-8")
                )
                self.assertEqual(stored["config_sha256"], summary["config_sha256"])
                self.assertEqual(len(stored["source_scenarios"]), 3)
                self.assertIn("no GEANT4", stored["model_scope"])
        finally:
            if old_backend is None:
                os.environ.pop("MPLBACKEND", None)
            else:
                os.environ["MPLBACKEND"] = old_backend

    def test_source_power_scaling_is_linear_at_fixed_voltage(self) -> None:
        low = PB.kramers_spectral_photon_rate_per_keV(
            25.52, 60.0, 75.0, 74, 9e-10
        )[0]
        high = PB.kramers_spectral_photon_rate_per_keV(
            25.52, 60.0, 500.0, 74, 9e-10
        )[0]
        self.assertAlmostEqual(high / low, 500.0 / 75.0)

    def test_no_geant4_dependency_is_imported(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0].lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0].lower())
        self.assertNotIn("geant4", imported)
        self.assertNotIn("geant4_pybind", imported)


if __name__ == "__main__":
    unittest.main()
