from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import heapq
from typing import Sequence


def prod(xs: Sequence[int]) -> int:
    out = 1
    for x in xs:
        out *= int(x)
    return out


@dataclass(frozen=True)
class CycleInfo:
    starts: tuple[int, ...]
    lengths: tuple[int, ...]
    histogram: dict[int, int]
    exact: bool = True

    @property
    def metadata_bytes(self) -> int:
        return len(self.starts) * 8


def matrix_transpose_cycles(rows: int, cols: int) -> CycleInfo:
    total = rows * cols
    visited = bytearray(total)
    starts: list[int] = []
    lengths: list[int] = []
    hist: Counter[int] = Counter()
    for s in range(total):
        if visited[s]:
            continue
        cur = s
        length = 0
        while not visited[cur]:
            visited[cur] = 1
            length += 1
            cur = (cur % cols) * rows + cur // cols
        hist[length] += 1
        if length > 1:
            starts.append(s)
            lengths.append(length)
    return CycleInfo(tuple(starts), tuple(lengths), dict(sorted(hist.items())), True)


def estimated_cycle_info(rows: int, cols: int) -> CycleInfo:
    # Cheap placeholder for planner search. Exact starts/lengths are generated
    # only for the final selected steps, because some candidate block swaps have
    # millions of logical positions.
    return CycleInfo((), (), {1: 0}, False)


@dataclass(frozen=True)
class SwapStep:
    index: int
    axes_before: tuple[int, ...]
    axes_after: tuple[int, ...]
    dims_before: tuple[int, ...]
    d_pre: int
    rows: int
    cols: int
    d_post: int
    cycles: CycleInfo
    bytes_moved: int
    estimated_ms: float
    left_len: int = 1
    right_len: int = 1

    @property
    def metadata_bytes(self) -> int:
        return self.cycles.metadata_bytes

    @property
    def kernel(self) -> str:
        return "float4" if self.d_post % 4 == 0 else "scalar"

    @property
    def kind(self) -> str:
        return "block_swap" if self.left_len > 1 or self.right_len > 1 else "axis_swap"


@dataclass(frozen=True)
class PermutePlan:
    shape: tuple[int, ...]
    permute: tuple[int, ...]
    steps: tuple[SwapStep, ...]
    estimated_ms: float
    estimated_aux_bytes: int
    total_bytes_moved: int
    planner: str = "block_dijkstra"


# ── Calibrated throughput model ───────────────────────────────────────────────
# Derived from controlled sweeps on RTX PRO 6000 Blackwell (N=1B).
# Re-run calibration/find_edge_costs/
# micro_benchmark.py and calibrate.py to re-derive for a different GPU.
#
# TAU: τ — throughput knee (Algorithm 3a).
#   Smallest D_post where observed throughput first reaches 50% of peak.
#   Reproduced from a standalone D_post sweep; see micro_benchmark.py.
#   Used for two things: pruning Dijkstra graph edges (make_step) and
#   filtering calibration samples when computing MU.
#
# D_POST_STAR: D_post* — routing gate (Algorithm 3b η pre-check only).
#   Minimum D_post at which box transpose consistently outperforms cycle
#   splitter, derived from the routing benchmark comparison across 136 cases.
#   Only used in _router.py; not involved in graph pruning or calibration.
#
# MU: μ — mean observed throughput (GB/s) for steps with D_post >= TAU.
#   Calibrated on the same τ-pruned graph that Dijkstra searches.
TAU         = 1     # τ  (elements) — graph pruning bypassed for box search for now. Used to be 80
D_POST_STAR = 1     # D_post* (elements) — always try box planning first for box search for now. Used to be 100.
MU          = 69.7  # μ  (GB/s) — throughput for steps passing τ


def step_cost_ms(bytes_moved: int, d_post: int, rows: int, cols: int) -> float:
    return bytes_moved / (MU * 1e9) * 1e3


def make_step(
    axes: tuple[int, ...],
    shape: tuple[int, ...],
    i: int,
    j: int,
    k: int,
    cycle_cache: dict[tuple[int, int], CycleInfo],
    elem_bytes: int,
) -> SwapStep | None:
    dims = tuple(shape[a] for a in axes)
    rows = prod(dims[i:j])
    cols = prod(dims[j:k])
    d_mid = rows * cols
    d_pre = prod(dims[:i])
    d_post = prod(dims[k:])
    if d_post < TAU:
        return None
    cycles = cycle_cache.setdefault((rows, cols), estimated_cycle_info(rows, cols))
    fixed = cycles.histogram.get(1, 0)
    moved_positions = d_mid - fixed
    bytes_moved = d_pre * moved_positions * d_post * elem_bytes * 2
    estimated_ms = step_cost_ms(bytes_moved, d_post, rows, cols)
    new_axes = axes[:i] + axes[j:k] + axes[i:j] + axes[k:]
    return SwapStep(
        index=i,
        axes_before=axes,
        axes_after=new_axes,
        dims_before=dims,
        d_pre=d_pre,
        rows=rows,
        cols=cols,
        d_post=d_post,
        cycles=cycles,
        bytes_moved=bytes_moved,
        estimated_ms=estimated_ms,
        left_len=j - i,
        right_len=k - j,
    )




def materialize_step_cycles(step: SwapStep, cycle_cache: dict[tuple[int, int], CycleInfo]) -> SwapStep | None:
    cycles = cycle_cache.setdefault((step.rows, step.cols), matrix_transpose_cycles(step.rows, step.cols))
    if not cycles.starts:
        return None
    fixed = cycles.histogram.get(1, 0)
    moved_positions = step.rows * step.cols - fixed
    # Keep the original estimated_ms; exact fixed points are negligible for the
    # large cases and preserving search cost avoids reshuffling the selected path.
    bytes_moved = step.d_pre * moved_positions * step.d_post * 4 * 2
    return SwapStep(
        index=step.index,
        axes_before=step.axes_before,
        axes_after=step.axes_after,
        dims_before=step.dims_before,
        d_pre=step.d_pre,
        rows=step.rows,
        cols=step.cols,
        d_post=step.d_post,
        cycles=cycles,
        bytes_moved=bytes_moved,
        estimated_ms=step.estimated_ms,
        left_len=step.left_len,
        right_len=step.right_len,
    )


def materialize_plan_steps(steps: tuple[SwapStep, ...]) -> tuple[SwapStep, ...]:
    exact_cache: dict[tuple[int, int], CycleInfo] = {}
    out: list[SwapStep] = []
    for step in steps:
        exact = materialize_step_cycles(step, exact_cache)
        if exact is not None:
            out.append(exact)
    return tuple(out)

def decompose_block_swaps(
    shape: Sequence[int],
    permute: Sequence[int],
    elem_bytes: int = 4,
) -> PermutePlan | None:
    shape = tuple(int(x) for x in shape)
    permute = tuple(int(x) for x in permute)
    rank = len(shape)
    if sorted(permute) != list(range(rank)):
        raise ValueError(f"invalid permute {permute} for rank {rank}")

    start = tuple(range(rank))
    target = permute
    cycle_cache: dict[tuple[int, int], CycleInfo] = {}
    dist: dict[tuple[int, ...], float] = {start: 0.0}
    prev: dict[tuple[int, ...], tuple[tuple[int, ...], SwapStep]] = {}
    heap: list[tuple[float, tuple[int, ...]]] = [(0.0, start)]

    while heap:
        cost, axes = heapq.heappop(heap)
        if cost != dist[axes]:
            continue
        if axes == target:
            break
        for i in range(rank - 1):
            for j in range(i + 1, rank):
                for k in range(j + 1, rank + 1):
                    step = make_step(axes, shape, i, j, k, cycle_cache, elem_bytes)
                    if step is None:
                        continue
                    nxt = step.axes_after
                    new_cost = cost + step.estimated_ms
                    if new_cost < dist.get(nxt, float("inf")):
                        dist[nxt] = new_cost
                        prev[nxt] = (axes, step)
                        heapq.heappush(heap, (new_cost, nxt))

    if target not in dist:
        return decompose_adjacent_swaps(shape, permute, elem_bytes)

    steps_rev: list[SwapStep] = []
    cur = target
    while cur != start:
        parent, step = prev[cur]
        steps_rev.append(step)
        cur = parent
    steps = materialize_plan_steps(tuple(reversed(steps_rev)))
    return PermutePlan(
        shape=shape,
        permute=permute,
        steps=steps,
        estimated_ms=sum(s.estimated_ms for s in steps),
        estimated_aux_bytes=sum(s.metadata_bytes for s in steps),
        total_bytes_moved=sum(s.bytes_moved for s in steps),
        planner="block_dijkstra",
    )


def decompose_adjacent_swaps(
    shape: Sequence[int],
    permute: Sequence[int],
    elem_bytes: int = 4,
) -> PermutePlan | None:
    shape = tuple(int(x) for x in shape)
    permute = tuple(int(x) for x in permute)
    if sorted(permute) != list(range(len(shape))):
        raise ValueError(f"invalid permute {permute} for rank {len(shape)}")

    axes = list(range(len(shape)))
    steps: list[SwapStep] = []
    cycle_cache: dict[tuple[int, int], CycleInfo] = {}

    for target_pos, desired_axis in enumerate(permute):
        pos = axes.index(desired_axis)
        while pos > target_pos:
            step = make_step(tuple(axes), shape, pos - 1, pos, pos + 1, cycle_cache, elem_bytes)
            if step is None:
                return None
            axes = list(step.axes_after)
            steps.append(step)
            pos -= 1

    exact_steps = materialize_plan_steps(tuple(steps))
    return PermutePlan(
        shape=shape,
        permute=permute,
        steps=exact_steps,
        estimated_ms=sum(s.estimated_ms for s in exact_steps),
        estimated_aux_bytes=sum(s.metadata_bytes for s in exact_steps),
        total_bytes_moved=sum(s.bytes_moved for s in exact_steps),
        planner="adjacent_baseline",
    )


# Public default: use the best block-swap search, not the adjacent baseline.
# Returns None if no valid box-following decomposition exists for this shape.
def plan_permute(shape: Sequence[int], permute: Sequence[int], elem_bytes: int = 4) -> PermutePlan | None:
    return decompose_block_swaps(shape, permute, elem_bytes)
