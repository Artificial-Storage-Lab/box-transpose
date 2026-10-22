#!/usr/bin/env python3
"""The test inputs: 1000 seeded (shape, permutation) pairs, stratified by D_post.

Shapes come from Equation (1), using the same sampler as dpost_sweep: N is
prime-factorised and each prime's exponent is spread over the r dimensions,
drawn uniformly over the ordered shape space. N and the rank are drawn
uniformly from SIZES and RANKS for every case.

D_post is the length of the contiguous run the permutation leaves in place --
the product of the trailing axes it does not move. It decides whether box
transpose can win, so the sample is stratified on it, an equal number of cases
per class:

  none     D_post = 1           the last axis moves; box transpose's limitation
  short    2 .. 1,023           a group survives but the runs are short
  medium   1,024 .. 65,535      around where box transpose starts winning
  long     >= 65,536            runs long enough to coalesce fully

A uniform draw over permutations lands in `none` most of the time, so each draw
pairs the shape with either a uniform permutation or one that reorders only the
first j axes, and the case is kept only if its class is not yet full. Equal
allocation is a choice about where to spend the test budget, not a claim about
how often each class occurs. Report the classes separately, never pooled.

Shapes with an axis of size 1 are dropped, as in dpost_sweep. A unit axis moves
anywhere without touching a byte, so such a shape is a lower rank in disguise.

CPU only, no torch. Same seed, same file.

    python experiments/shape_samples/run.py
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "raw_data" / "shape_samples" / "shapes.json"

_spec = importlib.util.spec_from_file_location("dpost_sweep", ROOT / "dpost_sweep" / "run.py")
eq1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eq1)

SIZES = {
    "2^24": 1 << 24,                        # 16,777,216     64 MB at fp32
    "2^26": 1 << 26,                        # 67,108,864    256 MB
    "2^28": 1 << 28,                        # 268,435,456   1 GB
    "2^12*3^4*5^2*7": 2**12 * 3**4 * 5**2 * 7,   # 58,060,800
    "2^18*3^3*5^2": 2**18 * 3**3 * 5**2,         # 176,947,200
}
RANKS = range(2, 11)
CLASSES = {                 # name: (lowest D_post, highest D_post)
    "none":   (1, 1),
    "short":  (2, 1023),
    "medium": (1024, 65535),
    "long":   (65536, None),
}
TOTAL = 1000
PER_CLASS = TOTAL // len(CLASSES)
MAX_TRIES = 1_000_000
SEED = 0


def dpost_class(d_post: int) -> str:
    for name, (lo, hi) in CLASSES.items():
        if d_post >= lo and (hi is None or d_post <= hi):
            return name
    raise ValueError(d_post)


def trailing_fixed(perm: tuple[int, ...]) -> int:
    """How many trailing axes the permutation leaves where they are."""
    k = 0
    for i in range(len(perm) - 1, -1, -1):
        if perm[i] != i:
            break
        k += 1
    return k


def random_perm(rank: int, rng: random.Random) -> tuple[int, ...]:
    ident = tuple(range(rank))
    while True:
        p = list(ident)
        rng.shuffle(p)
        if tuple(p) != ident:
            return tuple(p)


def leading_perm(rank: int, rng: random.Random) -> tuple[int, ...]:
    """Reorder only the first j axes, and make sure axis j-1 actually moves so
    the trailing fixed group is exactly the last r - j axes."""
    j = rng.randint(2, rank - 1)
    while True:
        head = list(range(j))
        rng.shuffle(head)
        if head[-1] != j - 1:
            return tuple(head) + tuple(range(j, rank))


def main() -> int:
    rng = random.Random(SEED)
    factored = {label: {r: eq1.shape_space(n, r) for r in RANKS} for label, n in SIZES.items()}
    filled = {name: [] for name in CLASSES}
    seen, tries = set(), 0

    while any(len(v) < PER_CLASS for v in filled.values()) and tries < MAX_TRIES:
        tries += 1
        label = rng.choice(list(SIZES))
        rank = rng.choice(list(RANKS))
        fac, omega = factored[label][rank]
        shape = eq1.random_shape(fac, rank, rng)
        if 1 in shape:
            continue
        # Rank 2 has no leading-only permutation that leaves a group behind.
        perm = random_perm(rank, rng) if rank == 2 or rng.random() < 0.5 else leading_perm(rank, rng)
        if (label, shape, perm) in seen:
            continue
        k = trailing_fixed(perm)
        d_post = math.prod(shape[rank - k:])
        cls = dpost_class(d_post)
        if len(filled[cls]) >= PER_CLASS:
            continue
        seen.add((label, shape, perm))
        filled[cls].append({
            "N_label": label, "N": SIZES[label], "rank": rank,
            "shape": list(shape), "perm": list(perm),
            "d_post": d_post, "d_post_class": cls,
            "shape_space": omega,
        })

    cases = [c for name in CLASSES for c in filled[name]]
    for i, c in enumerate(cases):
        c["id"] = i

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "seed": SEED,
        "total": len(cases),
        "classes": {name: {"d_post_lo": lo, "d_post_hi": hi, "count": len(filled[name])}
                    for name, (lo, hi) in CLASSES.items()},
        "sizes": SIZES,
        "ranks": list(RANKS),
        "cases": cases,
    }, indent=1) + "\n")

    print(f"{len(cases)} cases -> {OUT.relative_to(ROOT.parent)}")
    for name in CLASSES:
        print(f"  {name:>6}: {len(filled[name])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
