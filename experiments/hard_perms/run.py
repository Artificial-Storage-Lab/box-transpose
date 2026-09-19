#!/usr/bin/env python3
"""Box transpose against the in-place competitors on HARD permutations.

Every other sweep here uses permutations that move one or two leading axes and
leave a trailing group fixed -- the regime box transpose is built for, where a
plan is a single swap. This one draws permutations uniformly at random, which
is where plans get long and where a competitor might genuinely do better.

That is the question the routing policy turns on: box should serve the cases it
is best at and hand over the ones it is not. Deciding that needs a measurement
on the cases where it is plausibly not.

Box runs on the leader kernel. The table kernel needs the exact cycles of each
step, and materialising those is Theta(D_mid) on the host -- fine when a plan is
one swap of a small block, minutes when a random permutation puts most of the
tensor inside one swap. The leader kernel needs no cycle table at all, so it is
the path that actually covers this regime.

    python experiments/hard_perms/run.py --dry-run
    python experiments/hard_perms/run.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw_data" / "hard_perms"
sys.path.insert(0, str(ROOT / "src"))

ELEMENTS = 1 << 28
RANKS = range(4, 9)
PERMS_PER_RANK = 3
SEED = 0
ALPHA = 0.05
MAX_STEPS = 6


def shapes_for(rank: int) -> tuple[int, ...]:
    """One shape per rank: small leading axes, the remainder in the last.

    Held fixed across ranks so a difference between rows is the permutation
    and not the tensor.
    """
    lead = [2] * (rank - 1)
    return tuple(lead + [ELEMENTS >> (rank - 1)])


def sample(rng: random.Random):
    cases = []
    for rank in RANKS:
        shape = shapes_for(rank)
        seen = set()
        while len(seen) < PERMS_PER_RANK:
            p = list(range(rank))
            rng.shuffle(p)
            p = tuple(p)
            if p == tuple(range(rank)) or p in seen:
                continue
            seen.add(p)
            cases.append({"rank": rank, "shape": list(shape), "perm": list(p)})
    return cases


def run_sub(which: str, shape, perm, timeout=1800) -> dict:
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
    return {f"{which}_error": (out.stderr.strip().splitlines() or ["no json"])[-1][:200]}


def load_ittpd():
    d = ROOT / "n_dims" / "ittpd"
    sys.path.insert(0, str(d))
    spec = importlib.util.spec_from_file_location("ittpd_transpose", d / "transpose.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cases = sample(random.Random(SEED))
    if args.dry_run:
        for c in cases:
            print(c["rank"], c["shape"], c["perm"])
        return 0

    import torch
    import box_transpose as bt
    ittpd = load_ittpd()
    DEV = torch.device("cuda")
    gpu = torch.cuda.get_device_name(0)
    print(f"device: {gpu}   N = {ELEMENTS:,}   {len(cases)} hard permutations\n", flush=True)

    def timed(fn):
        torch.cuda.synchronize()
        e0 = torch.cuda.Event(enable_timing=True)
        e1 = torch.cuda.Event(enable_timing=True)
        e0.record(); fn(); e1.record()
        torch.cuda.synchronize()
        return e0.elapsed_time(e1)

    rows = []
    for i, c in enumerate(cases, 1):
        shape, perm = tuple(c["shape"]), tuple(c["perm"])
        row = dict(c, device=gpu, elements=ELEMENTS)
        print(f"[{i}/{len(cases)}] rank {c['rank']} {c['perm']}", flush=True)
        try:
            a = torch.randn(shape, dtype=torch.float32, device=DEV)
            src = a.permute(*perm)
            expected = src.contiguous()
            src.contiguous()
            row["contiguous_ms"] = round(timed(lambda: src.contiguous()), 3)

            plan = bt.plan_permute(shape, perm, materialize=False, max_steps=MAX_STEPS)
            if plan is None:
                row["box_error"] = f"no plan within {MAX_STEPS} steps"
            else:
                row["box_steps"] = len(plan.steps)
                row["box_moved_ratio"] = round(plan.moved_ratio, 4)
                w = a.clone(); bt.apply_leaderless(w, plan); torch.cuda.synchronize(); del w
                torch.cuda.empty_cache()
                b = a.clone()
                row["box_ms"] = round(timed(lambda: bt.apply_leaderless(b, plan)), 3)
                row["box_correct"] = bool(torch.equal(
                    b.view(-1).reshape(tuple(shape[p] for p in perm)), expected))
                del b; torch.cuda.empty_cache()

            cap = ALPHA * ELEMENTS * 4
            try:
                w = a.clone(); ittpd.transpose_inplace(w, shape, perm, max_aux_bytes=cap)
                torch.cuda.synchronize(); del w; torch.cuda.empty_cache()
                d = a.clone()
                row["ittpd_ms"] = round(timed(lambda: ittpd.transpose_inplace(
                    d, shape, perm, max_aux_bytes=cap)), 3)
                row["ittpd_correct"] = bool(torch.equal(
                    d.view(-1).reshape(tuple(shape[p] for p in perm)), expected))
                del d
            except Exception as exc:                       # noqa: BLE001
                row["ittpd_error"] = f"{type(exc).__name__}: {exc}"[:160]
            torch.cuda.empty_cache()
            del a, expected, src
            torch.cuda.empty_cache()
        except Exception as exc:                           # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"[:160]
            torch.cuda.empty_cache()

        for which, pre in (("gustavson", "gv"), ("gomezluna", "gl")):
            for k, v in run_sub(which, shape, perm).items():
                if k.startswith((pre + "_", which + "_")):
                    row[k] = v

        print(f"    cont {row.get('contiguous_ms', float('nan')):>8.2f} | "
              f"box {row.get('box_ms', float('nan')):>9.2f} "
              f"({row.get('box_steps','-')} st, mv {row.get('box_moved_ratio','-')}) | "
              f"ittpd {row.get('ittpd_ms', float('nan')):>8.2f} | "
              f"gv {row.get('gv_apply_ms', float('nan')):>8.2f} | "
              f"gl {row.get('gl_apply_ms', float('nan')):>8.2f}", flush=True)
        rows.append(row)

    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"results_{gpu.lower().replace(' ', '_')}.jsonl"
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} rows to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
