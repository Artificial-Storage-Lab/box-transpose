#!/usr/bin/env python3
r"""Every numeral the paper's prose prints, and what recomputes it.

The rule this enforces: no data point and no aggregate in the paper without a
tie to the raw data. A macro satisfies it -- \exampleTrials is written by a
script that counts rows, so the sentence moves when the rows do. A digit typed
into a sentence does not, however right it was the day it was typed.

This walks the hand-written section files under paper/sections/, finds every
literal number left in them, and fails on any that is not either

  * structural -- a cross-reference, a font size, a length, an equation's own
    coefficient -- which this recognises and skips; or
  * listed in allowed.txt, with a reason, because a human decided that
    particular literal answers to nothing and said why.

Generated files under any _generated/ are not scanned: they ARE the tie.

    python audit.py            # report, exit 1 on anything undeclared
    python audit.py --list     # print every literal with its context

Adding a number to the paper therefore costs either a generator or a line in
allowed.txt. That is the point: both are deliberate, and neither is typing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _q import SECTIONS

ALLOWED = Path(__file__).resolve().parent / "allowed.txt"

# Arguments that are names, not quantities: a label, a citation key, a path.
OPAQUE = re.compile(
    r"\\(?:label|ref|eqref|cite|citep|citet|input|include|includegraphics|"
    r"bibliography|bibliographystyle|externaldocument|newcommand|renewcommand|"
    r"usepackage|documentclass|hypersetup|pagestyle|color|definecolor)"
    r"\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}")
# A TeX length or font size: 4pt, 0.3pt, 1.5ex, \fontsize{7}{8.2}, 10^{-3}em.
DIMEN = re.compile(r"-?\d+(?:\.\d+)?\s*(?:pt|em|ex|mm|cm|in|bp|sp|dd|pc|\\baselineskip)\b")
FONTSIZE = re.compile(r"\\fontsize\s*\{[^{}]*\}\s*\{[^{}]*\}")
# \vspace{2pt}, \setlength{\abovedisplayskip}{4pt}, \scalebox{0.77}
SPACING = re.compile(
    r"\\(?:v|h)space\*?\s*\{[^{}]*\}|\\setlength\s*\{[^{}]*\}\s*\{[^{}]*\}|"
    r"\\(?:scalebox|resizebox|arraystretch|tabcolsep|extracolsep|addlinespace|"
    r"cmidrule|rule|multicolumn|multirow|fcolorbox|colorbox)\s*(?:\[[^\]]*\])?"
    r"(?:\s*\{[^{}]*\})*")
# A fraction of the measure in a column spec: p{0.34\linewidth}, {0.48\textwidth}
RELATIVE = re.compile(r"\d*\.?\d+\s*\\(?:line|text|column|page)width")
# Product and model names that happen to carry a digit. A name is not a
# quantity: nothing recomputes it, and a generator that tried would be
# inventing a tie rather than recording one. List yours here as you add them,
# so that adding one is as deliberate as adding an allowed.txt line -- e.g.
# NAMES = ["GPT-4", "Llama 3", "A100"].
NAMES: list[str] = ["RTX PRO 6000 Blackwell"]
COMMENT = re.compile(r"(?<!\\)%.*$")
# A list marker in running prose: "(1) the number of passes, (2) control over".
ENUM = re.compile(r"\((?:1?\d)\)")
# A rank or a dimensionality used as a name: rank-2, rank 3, 2-D, N-D, r-1.
RANKWORD = re.compile(r"\brank[-~ ]\d\b|\b\d-D\b|\brank-\{?\d", re.I)
# Math that indexes rather than measures: subscripts, superscripts, \prod
# limits, \frac arguments. A 1 in b_{i1} is a column of a matrix, not a
# quantity anyone can recompute, and neither is the 1 in i=1 or r-1.
MATHIDX = re.compile(r"[_^]\s*\{[^{}]*\}|[_^]\s*\\?\w+|[a-zA-Z}]\s*[-+]\s*\d+")
# The HEAD of a macro definition: the name being defined, and its arity if it
# takes arguments. Only the head -- the value is deliberately left standing,
# so a quantity typed into a \newcommand is seen and has to answer for itself
# like any other literal.
CLASSPARAM = re.compile(r"\\(?:re|provide)?newcommand\s*\{[^{}]*\}(?:\s*\[[^\]]*\])*")
# What counts as a number worth asking about. The lookbehind also excludes "#",
# so the #1 of a macro's body is the argument it stands for rather than a one.
NUMBER = re.compile(r"(?<![\\A-Za-z0-9._#])\d[\d,]*(?:\.\d+)?")


def strip(line: str) -> str:
    """Blank out everything that is markup or a name rather than a quantity."""
    line = COMMENT.sub("", line)
    for name in NAMES:
        line = line.replace(name, " " * len(name))
    for pat in (FONTSIZE, CLASSPARAM, SPACING, OPAQUE, RELATIVE, DIMEN,
                MATHIDX, RANKWORD, ENUM):
        line = pat.sub(lambda m: " " * len(m.group(0)), line)
    return line


def key(path: Path, number: str) -> str:
    return f"{path.relative_to(SECTIONS)}:{number}"


def read_allowed() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ALLOWED.exists():
        return out
    for raw in ALLOWED.read_text().splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        assert "  " in raw or "#" in raw, f"allowed.txt entry has no reason: {raw}"
        why = raw.split("#", 1)[1].strip() if "#" in raw else ""
        assert why, f"allowed.txt entry has no reason: {raw}"
        out[line] = why
    return out


def scan():
    """Every (file, line number, literal, source line) left in the prose."""
    found = []
    for path in sorted(SECTIONS.rglob("*.tex")):
        if "_generated" in path.parts:
            continue
        for n, raw in enumerate(path.read_text().splitlines(), 1):
            text = strip(raw)
            for m in NUMBER.finditer(text):
                found.append((path, n, m.group(0), raw.strip()))
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print every literal found, declared or not")
    args = ap.parse_args()

    allowed = read_allowed()
    found = scan()
    undeclared = [f for f in found if key(f[0], f[2]) not in allowed]

    if args.list:
        for path, n, num, raw in found:
            k = key(path, num)
            tag = "declared" if k in allowed else "UNDECLARED"
            print(f"[{tag:>10}] {path.relative_to(SECTIONS)}:{n}  {num!r}")
            print(f"             {raw[:110]}")
        print()

    files = len({f[0] for f in found})
    # A declaration that no longer matches anything rots as quietly as a stale
    # number: it is a note about a sentence that has since changed. Reported
    # whether or not anything else failed, and fatal either way.
    live = {key(p, num) for p, _, num, _ in found}
    stale = sorted(set(allowed) - live)

    if not undeclared and not stale:
        print(f"audit: {len(found)} literal(s) across {files} prose file(s), "
              f"all {len(allowed)} declared in allowed.txt; "
              "every other number in the paper is a macro")
        return

    print(f"audit: {len(undeclared)} undeclared literal(s), "
          f"{len(stale)} stale declaration(s).\n"
          "An undeclared literal is either a quantity that needs a generator "
          "under pipeline/quantities, or a line in allowed.txt saying why it "
          "answers to nothing.\n")
    for path, n, num, raw in undeclared:
        print(f"  {path.relative_to(SECTIONS)}:{n}  {num}")
        print(f"      {raw[:110]}")
    for k in stale:
        print(f"  stale allowed.txt entry, no longer in the prose: {k}")
    sys.exit(1)


if __name__ == "__main__":
    main()
