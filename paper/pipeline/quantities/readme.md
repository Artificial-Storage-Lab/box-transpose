# quantities

Numbers the paper says in a **sentence**. "The search issues 2.5x fewer
swaps." "mu is 69.7 GB/s."

Table cells belong to `../tables/`, chart marks to `../figures/`. See
[`../readme.md`](../readme.md).

## Why this folder exists

A table is generated, so its cells are safe. A sentence is typed, so it is
not. Someone writes "2.4x faster", the data changes, and the sentence stays
wrong forever because nothing is checking it.

So every number in a sentence becomes a macro, written by a script here.

## The audit

```bash
python3 audit.py          # fails on any typed-in number
python3 audit.py --list   # show every number it found
```

It reads the hand-written files under `sections/` and skips `_generated/`
(those are the generated ones). Any leftover digit must be either:

- computed by a script here, or
- listed in `allowed.txt` with a reason.

A stale `allowed.txt` line also fails, so an excuse can't outlive the sentence
it was written for.

## Adding one

Copy `gen_plan_defs.py` (reads `raw_data/`) or `gen_constants_defs.py`
(reads `src/_plan.py`). Point it at your data, write to
`generated("<section>")`, and add an `\input` line to `box-transpose.tex`.

Macro names must be letters only — `\planRankHi`, not `\planRank6`. TeX
cannot put a digit in a command name.

## What goes in allowed.txt

Numbers that nothing could compute. A year in a citation. A worked example
drawn by hand. A definition like "1x memory" that names a target rather than
reporting a result.

Never put a measurement there.
