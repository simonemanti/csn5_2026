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

PROGETTO

Name status:

The final acronym is not fixed. Avoid using BELISARIUS for now, because it overemphasizes EuAPS/betatron sources before the main scientific objective is mature.

Project goal:

Develop and validate a laboratory fluorescence-XAS platform for operando studies of realistic samples, where transmission XAS is impractical or unrepresentative.

The project should be clearly positioned as:

* X-ray spectroscopy instrumentation development
* Spectroscopy methodology development
* Laboratory fluorescence-XAS for realistic/thick/non-ideal samples
* Operando or in-situ XAS on scientifically motivated benchmark systems
* A future technology-transfer path toward compact or unconventional X-ray sources, including EuAPS if justified

The project must not appear as merely purchasing commercial equipment, nor as a setup built primarily for EuAPS. EuAPS is a possible application, extension, or dedicated WP, not the central goal.

---

# Scientific Motivation

Many relevant problems in energy materials, catalysis, and functional materials require chemical-state information under realistic conditions. XAS is one of the most direct tools for this because it probes oxidation state, local coordination, and electronic structure.

The emergency/problem to present:

* Synchrotron XAS provides excellent data but limited access, slow iteration, and limited compatibility with rapid laboratory screening.
* Laboratory transmission XAS is simpler but often requires thin, homogeneous, carefully prepared samples.
* Fluorescence XAS is better suited to realistic, thick, dilute, or operando samples, but in the laboratory it is limited by the coupled trade-off between flux, energy resolution, background, detector rate capability, and sample/cell geometry.

The proposed project develops:

* fluorescence-mode XAS in the laboratory
* an optimized crystal-optics and detection geometry
* validated simulation and analysis tools for predicting resolution, throughput, background, and signal-to-noise ratio
* an operando demonstration on well-defined benchmark samples

Possible application domains:

* Na-ion or Li-ion battery cathodes
* catalysts and redox-active materials
* reference oxides and foils for validation
* EuAPS or other compact/unconventional X-ray sources as later extensions

---

# Novelty Relative to the State of the Art

Do not claim novelty as "the first time that..." unless it is precise, documented, and necessary.

The novelty should be formulated as a specific capability gap:

Current laboratory XAS instruments can perform high-quality measurements in selected conditions, especially in transmission or with carefully prepared samples. However, routine fluorescence-mode operando XAS on realistic samples remains limited by the combined optimization of:

* accepted source étendue versus energy resolution
* fluorescence collection efficiency versus background
* detector rate capability and pile-up rejection
* sample environment constraints
* scan time versus signal-to-noise ratio
* quantitative agreement between simulation, calibration, and measured spectra

Proposed novelty:

* establish the quantitative operating domain of laboratory fluorescence-XAS for realistic and operando samples;
* design and validate a spectrometer/detection architecture optimized around the flux-resolution-background trade-off, not around a single commercial component;
* demonstrate chemically meaningful XAS observables, such as edge shift, white-line variation, and EXAFS-quality indicators, on selected benchmark samples;
* produce a reusable INFN methodology combining crystal-optics simulations, detector characterization, calibration procedures, and analysis tools.

The key question is:

How much source phase space can be accepted while retaining enough energy resolution and signal quality to extract chemically meaningful XAS information from realistic operando samples?

---

# VOXES Background

VOXES is a Von Hamos spectrometer developed at INFN.

Key features:

* HAPG mosaic crystals
* efficient use of non-microfocus X-ray sources
* eV-scale energy resolution
* Energy range approximately 2-10 keV

Important concept:

VOXES demonstrated that suitable crystal optics can preserve useful energy resolution while accepting enough flux for laboratory X-ray spectroscopy.

This philosophy should be transferred to fluorescence-mode laboratory XAS on realistic samples. EuAPS can later benefit from the same methodology, but it should not drive the main proposal.

---

# Proposed Experimental Roadmap

## Phase 1

Simulation and design.

Objectives:

* Laboratory source modelling
* Crystal optimization
* Geometry optimization
* Signal estimation
* Background estimation
* fluorescence collection and detector-rate estimates

Tools:

* SHADOW4
* Geant4

Outputs:

* Expected resolution
* Expected efficiency
* Expected signal rates
* detectability of selected XAS observables

---

## Phase 2

Laboratory validation.

Location:

VOXES setup at LNF.

Objectives:

* Build prototype
* Validate geometry
* Validate calibration procedures
* Demonstrate fluorescence-XAS capability
* Benchmark against reference spectra and simulations

Priority:

Fluorescence-XAS demonstration first.

Reason:

Fluorescence-XAS directly addresses realistic samples and is more defensible than XES unless flux and SNR estimates justify XES.

---

## Phase 3

Operando demonstration and possible EuAPS extension.

Primary objectives:

* Measure selected realistic samples under static and/or operando conditions
* Benchmark spectra against reference data and simulations
* Quantify edge-shift sensitivity, SNR, scan time, and reproducibility

Optional EuAPS objectives:

* Study compatibility with EuAPS source parameters
* Define required geometry, shielding, timing, and detector conditions
* Perform a pilot measurement only if EuAPS readiness and project timing allow it

Possible targets:

* Fe K-edge
* Ni K-edge
* Mn K-edge
* Cu K-edge

---

## Work Packages

### WP1 - Simulations

Develop complete simulation chain.

Tasks:

* source and sample-environment simulations
* SHADOW4 crystal simulations
* Optimization studies
* Flux and SNR estimates
* detector-rate and pile-up estimates

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

* reference XAS measurements
* fluorescence-XAS measurements
* Calibration studies
* Resolution measurements

Deliverables:

* Experimental validation report
* Conference contribution
* Publication

---

### WP4 - Operando Demonstration and EuAPS Applicability

Tasks:

* Static measurements on selected benchmark samples
* Operando or in-situ fluorescence-XAS demonstration
* Quantitative comparison with reference spectra
* EuAPS applicability study as an optional extension
* Possible pilot EuAPS measurement only if technically and logistically justified

Deliverables:

* Demonstration experiment on realistic samples
* Applicability report for EuAPS or other compact/unconventional X-ray sources

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

# Detector and Readout Component

The detector strategy is open. The project may use an existing SDD, buy a commercial SDD, or develop/customize an SDD-related system if a concrete need is identified.

Possible topics:

## Silicon Drift Detector Strategy

Motivations:

* fluorescence collection efficiency
* high-rate operation
* pile-up rejection
* multi-channel readout
* synchronization with energy scans and operando cells
* compatibility with sample environment and geometry

Possible activities:

* sensor characterization
* evaluation of existing or commercial SDDs
* definition of required active area, solid angle, shaping time, and energy resolution
* front-end electronics
* DAQ integration
* pile-up and dead-time correction
* trigger/synchronization only if scientifically needed

Important argument:

Do not claim "SDD development" unless the work is truly developmental. It is acceptable to use or purchase an SDD if the novelty is in the spectroscopy platform, geometry, calibration, and fluorescence-XAS methodology.

---

# Expected Criticisms and Responses

## Criticism

"You are building a setup for EuAPS."

Response:

No. The project develops laboratory fluorescence-XAS instrumentation, methodology, simulations, and analysis tools for realistic and operando samples. EuAPS is only a possible application or later WP.

---

## Criticism

"What is the so what?"

Response:

The project addresses the lack of routine laboratory fluorescence-XAS on realistic samples. The result is a permanent INFN platform for:

* XAS
* operando/in-situ XAS
* sample-environment-compatible fluorescence measurements
* detector/readout characterization if needed
* future compact-source spectroscopy

---

## Criticism

"Why not buy a commercial spectrometer?"

Response:

Commercial solutions may be useful components but do not by themselves solve the coupled problem:

* sample and cell constraints
* fluorescence background
* flux versus energy resolution
* detector rate and pile-up
* quantitative validation against simulations and reference measurements

The project develops know-how and instrumentation within INFN.

---

## Criticism

"What is the novelty compared with the state of the art?"

Response:

The novelty is not generic laboratory XAS. The novelty is a quantitatively validated fluorescence-XAS methodology for realistic and operando samples, built around the measurable trade-off between source acceptance, energy resolution, fluorescence efficiency, background, detector rate, and scan time.

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
* fluorescence-mode laboratory XAS
* operando/in-situ XAS
* ultrafast spectroscopy
* detector/readout integration
* future pump-probe experiments

Position INFN as a reference laboratory for high-resolution X-ray spectroscopy on realistic samples, with future applicability to compact and unconventional X-ray sources including EuAPS.
