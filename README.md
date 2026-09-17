# box-transpose

In-place N-D tensor permutation on CUDA by box following.

A permutation is decomposed into a sequence of **adjacent box swaps**. A *box*
is one or more neighbouring axes treated as a single unit; a swap exchanges two
adjacent boxes. Each swap is carried out as an in-place transpose of a logical
`rows x cols` matrix, batched over everything to the left (`d_pre`) and
vectorised over everything to the right (`d_post`). The sequence of swaps is
found by Dijkstra search over axis orderings.

Auxiliary memory is the cycle start/length arrays per step — kilobytes, not
`O(N)`. The data itself is never copied to a second buffer.

## You never type a number into the paper

An experiment writes its results to `raw_data/`. A script under
`paper/pipeline/` reads those results and writes a LaTeX macro. The paper uses
the macro. Re-run the experiment and every number in the paper changes by
itself.

If you type a number into the prose anyway, `make audit` fails. That is what
stops the rule from quietly rotting.

```bash
make sweep    # sample shape/permutation pairs, ranks 2-6, into raw_data/
make verify   # regenerate the paper's numbers, check, build the PDF
```

The root `Makefile` only forwards to `paper/`, which is where the real one
lives; `cd paper && make verify` is the same thing. `paper/README.md` lists
every target.

The sweep is CPU only and seeded, so that pair of commands works on a machine
with no GPU and reproduces the committed data exactly. `paper/pipeline/verify.py`
re-runs every generator into a scratch tree and diffs it against what is
committed, so a `_generated/` file that has gone stale against its data is
reported rather than silently fixed.

Section 2.3 of the write-up is the worked case end to end: one claim in the
prose, one table and one figure, all computed from
`raw_data/plan_sweep/results.jsonl`. Read `paper/pipeline/readme.md` to see
how, then copy the nearest generator when you add the next one.

`paper/` currently holds the CS 8045 project proposal, structured to the six
components its guidelines grade; `paper/README.md` maps each component to its
section.

## Install

```bash
pip install -e .
```

Or open the folder in VS Code and reopen in the dev container, which builds
from the `Dockerfile` and installs the package for you. `docker build -t
box-transpose . && docker run --gpus=all -it box-transpose bash` works too.

Requires PyTorch and a CUDA GPU. The kernel is JIT-compiled by
`torch.utils.cpp_extension` on first use and cached in
`src/_kernels/_build/`; the first call therefore takes a minute or
two, and every call after that is instant.

## Use

```python
import torch, box_transpose as bt

x = torch.arange(2 * 3 * 4, dtype=torch.float32, device="cuda").reshape(2, 3, 4)

plan = bt.plan_permute(x.shape, (2, 1, 0))   # search for a decomposition
bt.apply(x, bt.profile(plan))                 # x is now permuted, in place
```

`plan_permute` returns `None` if no box-following decomposition exists for that
shape. `profile` uploads the cycle arrays to the GPU once so a plan can be
applied repeatedly without re-deriving them.

Inspecting a plan:

```python
for step in plan.steps:
    print(step.d_pre, step.rows, step.cols, step.d_post, step.kind, step.bytes_moved)
```

`step.kind` is `axis_swap` when both boxes are single axes and `block_swap` when
either side bundles several. `step.kernel` reports `float4` when `d_post` is
divisible by 4 and the vectorised kernel is used, `scalar` otherwise.

## Layout

```
src/                 the box_transpose package (see note below)
  _plan.py          Dijkstra planner and cost model. Standard library only.
  _transpose.py     profile() / apply() — uploads cycles, drives the kernel.
  _kernels/
    _load.py        lazy JIT loader for the CUDA extension
    box_kernel.cu   the in-place cycle-following kernel (scalar + float4)
experiments/        scripts that run something and write raw_data/
raw_data/           what they wrote, as JSON lines
calibration/        cost-model constants: how they are fitted (see below)
  data_generation/  the measurement runners — no data ships, regenerate here
docs/               profiling notebook and the planner animation
paper/              LaTeX source, and the scripts that turn raw_data/ into its
                    numbers. `cd paper && make verify` (see paper/README.md)
```

The package lives directly in `src/` with no nested `box_transpose/` directory.
Python would normally take the import name from the directory name, so
`pyproject.toml` maps it explicitly with
`package-dir = { box_transpose = "src" }`. The import is `box_transpose`
regardless of what the folder is called — but if you move or rename `src/`,
update that mapping too or the package stops resolving.

## Calibration

`_plan.py` carries three constants near the top:

| constant | meaning |
|---|---|
| `MU` | mean observed throughput in GB/s, used to turn bytes into milliseconds |
| `TAU` | minimum `d_post` for a graph edge to be considered |
| `D_POST_STAR` | minimum `d_post` at which box following beats a cycle splitter |

`MU = 69.7` was measured on an RTX PRO 6000 Blackwell at N=1e9. **`TAU` and
`D_POST_STAR` are both currently set to `1`, which disables their pruning
entirely** — re-derive them before relying on either.

The `calibration/` scripts regenerate these:

```
data_generation/                     the runners that produce all measurement data
find_edge_costs/micro_benchmark.py   sweeps D_post on a GPU  -> micro_benchmark_results.jsonl
find_edge_costs/calibrate.py         fits MU and TAU from that sweep
find_edge_costs/evaluate.py          scores the model against pilot measurements
find_edge_costs/verify_across_ranks.py  same, per tensor rank
model.py                             wider runtime model over benchmark sweeps
```

**Measurement data is not vendored here** — it was hundreds of megabytes of
`.jsonl`. Scripts that need it read `$BT_PILOT_ROOT`, expecting
`rank-{n}/box/pilot_results.jsonl` beneath it; `model.py` reads `$BT_BENCH_ROOT`
expecting `four_rank/results.jsonl` and `five_rank/results.jsonl`. Without those
the scripts and `calibration/tests/` skip rather than fail.

`calibration/data_generation/` holds the runners that produce that data, and its
README maps each producer to its consumers and the environment variable that
connects them. `micro_benchmark.py` needs no external data at all — it measures
from scratch on whatever GPU it runs on, and is the right starting point on new
hardware.

## Documentation

`docs/box_transpose_profiling.ipynb` is the reproducible derivation of τ and μ,
with the throughput-versus-`d_post` plot that shows where the knee actually sits.
It reads the micro-benchmark sweep from `$BT_MICRO_RESULTS`, defaulting to
`calibration/find_edge_costs/micro_benchmark_results.jsonl` — run
`micro_benchmark.py` first to produce it.

`docs/dijkstra-animation.html` is a standalone page (open it in a browser, no
server needed) that steps through the planner one swap at a time on a
`(2,3,4) -> (2,1,0)` example: the pool, the cost of each candidate swap, and why
each one is pushed or skipped.

### The paper

`_plan.py` cites "Algorithm 3a", "Algorithm 3b" and "Section 3.1.2" by number.
Those are in the FAST'27 draft, which is **not** in this repository — and there
is no LaTeX source for it anywhere, only a Word draft. If you need the formal
statement of the algorithm or the reasoning behind τ and D_post\*, you need that
draft open alongside this code.

### The calibration docs describe a superseded model

`calibration/README.md` and `calibration/find_edge_costs/final_logic.md` are
worth reading, but they document an **earlier** cost model than the one shipped
here. They describe a cycle-enumeration budget β (~8M `d_mid`) and a three-tier
μ lookup table:

| tier | `d_post` | `d_mid` | μ |
|---|---|---|---|
| 0 | [0, 100) | [0, 10,000) | 35.8 GB/s |
| 1 | [0, 100) | [10,000, ∞) | 10.1 GB/s |
| 2 | [100, ∞) | any | 321.8 GB/s |

Neither β nor the tiers exist in `_plan.py`. It carries a single flat
`MU = 69.7` GB/s plus `TAU`/`D_POST_STAR` pruning instead. The change was made
deliberately, in a commit titled "Replace two-tier μ/β model with direct D_post
pruning in router" — the tiered model was judged overfitted, having been derived
from rank-4 and rank-5 cases only, as `final_logic.md` notes in its own
"Diverged / Surprises" section. That history lives in the repository this was
extracted from and is not reachable here.

Read those two documents as background on *how* the constants were fitted, not
as a description of the current code. The numbers in them also disagree with the
shipped `MU = 69.7`; if you re-run the calibration, decide which model you are
committing to rather than assuming they describe the same thing.

## A known gap between the cost model and the search

The documented cost of a swap is

```
d_pre x moved_cells x d_post x elem_bytes x 2
```

where `moved_cells` excludes fixed points — matrix cells that a transpose maps
to themselves. But during the Dijkstra search, `make_step` obtains its cycle
information from `estimated_cycle_info`, a placeholder that reports **zero**
fixed points, because enumerating the real cycles of every candidate edge would
mean walking millions of positions per edge.

With `moved_cells = rows * cols`, the cost of any step collapses to
`N x elem_bytes x 2` — identical for every edge in the graph. The search
therefore has uniform edge weights and minimises the *number of steps*, not the
bytes moved. Exact cycle counts are filled in afterwards by
`materialize_plan_steps`, so the `bytes_moved` a finished plan reports is
accurate even though it was not what the search optimised.

On large tensors the two agree closely: fixed points are typically just the two
corner cells out of millions. On small ones they diverge visibly — for
`(2,3,4) -> (2,1,0)` the planner returns a 336-byte plan where a 304-byte plan
exists. Both are two steps.