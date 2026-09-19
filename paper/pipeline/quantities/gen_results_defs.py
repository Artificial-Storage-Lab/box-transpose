#!/usr/bin/env python3
"""Every number the evaluation and limitations prose states, as macros.

Reads both measured sweeps:

  raw_data/dpost_sweep/    87 shapes drawn from Equation (1) at ranks 3-10,
                           each paired with a permutation that leaves a
                           trailing axis group fixed. Five methods.
  raw_data/hard_perms/     15 permutations drawn uniformly at random, which
                           is the case the method is NOT built for. Four
                           methods.

The two together are what lets the paper claim a region and bound it: the
first says what happens inside, the second what happens outside.

The gate -- one step, square block of side at most four, D_post at least the
coalescing width -- is recomputed here from the shipped planner rather than
copied, so a change to _plan.py moves these numbers instead of leaving the
sentence describing a router that no longer exists.
"""
from __future__ import annotations

import importlib.util
import sys

from _q import ROOT, emit_defs, generated, median, rows, tex_int

SRC = "quantities/gen_results_defs.py"
NOTE = "Regenerate after any change to raw_data/dpost_sweep/ or raw_data/hard_perms/."

# _plan.py is standard library only; the package __init__ pulls in torch.
_spec = importlib.util.spec_from_file_location("_bt_plan", ROOT / "src" / "_plan.py")
_plan = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _plan
_spec.loader.exec_module(_plan)

GATE_MAX_SIDE = 4          # square blocks wider than this have too few fixed points
GATE_MIN_DPOST = 1024      # below this the moved runs stop coalescing


def gated(r: dict) -> bool:
    plan = _plan.plan_permute(tuple(r["shape"]), tuple(r["perm"]), materialize=False)
    if plan is None or len(plan.steps) != 1:
        return False
    s = plan.steps[0]
    return s.rows == s.cols and s.rows <= GATE_MAX_SIDE and s.d_post >= GATE_MIN_DPOST


def main() -> None:
    sweep = [r for r in rows("dpost_sweep/results_nvidia_geforce_rtx_2070")
             if r.get("box_correct")]
    hard = rows("hard_perms/results_nvidia_geforce_rtx_2070")

    elements = {r["elements"] for r in sweep}
    assert len(elements) == 1, "the sweep no longer holds tensor size constant"
    n = elements.pop()
    ranks = sorted({r["rank"] for r in sweep})

    def med(key, src=sweep):
        return median([r[key] for r in src if r.get(key) is not None])

    # Head-to-head counts, over the cases where both methods reported.
    def wins(key, src=sweep, mine="box_ms"):
        both = [r for r in src if r.get(key) is not None and r.get(mine) is not None]
        return sum(1 for r in both if r[mine] < r[key]), len(both)

    w_ittpd = wins("ittpd_ms")
    w_gl = wins("gl_apply_ms")
    w_gv = wins("gv_apply_ms")

    g = [r for r in sweep if gated(r)]
    g_win = [r for r in g if r["box_ms"] < r["contiguous_ms"]]
    speedups = sorted(r["contiguous_ms"] / r["box_ms"] for r in g)

    # The hard sweep, split on whether a trailing block survived the permutation.
    def min_dpost(r):
        plan = _plan.plan_permute(tuple(r["shape"]), tuple(r["perm"]), materialize=False)
        return min(s.d_post for s in plan.steps) if plan else 0

    def best_inplace(r):
        c = {k: r.get(v) for k, v in
             (("box", "box_ms"), ("ittpd", "ittpd_ms"),
              ("gv", "gv_apply_ms"), ("gl", "gl_apply_ms"))}
        c = {k: v for k, v in c.items() if v}
        return min(c, key=c.get) if c else None

    big = [r for r in hard if min_dpost(r) >= GATE_MIN_DPOST]
    small = [r for r in hard if min_dpost(r) < GATE_MIN_DPOST]
    big_win = [r for r in big if best_inplace(r) == "box"]
    small_win = [r for r in small if best_inplace(r) == "box"]
    small_box = [r["box_ms"] for r in small if r.get("box_ms")]
    small_cont = [r["contiguous_ms"] for r in small if r.get("contiguous_ms")]

    emit_defs(generated("evaluation") / "results.defs.tex", SRC, NOTE, {
        # how the sweep was drawn
        "resCases": tex_int(len(sweep)),
        "resRankLo": str(min(ranks)),
        "resRankHi": str(max(ranks)),
        "resElements": tex_int(n),
        "resTensorMB": tex_int(n * 4 // (1024 * 1024)),
        "resDevice": sweep[0]["device"],
        # medians, all methods
        "resBoxMs": f"{med('box_ms'):.2f}",
        "resContMs": f"{med('contiguous_ms'):.2f}",
        "resIttpdMs": f"{med('ittpd_ms'):.2f}",
        "resGlMs": f"{med('gl_apply_ms'):.2f}",
        "resGvMs": f"{med('gv_apply_ms'):.2f}",
        "resBoxAux": tex_int(int(med("box_aux_bytes"))),
        "resGvAuxMB": f"{med('gv_aux_bytes') / (1024 * 1024):.0f}",
        # head to head
        "resWinIttpd": tex_int(w_ittpd[0]), "resWinIttpdOf": tex_int(w_ittpd[1]),
        "resWinGl": tex_int(w_gl[0]), "resWinGlOf": tex_int(w_gl[1]),
        "resWinGv": tex_int(w_gv[0]), "resWinGvOf": tex_int(w_gv[1]),
        # the gate
        "gateCases": tex_int(len(g)),
        "gateWins": tex_int(len(g_win)),
        "gateShare": f"{100 * len(g) / len(sweep):.0f}",
        "gateMedianX": f"{median(speedups):.2f}",
        "gateBestX": f"{max(speedups):.2f}",
        "gateMinDpost": tex_int(GATE_MIN_DPOST),
        "gateMaxSide": str(GATE_MAX_SIDE),
        # the hard sweep
        "hardCases": tex_int(len(hard)),
        "hardBigCases": tex_int(len(big)), "hardBigWins": tex_int(len(big_win)),
        "hardSmallCases": tex_int(len(small)), "hardSmallWins": tex_int(len(small_win)),
        "hardSmallBoxLo": f"{min(small_box):.0f}", "hardSmallBoxHi": f"{max(small_box):.0f}",
        "hardSmallContLo": f"{min(small_cont):.0f}", "hardSmallContHi": f"{max(small_cont):.0f}",
        "hardSmallSlowdown": f"{median(small_box) / median(small_cont):.0f}",
    })


if __name__ == "__main__":
    main()
