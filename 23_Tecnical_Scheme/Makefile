SHELL := /bin/bash
.DEFAULT_GOAL := all
LATEX ?= xelatex
DVISVGM ?= dvisvgm
INKSCAPE ?= inkscape
PNG_WIDTH ?= 2640
# Accept a version prefix, a full stem, or a .tex filename.
# Examples: make; make NAME=v1_; make NAME=v1_scheme_setup.tex
NAME ?= v1_
STEM := $(if $(filter %_,$(NAME)),$(NAME)scheme_setup,$(basename $(NAME)))

.PHONY: all clean help
.DELETE_ON_ERROR:
all: $(STEM).svg $(STEM).png

# Direct vector export from TikZ/XDV, without conversion through PDF.
# Editable Arial label groups; grouped math outlines preserve TeX typography.
$(STEM).svg: $(STEM).tex Makefile editable_svg.py
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	$(LATEX) -no-pdf -interaction=nonstopmode -halt-on-error -output-directory="$$tmp" $< >"$$tmp/build.log" || { cat "$$tmp/build.log"; exit 1; }; \
	$(DVISVGM) --font-format=woff --exact --bbox=papersize --output="$$tmp/text.svg" "$$tmp/$(STEM).xdv"; \
	$(DVISVGM) --no-fonts --exact --bbox=papersize --output="$$tmp/paths.svg" "$$tmp/$(STEM).xdv"; \
	python3 editable_svg.py "$$tmp/text.svg" "$$tmp/paths.svg" "$@"

$(STEM).png: $(STEM).svg
	$(INKSCAPE) $< --export-area-page --export-width=$(PNG_WIDTH) --export-background=white --export-background-opacity=1 --export-filename=$@

clean:
	rm -f $(STEM).svg $(STEM).png

help:
	@echo 'make [NAME=v1_] [PNG_WIDTH=2640]'
	@echo 'NAME accepts a version prefix, a source stem, or a .tex filename.'
	@echo 'Examples: make NAME=v1_; make NAME=v1_scheme_setup.tex'
	@echo 'clean removes only the selected version outputs.'
