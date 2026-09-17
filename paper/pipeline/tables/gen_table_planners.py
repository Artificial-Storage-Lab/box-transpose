#!/usr/bin/env python3
"""Table body for tab:planners: what the search costs and saves, per rank.

Writes two files, the pattern every table renderer follows:

  planners-table.tex       the tabular body and nothing else
  planners-table.defs.tex  the numbers the caption quotes, off the same rows

The float, the caption and the label are hand-written in
sections/3-design/3-tab-planners.tex, which \\input{}s the body.

One row per rank. Every rank's tensor has the same element count, so the
bytes column compares two searches rather than two tensor sizes.
"""
from __future__ import annotations

from collections import defaultdict

from _table import (emit_defs, emit_table, fmt_x, generated, median, notes,
                    rows, tex_int)

SRC = "tables/gen_table_planners.py"
NOTE = "Regenerate after any change to raw_data/plan_sweep/ (experiments/plan_sweep/run.py)."

SEARCH = "block_dijkstra"
BASELINE = "adjacent_baseline"


def main() -> None:
    r = rows("plan_sweep/results")

    # A case is one (shape, permutation) pair. The sweep samples several shapes
    # per rank, so the shape belongs in the key.
    key = lambda x: (x["rank"], tuple(x["shape"]), tuple(x["permute"]))
    by_case: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for x in r:
        by_case[key(x)][x["planner"]] = x

    ranks = sorted({x["rank"] for x in r})
    space = {x["rank"]: x["shape_space"] for x in r}

    body_rows = []
    factors = {}
    for rank in ranks:
        cases = [v for k, v in by_case.items() if k[0] == rank]
        shapes = len({k[1] for k in by_case if k[0] == rank})
        base = median([v[BASELINE]["steps"] for v in cases])
        srch = median([v[SEARCH]["steps"] for v in cases])
        factor = median([v[BASELINE]["bytes_moved"] / v[SEARCH]["bytes_moved"]
                         for v in cases])
        aux = max(v[SEARCH]["aux_bytes"] for v in cases)
        factors[rank] = factor
        body_rows.append(
            f"{rank} & {tex_int(space[rank])} & {tex_int(shapes)} & "
            f"{tex_int(len(cases))} & "
            f"{base:g} & {srch:g} & {fmt_x(factor)} & {tex_int(aux)} \\\\")

    body = [
        "\\small",
        "\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}l r r r rr r r@{}}",
        "\\toprule",
        " & & & & \\multicolumn{2}{c}{\\textbf{Swaps}} & & \\\\",
        "\\cmidrule(lr){5-6}",
        "\\textbf{Rank} & \\textbf{$\\Omega(N,r)$} & \\textbf{Shapes} & "
        "\\textbf{Pairs} & "
        "\\textbf{Adj.} & \\textbf{Search} & \\textbf{Bytes} & \\textbf{Aux (B)} \\\\",
        "\\midrule",
        *body_rows,
        "\\bottomrule",
        "\\end{tabular*}",
        *notes([
            "$\\Omega(N,r)$ is the size of the shape space of "
            "Equation~(\\ref{eq:shapes}) at this rank. "
            "\\textbf{Shapes} are drawn from it uniformly and "
            "\\textbf{Pairs} counts (shape, permutation) cases.",
            "Swaps and bytes are medians over the pairs in that row. "
            "\\textbf{Bytes} is the median per-pair ratio of bytes moved by the "
            "adjacent baseline to bytes moved by the search, so higher is better.",
            "\\textbf{Aux (B)} is the largest cycle-metadata footprint any one "
            "search plan in the row needed, in bytes.",
        ]),
    ]
    emit_table(generated("2-method") / "planners-table.tex", SRC, NOTE, body)

    best = max(factors, key=lambda k: factors[k])
    emit_defs(generated("2-method") / "planners-table.defs.tex", SRC, NOTE, {
        "planTabRanks": tex_int(len(ranks)),
        "planTabCases": tex_int(len(by_case)),
        "planTabSpaceTop": tex_int(space[max(ranks)]),
        "planTabBestRank": str(best),
        "planTabBestX": f"{factors[best]:.1f}",
        "planTabWorstX": f"{min(factors.values()):.1f}",
    })


if __name__ == "__main__":
    main()
