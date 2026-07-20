# Simulation of Ag K-edge XAS

## Goal

Implement a simulation chain using **SHADOW4** and **GEANT4** for fluorescence-mode X-ray absorption spectroscopy at the Ag K-edge (~25.5 keV), with a VOXES-like Von Hamos geometry and a Ge(880) crystal.

The simulation should determine:

- spot size and energy distribution at the Ag sample
- suitable tube-crystal and crystal-sample distances
- the effect and necessity of two slits
- the fluorescence spectrum measured by a CZT detector

The concept is inspired by `SANDBOX/Yamamoto_2026_SelectionMonochromator.pdf`, but must be adapted to a VOXES-like Von Hamos layout.

## Target geometry

```text
W-anode X-ray tube -> Slit 1 -> Ge(880) crystal -> Slit 2 -> Ag sample -> CZT detector
```

Main parameters:

- tube-to-crystal and crystal-to-sample distances
- slit positions and apertures
- crystal orientation, dimensions, and curvature
- angular acceptance, flux, and energy resolution
- CZT position, active area, and solid-angle coverage

## Simulation strategy

- **SHADOW4:** source generation, slits, crystal diffraction, and transport to the sample
- **GEANT4:** interactions in Ag, fluorescence production, transport, and CZT response

The SHADOW4-to-GEANT4 interface should store:

```text
x, y, z, dx, dy, dz, energy_keV, weight
```

Keep geometry and source parameters configurable and separate from the simulation logic.

## Work packages

### WP1 — Monoenergetic ray tracing

Develop a minimal SHADOW4 simulation using photons near 25.5 keV.

Tasks:

- define the source and Ge(880) crystal in Von Hamos geometry
- trace photons to the crystal and sample plane
- inspect acceptance, footprint, reflected directions, and focal position
- estimate suitable source-crystal and crystal-sample distances

Start with a Python script. Add an OASYS `.ows` files for visualization or debugging.

Outputs:

- ray distribution after the crystal
- 2D beam profile and spot size at the sample
- focal position
- accepted and rejected photon fractions
- central-ray geometry and curved-crystal visualization

### WP2 — Realistic X-ray tube

Replace the monoenergetic source with a tungsten-anode tube spectrum generated with **SpekPy**.

Tasks:

- configure tube voltage, filtration, anode angle, and source size
- generate and sample the tube spectrum
- propagate the spectrum through SHADOW4
- compare spectra before and after the crystal

Outputs:

- source spectrum
- spectrum and flux near the Ag K-edge after diffraction
- beam profile and energy-position correlation at the sample

### WP3 — Slits

Add two VOXES-like slits:

- Slit 1 after the tube for source shaping and divergence control
- Slit 2 before the crystal for angular selection

Scan slit positions and apertures, then quantify their effects on:

- transmitted flux
- divergence
- crystal illumination
- spot size
- spectral bandwidth

Determine whether both slits are required and identify recommended settings.

### WP4 — End-to-end SHADOW4 simulation

Combine the tube, slits, crystal, and sample plane.

Tasks:

- scan distances, slit apertures, and crystal settings
- optimize the compromise between flux, spot size, and energy resolution
- export the photon phase space at the sample for GEANT4

Outputs:

- optimized geometry
- 2D spot and angular distribution at the sample
- energy spectrum at the sample
- reusable phase-space file

### WP5 — Fluorescence simulation

Use GEANT4 to simulate the SHADOW4 beam interacting with an Ag sample and the resulting CZT response.

Tasks:

- import or sample photons from the WP4 phase space
- define the Ag sample geometry and thickness
- enable low-energy electromagnetic physics and atomic de-excitation
- simulate Ag fluorescence and scattering backgrounds
- define a simplified CZT detector
- scan detector position, distance, area, and angle
- apply a basic detector energy-resolution model

Outputs:

- deposited-energy spectrum in CZT
- Ag K-alpha and K-beta peaks
- scattering background
- detection efficiency and geometrical acceptance
- recommended CZT geometry

## Implementation priorities

1. Make WP1 minimal and functional before adding realism.
2. Store geometry and source parameters in configuration files.
3. Validate each work package independently.
4. Save intermediate results in reusable formats such as CSV, NumPy, HDF5, or ROOT.
5. Use reproducible random seeds and record simulation metadata.
6. Add parameter scans only after the baseline geometry works.
7. Keep the first GEANT4 model simple and add detector details later.

## Suggested repository structure

```text
project/
├── CONTEXT.md
├── config/
│   ├── geometry.yaml
│   ├── source.yaml
│   └── detector.yaml
├── shadow4/
│   ├── wp1_monoenergetic.py
│   ├── wp2_tube_source.py
│   ├── wp3_slit_scan.py
│   └── wp4_end_to_end.py
├── geant4/
│   └── fluorescence_simulation/
├── data/
├── results/
└── tests/
```

## Scope rules for Codex

- Prefer simple, testable scripts over premature abstractions.
- Do not invent SHADOW4 or GEANT4 APIs; verify classes and units before use.
- State all assumptions explicitly.
- Preserve physical units in variable names or use a unit library where practical.
- Generate plots and summary tables for every parameter scan.
- Do not optimize the GEANT4 detector before the SHADOW4 beam geometry is validated.
