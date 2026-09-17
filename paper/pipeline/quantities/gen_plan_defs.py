#!/usr/bin/env python3
"""The claims the method section's prose makes about the planner, as macros.

These are *quantities*: the numbers the running text states in a sentence --
how wide the sweep is, how many swaps the search saves over the adjacent
baseline, how little auxiliary memory the resulting plans need. The per-rank
breakdown is a table (pipeline/tables/gen_table_planners.py) and the same
medians drawn as a chart are a figure (pipeline/figures/plot_planner_steps.py);
this file is what lets the paragraph state the headline without anyone typing
a digit into it.

Reads raw_data/plan_sweep/ -- see experiments/plan_sweep/run.py, which is CPU
only and deterministic, so every number below is reproducible from a fresh
clone with no GPU.
"""
from __future__ import annotations

from collections import defaultdict

from _q import emit_defs, generated, median, rows, tex_int, word

SRC = "quantities/gen_plan_defs.py"
NOTE = "Regenerate after any change to raw_data/plan_sweep/ (experiments/plan_sweep/run.py)."

SEARCH = "block_dijkstra"
BASELINE = "adjacent_baseline"


def main() -> None:
    r = rows("plan_sweep/results")

    ranks = sorted({x["rank"] for x in r})
    elements = {x["elements"] for x in r}
    assert len(elements) == 1, "the sweep no longer holds tensor size constant"
    n_elements = elements.pop()

    # A case is one (shape, permutation) pair. The shape has to be in the key:
    # the sweep now samples several shapes per rank, so (rank, permutation)
    # alone would fold distinct cases together and silently halve the counts.
    key = lambda x: (x["rank"], tuple(x["shape"]), tuple(x["permute"]))
    cases = {key(x) for x in r}
    by_case: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for x in r:
        by_case[key(x)][x["planner"]] = x
    paired = [v for v in by_case.values() if SEARCH in v and BASELINE in v]
    assert len(paired) == len(cases), \
        "some case was not planned by both strategies; the comparison is not paired"

    # How the sweep was drawn, which the benchmark-design paragraph states.
    shapes_per_rank = {k: len({c[1] for c in cases if c[0] == k}) for k in ranks}
    assert len(set(shapes_per_rank.values())) == 1, \
        "ranks no longer sample the same number of shapes; that is two numbers, not one"
    space = {x["rank"]: x["shape_space"] for x in r}
    perms_per_shape = max(
        len({c[2] for c in cases if c[0] == k and c[1] == s})
        for k in ranks for s in {c[1] for c in cases if c[0] == k})

    step_factor = [v[BASELINE]["steps"] / v[SEARCH]["steps"] for v in paired]
    byte_factor = [v[BASELINE]["bytes_moved"] / v[SEARCH]["bytes_moved"] for v in paired]

    top = max(ranks)
    at_top = [v for v in paired if v[SEARCH]["rank"] == top]
    steps_base_top = median([v[BASELINE]["steps"] for v in at_top])
    steps_search_top = median([v[SEARCH]["steps"] for v in at_top])

    # The auxiliary-memory claim, stated against the worst plan the search
    # produced rather than the average one -- a bound the reader can hold.
    search_rows = [x for x in r if x["planner"] == SEARCH]
    aux_worst = max(x["aux_bytes"] for x in search_rows)
    tensor_bytes = n_elements * 4

    # How often the search actually uses the freedom the baseline does not
    # have: bundling several adjacent axes into one box for a single swap.
    search_steps = sum(x["steps"] for x in search_rows)
    block_steps = sum(x["block_swaps"] for x in search_rows)

    emit_defs(generated("2-method") / "plan.defs.tex", SRC, NOTE, {
        # the shape of the sweep
        "planRanks": word(len(ranks)),
        "planRankLo": str(min(ranks)),
        "planRankHi": str(top),
        "planElements": tex_int(n_elements),
        "planCases": tex_int(len(cases)),
        "planPlans": tex_int(len(r)),
        "planShapesPerRank": tex_int(next(iter(shapes_per_rank.values()))),
        "planPermsPerShape": tex_int(perms_per_shape),
        "planSpaceTop": tex_int(space[top]),
        # what the search buys, over the whole sweep and at the widest rank
        "planStepFactor": f"{median(step_factor):.1f}",
        "planByteFactor": f"{median(byte_factor):.1f}",
        "planByteFactorMax": f"{max(byte_factor):.1f}",
        "planStepsBaselineTop": f"{steps_base_top:g}",
        "planStepsSearchTop": f"{steps_search_top:g}",
        # the auxiliary-memory claim
        "planAuxWorst": tex_int(aux_worst),
        "planAuxPercent": f"{100 * aux_worst / tensor_bytes:.2f}",
        # how much of the gain comes from bundling axes into boxes
        "planBlockShare": f"{100 * block_steps / search_steps:.0f}",
    })


if __name__ == "__main__":
    main()
