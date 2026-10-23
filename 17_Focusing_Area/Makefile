SHELL := /bin/bash
.DEFAULT_GOAL := all
INKSCAPE ?= inkscape
PNG_WIDTH ?= 1800

.PHONY: all xas xanes czt crystal pulse clean
all: xas xanes czt crystal pulse

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
	$(MAKE) -C 3_CZT clean
	$(MAKE) -C 4_Crystal clean
	$(MAKE) -C 5_Pulse_Shape clean
