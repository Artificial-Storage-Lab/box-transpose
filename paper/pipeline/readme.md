# pipeline

Turns data into LaTeX, so no number in the paper is typed by hand.

## Three scripts, because numbers show up in three places

A number can appear in a sentence, in a table cell, or as a dot on a chart.
Each gets its own kind of script. They are equals — data does not pass
through one on its way to another.

| folder | handles | writes |
| --- | --- | --- |
| `quantities/` | numbers in a **sentence** ("2.5x fewer swaps") | `<name>.defs.tex` |
| `tables/` | the **cells** of a table | `<name>.tex` + `<name>.defs.tex` |
| `figures/` | the **dots and lines** of a chart, as TikZ | `<name>-fig.tex` + `<name>.defs.tex` |

Every one of them also writes a `.defs.tex` of macros. That is because
captions have numbers in them too, and a caption should be computed from the
same rows as the table under it.

Output goes to `sections/<section>/_generated/`. Never edit those files.

## What stays human

The scripts write numbers. You write words.

The float, the `\caption`, the `\label` and the prose around them are all
hand-written in `sections/`, and they use the macros instead of digits.

## Why figures are TikZ and not images

The chart is drawn by the paper's own build. So its labels come out in the
paper's fonts at the paper's sizes, and it stays sharp at any zoom. Exported
PNGs drift out of date and never quite match the text around them.

## Two sources, not one

Most generators read `raw_data/`. `quantities/gen_constants_defs.py` reads
`src/_plan.py` instead, lifting `MU`, `TAU` and `D_POST_STAR` straight out of
the implementation with `constant()` / `number()`. The rule is the same either
way: the paper states nothing that nothing recomputes, and a constant that is
retuned — or renamed — moves the sentence or fails the build rather than
leaving the paper describing code that no longer exists.

## Commands

```bash
make defs      # re-run all three
make audit     # fail if a number was typed into the prose
make verify    # defs + audit + build
```

`verify.py` regenerates into a temp folder and compares. So if a committed
file no longer matches its data, you get told — it is not silently fixed.

## What is wired up today

```
experiments/plan_sweep/run.py  ->  raw_data/plan_sweep/results.jsonl
                                     ->  quantities/  the "2.5x fewer swaps" claim
                                     ->  tables/      the per-rank breakdown
                                     ->  figures/     the same medians, as a chart
src/_plan.py                   ->  quantities/  mu, tau, D_post*
```

Section~3 is the worked case. Everything under `sections/` that is still a
`\placeholder` has no generator yet, which is fine — `audit.py` only demands
that the numbers which *are* in the prose answer to something.

## Adding one

Copy the nearest existing generator, point it at your data, write to
`generated("<section>")`, and add an `\input` line to `box-transpose.tex`.
