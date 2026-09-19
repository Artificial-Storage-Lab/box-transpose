# latexmk is not installed in the dev container, so the passes are driven by
# hand: pdflatex to emit .aux, bibtex to resolve citations, then two more
# pdflatex runs to settle references and page numbers.

PAPER := box-transpose
TEX   := $(PAPER).tex
PDF   := $(PAPER).pdf
LATEX := pdflatex -interaction=nonstopmode -halt-on-error
# Sources live under sections/ too, so the dependency list has to recurse -- a
# flat $(wildcard *.tex) only ever sees box-transpose.tex and wouldn't rebuild
# when a section, or a file a generator rewrote, changes.
#
# role-model/ is pruned: it is a separate, finished paper kept here to read,
# not a source of this one. Without the prune its ~40 .tex files land in this
# document's dependency list and touching any of them rebuilds our PDF.
ALLTEX := $(shell find . -path ./role-model -prune -o -name '*.tex' -print)
STY    := $(wildcard style/*.sty)
DEPS   := $(ALLTEX) $(STY) refs.bib

.PHONY: all clean distclean watch defs audit verify

all: $(PDF)

# Regenerate everything under sections/*/_generated/ from raw_data/ and src/:
# the prose quantities, the table bodies, and the figures' TikZ.
# The guard on each loop matters: a directory with no generators in it yet
# otherwise leaves the glob unexpanded and hands python3 a literal "gen_*.py".
defs:
	cd pipeline/quantities && for g in gen_*.py; do [ -e "$$g" ] && python3 "$$g"; done
	cd pipeline/tables && for g in gen_*.py; do [ -e "$$g" ] && python3 "$$g"; done
	cd pipeline/figures && for g in plot_*.py; do [ -e "$$g" ] || continue; python3 "$$g"; done

# Fail if the prose states a number that no generator or allowed.txt entry
# accounts for. See pipeline/quantities/readme.md.
audit:
	cd pipeline/quantities && python3 audit.py

# defs + audit + a full build, in that order -- the whole point of the
# pipeline is that these three together are what "the paper is honest" means.
verify: defs audit all

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
