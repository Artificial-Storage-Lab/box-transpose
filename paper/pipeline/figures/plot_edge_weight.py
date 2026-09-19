#!/usr/bin/env python3
r"""Figure body for fig:weight: where an edge's weight comes from.

Two small matrices side by side, drawn cell by cell. Cells a transpose maps to
themselves are filled in the warm accent; every other cell is white. Under each
sits its own arithmetic: the count of fixed cells from
$\gcd(rows-1, cols-1)+1$, and the share of the tensor the swap therefore moves.

The pair is chosen to make the bound visible rather than stated. The square on
the left is the best case any single swap can reach; the one on the right is
twice its size and already much closer to moving everything. Both numbers are
computed here from the same formula the planner uses, so the figure cannot
drift from Equation~(2).
"""
from __future__ import annotations

import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import generated                            # noqa: E402
from _diagram import SMALL, TINY, box, emit_figure, label  # noqa: E402

SRC = "figures/plot_edge_weight.py"
NOTE = "Fixed-point counts recomputed from gcd(rows-1, cols-1)+1; matches src/_plan.py."

PAIR = [(2, 2), (4, 4)]


def transpose_next(p, rows, cols):
    return (p % cols) * rows + p // cols


def main() -> None:
    W, H = 241.0, 104.0
    body = []
    panel_w = W / len(PAIR)

    for n, (rows, cols) in enumerate(PAIR):
        cx = panel_w * (n + 0.5)
        cell = 11.0 if rows <= 2 else 8.5
        gw, gh = cols * cell, rows * cell
        gx, gy = cx - gw / 2, H - 24.0 - gh

        fixed = 0
        for r in range(rows):
            for c in range(cols):
                p = r * cols + c
                stays = transpose_next(p, rows, cols) == p
                fixed += stays
                body += box(gx + c * cell, gy + (rows - 1 - r) * cell,
                            cell, cell, "daccentpale" if stays else "white",
                            lw=0.4, rounded=0.4)

        assert fixed == gcd(rows - 1, cols - 1) + 1, \
            f"{rows}x{cols}: drawn {fixed} fixed cells, formula says " \
            f"{gcd(rows - 1, cols - 1) + 1}"

        moved = 1 - fixed / (rows * cols)
        body += label(cx, H - 14.0, f"${rows}\\!\\times\\!{cols}$ block",
                      font=SMALL, anchor="north")
        body += label(cx, gy - 6.0,
                      f"$\\gcd({rows}\\!-\\!1,{cols}\\!-\\!1)+1 = {fixed}$ "
                      f"cells stay put", font=TINY, anchor="north")
        body += label(cx, gy - 16.0,
                      f"$moved = 1 - {fixed}/{rows * cols} = "
                      f"\\mathbf{{{moved:.2f}}}$", font=SMALL, anchor="north")
        body += label(cx, gy - 27.0,
                      "so the swap costs\\\\"
                      f"${moved:.2f} \\times 2N\\gamma$ bytes",
                      font=SMALL, anchor="north")

    emit_figure(generated("method") / "weight-fig.tex", SRC, NOTE, body, W, H)


if __name__ == "__main__":
    main()
