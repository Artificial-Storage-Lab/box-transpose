# latexmk is not installed in the dev container, so the passes are driven by
# hand: pdflatex to emit .aux, bibtex to resolve citations, then two more
# pdflatex runs to settle references and page numbers.

PAPER := box-transpose
TEX   := $(PAPER).tex
PDF   := $(PAPER).pdf
LATEX := pdflatex -interaction=nonstopmode -halt-on-error
DEPS  := $(wildcard *.tex) $(wildcard style/*.tex) $(wildcard style/*.sty) refs.bib

.PHONY: all clean distclean watch

all: $(PDF)

$(PDF): $(DEPS)
	$(LATEX) $(TEX)
# bibtex fails loudly when nothing is cited yet, which is the normal state of a
# new draft. The leading - lets the build continue through that.
	-bibtex $(PAPER)
	$(LATEX) $(TEX)
	$(LATEX) $(TEX)
	@echo
	@echo "built $(PDF) — $$(pdfinfo $(PDF) 2>/dev/null | awk '/^Pages/{print $$2}') pages"

# Poll for edits and rebuild. inotifywait/entr are not installed either, so this
# compares mtimes on a 2s tick rather than watching the filesystem properly.
watch:
	@echo "watching $(DEPS) — ctrl-c to stop"
	@while true; do \
	  if [ -n "$$(find $(DEPS) -newer $(PDF) 2>/dev/null)" ] || [ ! -f $(PDF) ]; then \
	    $(MAKE) --no-print-directory all || true; \
	  fi; \
	  sleep 2; \
	done

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc *.lof *.lot *.fls *.synctex.gz

distclean: clean
	rm -f $(PDF)
