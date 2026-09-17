"""
Box-following algorithm.

Decomposes the permutation into a sequence of 2D matrix transposes on
grouped axes, found via Dijkstra search over axis orderings. Each step
transposes a logical (rows x cols) matrix in-place using the known cycle
structure of matrix transposition.

Aux memory: cycle start/length arrays per step (bytes to KB, not O(N)).
Apply cost: O(n_steps * N) — typically 1-3 passes over the data.
"""
from __future__ import annotations

import torch

from ._kernels._load import get_box_ext
from ._plan import PermutePlan

DEVICE = torch.device("cuda")


class BoxProfile:
    """Holds the precomputed plan and materialized cycle arrays for one permutation."""

    def __init__(self, plan: PermutePlan, starts: list[torch.Tensor],
                 lengths: list[torch.Tensor]):
        self.plan    = plan
        self.starts  = starts
        self.lengths = lengths

    @property
    def aux_bytes(self) -> int:
        return sum(s.nbytes + l.nbytes for s, l in zip(self.starts, self.lengths))


def profile(plan: PermutePlan) -> BoxProfile:
    """Materialize cycle arrays for all steps in the plan onto the GPU."""
    starts  = []
    lengths = []
    for step in plan.steps:
        starts.append(torch.tensor(step.cycles.starts,  dtype=torch.int32, device=DEVICE))
        lengths.append(torch.tensor(step.cycles.lengths, dtype=torch.int32, device=DEVICE))
    return BoxProfile(plan, starts, lengths)


def apply(tensor: torch.Tensor, box_profile: BoxProfile) -> None:
    ext = get_box_ext()
    for step, starts, lengths in zip(
            box_profile.plan.steps, box_profile.starts, box_profile.lengths):
        ext.adjacent_box_swap(
            tensor, starts, lengths,
            step.d_pre, step.rows, step.cols, step.d_post)
