#!/usr/bin/env python3
"""Minimal SHADOW4 trace: source, Ge(880) crystal, and sample plane."""

from shadow4.beamline.optical_elements.crystals.s4_sphere_crystal import (
    S4SphereCrystal,
    S4SphereCrystalElement,
)
from shadow4.sources.source_geometrical.source_geometrical import SourceGeometrical
from syned.beamline.element_coordinates import ElementCoordinates
from syned.beamline.shape import Convexity, Direction, Rectangle


def main() -> None:
    energy_ev = 25_520.0
    distance_m = 0.50

    source = SourceGeometrical(nrays=100_000, seed=12345)
    source.set_spatial_type_gaussian(sigma_h=1e-4, sigma_v=1e-4)
    source.set_depth_distribution_off()
    source.set_angular_distribution_flat(
        hdiv1=-0.06, hdiv2=0.06, vdiv1=-1e-5, vdiv2=1e-5
    )
    source.set_energy_distribution_singleline(energy_ev, unit="eV")

    crystal = S4SphereCrystal(
        boundary_shape=Rectangle(-0.02, 0.02, -0.01, 0.01),
        material="Ge",
        miller_index_h=8,
        miller_index_k=8,
        miller_index_l=0,
        is_thick=1,
        thickness=1e-3,
        f_central=True,
        phot_cent=energy_ev,
        material_constants_library_flag=0,
        radius=0.25,
        is_cylinder=True,
        cylinder_direction=Direction.SAGITTAL,
        convexity=Convexity.DOWNWARD,
    )

    sample, footprint = S4SphereCrystalElement(
        optical_element=crystal,
        coordinates=ElementCoordinates(
            p=distance_m,
            q=distance_m,
            angle_radial=0.0,
            angle_azimuthal=0.0,
            angle_radial_out=None,
        ),
        input_beam=source.get_beam(),
    ).trace_beam()

    print(f"Raggi al cristallo: {footprint.get_number_of_rays(nolost=1)}")
    print(f"Raggi al sample:    {sample.get_number_of_rays(nolost=1)}")


if __name__ == "__main__":
    main()
