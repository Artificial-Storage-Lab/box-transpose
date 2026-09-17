#!/usr/bin/env python3
"""The cost model's three constants, read out of the implementation.

Not measured here and not read from raw_data: these are values the shipped
code carries, and the paper describes them in words. Lifting them straight
out of src/_plan.py means a retuned constant moves the sentence, and a
renamed or deleted one fails this generator instead of leaving the paper
describing a model that is no longer in the code.

That is the same rule the rest of the pipeline follows, applied to a source
file rather than to a results file: the paper states nothing that nothing
recomputes.
"""
from __future__ import annotations

from _q import SRC as SRC_DIR, constant, emit_defs, generated, number

SRC = "quantities/gen_constants_defs.py"
NOTE = "Regenerate after any change to the calibrated constants in src/_plan.py."

PLAN = SRC_DIR / "_plan.py"


def main() -> None:
    mu = number(PLAN, "MU")
    tau = constant(PLAN, "TAU")
    d_post_star = constant(PLAN, "D_POST_STAR")

    emit_defs(generated("2-method") / "constants.defs.tex", SRC, NOTE, {
        "costMu": f"{mu:g}",
        "costTau": str(tau),
        "costDPostStar": str(d_post_star),
        # Both thresholds are currently 1, which is the value at which they
        # prune nothing at all. The paper must not describe pruning that the
        # shipped code does not do, so the wording switches on the code.
        "costPruning": "disabled" if tau <= 1 and d_post_star <= 1 else "active",
    })


if __name__ == "__main__":
    main()
