SHELL := /bin/bash
.DEFAULT_GOAL := all
LATEX ?= xelatex
DVISVGM ?= dvisvgm
INKSCAPE ?= inkscape
PNG_WIDTH ?= 3360

.PHONY: all clean
all: Focusing_Area.svg Focusing_Area.png

# Reuse exactly the normalization of the Ag reference comparison.
XANES_DIR := ../21_XANES_Ag
XANES_INPUTS := $(XANES_DIR)/s1_ref_comparison.py $(XANES_DIR)/data/Ag2O/Ag-K_Ag2O_Si311_50ms_160624.txt $(XANES_DIR)/data/Ag_foil/Ag-K_Ag-foil_Si311_50ms_160624.txt
define XANES_DATA
import sys, runpy
from pathlib import Path
import numpy as np
source = Path("../21_XANES_Ag")
module = runpy.run_path(str(source / "s1_ref_comparison.py"))
for folder, filename, label, color, doi in module["SAMPLES"]:
    energy, mu = np.loadtxt(source / "data" / folder / filename).T
    assert np.isfinite(energy).all() and np.isfinite(mu).all() and np.all(np.diff(energy) > 0)
    normalized, step = module["normalize"](energy, mu, 25514., (-280., -150.), (150., 700.))
    name = "oxide" if folder == "Ag2O" else "metal"
    np.savetxt(Path(sys.argv[1]) / ("xanes_" + name + ".dat"), np.column_stack((energy, normalized)), fmt="%.12g")
    print("XANES", name, "points:", len(energy), "edge step:", step)
endef
export XANES_DATA

# Keep ordinary lettering editable; preserve exact TeX math outlines.
define EDITABLE_SVG
import sys, re, copy
import xml.etree.ElementTree as ET
from pathlib import Path
ns = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", ns[1:-1])
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
text_root = ET.parse(sys.argv[1]).getroot()
path_root = ET.parse(sys.argv[2]).getroot()
style = text_root.find(ns + "style")
math_classes = {c for c, f in re.findall(r"text\.(\w+) \{font-family:([^;]+);", style.text) if not f.startswith("nf")}
text_groups = [g for g in text_root.iter(ns + "g") if g.get("stroke") == "none"]
path_groups = [g for g in path_root.iter(ns + "g") if g.get("stroke") == "none"]
assert len(text_groups) == len(path_groups)
for original, outlined in zip(text_groups, path_groups):
    texts = original.findall(ns + "text")
    if texts and any(t.get("class") in math_classes for t in texts):
        assert all(t.get("class") in math_classes for t in texts)
        original[:] = [copy.deepcopy(e) for e in outlined]
for defs in path_root.findall(ns + "defs"):
    text_root.insert(0, copy.deepcopy(defs))
style.text = re.sub(r"@font-face\{[^}]*\}", "", style.text)
style.text = style.text.replace("font-family:nf0;", "font-family:Arial;font-weight:bold;").replace("font-family:nf1;", "font-family:Arial;")
# Reinsert the original vector icon, at exactly the old crop and physical size.
icon = ET.parse("Old/assets/XAS_C2.svg").getroot()
ids = {e.get("id"): "xas-" + e.get("id") for e in icon.iter() if e.get("id")}
for e in icon.iter():
    for k, v in list(e.attrib.items()):
        if k == "id":
            e.set(k, ids[v])
        else:
            for old, new in ids.items():
                v = v.replace("url(#" + old + ")", "url(#" + new + ")")
                if v == "#" + old: v = "#" + new
            e.set(k, v)
anchor = next(e for e in text_root.iter() if e.get("id") == "xas-original")
scale = (21.6 * 72 / 25.4) / 204
art = ET.SubElement(anchor, ns + "g", {"transform": "scale(%s) translate(-120,-120)" % scale, "stroke": "none"})
for child in icon:
    if child.tag in {ns + "defs", ns + "g", ns + "path", ns + "circle"}:
        art.append(copy.deepcopy(child))
ET.ElementTree(text_root).write(sys.argv[3], encoding="UTF-8", xml_declaration=True)
endef
export EDITABLE_SVG

# Direct TikZ -> XDV -> SVG, without PDF conversion.
Focusing_Area.svg: Focusing_Area.tex Makefile Old/assets/XAS_C2.svg $(XANES_INPUTS) Old/4_Crystal/reflectivity_Ge220.dat Old/5_Pulse_Shape/waveforms.dat
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	python3 -c "$$XANES_DATA" "$$tmp"; \
	TEXINPUTS="$$tmp:$${TEXINPUTS:-}" $(LATEX) -no-pdf -interaction=nonstopmode -halt-on-error -output-directory="$$tmp" $< >"$$tmp/build.log" || { cat "$$tmp/build.log"; exit 1; }; \
	$(DVISVGM) --font-format=woff --bbox=papersize --output="$$tmp/text.svg" "$$tmp/Focusing_Area.xdv"; \
	$(DVISVGM) --no-fonts --bbox=papersize --output="$$tmp/paths.svg" "$$tmp/Focusing_Area.xdv"; \
	python3 -c "$$EDITABLE_SVG" "$$tmp/text.svg" "$$tmp/paths.svg" "$@"

Focusing_Area.png: Focusing_Area.svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

clean:
	rm -f Focusing_Area.svg Focusing_Area.png
