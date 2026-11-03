SHELL := /bin/bash
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

LATEX ?= xelatex
PDFTOCAIRO ?= pdftocairo
PNG_WIDTH ?= 2400
NAME := v1_XAS_mode

.PHONY: all clean distclean
all: $(NAME).pdf $(NAME).svg $(NAME).png

$(NAME).pdf: $(NAME).tex
	mkdir -p .build
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build $<
	cp .build/$(NAME).pdf $@

# Cairo outlines the glyphs, preserving Arial on systems without the font.
$(NAME).svg: $(NAME).pdf
	$(PDFTOCAIRO) -svg $< $@

# Transparent PNG, with aspect ratio preserved.
$(NAME).png: $(NAME).pdf
	$(PDFTOCAIRO) -png -singlefile -transp -scale-to-x $(PNG_WIDTH) -scale-to-y -1 $< $(NAME)

clean:
	rm -rf .build

distclean: clean
	rm -f $(NAME).pdf $(NAME).svg $(NAME).png
