# raw_data

What the experiments produced. One folder per experiment, one JSON object per
line.

```
raw_data/<experiment>/results.jsonl
```

Nothing here is edited by hand. Scripts in `experiments/` write it; scripts in
`paper/pipeline/` read it.

Give each row a `status` field. The `rows()` helper in
`paper/pipeline/_common.py` drops anything that isn't `"ok"`, so a case the
planner could not solve, or a run that crashed, can't sneak into an average.

## What is committed

`*.jsonl` is gitignored by default, with `raw_data/plan_sweep/` as the
exception. That sweep is planner output: no GPU, no timing, no randomness
beyond a fixed seed, so it is small and reproduces byte for byte from a fresh
clone. Committing it is what lets `cd paper && make verify` work on a machine
with no CUDA.

Measured throughput data is the opposite. It runs to hundreds of megabytes
and is specific to the GPU that produced it. It is not vendored. `calibration/` reads it from
`$BT_PILOT_ROOT` and `$BT_BENCH_ROOT` instead, and its scripts skip rather
than fail when those are unset. See `calibration/data_generation/README.md`.

If you add an experiment whose output is bulk measurement data, keep it
outside the repo the same way and add a summariser that writes only the rows
the paper quotes into `raw_data/`. The paper has to build from a fresh clone.
