# PRISM v1 - Four independent CZT channels

Open `v1_Setup_PRISM.blend`. In the 3D viewport press **N**, then select **PRISM**.
The two mode buttons set a static fluorescence or incident-beam configuration.
The Switch slider traverses the complete motion. Play starts a reversible
252-frame sequence at 24 fps; Freeze retains the current position. Enable
"Drive from timeline" to scrub the animation directly. Views: Detail / Full / Top.

## Sidebar activation

The sidebar is embedded in the file as `PRISM_Controls.py`, marked Register.
Blender runs it on opening a trusted file with script execution allowed. If
Blender blocks it, use the Scripting workspace, select `PRISM_Controls.py` in
the Text Editor and press **Alt-P** (Run Script). Then return to Layout > N >
PRISM. No global security preference needs to be changed. The separate
`prism_controls.py` is the same source and can also be installed as an add-on.
The motion uses built-in arithmetic drivers and keyframes, with no custom
driver functions, external modules, network access or frame-change handlers.

## Dimensions and design choice

- 1 Blender unit = 1 mm (metric scale_length = 0.001); object mesh dimensions
  are physical, not exaggerated for visibility.
- Original optical positions retained from `11_SETUP_XAS/v2_Setup_PRISM.blend`:
  source-Ge and Ge-sample arms approximately 514.6235 mm; Ge(880), 40 mm
  sagittal chord x 20 mm tangential length x 1 mm thickness, radius 250 mm.
- 4 quasi-hemispherical CZT crystals, **10 x 10 x 5 mm** each, one anode channel
  per module, nominal entrance area **400 mm2** total. This is a size shown in
  Due2lab `WP70_Fabbricazione_EN.pdf`, p. 2. "Quasi-hemispherical" describes the
  electrode/field arrangement, not a dome-shaped outer crystal. Electrode
  details are not fabricated in this model.
- Chosen over an assumed 100 mm2 single-channel planar device because the
  supplied document explicitly shows this quasi-hemispherical size; its
  standard planar single pixel is only 2 x 2 mm2. This is a **geometric
  baseline, not a claim of superior performance at 22 keV**. A thin planar
  custom solution remains a procurement alternative after response testing.
- 1 central detector D1 and 3 detectors at polar angle 30 deg, azimuths
  90/210/330 deg about the central viewing axis. The head is on the same
  reflection side of the foil. Local X is the incident beam at the sample,
  local Y the central fluorescence direction, and Z vertical.
- Default illuminated-point to active-face distance **35 mm**, adjustable
  35-80 mm. The extra 5 mm over the earlier 30 mm example is a provisional
  packaging allowance. For four unobstructed square faces the exact
  geometrical acceptance is 16 atan[25/(r sqrt(r^2+50))] sr: approximately
  0.320 sr, or 2.55% of 4pi, at 35 mm. This is not the detected efficiency;
  windows, dead areas, photopeak response and sample absorption are excluded.
- Ag foil: 25 x 25 mm, **20 micrometres** thick, incidence 45 deg. Thickness
  comes from the existing photon-budget baseline, lateral size is assumed.
  Holder: 29 x 29 mm outer frame; vertical extraction **45 mm** (40-65 mm
  adjustable). Sensor faces remain at beam height or their cap offsets.
- Each module's 14 x 14 x 19 mm package envelope, readout board, mount, stage
  and lift assembly are design assumptions. No supplier package CAD or
  electronics layout was supplied. Tube/slit housings retain the approximate
  envelopes of the source file. Everything is in millimetres, but this is
  **not a fabrication-ready mechanical design**.

## Measurement modes and motion

1. Fluorescence: foil in beam; central D1 at 90 deg to the beam; all four
   active-face normals point to the illuminated spot. The three peripheral
   channels have different take-off angles and are not equivalent for a
   strongly absorbing foil; 400 mm2 is not automatically a 5.3x net gain.
2. Switch: first raise sample, then rotate the entire head horizontally by
   90 deg about the illuminated spot. Beam guides disappear during movement
   to represent a closed shutter; **no hardware shutter is controlled**.
3. Incident I0: sample out; D1 lies on the continuation of the incident beam.
   The other three channels are off-axis. This is a sequential I0 acquisition,
   not simultaneous incident monitoring and not collection of the direct
   beam over all 400 mm2. Actual beam footprint at D1 and attenuation/count
   rate must be measured or simulated before exposure planning.
4. Return: head rotates back before the sample is lowered.

No absolute flux, detector response, spectral resolution, procurement price,
electronic dead time, cable management or motor tolerance is predicted here.
The approximately EUR 53k cost target requires a supplier quotation.
The geometric inspection script verifies dimensions, pointing, incident
alignment, drivers, selected mechanical envelopes and reversible motion;
it does not replace a full supplier CAD interference/tolerance analysis.

## Rebuild and validate

From the project root:

```bash
blender -b --python 24_CZT_Channel_Layouts/create_v1_setup_prism.py -- --render
blender -b --enable-autoexec 24_CZT_Channel_Layouts/v1_Setup_PRISM.blend --python 24_CZT_Channel_Layouts/validate_v1_setup_prism.py
```

Use `-- --help` on the builder to see parameters and defaults. Source files in
`11_SETUP_XAS` and previous layout figures are not modified. The embedded
README and panel travel with the blend file; the preview PNGs are optional.
