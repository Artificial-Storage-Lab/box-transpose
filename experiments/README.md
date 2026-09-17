# experiments

One folder per experiment. Each script runs something and writes its results to
`raw_data/<same-name>/`.

Nothing here writes into `paper/`. That is the job of `paper/pipeline/`, which
reads `raw_data/` and turns it into the paper's numbers. Keeping the two
separate means you can re-run an experiment without touching the paper, and
rebuild the paper without re-running anything.

```
plan_sweep/    the planner, over every permutation of a fixed-size tensor at
               each rank, both search strategies. CPU only -- no GPU, no torch.
```

## What belongs here and what belongs in calibration/

`calibration/` predates this layout and stays where it is. Its
`data_generation/` runners measure GPU throughput and emit hundreds of
megabytes of `.jsonl`, which is why they read and write paths given by
`$BT_PILOT_ROOT` and `$BT_BENCH_ROOT` rather than committing anything. See
`calibration/data_generation/README.md`.

The rule for deciding where a new script goes:

- produces a small, deterministic, committable result the **paper** quotes
  -> `experiments/`, writing to `raw_data/`
- produces bulk measurement data used to **fit the cost model**
  -> `calibration/data_generation/`, writing outside the repo

If a calibration run ever needs to appear in the paper, add a summariser here
that reads `$BT_*_ROOT` and writes the handful of rows the paper actually
needs into `raw_data/`. Do not point `paper/pipeline/` at the bulk data
directly -- the paper must build from a fresh clone.
