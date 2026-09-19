#!/usr/bin/env python3
r"""Figure body for fig:boxes: the four-part split, and what one swap does.

Two rows. The top is the axis list of a worked shape, cut into four parts and
braced with the extent of each: the prefix $D_{pre}$, the left box, the right
box, the suffix $D_{post}$. The bottom is the same list after the swap, with
the two middle boxes exchanged and everything else in place.

Between them sits the point of the whole construction: the two middle boxes,
read as one $rows \times cols$ matrix whose cells are runs of $D_{post}$
values. The matrix is drawn small beside the rows so the reader can see that a
swap of axis groups and a transpose of a matrix are the same move.

The worked shape is the one Section 4's graph figure uses, so a reader
following both sees one example rather than two.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import ROOT, generated                       # noqa: E402
from _diagram import (BODY, SMALL, TINY, arrow, box, brace,  # noqa: E402
                      emit_figure, label)

SRC = "figures/plot_box_split.py"
NOTE = "Hand-laid diagram; the worked shape matches plot_search_graph.py."

SHAPE = (2, 2, 64)
AXES = ["$a_0$", "$a_1$", "$a_2$"]
# The swap drawn is rho(0,1,2): left box is axis 0, right box is axis 1.
SPLIT = (0, 1, 2)           # i, j, k


def main() -> None:
    W, H = 241.0, 118.0
    cw, ch = 34.0, 15.0      # one axis cell
    x0 = 30.0
    top, bot = H - 26.0, 30.0

    i, j, k = SPLIT
    r = len(SHAPE)
    rows = SHAPE[i]
    cols = SHAPE[j]
    d_post = 1
    for d in SHAPE[k:]:
        d_post *= d

    def fill_for(pos, order):
        """Colour follows the role a slot plays, not the axis sitting in it."""
        if pos < i or pos >= k:
            return "dpale"
        return "dlight" if pos < j else "dmid"

    body = []

    # ---- before -----------------------------------------------------------
    body += label(x0 - 6, top + ch / 2, "before", font=TINY, anchor="east")
    for pos in range(r):
        x = x0 + pos * cw
        body += box(x, top, cw, ch, fill_for(pos, None),
                    f"{AXES[pos]}\\,{SMALL}$=\\!{SHAPE[pos]}$", font=SMALL)
    body += brace(x0, x0 + i * cw if i else x0 + 0.01, top - 1.5,
                  "$D_{pre}$") if i else []
    body += brace(x0 + i * cw, x0 + j * cw, top - 1.5, "$rows$")
    body += brace(x0 + j * cw, x0 + k * cw, top - 1.5, "$cols$")
    body += brace(x0 + k * cw, x0 + r * cw, top - 1.5,
                  f"$D_{{post}}\\!=\\!{d_post}$")

    # ---- the swap itself --------------------------------------------------
    mid_y = (top + bot) / 2 + 2
    body += arrow(x0 + i * cw + cw / 2, top - 14.0,
                  x0 + j * cw + cw / 2, bot + ch + 4.0, lw=0.7, bend=28)
    body += arrow(x0 + j * cw + cw / 2, top - 14.0,
                  x0 + i * cw + cw / 2, bot + ch + 4.0, lw=0.7, bend=-28)
    body += label(x0 + r * cw + 28, mid_y,
                  "the two middle boxes are\\\\one $rows\\!\\times\\!cols$ matrix,\\\\"
                  "transposed in place", font=TINY)

    # ---- after ------------------------------------------------------------
    order = list(range(r))
    order = order[:i] + order[j:k] + order[i:j] + order[k:]
    body += label(x0 - 6, bot + ch / 2, "after", font=TINY, anchor="east")
    for pos in range(r):
        x = x0 + pos * cw
        a = order[pos]
        body += box(x, bot, cw, ch, fill_for(pos, order),
                    f"{AXES[a]}\\,{SMALL}$=\\!{SHAPE[a]}$", font=SMALL)

    # ---- the matrix, drawn beside the rows --------------------------------
    mx, my, cell = x0 + r * cw + 30, bot - 4, 8.0
    for rr in range(rows):
        for cc in range(cols):
            f = "daccentpale" if rr == cc else "white"
            body += box(mx + cc * cell, my + (rows - 1 - rr) * cell,
                        cell, cell, f, lw=0.4, rounded=0.4)
    body += label(mx + cols * cell / 2, my - 3.0,
                  f"each cell is a run of\\\\$D_{{post}}\\!=\\!{d_post}$ values",
                  font=TINY, anchor="north")

    emit_figure(generated("method") / "boxes-fig.tex", SRC, NOTE, body, W, H)


if __name__ == "__main__":
    main()
