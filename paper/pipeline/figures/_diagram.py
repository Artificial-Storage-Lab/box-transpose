#!/usr/bin/env python3
r"""Shared ink for the Section 2 diagrams.

Drawn in the idiom of the role-model paper's Section 4 figures: one rounded
frame around the whole thing, lettered panels inside it, and within a panel a
pale tinted region per group with its name on a band along the top. Content is
dense and labelled rather than sparse and abstract -- a reader should be able
to point at a cell and say what it is.

These are diagrams, not charts. Nothing is drawn to scale. They are generated
rather than hand-written for the same reason the tables are: a number that
appears in a figure is computed from the same source the prose cites, so the
two cannot drift.

DRAWING. One hand across all three. Every rim is a hairline (0.35pt for a
cell, 0.5pt for a region, 0.7pt for the frame), every fill is flat, nothing is
tinted on tint, nothing is dotted. Arrows are 0.8pt. Type is the ink of the
rules, and a font is always passed as a TikZ `font=` option -- with
align=center a node is a one-column alignment and a font written inside the
body applies to the first line only.

COLOUR. One cyan-to-slate family, coolest to deepest, plus a single warm
accent. The family orders the four boxes of a swap so a reader can tell which
is which without reading the band; the accent marks exactly one thing per
figure and nothing else may take it.
"""
from __future__ import annotations

INK = "16202A"          # every rule and every word
FRAME = "3E4C59"        # the outer frame
GROUND = "F4F8FB"       # a panel's own ground
R_PRE = "DCE9F2"        # D_pre    -- coolest
R_LEFT = "A9CFE3"       # left box
R_RIGHT = "6FA8C9"      # right box
R_POST = "CFE0EC"       # D_post
BAND = "2E5A75"         # a region's header band
ACCENT = "C2571A"       # the one warm thing
ACCENTPALE = "F6E2D2"

PREAMBLE = [
    f"\\definecolor{{dink}}{{HTML}}{{{INK}}}",
    f"\\definecolor{{dframe}}{{HTML}}{{{FRAME}}}",
    f"\\definecolor{{dground}}{{HTML}}{{{GROUND}}}",
    f"\\definecolor{{dpre}}{{HTML}}{{{R_PRE}}}",
    f"\\definecolor{{dleft}}{{HTML}}{{{R_LEFT}}}",
    f"\\definecolor{{dright}}{{HTML}}{{{R_RIGHT}}}",
    f"\\definecolor{{dpost}}{{HTML}}{{{R_POST}}}",
    f"\\definecolor{{dband}}{{HTML}}{{{BAND}}}",
    f"\\definecolor{{daccent}}{{HTML}}{{{ACCENT}}}",
    f"\\definecolor{{daccentpale}}{{HTML}}{{{ACCENTPALE}}}",
]

MICRO = "\\fontsize{4.6}{5.4}\\selectfont"
TINY = "\\fontsize{5.2}{6.2}\\selectfont"
SMALL = "\\fontsize{6}{7}\\selectfont"
BOLD = "\\fontsize{6}{7}\\selectfont\\bfseries"


def label(x, y, s, font=SMALL, anchor="center", color="dink", fill=None, rot=0):
    """Text. `fill` puts an opaque plate behind it, for anything over a line."""
    opt = f"anchor={anchor},text={color},align=center,font={font}"
    if fill:
        opt += f",fill={fill},inner sep=1.2pt,rounded corners=0.8pt"
    if rot:
        opt += f",rotate={rot}"
    return [f"\\node[{opt}] at ({x:.2f},{y:.2f}) {{{s}}};"]


def cell(x, y, w, h, fill, text=None, font=TINY, lw=0.35, color="dink"):
    """One small filled cell with a hairline rim."""
    out = [f"\\draw[fill={fill},draw=dink,line width={lw}pt] "
           f"({x:.2f},{y:.2f}) rectangle ({x + w:.2f},{y + h:.2f});"]
    if text:
        out += label(x + w / 2, y + h / 2, text, font=font, color=color)
    return out


def region(x, y, w, h, fill, title=None, band_h=7.0, lw=0.5):
    """A pale panel with its name on a deep band along the top.

    The band is what makes a group readable at 5pt: a title set loose above a
    tint reads as a caption for whatever is nearest, while a band belongs
    unambiguously to the block under it.
    """
    out = [f"\\draw[fill={fill},draw=dink,line width={lw}pt,rounded corners=1.2pt] "
           f"({x:.2f},{y:.2f}) rectangle ({x + w:.2f},{y + h:.2f});"]
    if title:
        out += [f"\\draw[fill=dband,draw=dband,line width=0.2pt,"
                f"rounded corners=1.2pt] ({x:.2f},{y + h - band_h:.2f}) "
                f"rectangle ({x + w:.2f},{y + h:.2f});",
                f"\\draw[fill=dband,draw=dband,line width=0.2pt] "
                f"({x:.2f},{y + h - band_h:.2f}) rectangle "
                f"({x + w:.2f},{y + h - band_h + 1.4:.2f});"]
        out += label(x + w / 2, y + h - band_h / 2, title, font=TINY,
                     color="white")
    return out


def panel(x, y, w, h, letter, lw=0.5):
    """A lettered sub-panel on the figure's ground."""
    out = [f"\\draw[fill=dground,draw=dframe,line width={lw}pt,"
           f"rounded corners=1.6pt] ({x:.2f},{y:.2f}) "
           f"rectangle ({x + w:.2f},{y + h:.2f});"]
    out += label(x + 4.0, y + h - 4.0, f"({letter})", font=BOLD, anchor="north west")
    return out


def arrow(x1, y1, x2, y2, lw=0.8, color="dink", bend=None, dashed=False):
    """Straight, or bent when `bend` is given. A bend needs to[bend ...]; a
    bend option on a `--` path is silently ignored and comes out straight."""
    opt = f"-{{Stealth[length=3pt,width=2.4pt]}},line width={lw}pt,draw={color}"
    if dashed:
        opt += ",dash pattern=on 2pt off 1.5pt"
    if bend is None:
        path = f"({x1:.2f},{y1:.2f}) -- ({x2:.2f},{y2:.2f})"
    else:
        side = "left" if bend > 0 else "right"
        path = f"({x1:.2f},{y1:.2f}) to[bend {side}={abs(bend)}] ({x2:.2f},{y2:.2f})"
    return [f"\\draw[{opt}] {path};"]


def brace(x1, x2, y, text, font=TINY, drop=3.2, color="dink"):
    return [f"\\draw[decorate,decoration={{brace,amplitude=2.5pt,mirror}},"
            f"line width=0.4pt,draw={color}] ({x1:.2f},{y:.2f}) -- ({x2:.2f},{y:.2f});"] \
        + label((x1 + x2) / 2, y - drop, text, font=font, anchor="north", color=color)


def emit_figure(path, src, note, body, width, height, frame=True):
    """A standalone tikzpicture sized in points, inside the house frame."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from _common import banner, emit
    pre = []
    if frame:
        pre = [f"\\draw[draw=dframe,line width=0.7pt,rounded corners=2.4pt] "
               f"(0,0) rectangle ({width:.1f},{height:.1f});"]
    emit(path, banner(src, note) + [
        "\\begin{tikzpicture}[x=1pt,y=1pt]",
        *PREAMBLE,
        f"\\useasboundingbox (0,0) rectangle ({width:.1f},{height:.1f});",
        *pre,
        *body,
        "\\end{tikzpicture}",
    ])
