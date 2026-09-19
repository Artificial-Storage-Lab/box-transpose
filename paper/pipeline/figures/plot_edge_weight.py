#!/usr/bin/env python3
r"""Figure body for fig:weight: where an edge's weight comes from.

Two panels, one block each, drawn cell by cell at its real size. A cell the
transpose maps to itself is shaded and marked; every other cell carries an
arrow to where its value goes. Under each block a band gives the arithmetic:
the count of fixed cells from $\gcd(rows-1,cols-1)+1$, and the share of the
tensor the swap therefore moves.

The pair makes the bound visible rather than asserted. The square on the left
is the best case any single swap can reach -- half its cells never move. The
one on the right is twice the side and already moves three quarters.

Both counts are recomputed here from the same formula the planner uses, and
the drawing is asserted against it, so a wrong picture fails `make defs`
rather than printing.
"""
from __future__ import annotations

import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import generated                                   # noqa: E402
from _diagram import (MICRO, SMALL, TINY, cell, emit_figure,     # noqa: E402
                      label, panel, region)

SRC = "figures/plot_edge_weight.py"
NOTE = "Fixed-cell counts recomputed from gcd(rows-1, cols-1)+1; matches src/_plan.py."

PAIR = [(2, 2), (4, 4)]


def nxt(p, rows, cols):
    return (p % cols) * rows + p // cols


def main() -> None:
    W, H = 241.0, 120.0
    pad = 6.0
    pw = (W - 2 * pad - 4.0) / 2
    ph = H - 2 * pad
    body = []

    for n, (rows, cols) in enumerate(PAIR):
        px = pad + n * (pw + 4.0)
        body += panel(px, pad, pw, ph, "ab"[n])

        cs = 20.0 if rows <= 2 else 14.0
        gw, gh = cols * cs, rows * cs
        gx = px + (pw - gw) / 2
        gy = pad + ph - 18.0 - gh

        # Every cell carries its flat position, and a cell that stays put says
        # where it goes as well -- to itself. Numbering the grid the way the
        # role-model's Figure 3 numbers its addresses is what makes the claim
        # checkable by eye; destination arrows were tried here first and at
        # this size they read as scribbles over the cells.
        fixed = 0
        for rr in range(rows):
            for cc in range(cols):
                p = rr * cols + cc
                stays = nxt(p, rows, cols) == p
                fixed += stays
                body += cell(gx + cc * cs, gy + (rows - 1 - rr) * cs, cs, cs,
                             "daccentpale" if stays else "white",
                             f"{p}" if not stays else f"\\textbf{{{p}}}",
                             font=MICRO,
                             color="daccent" if stays else "dink")

        assert fixed == gcd(rows - 1, cols - 1) + 1, \
            f"{rows}x{cols}: drew {fixed} fixed cells, formula says " \
            f"{gcd(rows - 1, cols - 1) + 1}"

        body += label(px + pw / 2, pad + ph - 9.0,
                      f"a ${rows}\\!\\times\\!{cols}$ block", font=SMALL,
                      anchor="center")

        moved = 1 - fixed / (rows * cols)
        band_h = 24.0
        body += region(px + 5.0, pad + 5.0, pw - 10.0, band_h, "dpre")
        body += label(px + pw / 2, pad + 5.0 + band_h - 6.5,
                      f"$\\gcd({rows}\\!-\\!1,{cols}\\!-\\!1)+1 = {fixed}$ stay put",
                      font=MICRO)
        body += label(px + pw / 2, pad + 5.0 + band_h - 17.0,
                      f"$moved = 1-\\tfrac{{{fixed}}}{{{rows * cols}}} = "
                      f"\\mathbf{{{moved:.2f}}}$", font=TINY)

    emit_figure(generated("method") / "weight-fig.tex", SRC, NOTE, body, W, H)


if __name__ == "__main__":
    main()
