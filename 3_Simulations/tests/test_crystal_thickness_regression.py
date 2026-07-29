#!/usr/bin/env python3
"""Regression test for the CrystalPy thick-crystal off-Bragg tails.

The configured 1 mm Ge(880) crystal must use the finite-thickness branch for
polychromatic bandwidth studies.  With identical monoenergetic rays, that
branch preserves the central response while suppressing the non-physical
kiloelectronvolt-scale tails produced by the current thick approximation.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import numpy as np


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
SHADOW4_DIRECTORY = SIMULATION_ROOT / "shadow4"
if str(SHADOW4_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SHADOW4_DIRECTORY))

import wp1_monoenergetic as WP1  # noqa: E402
import wp2_tube_source as WP2  # noqa: E402


class CrystalThicknessRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source_config = WP1.load_json(
            SIMULATION_ROOT / "config" / "wp1_source.json"
        )
        source_config.update(
            nrays=2000,
            seed=77123,
            energy_keV=25.52,
            spatial_distribution="point",
            horizontal_angle_min_rad=-5.0e-4,
            horizontal_angle_max_rad=5.0e-4,
            vertical_angle_min_rad=-1.0e-5,
            vertical_angle_max_rad=1.0e-5,
        )
        cls.incident_beam = WP1.build_source(source_config).get_beam()
        cls.geometry_config = WP1.load_json(
            SIMULATION_ROOT / "config" / "wp1_geometry.json"
        )

    def response(self, energy_keV: float, *, is_thick: bool) -> float:
        incident = self.incident_beam.duplicate()
        incident.set_photon_energy_eV(1000.0 * energy_keV)
        geometry = copy.deepcopy(self.geometry_config)
        geometry["crystal"]["use_thick_crystal_approximation"] = is_thick
        _, post_crystal, _, _ = WP2.trace_incident_beam(
            incident,
            geometry,
            reference_energy_keV=25.52,
        )
        incident_weight = float(np.sum(incident.get_column(23)))
        reflected_weight = float(np.sum(post_crystal.get_column(23)))
        self.assertGreater(incident_weight, 0.0)
        return reflected_weight / incident_weight

    def test_finite_thickness_preserves_peak_and_removes_thick_wings(self) -> None:
        central_thick = self.response(25.52, is_thick=True)
        central_finite = self.response(25.52, is_thick=False)

        self.assertGreater(central_finite, 1.0e-3)
        self.assertAlmostEqual(
            central_finite / central_thick,
            1.0,
            delta=0.01,
        )

        for wing_energy_keV in (24.52, 26.52):
            with self.subTest(energy_keV=wing_energy_keV):
                wing_thick = self.response(wing_energy_keV, is_thick=True)
                wing_finite = self.response(wing_energy_keV, is_thick=False)
                self.assertLess(wing_finite / central_finite, 1.0e-6)
                self.assertGreater(wing_thick / central_thick, 1.0e-3)
                self.assertGreater(wing_thick, 1.0e5 * wing_finite)


if __name__ == "__main__":
    unittest.main()
