#!/usr/bin/env python3
r"""Figure body for fig:boxes: a shape, cut into four boxes by one swap.

Three stacked panels on one worked rank-6 example.

  (a) the axes we have and the order we want. Each cell is one axis, carrying
      its name and its extent; the axes the permutation actually disturbs are
      marked.
  (b) the same axes, now covered by the four regions a single swap cuts them
      into -- $D_{pre}$, the left box, the right box, $D_{post}$ -- each a
      tinted block with its name on a band and its extent under it. This is
      the panel the whole figure exists for: a box is one or more neighbouring
      axes, so a region may cover two cells as easily as one.
  (c) the order after the swap, with the two middle regions exchanged and the
      outer two untouched.

Every extent is a product of the shape, computed here, so the figure cannot
disagree with the arithmetic in the text.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import generated                                      # noqa: E402
from _diagram import (BOLD, MICRO, SMALL, TINY, arrow, cell,       # noqa: E402
                      emit_figure, label, panel, region)

SRC = "figures/plot_box_split.py"
NOTE = "Worked rank-6 example; every extent is a product of SHAPE computed here."

SHAPE = (2, 3, 4, 5, 6, 7)
SPLIT = (1, 2, 4)          # i, j, k -- the left box is one axis, the right box two
PERM = (0, 2, 3, 1, 4, 5)  # what that swap achieves


def prod(xs):
    out = 1
    for x in xs:
        out *= x
    return out


def main() -> None:
    W, H = 500.0, 178.0
    i, j, k = SPLIT
    r = len(SHAPE)

    d_pre, rows = prod(SHAPE[:i]), prod(SHAPE[i:j])
    cols, d_post = prod(SHAPE[j:k]), prod(SHAPE[k:])

    pad = 7.0
    # Panel (b) has to hold a band, a row of cells and an extent line, so it
    # is the tallest; the gap between (b) and (c) has to hold the two crossing
    # arrows, so it is wider than the other gap.
    ph_a, ph_b, ph_c = 44.0, 56.0, 44.0
    gap_ab, gap_bc = 5.0, 15.0
    note_w = 150.0
    x0 = pad + 26.0                          # room inside the panel for "have"/"want"
    cw = (W - pad - x0 - note_w) / r
    ch = 14.0

    body = []
    top_a = H - pad - ph_a
    top_b = top_a - gap_ab - ph_b
    top_c = top_b - gap_bc - ph_c
    assert top_c >= pad - 0.01, "panels do not fit the declared height"

    # ── (a) the axes, and the order we want ────────────────────────────────
    py, ph = top_a, ph_a
    body += panel(pad, py, W - 2 * pad, ph, "a")
    body += label(x0 - 4, py + ph - 20.0, "have", font=TINY, anchor="east")
    moved_axes = {t for t in range(r) if PERM[t] != t}
    for t in range(r):
        body += cell(x0 + t * cw, py + ph - 27.0, cw, ch,
                     "daccentpale" if t in moved_axes else "white",
                     f"$a_{{{t}}}$\\,$=\\,{SHAPE[t]}$", font=TINY)
    body += label(x0 - 4, py + 10.0, "want", font=TINY, anchor="east")
    for t in range(r):
        body += cell(x0 + t * cw, py + 4.0, cw, ch,
                     "daccentpale" if PERM[t] != t else "white",
                     f"$a_{{{PERM[t]}}}$", font=TINY)
    body += label(x0 + r * cw + 12.0, py + ph / 2 - 2.0,
                  f"shape $(d_0,\\dots,d_{{{r - 1}}})$ and a target\\\\"
                  f"permutation $\\pi$. Shaded axes move;\\\\the rest stay where "
                  "they are.", font=TINY, anchor="west")

    # ── (b) the four boxes ─────────────────────────────────────────────────
    py, ph = top_b, ph_b
    body += panel(pad, py, W - 2 * pad, ph, "b")
    spans = [(0, i, "dpre", "$D_{pre}$", d_pre),
             (i, j, "dleft", "left box ($rows$)", rows),
             (j, k, "dright", "right box ($cols$)", cols),
             (k, r, "dpost", "$D_{post}$", d_post)]
    ry, rh = py + 8.0, 38.0
    for a, b, fill, title, ext in spans:
        if a == b:
            continue
        rx, rw = x0 + a * cw, (b - a) * cw
        body += region(rx, ry, rw, rh, fill, title)
        for t in range(a, b):
            body += cell(x0 + t * cw + 1.6, ry + 14.0, cw - 3.2, ch - 3.0,
                         "white", f"$a_{{{t}}}$\\,$=\\,{SHAPE[t]}$", font=MICRO)
        # Extent inside the region, under its own cells, not loose beneath the
        # panel where it collided with the arrows from (b) to (c).
        body += label(rx + rw / 2, ry + 7.0, f"extent $=\\,{ext:,}$",
                      font=MICRO, anchor="center")
    body += label(x0 + r * cw + 12.0, py + ph / 2 - 2.0,
                  "One swap cuts the axis list\\\\into four boxes. A box is one\\\\"
                  "or more neighbouring axes, so\\\\its extent is their product.",
                  font=TINY, anchor="west")

    # ── (c) after the swap ─────────────────────────────────────────────────
    py, ph = top_c, ph_c
    body += panel(pad, py, W - 2 * pad, ph, "c")
    order = list(range(r))
    order = order[:i] + order[j:k] + order[i:j] + order[k:]
    assert tuple(order) == PERM, "SPLIT does not produce PERM"
    after = [(0, i, "dpre", d_pre), (i, i + (k - j), "dright", cols),
             (i + (k - j), k, "dleft", rows), (k, r, "dpost", d_post)]
    ry, rh_c = py + 11.0, 21.0
    for a, b, fill, ext in after:
        if a == b:
            continue
        rx, rw = x0 + a * cw, (b - a) * cw
        body += region(rx, ry, rw, rh_c, fill)
        for t in range(a, b):
            body += cell(x0 + t * cw + 1.6, ry + 3.5, cw - 3.2, ch - 3.0,
                         "white", f"$a_{{{order[t]}}}$\\,$=\\,{SHAPE[order[t]]}$",
                         font=MICRO)
    # The two crossing arrows live entirely in the gap between (b) and (c).
    y_from, y_to = top_b + 1.0, top_c + ph_c - 1.0
    body += arrow(x0 + (i + j) / 2 * cw, y_from,
                  x0 + (i + (k - j) + k) / 2 * cw, y_to,
                  lw=0.8, color="daccent", bend=-30)
    body += arrow(x0 + (j + k) / 2 * cw, y_from,
                  x0 + (i + i + (k - j)) / 2 * cw, y_to,
                  lw=0.8, color="daccent", bend=30)
    # Clear of the crossing point, which is near the middle of the span.
    body += label(x0 + 3.0, (y_from + y_to) / 2, "swap",
                  font=MICRO, color="daccent", anchor="east")
    body += label(x0 + r * cw + 12.0, py + ph / 2 - 2.0,
                  "The two middle boxes trade\\\\places. The outer two never\\\\"
                  "move. Read together the middle\\\\pair is one "
                  f"${rows}\\!\\times\\!{cols:,}$ matrix,\\\\transposed in place.",
                  font=TINY, anchor="west")

    emit_figure(generated("method") / "boxes-fig.tex", SRC, NOTE, body, W, H)


if __name__ == "__main__":
    main()
