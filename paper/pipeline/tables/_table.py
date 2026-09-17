#!/usr/bin/env python3
"""Shared plumbing for the table renderers.

A renderer here owns a table's *cells* and nothing else. It writes two files
into the section's `_generated/`:

  <name>.tex        the tabular body -- \\toprule, rows, \\bottomrule -- and
                    nothing outside it. No float, no caption, no label.
  <name>.defs.tex   the macros for every number the caption and the prose
                    around the float quote, computed from the same rows as
                    the cells, so a sentence and the cell beside it cannot
                    disagree.

The float itself is hand-written, in a small file under `sections/` that
carries the `\\begin{table}`, the `\\caption{...}` citing those macros, the
`\\label`, and one `\\input` of the body. That split is the point: the
pipeline owns the numbers, a person owns the wording.

Formatters live here rather than in each renderer so that two tables cannot
round the same quantity two different ways.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import (  # noqa: E402,F401
    EXPERIMENTS, PAPER, RAW, ROOT, SECTIONS, SRC,
    banner, constant, emit, emit_defs, generated, median, number, rows, sci,
    tex_int, word,
)


def fmt_ms(v: float | None) -> str:
    """Milliseconds: two decimals until the number is big enough not to need them."""
    if v is None:
        return "--"
    return f"{v:,.2f}" if v < 1000 else f"{v:,.0f}"


def fmt_x(v: float | None) -> str:
    """A ratio, as the prose says it: 2.9x."""
    return "--" if v is None else f"{v:,.1f}x"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "--"
    if 0 < v < 0.01:
        return "$<$0.01"
    return f"{v:,.2f}" if v < 10 else f"{v:,.0f}"


def notes(lines: list[str], pt: float = 6, lead: float = 6.8) -> list[str]:
    """Table notes, as one wrapped paragraph set *after* the tabular.

    One \\multicolumn row per note begins a fresh line for every sentence and
    leaves most of the measure empty, so three lines of text cost five or six
    lines of table. It also constrains what a note may say: a \\multicolumn
    wider than the columns it spans hands the excess to the last of them and
    stretches that column away from its block.

    Set outside the tabular, both problems go away -- the text fills the
    measure and wraps, and it cannot influence any column width. Spend the
    room that buys on 6pt type rather than \\tiny, which is 5pt at this base
    size: a note block should get shorter by saying less, never by setting
    smaller type.
    """
    return ["", "\\vspace{1.5pt}",
            "\\parbox{\\linewidth}{\\fontsize{%g}{%g}\\selectfont\\raggedright %s}"
            % (pt, lead, " ".join(lines))]


def emit_table(path: Path, src: str, note: str, body: list[str]) -> None:
    """The tabular body, with the banner saying what wrote it."""
    emit(path, banner(src, note) + body)
