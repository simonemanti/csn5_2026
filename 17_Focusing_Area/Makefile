SHELL := /bin/bash
.DEFAULT_GOAL := all
# Inkscape exports share a D-Bus application; serialize even when make uses -j.
.NOTPARALLEL:
INKSCAPE ?= inkscape
LATEX ?= lualatex
PDFTOCAIRO ?= pdftocairo
PNG_WIDTH ?= 1800
FOCUSING_PNG_WIDTH ?= 3363
NAMES := v1_Focusing_Area v2_Focusing_Area v3_Focusing_Area v4_Focusing_Area

.PHONY: all focusing vignettes xas xanes czt crystal pulse clean
all: focusing
focusing: $(NAMES:%=%.pdf) $(NAMES:%=%.svg) $(NAMES:%=%.png) v0_Confronto.png
vignettes: xas xanes czt crystal pulse

.build/XAS.pdf: 1_XAS/XAS.svg
	mkdir -p .build
	$(INKSCAPE) $< --export-area-page --export-type=pdf --export-filename=$@

.build/XANES.pdf: 2_XANES/XANES.svg
	mkdir -p .build
	$(INKSCAPE) $< --export-area-page --export-type=pdf --export-filename=$@

# Recolour only the outlined text groups; black curves, levels and borders stay.
assets/XAS_C2.svg: 1_XAS/XAS.svg Makefile
	mkdir -p assets
	sed -e 's/\#1f77b4/\#2ca02c/g' -e 's/fill:\#000000;fill-opacity:1;stroke-width:/fill:\#002a48;fill-opacity:1;stroke-width:/g' $< > $@

assets/XANES_C4.svg: 2_XANES/XANES.svg Makefile
	mkdir -p assets
	sed -e 's/\#ff7f0e/\#9467bd/g' -e 's/style="fill:\#000000;fill-opacity:1"/style="fill:\#002a48;fill-opacity:1"/g' $< > $@

.build/XAS_C2.pdf: assets/XAS_C2.svg
	mkdir -p .build
	$(INKSCAPE) $< --export-area-page --export-type=pdf --export-filename=$@

.build/XANES_C4.pdf: assets/XANES_C4.svg
	mkdir -p .build
	$(INKSCAPE) $< --export-area-page --export-type=pdf --export-filename=$@

$(NAMES:%=%.pdf): %.pdf: %.tex focusing_common.tex .build/XAS_C2.pdf .build/XANES_C4.pdf 4_Crystal/reflectivity_Ge220.dat 5_Pulse_Shape/waveforms.dat
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build $<
	cp .build/$@ $@

$(NAMES:%=%.svg): %.svg: %.pdf
	$(PDFTOCAIRO) -svg $< $@
	$(INKSCAPE) $@ --export-text-to-path --export-plain-svg --export-filename=$@

$(NAMES:%=%.png): %.png: %.svg
	$(INKSCAPE) $< --export-area-page --export-width=$(FOCUSING_PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

v0_Confronto.png: compare_layouts.py $(NAMES:%=%.png)
	python3 compare_layouts.py

xas: 1_XAS/XAS.png
xanes: 2_XANES/XANES.png

1_XAS/XAS.png: 1_XAS/XAS.svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

2_XANES/XANES.png: 2_XANES/XANES.svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

czt:
	$(MAKE) -C 3_CZT PNG_WIDTH=$(PNG_WIDTH)

crystal:
	$(MAKE) -C 4_Crystal PNG_WIDTH=$(PNG_WIDTH)

pulse:
	$(MAKE) -C 5_Pulse_Shape PNG_WIDTH=$(PNG_WIDTH)

clean:
	rm -rf .build
	$(MAKE) -C 3_CZT clean
	$(MAKE) -C 4_Crystal clean
	$(MAKE) -C 5_Pulse_Shape clean
