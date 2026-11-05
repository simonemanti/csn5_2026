SHELL := /bin/bash
.DEFAULT_GOAL := all
INKSCAPE ?= inkscape
LATEX ?= lualatex
PDFTOCAIRO ?= pdftocairo
PNG_WIDTH ?= 1800
FOCUSING_PNG_WIDTH ?= 3363
NAME := v1_Focusing_Area

.PHONY: all focusing vignettes xas xanes czt crystal pulse clean
all: focusing
focusing: $(NAME).pdf $(NAME).svg $(NAME).png
vignettes: xas xanes czt crystal pulse

.build/XAS.pdf: 1_XAS/XAS.svg
	mkdir -p .build
	$(INKSCAPE) $< --export-area-page --export-type=pdf --export-filename=$@

.build/XANES.pdf: 2_XANES/XANES.svg
	mkdir -p .build
	$(INKSCAPE) $< --export-area-page --export-type=pdf --export-filename=$@

$(NAME).pdf: $(NAME).tex .build/XAS.pdf .build/XANES.pdf 4_Crystal/reflectivity_Ge220.dat 5_Pulse_Shape/waveforms.dat
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build $<
	cp .build/$(NAME).pdf $@

$(NAME).svg: $(NAME).pdf
	$(PDFTOCAIRO) -svg $< $@
	$(INKSCAPE) $@ --export-text-to-path --export-plain-svg --export-filename=$@

$(NAME).png: $(NAME).svg
	$(INKSCAPE) $< --export-area-page --export-width=$(FOCUSING_PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

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
