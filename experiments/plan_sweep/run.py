#!/usr/bin/env python3
"""The planner over every permutation of a fixed-size tensor, at each rank.

Writes raw_data/plan_sweep/results.jsonl: one row per (rank, permutation,
planner). For each case both search strategies in `_plan.py` are run --

    block_dijkstra     the shipped planner: shortest path over axis orderings,
                       free to bundle several axes into one box per swap
    adjacent_baseline  the fallback: bubble each axis into place with
                       single-axis swaps, no bundling

-- and their plans are recorded: how many swaps, how many bytes those swaps
move, how much auxiliary cycle metadata they need, and which of them land on
the float4 kernel path.

This measures the *planner*, not the kernel. Nothing here touches a GPU and
nothing is timed, so the rows are deterministic: re-running on any machine
reproduces the file byte for byte. That is what makes it committable, and what
lets `paper/pipeline/` quote it without the paper depending on hardware being
present. Throughput measurement lives in `calibration/` instead, and is not
committed.

Every rank uses a shape of the same ELEMENTS total, so a bytes-moved number
compared across ranks is comparing the search and not the tensor size.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw_data" / "plan_sweep"

# _plan.py is standard library only; the package's __init__ pulls in _transpose
# and therefore torch. Loading the module by path keeps this script runnable on
# a machine with no torch and no CUDA, which is the whole point of it being the
# experiment the paper builds from.
_spec = importlib.util.spec_from_file_location("_bt_plan", ROOT / "src" / "_plan.py")
_plan = importlib.util.module_from_spec(_spec)
# @dataclass resolves annotations through sys.modules[cls.__module__], so the
# module has to be registered there before it is executed, not after.
sys.modules[_spec.name] = _plan
_spec.loader.exec_module(_plan)

ELEM_BYTES = 4
ELEMENTS = 40_320

# One shape per rank, every one of them ELEMENTS elements, with no axis equal
# to another -- equal axes make some permutations no-ops and would quietly
# flatter whichever planner skips them.
SHAPES: dict[int, tuple[int, ...]] = {
    2: (192, 210),
    3: (48, 40, 21),
    4: (24, 40, 6, 7),
    5: (24, 8, 5, 6, 7),
    6: (4, 6, 8, 5, 6, 7),
}

# Ranks 2-5 are swept exhaustively. Rank 6 has 720 permutations and each plan
# walks the full cycle structure of its steps in Python, so it is sampled
# instead -- seeded, so the sample is the same sample on every run.
EXHAUSTIVE_THROUGH = 5
RANK6_SAMPLE = 60
SEED = 0

PLANNERS = {
    "block_dijkstra": lambda *a: _plan.decompose_block_swaps(*a),
    "adjacent_baseline": lambda *a: _plan.decompose_adjacent_swaps(*a),
}


def permutations(rank: int, rng: random.Random) -> list[tuple[int, ...]]:
    """Every non-identity permutation of `rank` axes, sampled past rank 5.

    The identity is dropped: it decomposes to the empty plan under both
    strategies and would add a row that says nothing.
    """
    identity = tuple(range(rank))
    perms = [p for p in itertools.permutations(identity) if p != identity]
    if rank > EXHAUSTIVE_THROUGH:
        perms = sorted(rng.sample(perms, RANK6_SAMPLE))
    return perms


def record(rank: int, shape: tuple[int, ...], permute: tuple[int, ...],
           planner: str) -> dict:
    """One row: what the named planner made of this permutation.

    A planner that finds no box-following decomposition returns None, and a
    plan whose steps all turn out to be pure fixed points materialises to no
    steps at all. Both are recorded as status "none" rather than dropped, so
    the count of cases stays the same across planners and a coverage gap is
    visible in the data instead of being invisible in its absence.
    """
    plan = PLANNERS[planner](shape, permute, ELEM_BYTES)
    row = {
        "rank": rank,
        "shape": list(shape),
        "permute": list(permute),
        "elements": ELEMENTS,
        "planner": planner,
    }
    if plan is None or not plan.steps:
        return {**row, "status": "none"}
    return {**row,
            "status": "ok",
            "steps": len(plan.steps),
            "bytes_moved": plan.total_bytes_moved,
            "aux_bytes": plan.estimated_aux_bytes,
            "estimated_ms": round(plan.estimated_ms, 6),
            "float4_steps": sum(1 for s in plan.steps if s.kernel == "float4"),
            "block_swaps": sum(1 for s in plan.steps if s.kind == "block_swap")}


def main() -> None:
    rng = random.Random(SEED)
    RAW.mkdir(parents=True, exist_ok=True)
    n = 0
    with (RAW / "results.jsonl").open("w") as f:
        for rank in sorted(SHAPES):
            shape = SHAPES[rank]
            assert _plan.prod(shape) == ELEMENTS, \
                f"rank-{rank} shape {shape} is not {ELEMENTS} elements"
            for permute in permutations(rank, rng):
                for planner in PLANNERS:
                    f.write(json.dumps(record(rank, shape, permute, planner)) + "\n")
                    n += 1
            print(f"rank {rank}: {shape}  done")
    print(f"wrote {n} rows to {(RAW / 'results.jsonl').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
