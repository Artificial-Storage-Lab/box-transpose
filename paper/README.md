# paper

LaTeX source for the box transpose paper, set up for terminal editing.

## Build

```bash
make              # pdflatex -> bibtex -> pdflatex x2, writes main.pdf
make watch        # rebuild on edit, 2s poll
make clean        # drop .aux/.log/.bbl, keep the PDF
make distclean    # also drop the PDF
```

`make` after `make clean` will say "nothing to be done" — `clean` leaves
`main.pdf` in place and Make sees it as current. Use `distclean` when you want
a build from nothing.

## Layout

```
main.tex          the paper
refs.bib          bibliography (plain.bst)
figures/          figure sources and generated PDFs
style/
  usenix-2020-09.sty   USENIX two-column style
  packages.tex         package preamble
  layout.tex           float, section-depth and column settings
  macros.tex           \capheadline, \placeholder, \pname, \aname
  algorithms.tex       breakable pseudocode listings
```

`style/` is carried over unchanged from the smartcontiguous paper, so this
document lays out identically to that one. Each file explains its own settings
in comments — several encode fixes for specific failures (link boxes spanning a
column break, float pages ignoring `[t]`, stealth arrowheads reading as blobs).
Read those before changing anything there.

## Drafting

`\placeholder{...}` renders a boxed, deliberately loud marker so an unwritten
section cannot be mistaken for finished prose. Find them all with:

```bash
grep -n 'placeholder' main.tex
```

Delete every call, and the macro itself, before submission.

## Toolchain

The base image (`nvcr.io/nvidia/pytorch`) ships no LaTeX, so the `Dockerfile`
installs it — six TeX Live packages plus `poppler-utils`, about 0.3&nbsp;GB. The
set was derived by tracing every file this paper's build loads back to its
owning package, so it is what the preamble needs and nothing more. Two of those
are easy to get wrong if you ever prune the list:

- `texlive-science` — not obvious from the name, but it owns `algorithm.sty`
  and `algpseudocode.sty`.
- `texlive-pictures` — supplies `arrows.meta` at the pgf layer
  (`pgflibraryarrows.meta.code.tex`); there is no tikzlibrary file by that name,
  so a search for one turns up empty even though the library works.

`latexmk`, `inotifywait` and `texcount` are deliberately absent. The Makefile
drives the passes by hand and polls mtimes instead of depending on them, so
nothing here breaks if you rebuild the image without adding them.
