SHELL := /bin/bash
.DEFAULT_GOAL := all
LATEX := xelatex
DVISVGM ?= dvisvgm
INKSCAPE ?= inkscape
PNG_WIDTH ?= 3300
REFERENCE := ../21_XANES_Ag/data/Ag_foil/Ag-K_Ag-foil_Si311_50ms_160624.txt
DATA := ag_foil_reference.dat scan_coarse.dat scan_fine.dat scan_grid.dat protocol.json

.PHONY: all clean
all: Protocol_XANES.svg Protocol_XANES.png

$(DATA) &: prepare_data.py $(REFERENCE)
	python3 prepare_data.py

Protocol_XANES.svg: Protocol_XANES.tex $(DATA) Makefile
	mkdir -p .build
	$(LATEX) -no-pdf -interaction=nonstopmode -halt-on-error -output-directory=.build $< > .build/build.log || { cat .build/build.log; exit 1; }
	$(DVISVGM) --no-fonts --bbox=papersize --output=$@ .build/Protocol_XANES.xdv

Protocol_XANES.png: Protocol_XANES.svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-filename=$@

clean:
	rm -rf .build
	rm -f Protocol_XANES.svg Protocol_XANES.png $(DATA)
