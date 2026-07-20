# WP1 OASYS2 workflow

`wp1_monoenergetic.ows` is the visual/debugging counterpart of
`../shadow4/wp1_monoenergetic.py`.  It contains:

1. a 25.52 keV Gaussian geometrical source;
2. a finite 40 x 20 mm Ge(880) crystal, cylindrically curved in the sagittal
   direction with a 0.25 m radius;
3. an X-Z profile at the nominal sample plane;
4. an X-Y crystal-footprint plot;
5. the SHADOW4 beamline information viewer.

The source and image arms are both 0.5146234948 m.  The crystal widget uses
its `Concave` GUI selection because OASYS2-SHADOW4 0.0.46 maps that selection
to SHADOW4 `Convexity.DOWNWARD`, matching the Python baseline.

Launch it from the repository root with:

```bash
conda run -n shadow4 python -m oasys2.canvas \
  3_Simulations/oasys/wp1_monoenergetic.ows
```

Validate the XML, widget names, channels, and settings against the installed
OASYS2 registry without opening the GUI with:

```bash
conda run -n shadow4 python \
  3_Simulations/oasys/validate_wp1_ows.py
```

The workflow is intentionally a visual baseline.  The Python driver remains
the authoritative batch workflow for the longitudinal scan, HDF5 export, and
exclusive throughput accounting.
