# CONTEXT.md

## User

Simone Manti, physicist and postdoctoral researcher at INFN Laboratori Nazionali di Frascati.

Main expertise:

* X-ray spectroscopy (XES, XAS, XRF)
* Crystal spectrometers
* Bayesian optimization
* Detector development
* Atomic physics
* Kaonic atoms
* Condensed matter applications
* Machine learning for physics

The goal is to assist in scientific research, proposal writing, simulation development, data analysis, and experimental design.

---

# Main Project

## Grant Giovani INFN CSN5

### Working title

BELISARIUS

Possible expansion:

BEtatron LIght for Spectroscopic Absorption and Resonant Investigations using Ultrafast Sources

Project goal:

Develop and validate a VOXES-like crystal spectrometer for X-ray Absorption Spectroscopy (XAS) and X-ray Emission Spectroscopy (XES) using the EuAPS betatron source.

The project should be clearly positioned as:

* Detector and instrumentation development
* Spectroscopy methodology development
* Technology transfer toward EuAPS
* New capability for laboratory-scale ultrafast spectroscopy

The project must not appear as merely purchasing commercial equipment for EuAPS.

---

# Scientific Motivation

Current EuAPS diagnostics focus mainly on:

* imaging
* beam characterization
* source optimization

The proposed project develops:

* high-resolution XAS
* high-resolution XES
* future pump-probe spectroscopy

using crystal spectrometers optimized for extended betatron sources.

Main novelty:

Demonstrate that high-resolution crystal spectroscopy traditionally associated with synchrotrons can be adapted to compact laser-plasma betatron sources.

---

# VOXES Background

VOXES is a Von Hamos spectrometer developed at INFN.

Key features:

* HAPG mosaic crystals
* Extended X-ray sources
* eV-scale energy resolution
* Energy range approximately 2-10 keV

Important concept:

VOXES demonstrated that extended sources can still provide high-resolution spectroscopy through suitable crystal optics.

This philosophy should be transferred to EuAPS.

---

# Proposed Experimental Roadmap

## Phase 1

Simulation and design.

Objectives:

* Source modelling
* Crystal optimization
* Geometry optimization
* Signal estimation
* Background estimation

Tools:

* SHADOW4
* Geant4

Outputs:

* Expected resolution
* Expected efficiency
* Expected signal rates

---

## Phase 2

Laboratory validation.

Location:

VOXES setup at LNF.

Objectives:

* Build prototype
* Validate geometry
* Validate calibration procedures
* Demonstrate XAS capability
* Demonstrate XES capability

Priority:

XAS demonstration first.

Reason:

XAS is likely more feasible with betatron flux than XES.

---

## Phase 3

Deployment at EuAPS.

Objectives:

* Install spectrometer
* Commission beamline
* Measure reference samples
* Benchmark against simulations

Possible targets:

* Cu K-edge
* Fe K-edge
* Ni K-edge

---

## Work Packages

### WP1 - Simulations

Develop complete simulation chain.

Tasks:

* Geant4 source simulations
* SHADOW4 crystal simulations
* Optimization studies
* Flux and SNR estimates

Deliverables:

* Optimized geometry
* Performance predictions

---

### WP2 - Design and Construction

Selection and procurement of:

* crystals
* motorized stages
* detectors
* mechanics

Development of:

* support structures
* alignment procedures

Deliverables:

* Complete spectrometer prototype

---

### WP3 - Validation at VOXES

Tasks:

* XES measurements
* XAS measurements
* Calibration studies
* Resolution measurements

Deliverables:

* Experimental validation report
* Conference contribution
* Publication

---

### WP4 - EuAPS Measurements

Tasks:

* Installation
* Commissioning
* First XAS measurements
* First XES measurements

Deliverables:

* Demonstration experiment

---

### WP5 - Dissemination

Tasks:

* Conferences
* Publications
* INFN reports
* Student training

Deliverables:

* Journal papers
* Conference presentations

---

# Detector Development Component

The project should include genuine instrumentation development.

Possible topics:

## Silicon Drift Detector Development

Motivations:

* Timing capability
* High-rate operation
* Custom geometry
* Multi-channel readout
* Trigger generation
* Integration with EuAPS timing structure

Possible activities:

* Sensor characterization
* Bonding
* Front-end electronics
* Readout firmware
* DAQ integration

Important argument:

Commercial SDDs do not necessarily satisfy timing, geometry, trigger, and integration requirements of EuAPS.

---

# Expected Criticisms and Responses

## Criticism

"You are building a setup for EuAPS."

Response:

The project develops instrumentation, methodology, simulations, and analysis tools that remain available to INFN independently of EuAPS.

---

## Criticism

"What happens after EuAPS?"

Response:

The spectrometer becomes a permanent platform for:

* XAS
* XES
* detector R&D
* future compact-source spectroscopy

---

## Criticism

"Why not buy a commercial spectrometer?"

Response:

Commercial solutions are not optimized for:

* EuAPS source characteristics
* timing requirements
* detector integration
* future developments

The project develops know-how and instrumentation within INFN.

---

# Preferred Coding Style

Python:

* clean
* modular
* object oriented when useful
* scientific readability over cleverness

Preferred libraries:

* numpy
* scipy
* matplotlib
* pandas
* gpytorch
* botorch
* zfit
* iminuit
* geant4 interfaces
* SHADOW4

For simulations:

* reproducibility first
* configuration files
* version control
* documented assumptions

---

# Long-Term Vision

Create an INFN capability for:

* compact-source XAS
* compact-source XES
* ultrafast spectroscopy
* detector development
* future pump-probe experiments

Position INFN as a reference laboratory for high-resolution spectroscopy using laser-plasma accelerator based X-ray sources.
