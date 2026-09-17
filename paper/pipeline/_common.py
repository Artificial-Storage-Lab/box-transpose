#!/usr/bin/env python3
"""Plumbing shared by all three producers of generated LaTeX.

There are three, and they divide the paper's numbers between them:

  quantities/  numbers the prose states in a *sentence* -- "the search
               cuts the median rank-6 permutation from seven swaps to two",
               "mu is 69.7 GB/s". Only these are policed by audit.py, because
               only these live in hand-written prose.
  tables/      the *cells* of a table. A renderer writes the tabular body and,
               beside it, the macros its caption and the surrounding prose
               quote off the same rows.
  figures/     the *marks* of a figure, emitted as TikZ so a plot is typeset
               in the paper's own fonts rather than pasted in as an image.
               Like tables, a figure also writes the macros its caption cites.

All three write into `sections/<section>/_generated/`, all three stamp a
banner saying which script wrote the file, and none of them ever writes prose:
captions and the sentences around a float are hand-written in `sections/` and
cite the macros, so the pipeline owns the numbers without owning the wording.

Generated files are committed, so the paper builds without re-running
anything; pipeline/verify.py regenerates into a scratch tree and diffs, which
is what catches a committed file that has gone stale against its data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent          # paper/pipeline
PAPER = HERE.parent                             # paper
ROOT = PAPER.parent                             # repo root
RAW = ROOT / "raw_data"
EXPERIMENTS = ROOT / "experiments"
SRC = ROOT / "src"
SECTIONS = PAPER / "sections"


def generated(section: str) -> Path:
    """paper/sections/<section>/_generated, creating it if needed.

    One `_generated/` per section, beside the prose that cites it. Nothing
    under it is hand-edited.
    """
    d = SECTIONS / section / "_generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def rows(name: str) -> list[dict]:
    """Every line of a raw_data jsonl that ran to completion.

    `name` is a path under raw_data/ with or without the extension, e.g.
    "plan_sweep/results". Rows carrying a `status` field are kept only when it is
    "ok", so a crashed or skipped case cannot silently count toward an
    aggregate.
    """
    path = RAW / (name if name.endswith(".jsonl") else f"{name}.jsonl")
    out = []
    for line in path.open():
        if line.strip():
            r = json.loads(line)
            if r.get("status", "ok") == "ok":
                out.append(r)
    assert out, f"{path.relative_to(ROOT)} produced no usable rows"
    return out


def constant(path: Path, name: str) -> int:
    """Read `name = <int>` out of a Python, C++ or CUDA source file.

    For a design constant the paper states in words -- a window size, a
    threshold -- so that a retuned constant breaks this generator instead of
    leaving the sentence quietly describing code that no longer exists.
    """
    text = path.read_text()
    m = re.search(rf"^\s*(?:constexpr\s+int\s+)?{re.escape(name)}\s*=\s*(-?\d+)",
                  text, re.M)
    assert m, f"{name} is no longer defined in {path.relative_to(ROOT)}"
    return int(m.group(1))


def number(path: Path, name: str) -> float:
    """Read `name = <number>` out of a source file, integer or float.

    The integer-only `constant` above is the common case; this exists because
    the cost model's throughput constant is written `MU = 69.7` in
    src/_plan.py. A calibration that retunes it moves the paper's sentence
    about it, and a calibration that *renames* it breaks this generator rather
    than leaving the sentence describing a constant that no longer exists.
    """
    text = path.read_text()
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*(-?\d+(?:\.\d+)?)", text, re.M)
    assert m, f"{name} is no longer defined in {path.relative_to(ROOT)}"
    return float(m.group(1))


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    assert n, "median of nothing"
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def tex_int(n: int) -> str:
    """An integer with LaTeX's thin thousands separator."""
    return f"{n:,}".replace(",", "{,}")


def sci(n: float) -> str:
    """A round value as prose sets it: 10^{8}, 7\\times 10^{9}."""
    mant, exp = f"{n:e}".split("e")
    m, e = float(mant), int(exp)
    assert m == int(m), f"{n} is not a round mantissa"
    return f"10^{{{e}}}" if int(m) == 1 else f"{int(m)}\\times 10^{{{e}}}"


WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
         7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def word(n: int) -> str:
    """A small count spelled out the way prose spells numbers, not digits."""
    assert n in WORDS, f"{n} is past where prose spells numbers out"
    return WORDS[n]


def banner(src: str, note: str) -> list[str]:
    """`src` is a path under pipeline/, e.g. "tables/gen_table_example.py"."""
    return [f"% GENERATED by pipeline/{src} -- do not edit by hand.",
            f"% {note}"]


def emit(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n")
    print(f"wrote {path.relative_to(PAPER)}")


def emit_defs(path: Path, src: str, note: str, macros: dict[str, str]) -> None:
    """Measured values a caption or a paragraph needs, as \\newcommand macros.

    Prose cites \\exampleSpeedup rather than typing 2.9, so re-running the
    pipeline updates the sentence and a dropped measurement breaks the build
    instead of leaving a stale number sitting there looking correct.

    Macro names must be letters only -- a TeX control sequence cannot contain
    a digit -- which is why counts get spelled-out names like \\exampleSizeLo.
    """
    for k in macros:
        assert k.isalpha(), f"\\{k}: a control sequence cannot contain a digit"
    emit(path, banner(src, note)
         + [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()])
