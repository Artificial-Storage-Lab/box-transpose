#!/usr/bin/env python3
"""All five methods, ranks 2 through 10, in the large-D_post regime.

Shapes come from Equation (1): N is prime-factorised and each prime's exponent
is spread over the r dimensions, so the population is the full ordered shape
space rather than shapes chosen by hand. Two restrictions are applied, and both
are stated before any result is looked at:

  1. No unit axes. A dimension of 1 moves anywhere without touching a byte, so
     a shape containing one is a rank-r tensor in name only.

  2. D_post >= D_POST_MIN. This is box transpose's stated precondition -- the
     permutation has to leave a trailing group of axes fixed, and that group
     has to be large enough for the moved runs to coalesce. It is the same
     condition tau encodes in the planner, and the paper's routing rule: a
     permutation that fails it is handed to .contiguous() rather than planned.

Restriction 2 is what makes this a report on the regime box transpose claims,
not on the whole permutation space. Cases outside it are not silently dropped:
`coverage` in the summary says how much of each rank's sampled space qualifies.

Why the regime is favourable is not a tuning accident. A swap block of
rows x cols has gcd(rows-1, cols-1) + 1 fixed points -- cells a transpose maps
to themselves. Box transpose skips them; an out-of-place copy must write every
output position whether or not it already holds the right value. So on a square
n x n block box moves 1 - 1/n of the tensor and .contiguous() moves all of it,
and the ratio of their runtimes is that fraction. `moved_frac` is recorded per
case so the prediction can be checked against the measurement.

Runtime is CUDA-event timed with one warmup per method, matching
n_dims/ittpd/benchmark.py. Gustavson and Gomez-Luna run in subprocesses: both
reconstructions define a top-level `decomposition` module, so in one process
whichever imports first shadows the other.

    python experiments/dpost_sweep/run.py --dry-run    # shapes only, no GPU
    python experiments/dpost_sweep/run.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw_data" / "dpost_sweep"
sys.path.insert(0, str(ROOT / "src"))

ELEM_BYTES = 4
ELEMENTS = 1 << 28            # 268,435,456 -- 1.07 GB at fp32
RANKS = range(2, 11)
D_POST_MIN = 1 << 16          # 65,536 elements = 256 KB of contiguous run
SHAPES_PER_RANK = 6
SEED = 0
ALPHA = 0.05


# ── Equation (1): the shape space ────────────────────────────────────────────

def factorise(n: int) -> list[tuple[int, int]]:
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


def n_compositions(total: int, parts: int) -> int:
    """Stars and bars: ways to spread one prime's exponent over `parts` dims."""
    return math.comb(total + parts - 1, parts - 1)


def random_composition(total: int, parts: int, rng: random.Random) -> tuple[int, ...]:
    """One composition drawn uniformly, without enumerating the space.

    At rank 10 with N = 2^28 there are C(37, 9) = 124,403,620 ways to split the
    exponent of 2 alone, so the space is sampled by placing bars rather than
    listed. Each draw is uniform over exactly the set Equation (1) defines.
    """
    if parts == 1:
        return (total,)
    bars = sorted(rng.sample(range(total + parts - 1), parts - 1))
    out, prev = [], -1
    for b in bars:
        out.append(b - prev - 1)
        prev = b
    out.append(total + parts - 2 - prev)
    return tuple(out)


def shape_space(n: int, rank: int):
    fac = factorise(n)
    return fac, math.prod(n_compositions(e, rank) for _, e in fac)


def random_shape(fac, rank: int, rng: random.Random) -> tuple[int, ...]:
    dims = [1] * rank
    for prime, exp in fac:
        for j, b in enumerate(random_composition(exp, rank, rng)):
            dims[j] *= prime ** b
    return tuple(dims)


def sample_cases(rank: int, rng: random.Random):
    """Shapes from the space, paired with permutations that fix a trailing group.

    A permutation that rearranges only the first j axes leaves D_post equal to
    the product of the remaining r - j, which is what makes D_post large. Both
    the 2-axis swap and the 3-axis rotation are taken where the rank allows, so
    the sample is not one permutation shape repeated.
    """
    fac, omega = shape_space(ELEMENTS, rank)
    seen, cases, tried, qualified = set(), [], 0, 0
    # Sample until SHAPES_PER_RANK shapes QUALIFY, not until that many are
    # drawn: the D_post filter rejects most of the space at low rank, and
    # counting draws instead of acceptances would silently shrink those ranks.
    # `acceptance` records how harsh the filter was, which is the coverage
    # number the paper has to report alongside any result from this regime.
    while qualified < SHAPES_PER_RANK and tried < 200000:
        tried += 1
        shape = random_shape(fac, rank, rng)
        if 1 in shape or shape in seen:
            continue
        seen.add(shape)
        before = len(cases)
        perms = [(1, 0) + tuple(range(2, rank))]
        if rank >= 3:
            perms.append((2, 0, 1) + tuple(range(3, rank)))
        for perm in perms:
            j = 2 if perm[0] == 1 else 3
            d_post = math.prod(shape[j:]) if j < rank else 1
            if d_post < D_POST_MIN:
                continue
            cases.append({"rank": rank, "shape": list(shape), "perm": list(perm),
                          "d_post": d_post, "shape_space": omega})
        if len(cases) > before:
            qualified += 1
    acceptance = qualified / max(len(seen), 1)
    for c in cases:
        c["shape_acceptance"] = round(acceptance, 4)
        c["stratum"] = "sampled"

    # Second stratum: a SQUARE leading block of side n. These are ordinary
    # members of the same shape space -- the exponent split that gives the
    # first two dimensions equal shares -- but they are drawn deliberately
    # rather than waited for, because they are where the fixed points are.
    #
    # An n x n transpose fixes its n diagonal cells, so box transpose moves
    # 1 - 1/n of the tensor while .contiguous() must write all of it. The
    # smaller n, the larger the saving: n = 2 moves half. A uniform draw from
    # the space almost never lands on a small square block, so a sweep without
    # this stratum measures the regime and misses its most favourable corner.
    for n in (2, 4, 8):
        if rank < 3:
            break
        e = n.bit_length() - 1                 # n = 2^e
        rest = 28 - 2 * e
        if rest < rank - 2:
            continue
        tail = random_composition(rest, rank - 2, rng)
        if any(b == 0 for b in tail):
            tail = tuple(b + 1 for b in tail)
            over = sum(tail) - rest
            tail = (tail[0] - over,) + tail[1:]
            if tail[0] < 1:
                continue
        shape = (n, n) + tuple(1 << b for b in tail)
        if math.prod(shape) != ELEMENTS or 1 in shape:
            continue
        d_post = math.prod(shape[2:])
        if d_post < D_POST_MIN:
            continue
        cases.append({"rank": rank, "shape": list(shape),
                      "perm": [1, 0] + list(range(2, rank)),
                      "d_post": d_post, "shape_space": omega,
                      "shape_acceptance": round(acceptance, 4),
                      "stratum": f"square{n}"})
    return cases, omega


# ── competitors in subprocesses ──────────────────────────────────────────────

def run_sub(which: str, shape, perm, timeout=1200) -> dict:
    d = ROOT / "n_dims" / which
    try:
        out = subprocess.run(
            [sys.executable, str(d / "benchmark.py"),
             json.dumps(list(shape)), json.dumps(list(perm))],
            capture_output=True, text=True, timeout=timeout, cwd=str(d))
    except subprocess.TimeoutExpired:
        return {f"{which}_error": "timeout"}
    for line in reversed(out.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    tail = (out.stderr.strip().splitlines() or ["no json"])[-1]
    return {f"{which}_error": tail[:200]}


def load_ittpd():
    d = ROOT / "n_dims" / "ittpd"
    sys.path.insert(0, str(d))
    spec = importlib.util.spec_from_file_location("ittpd_transpose", d / "transpose.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print the sampled cases and stop, no GPU needed")
    ap.add_argument("--ranks", type=str, default=None, help="e.g. 2,3,4")
    args = ap.parse_args()

    ranks = [int(x) for x in args.ranks.split(",")] if args.ranks else list(RANKS)
    rng = random.Random(SEED)
    all_cases, coverage = [], {}
    for rank in ranks:
        cases, omega = sample_cases(rank, rng)
        all_cases += cases
        coverage[rank] = (len(cases), omega)
        if not cases:
            # Rank 2 lands here by construction: perm (1,0) leaves no trailing
            # axes, so D_post is 1 and the precondition cannot be met at all.
            # That is a property of the method, not a sampling failure, and it
            # is printed rather than passed over in silence.
            print(f"rank {rank}: NO CASES -- precondition unsatisfiable "
                  f"(no trailing axis group to fix)")
            continue
        acc = cases[0]["shape_acceptance"]
        print(f"rank {rank}: {len(cases)} cases from a space of {omega:,} shapes "
              f"({100*acc:.0f}% of sampled shapes met D_post >= {D_POST_MIN:,})")

    if args.dry_run:
        print(f"\n{'rank':>4} {'shape':>44} {'perm':>24} {'D_post':>14}")
        for c in all_cases:
            print(f"{c['rank']:>4} {str(c['shape']):>44} {str(c['perm']):>24} {c['d_post']:>14,}")
        return 0

    import torch
    import box_transpose as bt
    ittpd = load_ittpd()
    DEV = torch.device("cuda")
    gpu = torch.cuda.get_device_name(0)
    print(f"\ndevice: {gpu}   N = {ELEMENTS:,} ({ELEMENTS*ELEM_BYTES/1e9:.2f} GB)\n")

    def timed(fn):
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats(DEV)
        base = torch.cuda.memory_allocated(DEV)
        e0 = torch.cuda.Event(enable_timing=True)
        e1 = torch.cuda.Event(enable_timing=True)
        e0.record(); fn(); e1.record()
        torch.cuda.synchronize()
        return e0.elapsed_time(e1), torch.cuda.max_memory_allocated(DEV) - base

    rows = []
    for i, c in enumerate(all_cases, 1):
        shape, perm = tuple(c["shape"]), tuple(c["perm"])
        row = dict(c, device=gpu, elements=ELEMENTS)
        print(f"[{i}/{len(all_cases)}] rank {c['rank']} {c['shape']} {c['perm']}", flush=True)
        try:
            a = torch.randn(shape, dtype=torch.float32, device=DEV)
            src = a.permute(*perm)
            expected = src.contiguous()

            src.contiguous()
            ms, aux = timed(lambda: src.contiguous())
            row["contiguous_ms"], row["contiguous_aux_bytes"] = round(ms, 4), aux

            plan = bt.plan_permute(shape, perm)
            prof = bt.profile(plan)
            row["box_steps"] = len(plan.steps)
            row["box_aux_bytes"] = prof.aux_bytes
            row["moved_frac"] = plan.total_bytes_moved / (2 * ELEMENTS * ELEM_BYTES)
            row["box_min_d_post"] = min(s.d_post for s in plan.steps)
            w = a.clone(); bt.apply(w, prof); torch.cuda.synchronize(); del w
            torch.cuda.empty_cache()
            b = a.clone()
            ms, aux = timed(lambda: bt.apply(b, prof))
            row["box_ms"] = round(ms, 4)
            row["box_correct"] = bool(torch.equal(
                b.view(-1).reshape(tuple(shape[p] for p in perm)), expected))
            del b; torch.cuda.empty_cache()

            cap = ALPHA * ELEMENTS * ELEM_BYTES
            try:
                w = a.clone()
                ittpd.transpose_inplace(w, shape, perm, max_aux_bytes=cap)
                torch.cuda.synchronize(); del w; torch.cuda.empty_cache()
                d = a.clone()
                ms, aux = timed(lambda: ittpd.transpose_inplace(
                    d, shape, perm, max_aux_bytes=cap))
                row["ittpd_ms"], row["ittpd_aux_bytes"] = round(ms, 4), aux
                row["ittpd_correct"] = bool(torch.equal(
                    d.view(-1).reshape(tuple(shape[p] for p in perm)), expected))
                del d
            except Exception as exc:                     # noqa: BLE001
                row["ittpd_error"] = f"{type(exc).__name__}: {exc}"[:200]
            torch.cuda.empty_cache()

            del a, expected, src
            torch.cuda.empty_cache()
        except Exception as exc:                         # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"[:200]
            torch.cuda.empty_cache()

        for which, pre in (("gustavson", "gv"), ("gomezluna", "gl")):
            res = run_sub(which, shape, perm)
            for k, v in res.items():
                if k.startswith((pre + "_", which + "_")):
                    row[k] = v

        print(f"    cont {row.get('contiguous_ms', float('nan')):>8.2f} | "
              f"box {row.get('box_ms', float('nan')):>8.2f} "
              f"({'ok' if row.get('box_correct') else 'x'}) | "
              f"ittpd {row.get('ittpd_ms', float('nan')):>8.2f} | "
              f"gv {row.get('gv_apply_ms', float('nan')):>8.2f} | "
              f"gl {row.get('gl_apply_ms', float('nan')):>8.2f}", flush=True)
        rows.append(row)

    RAW.mkdir(parents=True, exist_ok=True)
    tag = gpu.lower().replace(" ", "_").replace("/", "_")
    out = RAW / f"results_{tag}.jsonl"
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} rows to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
