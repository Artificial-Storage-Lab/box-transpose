#!/usr/bin/env python3
"""The planner over sampled shape/permutation pairs, at each rank.

Writes raw_data/plan_sweep/results.jsonl: one row per (shape, permutation,
planner). For each pair both search strategies in `_plan.py` are run --

    block_dijkstra     the shipped planner: shortest path over axis orderings,
                       free to bundle several axes into one box per swap
    adjacent_baseline  the fallback: bubble each axis into place with
                       single-axis swaps, no bundling

-- and their plans are recorded: how many swaps, how many bytes those swaps
move, how much auxiliary cycle metadata they need, and which of them land on
the float4 kernel path.

Shapes are not hand-picked. For a tensor of N elements and rank r, the set of
valid shapes is every ordered r-tuple whose dimensions multiply to N. Those are
enumerated by prime-factorising N and distributing each prime's exponent across
the r dimensions, which is Equation (1) of the proposal and the same
construction the Cycle Splitter evaluation uses. Sampling from that space
rather than choosing shapes by hand is what makes the comparison fair: nobody
picked the cases where the search happens to do well.

This measures the *planner*, not the kernel. Nothing here touches a GPU and
nothing is timed, so the rows are deterministic: re-running on any machine
reproduces the file byte for byte. That is what makes it committable, and what
lets `paper/pipeline/` quote it without the paper depending on hardware being
present. Throughput measurement lives in `calibration/` instead, and is not
committed.

Every rank uses the same N, so a bytes-moved number compared across ranks is
comparing the search and not the tensor size.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
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
ELEMENTS = 40_320            # 8! = 2^7 * 3^2 * 5 * 7, four distinct primes
RANKS = range(2, 7)

SHAPES_PER_RANK = 12
PERMS_PER_SHAPE = 4
SEED = 0

PLANNERS = {
    "block_dijkstra": lambda *a: _plan.decompose_block_swaps(*a),
    "adjacent_baseline": lambda *a: _plan.decompose_adjacent_swaps(*a),
}


def factorise(n: int) -> list[tuple[int, int]]:
    """N as [(prime, exponent), ...]."""
    out, d = [], 2
    while d * d <= n:
        e = 0
        while n % d == 0:
            n //= d
            e += 1
        if e:
            out.append((d, e))
        d += 1
    if n > 1:
        out.append((n, 1))
    return out


def compositions(total: int, parts: int) -> list[tuple[int, ...]]:
    """Every way to write `total` as an ordered sum of `parts` non-negatives.

    This is the stars-and-bars count C(total + parts - 1, parts - 1): the ways
    one prime's exponent can be spread over the shape's dimensions.
    """
    if parts == 1:
        return [(total,)]
    return [(first,) + rest
            for first in range(total + 1)
            for rest in compositions(total - first, parts - 1)]


def shape_space(n: int, rank: int) -> tuple[list[int], list[list[tuple[int, ...]]], int]:
    """The shape space of Equation (1): primes, their splits, and its size.

    Returns the distinct primes of `n`, the list of exponent splits available
    to each of them, and Omega = the product of those counts, which is how many
    ordered rank-`rank` shapes multiply to `n`.
    """
    fac = factorise(n)
    primes = [p for p, _ in fac]
    splits = [compositions(e, rank) for _, e in fac]
    omega = math.prod(len(s) for s in splits)
    return primes, splits, omega


def decode(index: int, primes: list[int],
           splits: list[list[tuple[int, ...]]], rank: int) -> tuple[int, ...]:
    """Shape number `index` of the space, as mixed-radix over the primes.

    Indexing the space rather than materialising it matters: at rank 6 this N
    has 598,752 shapes, and we only want a handful of them.
    """
    dims = [1] * rank
    for prime, choices in zip(primes, splits):
        split = choices[index % len(choices)]
        index //= len(choices)
        for j, b in enumerate(split):
            dims[j] *= prime ** b
    return tuple(dims)


def sample_shapes(rank: int, rng: random.Random) -> tuple[list[tuple[int, ...]], int]:
    """`SHAPES_PER_RANK` shapes drawn uniformly from the rank's shape space.

    Shapes containing a unit axis are rejected. A dimension of 1 can be moved
    anywhere without touching a byte, so such a shape is a rank-`rank` tensor
    in name only and would flatter both planners equally but meaninglessly.
    Rejection is done by drawing more indices rather than by biasing the draw.
    """
    primes, splits, omega = shape_space(ELEMENTS, rank)
    wanted = min(SHAPES_PER_RANK, omega)
    seen: dict[tuple[int, ...], None] = {}
    for index in rng.sample(range(omega), omega):
        dims = decode(index, primes, splits, rank)
        if 1 not in dims:
            seen.setdefault(dims, None)
        if len(seen) == wanted:
            break
    return sorted(seen), omega


def sample_permutations(rank: int, rng: random.Random) -> list[tuple[int, ...]]:
    """Up to `PERMS_PER_SHAPE` non-identity permutations of `rank` axes.

    The identity is excluded because it decomposes to the empty plan under
    both strategies. Rank 2 has exactly one non-identity permutation, so it
    contributes one pair per shape however large PERMS_PER_SHAPE is.
    """
    identity = tuple(range(rank))
    perms = [p for p in itertools.permutations(identity) if p != identity]
    if len(perms) > PERMS_PER_SHAPE:
        perms = rng.sample(perms, PERMS_PER_SHAPE)
    return sorted(perms)


def record(rank: int, shape: tuple[int, ...], permute: tuple[int, ...],
           omega: int, planner: str) -> dict:
    """One row: what the named planner made of this shape and permutation.

    A planner that finds no box-following decomposition returns None, and a
    plan whose steps all turn out to be pure fixed points materialises to no
    steps at all. Both are recorded as status "none" rather than dropped, so
    the count of pairs stays the same across planners and a coverage gap is
    visible in the data instead of being invisible in its absence.
    """
    plan = PLANNERS[planner](shape, permute, ELEM_BYTES)
    row = {
        "rank": rank,
        "shape": list(shape),
        "permute": list(permute),
        "elements": ELEMENTS,
        "shape_space": omega,
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
        for rank in RANKS:
            shapes, omega = sample_shapes(rank, rng)
            for shape in shapes:
                assert _plan.prod(shape) == ELEMENTS, \
                    f"{shape} is not {ELEMENTS} elements"
                for permute in sample_permutations(rank, rng):
                    for planner in PLANNERS:
                        f.write(json.dumps(
                            record(rank, shape, permute, omega, planner)) + "\n")
                        n += 1
            print(f"rank {rank}: {len(shapes)} shapes sampled from {omega:,}")
    print(f"wrote {n} rows to {(RAW / 'results.jsonl').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
