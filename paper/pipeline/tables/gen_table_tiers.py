#!/usr/bin/env python3
"""Three regimes, and which method wins each.

The paper's central claim is not a single number but a partition: two
quantities computed from the shape put every (shape, permutation) pair into one
of three regimes, and the winner differs in each. This table is that partition,
measured.

The rows come from both sweeps, because neither alone covers the partition.
`dpost_sweep` samples permutations that keep a trailing axis group fixed, so it
populates the first two regimes; `hard_perms` draws permutations uniformly at
random, which is the only way to reach the third.
"""
from __future__ import annotations

import importlib.util
import sys

from _table import (ROOT, emit_defs, emit_table, fmt_ms, generated, median,
                    notes, rows, tex_int)

SRC = "tables/gen_table_tiers.py"
NOTE = "Regenerate after any change to raw_data/dpost_sweep/ or raw_data/hard_perms/."

_spec = importlib.util.spec_from_file_location("_bt_plan3", ROOT / "src" / "_plan.py")
_plan = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _plan
_spec.loader.exec_module(_plan)

GATE_MAX_SIDE = 4
GATE_MIN_DPOST = 1024


def classify(r):
    """(regime, plan) for one case, or (None, None) if it did not plan."""
    plan = _plan.plan_permute(tuple(r["shape"]), tuple(r["perm"]), materialize=False)
    if plan is None:
        return None, None
    if min(s.d_post for s in plan.steps) < GATE_MIN_DPOST:
        return "small", plan
    s = plan.steps[0]
    if len(plan.steps) == 1 and s.rows == s.cols and s.rows <= GATE_MAX_SIDE:
        return "beats", plan
    return "inplace", plan


def main() -> None:
    sweep = [r for r in rows("dpost_sweep/results_nvidia_geforce_rtx_2070")
             if r.get("box_correct")]
    hard = rows("hard_perms/results_nvidia_geforce_rtx_2070")
    buckets = {"beats": [], "inplace": [], "small": []}
    for r in sweep + hard:
        k, _ = classify(r)
        if k:
            buckets[k].append(r)

    def best_other(r):
        """Fastest method other than ours that reported on this case."""
        c = {k: r.get(v) for k, v in (("ITTPD", "ittpd_ms"),
                                      ("Gustavson", "gv_apply_ms"),
                                      ("Gomez-Luna", "gl_apply_ms"))}
        c = {k: v for k, v in c.items() if v}
        return min(c.values()) if c else None

    LABELS = [
        ("beats", "$D_{post}\\!\\ge\\!\\tau$, one small square swap"),
        ("inplace", "$D_{post}\\!\\ge\\!\\tau$, otherwise"),
        ("small", "$D_{post}\\!<\\!\\tau$"),
    ]
    body_rows = []
    for key, label in LABELS:
        b = buckets[key]
        if not b:
            continue
        box = median([r["box_ms"] for r in b])
        cont = median([r["contiguous_ms"] for r in b])
        others = [best_other(r) for r in b]
        others = [o for o in others if o]
        n_beat_cont = sum(1 for r in b if r["box_ms"] < r["contiguous_ms"])
        n_beat_other = sum(1 for r in b
                           if best_other(r) and r["box_ms"] < best_other(r))
        body_rows.append(" & ".join([
            label, tex_int(len(b)), fmt_ms(box), fmt_ms(cont),
            fmt_ms(median(others)) if others else "--",
            f"{n_beat_cont}/{len(b)}", f"{n_beat_other}/{len(b)}",
        ]) + " \\\\")

    body = [
        "\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}lrrrrrr@{}}",
        "\\toprule",
        " & & \\multicolumn{3}{c}{Median ms} & \\multicolumn{2}{c}{Box faster than} \\\\",
        "\\cmidrule(lr){3-5}\\cmidrule(lr){6-7}",
        "Regime & Cases & Box & Copy & Best other & Copy & Best other \\\\",
        "\\midrule",
        *body_rows,
        "\\bottomrule",
        "\\end{tabular*}",
        *notes([
            "\\textbf{Copy} is PyTorch \\texttt{.contiguous()}. "
            "\\textbf{Best other} is whichever in-place method was fastest on "
            "that case. Both tests are worked out from the shape before any "
            "data is touched.",
            "The last row is where our method falls down: a permutation that "
            "moves the innermost axis forces a swap with $D_{post}=1$, each "
            "value we move is then a lone number, and the published in-place "
            "methods are faster. We report this rather than route around it.",
        ]),
    ]
    emit_table(generated("evaluation") / "tiers-table.tex", SRC, NOTE, body)

    beats, small = buckets["beats"], buckets["small"]
    emit_defs(generated("evaluation") / "tiers-table.defs.tex", SRC, NOTE, {
        "tierBeatsCases": tex_int(len(beats)),
        "tierBeatsX": f"{median([r['contiguous_ms'] / r['box_ms'] for r in beats]):.2f}",
        "tierInplaceCases": tex_int(len(buckets["inplace"])),
        "tierSmallCases": tex_int(len(small)),
        "tierSmallX": f"{median([r['box_ms'] / r['contiguous_ms'] for r in small]):.0f}",
    })


if __name__ == "__main__":
    main()
