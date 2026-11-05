SHELL := /bin/bash
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

LATEX ?= xelatex
PDFTOCAIRO ?= pdftocairo
INKSCAPE ?= inkscape
PNG_WIDTH ?= 2400
NAME := v1_XAS_mode

.PHONY: all clean distclean
all: $(NAME).pdf $(NAME)_editable.svg $(NAME).png

$(NAME).pdf: $(NAME).tex
	mkdir -p .build
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build $<
	cp .build/$(NAME).pdf $@

# Inkscape internal PDF import preserves ordinary text as editable SVG text.
$(NAME)_editable.svg: $(NAME).pdf
	$(INKSCAPE) $< --export-plain-svg --export-filename=$@

# Transparent PNG, with aspect ratio preserved.
$(NAME).png: $(NAME).pdf
	$(PDFTOCAIRO) -png -singlefile -transp -scale-to-x $(PNG_WIDTH) -scale-to-y -1 $< $(NAME)

clean:
	rm -rf .build

distclean: clean
	rm -f $(NAME).pdf $(NAME).svg $(NAME)_editable.svg $(NAME).png
