#!/usr/bin/env python3
"""Minimal TikZ chart primitives, shared by the result figures.

A figure here is *typeset*, not pasted in: a renderer emits TikZ that the
paper's own build draws, so the labels are the paper's fonts at the paper's
sizes, the marks are vector at any zoom, and a colour can be changed without
re-exporting an image. That is the whole reason this exists instead of a
matplotlib call writing a PDF.

Geometry is in points against the measure the figure will occupy -- 241pt for
one USENIX column, about 505pt for the full text width -- so a size set here
is the size on the page, and 6.5pt type is 6.5pt type. Nothing is scaled
afterwards; a `\\resizebox` around a chart is what makes labels come out at
four different sizes in one paper.

Log axes are handled by mapping log10 of the value, so everything downstream
is linear.

Like the table renderers, a figure renderer owns only the marks. The float,
the `\\caption` and the `\\label` are hand-written under `sections/`, and a
renderer that has numbers worth quoting writes them to a `<name>.defs.tex`
with emit_defs so the caption can cite them.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import (  # noqa: E402,F401
    EXPERIMENTS, PAPER, RAW, ROOT, SECTIONS, SRC,
    banner, emit, emit_defs, generated, median, number, rows, sci, tex_int, word,
)

# A brand-neutral default. Hue carries the series; the ink/mid/grid greys are
# a single value ramp so the chart still reads in grayscale print.
INK = "1C1B18"
MID = "6B6A65"
GRID = "C9C7C0"
BLUE = "2A78D6"
ORANGE = "EB6834"

PREAMBLE = [
    f"\\definecolor{{pink}}{{HTML}}{{{INK}}}",
    f"\\definecolor{{pmid}}{{HTML}}{{{MID}}}",
    f"\\definecolor{{pgrid}}{{HTML}}{{{GRID}}}",
    f"\\definecolor{{pblue}}{{HTML}}{{{BLUE}}}",
    f"\\definecolor{{porange}}{{HTML}}{{{ORANGE}}}",
]

TINY = "\\fontsize{5.5}{6.5}\\selectfont"
SMALL = "\\fontsize{6}{7}\\selectfont"
TITLE = "\\fontsize{6.5}{7.5}\\selectfont"


class Axes:
    """One panel. `logx`/`logy` mark which axes carry log10-mapped values."""

    def __init__(self, x0, y0, w, h, xlim, ylim, logx=False, logy=False):
        self.x0, self.y0, self.w, self.h = x0, y0, w, h
        self.logx, self.logy = logx, logy
        self.xlo, self.xhi = (math.log10(xlim[0]), math.log10(xlim[1])) if logx else xlim
        self.ylo, self.yhi = (math.log10(ylim[0]), math.log10(ylim[1])) if logy else ylim
        self.out: list[str] = []

    def px(self, v):
        v = math.log10(v) if self.logx else v
        return self.x0 + self.w * (v - self.xlo) / (self.xhi - self.xlo)

    def py(self, v):
        v = math.log10(v) if self.logy else v
        return self.y0 + self.h * (v - self.ylo) / (self.yhi - self.ylo)

    def frame(self, xticks, yticks, xfmt=str, yfmt=str, grid=True, xrot=0):
        for v in yticks:
            y = self.py(v)
            if grid:
                self.out.append(f"\\draw[pgrid,line width=0.4pt] "
                                f"({self.x0:.2f},{y:.2f}) -- ({self.x0 + self.w:.2f},{y:.2f});")
            self.out.append(f"\\node[anchor=east,text=pink,font={TINY}] "
                            f"at ({self.x0 - 2:.2f},{y:.2f}) {{{yfmt(v)}}};")
        for v in xticks:
            x = self.px(v)
            anchor = "north east" if xrot else "north"
            rot = f",rotate={xrot}" if xrot else ""
            self.out.append(f"\\node[anchor={anchor},text=pink,font={TINY}{rot}] "
                            f"at ({x:.2f},{self.y0 - 2.5:.2f}) {{{xfmt(v)}}};")
        self.out.append(f"\\draw[pgrid,line width=0.6pt] ({self.x0:.2f},{self.y0:.2f}) -- "
                        f"({self.x0 + self.w:.2f},{self.y0:.2f});")
        self.out.append(f"\\draw[pgrid,line width=0.6pt] ({self.x0:.2f},{self.y0:.2f}) -- "
                        f"({self.x0:.2f},{self.y0 + self.h:.2f});")

    def series(self, xs, ys, color="pblue", marker="o", size=1.5):
        """A line with markers. Markers are knocked out in white first, so a
        crossing line does not run through the middle of a point."""
        pts = [(self.px(a), self.py(b)) for a, b in zip(xs, ys)]
        self.out.append(f"\\draw[{color},line width=0.9pt] "
                        + " -- ".join(f"({x:.2f},{y:.2f})" for x, y in pts) + ";")
        for x, y in pts:
            if marker == "o":
                shape = f"({x:.2f},{y:.2f}) circle ({size}pt)"
            elif marker == "s":
                shape = (f"({x - size:.2f},{y - size:.2f}) rectangle "
                         f"({x + size:.2f},{y + size:.2f})")
            else:  # diamond
                shape = (f"({x:.2f},{y + size * 1.3:.2f}) -- ({x + size:.2f},{y:.2f}) -- "
                         f"({x:.2f},{y - size * 1.3:.2f}) -- ({x - size:.2f},{y:.2f}) -- cycle")
            self.out.append(f"\\fill[white] {shape};")
            self.out.append(f"\\draw[{color},line width=0.7pt] {shape};")

    def bars(self, xs, ys, color="pblue", width=6.0, offset=0.0):
        """Vertical bars from the axis floor, for a categorical comparison."""
        for a, b in zip(xs, ys):
            x = self.px(a) + offset
            self.out.append(f"\\fill[{color}] ({x - width / 2:.2f},{self.y0:.2f}) "
                            f"rectangle ({x + width / 2:.2f},{self.py(b):.2f});")
            self.out.append(f"\\draw[pink,line width=0.3pt] ({x - width / 2:.2f},{self.y0:.2f}) "
                            f"rectangle ({x + width / 2:.2f},{self.py(b):.2f});")

    def rule(self, y, label=None, color="pmid"):
        yy = self.py(y)
        self.out.append(f"\\draw[{color},line width=0.6pt,dash pattern=on 2pt off 1.5pt] "
                        f"({self.x0:.2f},{yy:.2f}) -- ({self.x0 + self.w:.2f},{yy:.2f});")
        if label:
            self.out.append(f"\\node[anchor=south west,text={color},font={TINY}] "
                            f"at ({self.x0 + 2:.2f},{yy + 0.6:.2f}) {{{label}}};")

    def note(self, x, y, text, anchor="west"):
        self.out.append(f"\\node[anchor={anchor},text=pink,font={TINY},align=left] "
                        f"at ({self.px(x):.2f},{self.py(y):.2f}) {{{text}}};")

    def title(self, text):
        self.out.append(f"\\node[anchor=south,text=pink,font={TITLE}] at "
                        f"({self.x0 + self.w / 2:.2f},{self.y0 + self.h + 3:.2f}) {{{text}}};")

    def xlabel(self, text, drop=11):
        self.out.append(f"\\node[anchor=north,text=pink,font={SMALL}] at "
                        f"({self.x0 + self.w / 2:.2f},{self.y0 - drop:.2f}) {{{text}}};")

    def ylabel(self, text, shift=17):
        self.out.append(f"\\node[anchor=south,rotate=90,text=pink,font={SMALL}] at "
                        f"({self.x0 - shift:.2f},{self.y0 + self.h / 2:.2f}) {{{text}}};")

    def legend(self, entries, x, y, dy=7.5):
        """entries: (label, color, marker)."""
        for i, (label, color, _marker) in enumerate(entries):
            yy = self.py(y) - i * dy
            xx = self.px(x)
            self.out.append(f"\\draw[{color},line width=0.9pt] "
                            f"({xx:.2f},{yy:.2f}) -- ({xx + 9:.2f},{yy:.2f});")
            self.out.append(f"\\node[anchor=west,text=pink,font={TINY}] "
                            f"at ({xx + 11:.2f},{yy:.2f}) {{{label}}};")


def document(body: list[str], src: str, note: str, width: float, height: float) -> list[str]:
    """Wrap a panel's marks as a standalone tikzpicture, ready to \\input.

    Two details that are easy to lose and annoying to rediscover:

    * every line ends in `%`. Without it each newline becomes an interword
      space in the enclosing hbox, which pads the picture and widens any frame
      drawn around it.
    * `\\useasboundingbox` fixes the picture's size to the geometry asked for,
      rather than letting it shrink-wrap whatever marks happen to land at the
      edges -- so two figures declared the same width actually set the same
      width, however far their labels stick out.
    """
    lines = (banner(src, note)
             + ["\\begingroup", *PREAMBLE, "\\begin{tikzpicture}[x=1pt,y=1pt]",
                f"\\useasboundingbox (0,0) rectangle ({width:.2f},{height:.2f});",
                *body, "\\end{tikzpicture}", "\\endgroup"])
    return [l + "%" if not l.startswith("%") else l for l in lines]
