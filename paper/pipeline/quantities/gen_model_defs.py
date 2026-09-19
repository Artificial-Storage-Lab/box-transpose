#!/usr/bin/env python3
"""The cost model's claims, recomputed rather than asserted.

The model has no fitted constants, so there is nothing here read off a
calibration run. What there is instead are three facts the method section
states in words, each of which this file derives:

  * the smallest fraction of a tensor a single swap can move, which is what
    makes "beats a copy" and "is one swap" the same condition;
  * how accurately `moved` predicts the measured runtime ratio inside the
    region the method claims, and how badly outside it -- the second number is
    the reason the region exists;
  * MAX_STEPS, lifted out of the implementation so a retuned limit moves the
    sentence.

An earlier version of this work carried three constants measured on one GPU
(a throughput knee, a routing gate, a mean bandwidth). They are gone, and
nothing here replaces them.
"""
from __future__ import annotations

import importlib.util
import sys
from math import gcd

from _q import ROOT, constant, emit_defs, generated, median, rows

SRC = "quantities/gen_model_defs.py"
NOTE = "Regenerate after any change to src/_plan.py or raw_data/dpost_sweep/."

_spec = importlib.util.spec_from_file_location("_bt_plan2", ROOT / "src" / "_plan.py")
_plan = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _plan
_spec.loader.exec_module(_plan)

SEARCH_LIMIT = 200         # block sides scanned when bounding the moved fraction
GATE_MAX_SIDE = 4
GATE_MIN_DPOST = 1024


def main() -> None:
    # The floor on a single swap. moved = 1 - (gcd(r-1,c-1)+1)/(rc), and since
    # gcd(r-1,c-1) <= min(r,c)-1 the skipped share is at most 1/max(r,c) <= 1/2.
    # Scanned rather than argued so the paper's claim is checked, not asserted.
    best, arg = 1.0, None
    for r in range(2, SEARCH_LIMIT):
        for c in range(2, SEARCH_LIMIT):
            mv = 1 - (gcd(r - 1, c - 1) + 1) / (r * c)
            if mv < best:
                best, arg = mv, (r, c)

    sweep = [x for x in rows("dpost_sweep/results_nvidia_geforce_rtx_2070")
             if x.get("box_correct")]
    inside, outside = [], []
    for x in sweep:
        plan = _plan.plan_permute(tuple(x["shape"]), tuple(x["perm"]), materialize=False)
        if plan is None:
            continue
        s = plan.steps[0]
        in_region = (len(plan.steps) == 1 and s.rows == s.cols
                     and s.rows <= GATE_MAX_SIDE and s.d_post >= GATE_MIN_DPOST)
        err = abs(x["box_ms"] / x["contiguous_ms"] - plan.moved_ratio) / plan.moved_ratio
        (inside if in_region else outside).append(100 * err)

    emit_defs(generated("method") / "model.defs.tex", SRC, NOTE, {
        "modelMinMoved": f"{best:.2f}",
        "modelMinMovedRows": str(arg[0]),
        "modelMinMovedCols": str(arg[1]),
        "modelErrIn": f"{median(inside):.1f}",
        "modelErrOut": f"{median(outside):.0f}",
        "modelMaxSteps": str(constant(ROOT / "src" / "_plan.py", "MAX_STEPS")),
    })


if __name__ == "__main__":
    main()
