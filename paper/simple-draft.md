# Box Transpose: Rearranging a Tensor Without Making a Copy

## 1. The problem

Deep learning code reshuffles the dimensions of tensors constantly. In PyTorch,
`permute` and `transpose` do this for free — they only change a label, not the
data. But the data is now in the wrong order in memory, and many operations
refuse to run on it or run slowly. The standard fix is `.contiguous()`.

`.contiguous()` works by making a second copy. It allocates a whole new tensor,
copies every element into its correct place, then throws the old one away. For a
moment, both exist.

That moment is the problem. Converting a 1 GB tensor needs 2 GB. On a machine
that is already nearly full, this is the thing that kills the job with an
out-of-memory error. It also chops the free memory into pieces, which can cause
a failure later even when there is technically enough space left.

So a layout problem becomes a memory problem.

## 2. What we built

Box transpose rearranges the tensor **in place**. There is no second copy. It
needs about 144 bytes of bookkeeping instead of another gigabyte.

It works on any shape and any permutation. In every case we tested — 87 sampled
shapes from rank 3 to rank 10, plus 15 randomly chosen hard permutations — it
produced a valid plan and got the right answer. Nothing was rejected.

## 3. How it works

### 3.1 Breaking the job into swaps

A *box* is a group of neighbouring dimensions treated as one. Because they sit
next to each other in memory, their sizes just multiply together and the group
behaves like a single dimension.

Any reordering of dimensions can be done as a series of **box swaps**: pick two
neighbouring boxes and exchange them. Repeat until the order is right.

The useful part is what one swap turns into. Split the dimension list into four
parts — a prefix, a left box, a right box, and a suffix — with sizes `D_pre`,
`rows`, `cols`, and `D_post`. Swapping the two middle boxes is exactly
transposing a `rows x cols` matrix. It is done once for each of the `D_pre`
leading positions, and each "element" of that matrix is a run of `D_post`
neighbouring values.

So every step is a plain matrix transpose, which is a well-understood problem.

### 3.2 Doing a swap without a spare buffer

To transpose a matrix in place you cannot simply move element A to slot B,
because something else is already sitting in slot B. Instead you pick a value
up, put it where it belongs, and find yourself holding whatever was there. You
keep going and eventually arrive back where you started. That loop is a *cycle*,
and walking it is called cycle following.

The only storage this needs is the one value in your hand. In our kernel that is
a single register per thread.

This is not new — cycle following for in-place transposition is decades old, and
Gustavson, Karlsson and Kagstrom (2012) give a way to find where each cycle
starts using number theory. What is new is what happens in N dimensions.

### 3.3 Why N dimensions helps

A two-dimensional method can only run as many cycles at once as there are
cycles. Catanzaro's paper says so directly: a shape with nine cycles gets
nine-way parallelism on a GPU with 188 processors.

We do not have that limit. Our swap is repeated `D_pre` times and each element
is `D_post` values wide, so we can run `D_pre x cycles x D_post` things at once.
Those two extra dimensions only exist in N-D. A 2-D method has nowhere to find
them.

### 3.4 The part that makes us faster than copying

Some cells of a matrix are already where they belong. Transposing a square
matrix never moves the diagonal.

**We skip those cells. A copy cannot.** `.contiguous()` is building a fresh
tensor, so it has to write every output position, including the ones that would
have been correct anyway.

The number of cells that stay put has a simple formula:

    fixed cells = gcd(rows - 1, cols - 1) + 1

So the fraction of the tensor we actually touch is

    moved = 1 - (gcd(rows - 1, cols - 1) + 1) / (rows x cols)

For a 2x2 block that is 1/2. We move half the data and take half the time.

This is worth stating plainly: **every other method must read and write the
whole tensor at least once. We can do half a pass.** No method that builds
output positions can do less than one full pass, because it has to write them
all. Only skipping can do a fraction.

### 3.5 Choosing which swaps to make

There are many ways to reach the same final order, and they cost different
amounts. We build a graph: each way of ordering the dimensions is a point, and
each legal box swap is a link between two points. The weight on a link is the
number of bytes that swap moves, which we know exactly from the formula above.
Dijkstra's algorithm then finds the cheapest route.

No links are removed from the graph and no thresholds are applied. The only
rejection happens at the end: if the cheapest route still needs more steps than
the caller allows, we return nothing and let the caller use `.contiguous()`.

### 3.6 No tuning constants

The cost model has **no numbers measured on a GPU in it**. Both we and
`.contiguous()` move data at the same speed in the cases where our method is
worth using, so the speed cancels out and only the amount of data matters. That
means `moved` is directly the predicted ratio of our runtime to
`.contiguous()`'s. Below 1, we should win.

We checked this: inside the region where the method applies, the prediction is
off by about 2%. Outside it, by 64% — which is exactly why we do not apply the
method there.

An earlier version of this work had three constants fitted on one particular
GPU. They are gone. The model now works on any GPU without remeasuring
anything.

## 4. When it works and when it does not

Two numbers, both computed from the shape before touching any data, decide
everything.

**`moved`** — the fraction of the tensor we touch, from the formula above. If it
is below 1 we do less work than a copy.

**`D_post`** — the size of the trailing group of dimensions that does not move.
Each value we move is a run of `D_post` neighbours. If that run is long, the
memory system is happy. If it is 1, we are moving four bytes at a time and the
hardware fetches 128 bytes to use 4 of them.

A useful fact: `moved` can never go below 0.5 for a single swap, so a plan with
two or more swaps always moves at least as much as a copy does. **Beating
`.contiguous()` and being a single swap are the same condition.**

## 5. Results

All measurements on an NVIDIA RTX 2070, tensors of 268,435,456 floats (1024 MB).

### 5.1 Against everything, all cases

87 shapes drawn from the shape space, ranks 3 to 10:

| method | median time | memory used |
|---|---|---|
| PyTorch `.contiguous()` | 7.70 ms | 1024 MB |
| **box transpose** | **10.21 ms** | **144 bytes** |
| ITTPD | 80.49 ms | 0 |
| Gomez-Luna | 82.91 ms | 16 bytes |
| Gustavson | 97.39 ms | 48 MB |

We are faster than ITTPD on 87 of 87, Gomez-Luna on 87 of 87, and Gustavson on
79 of 87.

### 5.2 Where we beat the copy too

When the two numbers say we should win, we did — on 21 of 21 cases, by 1.73x at
the median and 2.05x at best. The prediction was right every time.

| shape | `.contiguous()` | box | ratio |
|---|---|---|---|
| `[2, 2, 67108864]` | 7.96 ms | 3.98 ms | 0.50x |
| `[2, 2, 1048576, 8, 8]` | 7.74 ms | 3.86 ms | 0.50x |
| `[2, 2, 64, 32, 16384, 2]` | 8.29 ms | 4.04 ms | 0.49x |
| `[2, 2, 4, 256, 32, 512, 4]` | 7.87 ms | 3.84 ms | 0.49x |
| `[2, 2, 1024, 2, 2, 4, 8, 2, 256]` | 7.83 ms | 3.86 ms | 0.49x |

Rank 3 through rank 9, all at almost exactly half the time — which is what the
formula said would happen, because these all move half the data.

### 5.3 Where it falls apart

We also tried 15 randomly chosen permutations, which is the unfriendly case.

When a trailing block survived (`D_post` large), we were the fastest in-place
method on 4 out of 4.

When it did not (`D_post` = 1), we were the **slowest** in-place method on 11
out of 11 — 145 to 314 ms against a 7 to 14 ms copy.

## 6. Limitations

**No trailing block, no performance.** If the permutation moves the innermost
dimension, some step is forced to have `D_post` = 1. Each moved value is then a
lone number, memory access cannot be batched, and we run 20 to 40 times slower
than a copy. We still finish and we still allocate nothing, but we are the wrong
tool. On these permutations the existing in-place methods are 3 to 6 times
faster than ours. A production system would hand those cases to one of them. We
do not implement that.

**Rank 2 is always in this category.** A plain matrix transpose has no trailing
dimensions to leave alone.

**More than one swap means losing to the copy.** Two swaps always move at least
a full tensor's worth, so `.contiguous()` wins. We are still the best in-place
option there, but we are not faster than copying.

**Planning gets expensive at high rank.** Finding the cheapest route took 13
seconds at rank 8 for a hard permutation. Plans depend only on the shape and
permutation, so they are computed once and reused, but a very high rank would
need a smarter search.

**One GPU.** Everything here is an RTX 2070. The 2x result is arithmetic — we
move half the data — so it should hold anywhere, but the comparisons against
other methods need repeating on other hardware.

## 7. Related work

**Catanzaro, Keller and Garland (2014)** solve the two-dimensional case by
splitting a transpose into row and column shuffles. Their method needs a
temporary buffer and its parallelism is limited by the number of cycles.

**Gustavson, Karlsson and Kagstrom (2012)** work out where each cycle starts
using number theory instead of searching for it. Two-dimensional. We use the
same idea for the case where a block is square, where it becomes a single
comparison.

**Gomez-Luna et al. (2016)** pad dimensions to convenient sizes. Padding makes
the array bigger, which works against the goal of saving memory — in one of our
tests it asked for 13 times the size of the tensor.

**Cheng and Lee (2025), "ITTPD"** is the closest work. They break an N-D
permutation into the same kind of block swap we do — their `rho(i, j, k)` and
our box swap are the same operation. **We do not claim that decomposition as
new.** The differences are that their steps are built from Catanzaro's
two-dimensional method while ours follow cycles directly, and that they must
choose their decomposition to fit inside a memory budget while we do not. In
our measurements we were faster on 87 of 87 cases where a trailing block was
present, and slower on the cases where it was not.

## 8. Summary

Box transpose rearranges a tensor in place. It works for every shape and
permutation we tested, uses 144 bytes instead of a second tensor, and is faster
than every other in-place method we compared against when the permutation
leaves a trailing block of dimensions alone. When the block is large and the
swap is small and square, it is also up to twice as fast as PyTorch's own copy,
because it skips the data that is already in the right place — something a copy
cannot do.

When there is no trailing block, it is slow, and we can tell before running.
