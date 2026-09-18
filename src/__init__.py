"""In-place N-D tensor permutation by box following.

A permutation is decomposed into a sequence of adjacent box swaps, each of
which transposes a logical (rows x cols) matrix in place using the known
cycle structure of matrix transposition. The decomposition is found by
Dijkstra search over axis orderings.

    import torch, box_transpose as bt

    x    = torch.randn(2, 3, 4, device="cuda")
    plan = bt.plan_permute(x.shape, (2, 1, 0))
    bt.apply(x, bt.profile(plan))     # x is now permuted in place
"""
from ._plan import (
    CycleInfo,
    PermutePlan,
    SwapStep,
    matrix_transpose_cycles,
    plan_permute,
)
from ._transpose import BoxProfile, apply, apply_leaderless, profile

__all__ = [
    "BoxProfile",
    "CycleInfo",
    "PermutePlan",
    "SwapStep",
    "apply",
    "apply_leaderless",
    "matrix_transpose_cycles",
    "plan_permute",
    "profile",
]
