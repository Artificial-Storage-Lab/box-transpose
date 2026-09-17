#!/usr/bin/env python3
"""Figure fig:steps: median swaps per permutation against rank, both planners.

Writes two files, the same pattern the table renderers follow:

  steps-fig.tex       the tikzpicture, ready to \\input inside a float
  steps-fig.defs.tex  the numbers the caption quotes, off the same rows

Both axes are linear. The baseline's cost grows with the number of adjacent
transpositions a permutation needs, which is quadratic in rank but small in
absolute terms across the range swept -- a log axis would flatten exactly the
divergence the panel exists to show.

Geometry is in points against a 241pt USENIX column, so what is set here is
the size on the page. Do not wrap the result in \\resizebox.
"""
from __future__ import annotations

from collections import defaultdict

from _tikzplot import Axes, document, emit, emit_defs, generated, median, rows

SRC = "figures/plot_planner_steps.py"
NOTE = "Regenerate after any change to raw_data/plan_sweep/ (experiments/plan_sweep/run.py)."

WIDTH, HEIGHT = 241.0, 132.0
LEFT, BOTTOM = 30.0, 26.0          # gutters for the tick labels and axis titles
PANEL_W, PANEL_H = WIDTH - LEFT - 8.0, HEIGHT - BOTTOM - 12.0

SERIES = [("adjacent_baseline", "adjacent baseline", "porange", "s"),
          ("block_dijkstra", "box search", "pblue", "o")]


def main() -> None:
    r = rows("plan_sweep/results")
    by = defaultdict(list)
    for x in r:
        by[(x["planner"], x["rank"])].append(x["steps"])
    ranks = sorted({x["rank"] for x in r})
    med = {k: median(v) for k, v in by.items()}

    top = max(med.values())
    yhi = float(int(top) + (2 - int(top) % 2))      # next even value above the data
    yticks = [float(v) for v in range(0, int(yhi) + 1, 2)]
    xticks = [float(k) for k in ranks]

    ax = Axes(LEFT, BOTTOM, PANEL_W, PANEL_H,
              xlim=(ranks[0] - 0.4, ranks[-1] + 0.4), ylim=(0.0, yhi))
    ax.frame(xticks, yticks, xfmt=lambda v: f"{int(v)}", yfmt=lambda v: f"{int(v)}")
    for planner, _label, color, marker in SERIES:
        ax.series(xticks, [med[(planner, k)] for k in ranks], color=color, marker=marker)
    ax.xlabel("tensor rank")
    ax.ylabel("median swaps per permutation")
    ax.legend([(label, color, marker) for _p, label, color, marker in SERIES],
              x=ranks[0] - 0.2, y=yhi * 0.96)

    emit(generated("3-design") / "steps-fig.tex",
         document(ax.out, SRC, NOTE, WIDTH, HEIGHT))

    top_rank = ranks[-1]
    emit_defs(generated("3-design") / "steps-fig.defs.tex", SRC, NOTE, {
        "stepsFigRanks": str(len(ranks)),
        "stepsFigTopRank": str(top_rank),
        "stepsFigTopBaseline": f"{med[('adjacent_baseline', top_rank)]:g}",
        "stepsFigTopSearch": f"{med[('block_dijkstra', top_rank)]:g}",
    })


if __name__ == "__main__":
    main()
