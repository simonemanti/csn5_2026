SHELL := /bin/bash
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

# Override, for example: make PNG_WIDTH=3200
LATEX := xelatex
PDFTOCAIRO ?= /usr/bin/pdftocairo
PNG_WIDTH ?= 2400
NAME := v1_configurations
FIGURES := $(NAME) $(NAME)_I $(NAME)_I0

.PHONY: all pdf svg png clean distclean
all: pdf svg png
pdf: $(addsuffix .pdf,$(FIGURES))
svg: $(addsuffix .svg,$(FIGURES))
png: $(addsuffix .png,$(FIGURES))

$(NAME).pdf: $(NAME).tex Makefile
	mkdir -p .build
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build $<
	cp .build/$(NAME).pdf $@

$(NAME)_I.pdf: $(NAME).tex Makefile
	mkdir -p .build
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build -jobname=$(NAME)_I '\def\ConfigurationPanel{1}\input{$<}'
	cp .build/$(NAME)_I.pdf $@

$(NAME)_I0.pdf: $(NAME).tex Makefile
	mkdir -p .build
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build -jobname=$(NAME)_I0 '\def\ConfigurationPanel{2}\input{$<}'
	cp .build/$(NAME)_I0.pdf $@

# Outline lettering so that SVGs do not require Arial on the target computer.
%.svg: %.pdf
	$(PDFTOCAIRO) -svg $< $@

# Transparent background; preserve the aspect ratio.
%.png: %.pdf
	$(PDFTOCAIRO) -png -singlefile -transp -scale-to-x $(PNG_WIDTH) -scale-to-y -1 $< $*

clean:
	rm -rf .build

distclean: clean
	rm -f $(addsuffix .pdf,$(FIGURES)) $(addsuffix .svg,$(FIGURES)) $(addsuffix .png,$(FIGURES))
