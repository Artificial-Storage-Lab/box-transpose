from __future__ import annotations

from collections import Counter
from math import gcd
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


def fixed_point_count(rows: int, cols: int) -> int:
    """Cells a rows x cols transpose maps to themselves, in closed form.

    The transpose sends flat position p to (p mod cols) * rows + p // cols. On
    0 < p < rows*cols - 1 that is multiplication by `cols` modulo
    M = rows*cols - 1, so a fixed point solves p*(cols - 1) = 0 (mod M), which
    has gcd(cols - 1, M) solutions; since M = cols*(rows - 1) + (cols - 1),
    that gcd is gcd(rows - 1, cols - 1). The endpoint p = M is fixed too, hence
    the + 1.

    This is what makes the search meaningful. It used to be a placeholder that
    reported zero fixed points, which collapsed every edge weight to
    N * elem_bytes * 2 -- identical for all of them -- so Dijkstra minimised the
    number of steps rather than the bytes moved. Checked against enumeration
    over every matrix up to 39 x 39.
    """
    return gcd(rows - 1, cols - 1) + 1


def search_cycle_info(rows: int, cols: int) -> CycleInfo:
    """Fixed-point count only: enough to weight an edge, no cycle walk.

    Enumerating real cycles is Theta(rows*cols) and the search touches O(r^3)
    edges per vertex. Starts and lengths are filled in afterwards, for the few
    steps that survive, by materialize_plan_steps.
    """
    return CycleInfo((), (), {1: fixed_point_count(rows, cols)}, False)


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
    estimated_aux_bytes: int
    total_bytes_moved: int
    planner: str = "block_dijkstra"

    @property
    def moved_ratio(self) -> float:
        """Bytes this plan moves, over what an out-of-place copy would move.

        An out-of-place copy reads every element and writes every element, so
        it moves 2*N*elem_bytes whatever the permutation. This plan skips fixed
        points, so it can move less -- and each extra step costs another pass,
        so it can move more.

        Both methods run at the same achieved bandwidth in the regime where a
        box plan is worth running, so this ratio IS the predicted runtime ratio,
        with no hardware constant in it. Below 1 the plan is expected to beat
        `.contiguous()`; at or above 1 it is not.
        """
        n = prod(self.shape)
        return self.total_bytes_moved / (2 * n * 4)


# A plan longer than this moves several times the tensor, at which point the
# caller is better served by an out-of-place copy. `plan_permute` returns None
# rather than a plan it knows is not worth running; see `max_steps`.
MAX_STEPS = 6


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
    cycles = cycle_cache.setdefault((rows, cols), search_cycle_info(rows, cols))
    fixed = cycles.histogram.get(1, 0)
    moved_positions = d_mid - fixed
    if moved_positions == 0:
        return None                      # every cell is fixed: the swap is a no-op
    bytes_moved = d_pre * moved_positions * d_post * elem_bytes * 2
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
        left_len=j - i,
        right_len=k - j,
    )




def materialize_step_cycles(step: SwapStep, cycle_cache: dict[tuple[int, int], CycleInfo]) -> SwapStep | None:
    cycles = cycle_cache.setdefault((step.rows, step.cols), matrix_transpose_cycles(step.rows, step.cols))
    if not cycles.starts:
        return None
    # bytes_moved was already exact -- fixed_point_count and the enumeration
    # agree by construction -- so materialisation only attaches the starts and
    # lengths the table kernel needs.
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
        bytes_moved=step.bytes_moved,
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
    materialize: bool = True,
    max_steps: int | None = MAX_STEPS,
) -> PermutePlan | None:
    """`materialize=False` skips the exact cycle walk, which is Theta(D_mid)
    on the host and produces the starts/lengths arrays profile() uploads. The
    leader kernel needs neither, so a plan destined for it should be built
    without them -- at N = 1e8 the walk is the dominant cost of planning."""
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
                    new_cost = cost + step.bytes_moved
                    if new_cost < dist.get(nxt, float("inf")):
                        dist[nxt] = new_cost
                        prev[nxt] = (axes, step)
                        heapq.heappush(heap, (new_cost, nxt))

    if target not in dist:
        return None

    steps_rev: list[SwapStep] = []
    cur = target
    while cur != start:
        parent, step = prev[cur]
        steps_rev.append(step)
        cur = parent
    steps = tuple(reversed(steps_rev))
    if max_steps is not None and len(steps) > max_steps:
        # The cheapest decomposition still needs more passes than the caller is
        # willing to pay for. Each pass rewrites the whole buffer, so a long
        # plan moves several times the tensor and an out-of-place copy wins on
        # both time and simplicity. Declining is the useful answer.
        return None
    if materialize:
        steps = materialize_plan_steps(steps)
    return PermutePlan(
        shape=shape,
        permute=permute,
        steps=steps,
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
        estimated_aux_bytes=sum(s.metadata_bytes for s in exact_steps),
        total_bytes_moved=sum(s.bytes_moved for s in exact_steps),
        planner="adjacent_baseline",
    )


# Public default: use the best block-swap search, not the adjacent baseline.
# Returns None if no valid box-following decomposition exists for this shape.
def plan_permute(shape: Sequence[int], permute: Sequence[int], elem_bytes: int = 4,
                 materialize: bool = True,
                 max_steps: int | None = MAX_STEPS) -> PermutePlan | None:
    """The cheapest box decomposition of `permute`, by bytes moved.

    Returns None when the cheapest one still needs more than `max_steps`
    passes; pass max_steps=None to take whatever the search finds.
    """
    return decompose_block_swaps(shape, permute, elem_bytes, materialize, max_steps)
