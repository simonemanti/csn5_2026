SHELL := /bin/bash
.DEFAULT_GOAL := all
LATEX ?= lualatex
PDFTOCAIRO ?= pdftocairo
INKSCAPE ?= inkscape
PNG_WIDTH ?= 1800
NAME := Crystal

.PHONY: all clean
all: $(NAME).pdf $(NAME).svg $(NAME).png

$(NAME).pdf: $(NAME).tex
	mkdir -p .build
	$(LATEX) -interaction=nonstopmode -halt-on-error -output-directory=.build $<
	cp .build/$(NAME).pdf $@

$(NAME).svg: $(NAME).pdf
	$(PDFTOCAIRO) -svg $< $@

$(NAME).png: $(NAME).svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-background-opacity=0 --export-filename=$@

clean:
	rm -rf .build
