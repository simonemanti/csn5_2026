PYTHON ?= python3
PDFTOCAIRO ?= pdftocairo
RSVG_CONVERT ?= rsvg-convert

PLOT_PDF := v1_feasibility.pdf
PLOT_PNG := v1_feasibility.png
IMPORTED_SVG := build/v1_feasibility.imported.svg
FINAL_SVG := v2_feasibility.svg
FINAL_PDF := v2_feasibility.pdf
FINAL_PNG := v2_XAS.png

PLOT_INPUTS := \
	s1_plot.py \
	HAPGrot_Scan.db \
	2025_05_22_Co_N1000_T1_V25_I700_HAPGrot7225_HAPGphi_10.txt

.PHONY: all plot svg pdf png clean help

all: $(FINAL_SVG) $(FINAL_PDF) $(FINAL_PNG)

plot: $(PLOT_PDF)

svg: $(FINAL_SVG)

pdf: $(FINAL_PDF)

png: $(FINAL_PNG)

$(PLOT_PDF): $(PLOT_INPUTS)
	MPLBACKEND=Agg $(PYTHON) s1_plot.py --no-show

$(PLOT_PNG): $(PLOT_PDF)
	@test -f $@ || { rm -f $(PLOT_PDF); $(MAKE) $(PLOT_PDF); }

$(IMPORTED_SVG): $(PLOT_PDF) | build
	$(PDFTOCAIRO) -svg $< $@

$(FINAL_SVG): $(IMPORTED_SVG) compose_svg.py
	$(PYTHON) compose_svg.py $< $@

$(FINAL_PDF): $(FINAL_SVG)
	$(RSVG_CONVERT) --format=pdf --output=$@ $<

$(FINAL_PNG): $(FINAL_SVG)
	$(RSVG_CONVERT) \
		--format=png \
		--dpi-x=600 \
		--dpi-y=600 \
		--output=$@ \
		$<

build:
	mkdir -p $@

clean:
	rm -f $(PLOT_PDF) $(PLOT_PNG) $(FINAL_SVG) $(FINAL_PDF) $(FINAL_PNG)
	rm -rf build

help:
	@echo "make       Generate plot, final SVG, PDF and 600 dpi PNG"
	@echo "make plot  Generate only the Matplotlib PDF/PNG"
	@echo "make svg   Import the PDF and compose the final SVG"
	@echo "make pdf   Generate the final PDF"
	@echo "make png   Generate the final 600 dpi PNG"
	@echo "make clean Remove all generated files"
