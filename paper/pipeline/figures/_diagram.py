#!/usr/bin/env python3
r"""Shared ink for the Section 3 diagrams.

These are diagrams, not charts: nothing here is a measurement drawn to scale.
They are generated rather than hand-written for the same reason the tables are
-- a number that appears in a figure (a byte count on an edge, a moved
fraction) is computed from the same source the prose cites, so a figure cannot
drift away from the text beside it.

DRAWING. One hand across all three. Every rim and rule is a black pen line
(0.4pt for a cell, 0.6pt for a box, 0.8pt for an arrow), every fill is flat,
nothing is tinted on tint and nothing is dotted. Type is the same ink as the
rules. Geometry is in points against the 241pt USENIX column, which is the
convention the role-model's figures use.

COLOUR. One blue-to-slate family plus a single warm accent, so a diagram never
reads as a measurement. The accent marks exactly one thing per figure -- the
cells that stay put, the chosen route -- and nothing else is allowed to take
it.
"""
from __future__ import annotations

INK = "1C1B18"        # every rule and every word
PALE = "E8EEF5"       # the lightest ground: a prefix or suffix box
LIGHT = "C5D6E8"      # a box being swapped
MID = "8FB0D0"        # the other box being swapped
DEEP = "4A6D91"       # a heading band
ACCENT = "D96B2B"     # the one warm thing per figure
ACCENTPALE = "F7DFCE"

PREAMBLE = [
    f"\\definecolor{{dink}}{{HTML}}{{{INK}}}",
    f"\\definecolor{{dpale}}{{HTML}}{{{PALE}}}",
    f"\\definecolor{{dlight}}{{HTML}}{{{LIGHT}}}",
    f"\\definecolor{{dmid}}{{HTML}}{{{MID}}}",
    f"\\definecolor{{ddeep}}{{HTML}}{{{DEEP}}}",
    f"\\definecolor{{daccent}}{{HTML}}{{{ACCENT}}}",
    f"\\definecolor{{daccentpale}}{{HTML}}{{{ACCENTPALE}}}",
]

# Passed as a TikZ `font=` option, never inlined into the node body. With
# align=center a node is a one-column alignment and each `\\`-separated line is
# its own cell, so a font command written inside the body applies to the first
# line and nothing else -- which is how the first draft of fig:boxes came out
# with one small line above two large ones.
TINY = "\\fontsize{5.5}{6.5}\\selectfont"
SMALL = "\\fontsize{6}{7}\\selectfont"
BODY = "\\fontsize{6.5}{7.5}\\selectfont"


def box(x, y, w, h, fill, label=None, lw=0.6, font=SMALL, text="dink", rounded=1.2):
    """A filled, black-rimmed rectangle with its label centred."""
    out = [f"\\draw[fill={fill},draw=dink,line width={lw}pt,rounded corners={rounded}pt] "
           f"({x:.2f},{y:.2f}) rectangle ({x + w:.2f},{y + h:.2f});"]
    if label:
        out.append(f"\\node[text={text},align=center,font={font}] "
                   f"at ({x + w / 2:.2f},{y + h / 2:.2f}) {{{label}}};")
    return out


def label(x, y, s, font=SMALL, anchor="center", color="dink", fill=None):
    """`fill` puts an opaque plate behind the text.

    Worth it for anything that has to sit over a drawn line. Chasing the exact
    perpendicular offset that clears a bent edge is a losing game -- the bow
    depends on the edge's length, so an offset tuned on a short edge sits on a
    long one and an offset tuned on the long one leaves the frame.
    """
    opt = f"anchor={anchor},text={color},align=center,font={font}"
    if fill:
        opt += f",fill={fill},inner sep=1.2pt,rounded corners=0.8pt"
    return [f"\\node[{opt}] at ({x:.2f},{y:.2f}) {{{s}}};"]


def arrow(x1, y1, x2, y2, lw=0.8, color="dink", bend=None, dashed=False):
    """A straight arrow, or a bent one when `bend` is given (degrees, signed).

    A bend needs `to[bend ...]` rather than `--`; writing `--` with a bend
    option in the draw is silently ignored by TikZ and the curve comes out
    straight, which is how the first version of fig:boxes lost its two
    crossing arrows.
    """
    opt = f"-{{Stealth[length=3pt,width=2.4pt]}},line width={lw}pt,draw={color}"
    if dashed:
        opt += ",dash pattern=on 2pt off 1.5pt"
    if bend is None:
        path = f"({x1:.2f},{y1:.2f}) -- ({x2:.2f},{y2:.2f})"
    else:
        side = "left" if bend > 0 else "right"
        path = (f"({x1:.2f},{y1:.2f}) to[bend {side}={abs(bend)}] "
                f"({x2:.2f},{y2:.2f})")
    return [f"\\draw[{opt}] {path};"]


def brace(x1, x2, y, text, font=TINY, drop=3.0):
    """A horizontal brace under [x1,x2] carrying a caption."""
    return [f"\\draw[decorate,decoration={{brace,amplitude=2.5pt,mirror}},"
            f"line width=0.4pt,draw=dink] ({x1:.2f},{y:.2f}) -- ({x2:.2f},{y:.2f});",
            f"\\node[anchor=north,text=dink,align=center,font={font}] "
            f"at ({(x1 + x2) / 2:.2f},{y - drop:.2f}) {{{text}}};"]


def emit_figure(path, src, note, body, width, height):
    """A standalone tikzpicture, sized in points, with the banner above it."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from _common import banner, emit
    emit(path, banner(src, note) + [
        "\\begin{tikzpicture}[x=1pt,y=1pt]",
        *PREAMBLE,
        f"\\useasboundingbox (0,0) rectangle ({width:.1f},{height:.1f});",
        *body,
        "\\end{tikzpicture}",
    ])
