SHELL := /bin/bash
.DEFAULT_GOAL := all
LATEX ?= lualatex
INKSCAPE ?= inkscape
PDFTOCAIRO ?= pdftocairo
PNG_WIDTH ?= 3360

.PHONY: all clean
all: Focusing_Area.svg Focusing_Area.png

Focusing_Area.svg: Focusing_Area.tex Old/.build/XAS_C2.pdf Old/.build/XANES_C4.pdf Old/4_Crystal/reflectivity_Ge220.dat Old/5_Pulse_Shape/waveforms.dat
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory="$$tmp" $< >/dev/null && \
	$(PDFTOCAIRO) -svg "$$tmp/Focusing_Area.pdf" $@ && \
	$(INKSCAPE) $@ --export-text-to-path --export-plain-svg --export-filename=$@

Focusing_Area.png: Focusing_Area.svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

clean:
	rm -f Focusing_Area.svg Focusing_Area.png
