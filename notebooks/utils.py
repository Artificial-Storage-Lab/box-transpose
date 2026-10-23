"""Helpers for demo.ipynb: timing, the other methods, running a case and showing it."""
import importlib.util, json, math, statistics, subprocess, sys, time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import torch
from IPython.display import display
import box_following as bf

ROOT = Path(__file__).resolve().parent.parent
DEV = torch.device("cuda")
GB = 2**30


def run_timed(fn, reps=10):
    fn()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats(DEV)
    base = torch.cuda.memory_allocated(DEV)
    times = []
    for _ in range(reps):
        start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        start.record(); fn(); end.record()
        torch.cuda.synchronize()
        times.append(start.elapsed_time(end))
    return statistics.median(times), torch.cuda.max_memory_allocated(DEV) - base


def nice_bytes(b):
    for unit in ("bytes", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:,.0f} {unit}" if unit == "bytes" else f"{b:,.1f} {unit}"
        b /= 1024
    return f"{b:,.1f} TB"


ittpd_dir = ROOT / "n_dims" / "ittpd"
sys.path.insert(0, str(ittpd_dir))
spec = importlib.util.spec_from_file_location("ittpd_transpose", ittpd_dir / "transpose.py")
ittpd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ittpd)


def ittpd_passes(step):
    if step["mode"].startswith("linearize"):
        return 1
    return 3 if math.gcd(step["M"], step["K"]) > 1 else 2


def print_placement(ptr_before, ptr_after, size_before, size_after, correct):
    print(f"  address         {ptr_before:#x} -> {ptr_after:#x}   same: {ptr_before == ptr_after}")
    print(f"  buffer size     {size_before:,} -> {size_after:,} bytes   same: {size_before == size_after}")
    print(f"  correct         {correct}")


def run_other(folder, SHAPE, PERM):
    out = subprocess.run([sys.executable, "benchmark.py", json.dumps(SHAPE), json.dumps(PERM)],
                         cwd=ROOT / "n_dims" / folder, capture_output=True, text=True)
    line = [l for l in out.stdout.splitlines() if l.startswith("{")][-1]
    return json.loads(line)


def run_case(SHAPE, PERM):
    OUT_SHAPE = tuple(SHAPE[p] for p in PERM)
    N = math.prod(SHAPE)
    TENSOR_BYTES = N * 4
    results = {}

    def fresh():
        torch.manual_seed(0)
        return torch.randn(SHAPE, dtype=torch.float32, device=DEV)

    expected = fresh().permute(*PERM).contiguous()
    print(f"shape {SHAPE}, permutation {PERM}: {N:,} elements, {TENSOR_BYTES / GB:.2f} GB\n")

    # ---- box following: one time profiling
    t0 = time.perf_counter()
    plan = bf.plan_permute(SHAPE, PERM)
    plan_ms = (time.perf_counter() - t0) * 1e3
    t0 = time.perf_counter()
    prof = bf.profile(plan)
    torch.cuda.synchronize()
    upload_ms = (time.perf_counter() - t0) * 1e3

    print("BOX FOLLOWING")
    for i, s in enumerate(plan.steps, 1):
        print(f"  swap {i}: d_pre={s.d_pre}  rows={s.rows}  cols={s.cols}  d_post={s.d_post:,}")
    print(f"  planning time   {plan_ms:.2f} ms")
    print(f"  upload to GPU   {upload_ms:.2f} ms")
    print(f"  plan memory     {nice_bytes(prof.aux_bytes)}")

    # ---- box following: run, check in place and correct
    x = fresh()
    ptr_before, size_before = x.data_ptr(), x.untyped_storage().nbytes()
    bf.apply(x, prof)
    torch.cuda.synchronize()
    ptr_after, size_after = x.data_ptr(), x.untyped_storage().nbytes()
    box_correct = torch.equal(x.view(OUT_SHAPE), expected)
    print_placement(ptr_before, ptr_after, size_before, size_after, box_correct)
    box_ms, box_extra = run_timed(lambda: bf.apply(x, prof))
    results["Box following (ours)"] = dict(ms=box_ms, aux=prof.aux_bytes + box_extra,
                                          in_place=ptr_before == ptr_after, correct=box_correct,
                                          passes=len(plan.steps))
    del x

    # ---- .contiguous(): writes into a new tensor
    src = fresh().permute(*PERM)
    out = src.contiguous()
    cont_correct = torch.equal(out, expected)
    print("\n.contiguous()")
    print(f"  address         {src.data_ptr():#x} -> {out.data_ptr():#x}   same: {src.data_ptr() == out.data_ptr()}")
    print(f"  correct         {cont_correct}")
    del out
    cont_ms, cont_extra = run_timed(lambda: src.contiguous())
    results["PyTorch .contiguous()"] = dict(ms=cont_ms, aux=cont_extra, in_place=False, correct=cont_correct,
                                           passes=1)
    del src

    # ---- ITTPD
    cap = 0.05 * TENSOR_BYTES
    y = fresh()
    ptr_before, size_before = y.data_ptr(), y.untyped_storage().nbytes()
    steps = ittpd.transpose_inplace(y, SHAPE, PERM, max_aux_bytes=cap)
    torch.cuda.synchronize()
    ittpd_n = sum(ittpd_passes(s) for s in steps)
    ittpd_correct = torch.equal(y.view(-1).view(OUT_SHAPE), expected)
    print("\nITTPD")
    print_placement(ptr_before, y.data_ptr(), size_before, y.untyped_storage().nbytes(), ittpd_correct)
    ittpd_ms, ittpd_extra = run_timed(lambda: ittpd.transpose_inplace(y, SHAPE, PERM, max_aux_bytes=cap))
    results["ITTPD"] = dict(ms=ittpd_ms, aux=ittpd_extra, in_place=y.data_ptr() == ptr_before,
                            correct=ittpd_correct, passes=ittpd_n)
    del y, expected
    torch.cuda.empty_cache()   # give the GPU back before the other processes need it

    # ---- Gustavson and Gomez-Luna, each in its own process
    gv = run_other("gustavson", SHAPE, PERM)
    results["Gustavson"] = dict(ms=gv["gv_apply_ms"], aux=gv["gv_aux_bytes"],
                                in_place=gv["gv_ptr_before"] == gv["gv_ptr_after"],
                                correct=gv["gv_correct"], passes=gv["gv_passes"])
    gl = run_other("gomezluna", SHAPE, PERM)
    results["Gomez-Luna"] = dict(ms=gl["gl_apply_ms"], aux=gl["gl_aux_bytes"],
                                 in_place=gl["gl_ptr_before"] == gl["gl_ptr_after"],
                                 correct=gl["gl_correct"], passes=gl["n_stages"])
    for name, r, k in (("Gustavson", gv, "gv"), ("Gomez-Luna", gl, "gl")):
        print(f"\n{name}")
        print_placement(r[f"{k}_ptr_before"], r[f"{k}_ptr_after"],
                        r[f"{k}_size_before"], r[f"{k}_size_after"], r[f"{k}_correct"])
    return results


BASELINE = "PyTorch .contiguous()"
OURS, BASE, OTHER, INK, MUTED = "#2a78d6", "#7d7c78", "#c3c2b7", "#0b0b0b", "#52514e"


def show(results, SHAPE, PERM):
    base = results[BASELINE]
    speedup = {n: base["ms"] / r["ms"] for n, r in results.items()}
    order = [BASELINE] + sorted((n for n in results if n != BASELINE), key=lambda n: results[n]["ms"])

    table = pd.DataFrame([
        {"Method": n,
         "Runtime (ms)": round(results[n]["ms"], 2),
         "Speedup vs baseline": "1.0x (baseline)" if n == BASELINE else f"{speedup[n]:.2f}x",
         # Data movement Amplification: full-tensor read+write traversals, relative to the one a correct conversion needs.
         "Data movement Amplification": f"{results[n]['passes'] / base['passes']:.1f}x",
         "Extra memory": nice_bytes(results[n]["aux"]),
         "In place": "yes" if results[n]["in_place"] else "no",
         "Correct": "yes" if results[n]["correct"] else "NO"}
        for n in order
    ]).set_index("Method")
    display(table)

    names = order[::-1]
    times = [results[n]["ms"] for n in names]
    colors = [OURS if n.startswith("Box") else BASE if n == BASELINE else OTHER for n in names]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.barh(names, times, color=colors, height=0.55)
    ax.set_xscale("log")
    ax.axvline(base["ms"], color=BASE, linestyle="--", linewidth=1)
    for i, (n, t) in enumerate(zip(names, times)):
        label = f"{t:.1f} ms" + ("  (baseline)" if n == BASELINE else f"  {speedup[n]:.2f}x")
        ax.text(max(t, base["ms"]) * 1.08, i, label, va="center", fontsize=9, color=INK)
    ax.set_xlabel("Runtime, ms (log scale, lower is better). Dashed line is the .contiguous() baseline.", color=MUTED)
    ax.set_title(f"shape {SHAPE}, permutation {PERM}", loc="left", fontsize=10, color=INK)
    ax.set_xlim(1, max(times) * 4)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(OTHER)
    ax.tick_params(colors=MUTED, length=0)
    ax.grid(axis="x", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.show()
