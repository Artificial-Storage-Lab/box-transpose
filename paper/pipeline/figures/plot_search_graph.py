#!/usr/bin/env python3
r"""Figure body for fig:graph: the whole graph the planner searches.

This is the picture docs/dijkstra-animation.html steps through, drawn still.
Same worked example -- shape $(2,3,4)$ to permutation $(2,1,0)$ -- same six
nodes, same layout, so a reader who opens the animation sees the figure move
rather than a second, unrelated diagram.

Every ordering of the axes is a node. Every legal swap is an edge. All of them
are drawn, faint, because the point of the figure is that the graph is small
and complete and the planner still has a real choice to make inside it. The
cheapest route is drawn in the accent with its weights; the accompanying prose
gives the total.

The weights come from `src/_plan.py`, and the animation's own cost model is
checked against it in the assertion below. The two agreed only after the cost
model was rewritten: the shipped planner used to report zero fixed points
during the search, which made every edge weigh the same, while the animation
always counted them properly. Fixing the planner (Section 3.3) made the
picture and the code the same thing.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import ROOT, generated                      # noqa: E402
from _diagram import (SMALL, TINY, arrow, cell, emit_figure,   # noqa: E402
                      label, region)

SRC = "figures/plot_search_graph.py"
NOTE = "Weights from src/_plan.py; layout mirrors docs/dijkstra-animation.html."

_spec = importlib.util.spec_from_file_location("_bt_plan_fig", ROOT / "src" / "_plan.py")
_plan = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _plan
_spec.loader.exec_module(_plan)

SHAPE = (2, 3, 4)
TARGET = (2, 1, 0)
NAMES = "ABC"

# The animation's own node order and placement, rescaled from its 990x700 SVG
# canvas to points. Keeping the arrangement identical is the whole point.
ORDERINGS = [(0, 1, 2), (1, 0, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0)]
SVG_POS = [(124, 350), (344, 146), (652, 146), (344, 554), (652, 554), (866, 350)]
BEND = 9        # degrees; shared by the edges and by the weight offset


def trim(fx, fy, tx, ty, hw, hh, pad):
    """Where the segment from (fx,fy) to (tx,ty) leaves the box around (tx,ty).

    Ported from the animation's own trim(). Without it an edge runs from centre
    to centre, disappears under the node rectangles (which are drawn after the
    edges) and reads as one long arc sweeping past nodes it never visits.
    """
    dx, dy = tx - fx, ty - fy
    hw, hh = hw + pad, hh + pad
    t = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return tx - dx * t, ty - dy * t


def anim_moved(rows, cols):
    """movedCells() from the animation, transcribed, for the assertion below."""
    total = rows * cols
    seen = [0] * total
    moved = 0
    for s in range(total):
        if seen[s]:
            continue
        cur, ln = s, 0
        while not seen[cur]:
            seen[cur] = 1
            ln += 1
            cur = (cur % cols) * rows + cur // cols
        if ln > 1:
            moved += ln
    return moved


def main() -> None:
    W, H = 500.0, 150.0
    bw, bh = 52.0, 17.0
    sx = (W - bw - 14.0) / (max(p[0] for p in SVG_POS) - min(p[0] for p in SVG_POS))
    sy = (H - bh - 30.0) / (max(p[1] for p in SVG_POS) - min(p[1] for p in SVG_POS))
    x0 = min(p[0] for p in SVG_POS)
    y0 = min(p[1] for p in SVG_POS)
    pos = [((px - x0) * sx + bw / 2 + 7.0,
            H - 16.0 - ((py - y0) * sy + bh / 2))
           for px, py in SVG_POS]
    idx = {o: n for n, o in enumerate(ORDERINGS)}

    # Every edge, with the weight the shipped planner gives it.
    cache, edges = {}, {}
    r = len(SHAPE)
    for order in ORDERINGS:
        for i in range(r - 1):
            for j in range(i + 1, r):
                for k in range(j + 1, r + 1):
                    st = _plan.make_step(order, SHAPE, i, j, k, cache, 4)
                    if st is None:
                        continue
                    assert st.bytes_moved == (st.d_pre * anim_moved(st.rows, st.cols)
                                              * st.d_post * 4 * 2), \
                        "the animation's cost model and src/_plan.py disagree"
                    e = (idx[order], idx[st.axes_after])
                    edges[e] = min(edges.get(e, st.bytes_moved), st.bytes_moved)

    plan = _plan.decompose_block_swaps(SHAPE, TARGET, materialize=False)
    route, cur = [], tuple(range(r))
    for st in plan.steps:
        route.append(((idx[cur], idx[st.axes_after]), st.bytes_moved))
        cur = st.axes_after
    on_route = {e for e, _ in route}

    def ends(u, v, pad=2.0):
        ux, uy = pos[u]
        vx, vy = pos[v]
        sx_, sy_ = trim(vx, vy, ux, uy, bw / 2, bh / 2, pad)
        ex_, ey_ = trim(ux, uy, vx, vy, bw / 2, bh / 2, pad)
        return sx_, sy_, ex_, ey_

    body = []
    for (u, v), cost in sorted(edges.items()):
        if (u, v) in on_route:
            continue
        body += arrow(*ends(u, v), lw=0.35, color="dright", bend=BEND)

    for (u, v), cost in route:
        sx_, sy_, ex_, ey_ = ends(u, v)
        body += arrow(sx_, sy_, ex_, ey_, lw=1.5, color="daccent", bend=BEND)
        # Weight sits partway along the edge on a white plate. The plate is
        # what makes this robust: the bow of a bent edge grows with its
        # length, so no single perpendicular offset clears both the short
        # edge and the long one.
        dx, dy = ex_ - sx_, ey_ - sy_
        n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        t, off = 0.38, 7.0
        body += label(sx_ + dx * t - dy / n * off,
                      sy_ + dy * t + dx / n * off,
                      f"{cost:,}\\,B", font=SMALL, color="daccent", fill="white")

    start_n, target_n = idx[tuple(range(r))], idx[TARGET]
    for n, order in enumerate(ORDERINGS):
        fill = ("dleft" if n == start_n else
                "daccentpale" if n == target_n else "dpre")
        nm = "".join(NAMES[a] for a in order)
        body += cell(pos[n][0] - bw / 2, pos[n][1] - bh / 2, bw, bh, fill,
                     f"({nm})", font=SMALL, lw=0.5)
        if n == start_n:
            body += label(pos[n][0], pos[n][1] + bh / 2 + 3, "start",
                          font=TINY, anchor="south")
        if n == target_n:
            body += label(pos[n][0], pos[n][1] + bh / 2 + 3, "target",
                          font=TINY, anchor="south")

    body += label(W / 2, 11.0,
                  f"Shape $({','.join(str(d) for d in SHAPE)})$, target "
                  f"$({','.join(str(p) for p in TARGET)})$. Every ordering is a "
                  f"node and every legal swap an edge. The cheapest route costs "
                  f"{plan.total_bytes_moved:,}\\,bytes.",
                  font=TINY, anchor="north")

    emit_figure(generated("method") / "graph-fig.tex", SRC, NOTE, body, W, H)


if __name__ == "__main__":
    main()
