#!/usr/bin/env python3
"""Does the paper match the evidence. Measures nothing itself.

Three checks, each named by what it catches:

  A  regenerate  -- every gen_*_defs.py, run into a scratch copy of
                    sections/, diffed against what's committed. Catches a
                    _generated/ file that's gone stale against raw_data/ or
                    src/ since it was last committed.
  B  audit       -- pipeline/quantities/audit.py: no literal number in the
                    hand-written prose without a tie to a generator or a
                    documented exception.
  C  build       -- pdflatex actually produces a PDF from the current tree.

    python verify.py

Exits 1 if anything fails. This is deliberately small -- add checks here as
the paper grows real experiments to cross-check (a platform capture, a
notebook's recorded output, a link check), following the same A/B/C-letter
convention so a failure is easy to name in conversation.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent      # paper/pipeline
PAPER = HERE.parent                         # paper
ROOT = PAPER.parent                         # repo root
SECTIONS = PAPER / "sections"

OK, FAIL = "  ok  ", " FAIL "
results: list[bool] = []


def report(name: str, passed: bool, detail: str = "") -> None:
    print(f"[{OK if passed else FAIL}] {name}" + (f"  --  {detail}" if detail else ""))
    results.append(passed)


def check_regenerate() -> None:
    """Copy raw_data/, src/ and paper/ into a scratch tree, re-run every
    generator there, and diff its sections/ against the committed one.

    _q.py resolves raw_data/src/sections relative to its own file, so
    preserving the repo's relative layout in the copy is what makes the
    generators land in the scratch sections/ instead of the real one -- the
    real _generated/ files are never touched, so a stale commit is reported,
    not silently fixed.
    """
    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td)
        for name in ("raw_data", "src", "paper"):
            src = ROOT / name
            if src.is_dir():
                shutil.copytree(src, scratch / name)
        pipeline = scratch / "paper" / "pipeline"
        gens = (sorted((pipeline / "quantities").glob("gen_*.py"))
                + sorted((pipeline / "tables").glob("gen_*.py"))
                + sorted((pipeline / "figures").glob("plot_*.py")))
        ok = True
        for g in gens:
            p = subprocess.run([sys.executable, g.name], cwd=g.parent,
                                capture_output=True, text=True)
            if p.returncode != 0:
                ok = False
                report(f"A  {g.name} runs", False, p.stderr.strip().splitlines()[-1])
        diffs = _diffs(SECTIONS, scratch / "paper" / "sections")
        report("A  _generated/ matches what raw_data/ and src/ produce now",
               ok and not diffs, "; ".join(diffs) if diffs else "")


def _diffs(committed: Path, regenerated: Path) -> list[str]:
    """Every file under _generated/ that differs between the two trees."""
    out = []
    for path in sorted(committed.glob("*/_generated/*")):
        other = regenerated / path.relative_to(committed)
        if not other.exists() or path.read_text() != other.read_text():
            out.append(str(path.relative_to(committed)))
    return out


def check_audit() -> None:
    p = subprocess.run([sys.executable, "audit.py"], cwd=HERE / "quantities",
                        capture_output=True, text=True)
    tail = [l for l in p.stdout.splitlines() if l.strip()][-1:]
    report("B  audit: every prose number ties to raw data", p.returncode == 0,
           tail[0].strip() if tail else p.stderr.strip())


def check_build() -> None:
    p = subprocess.run(["make", "all"], cwd=PAPER, capture_output=True, text=True)
    report("C  paper builds", p.returncode == 0,
           "no pdflatex/make in this environment" if p.returncode == 127 else "")


def main() -> None:
    check_regenerate()
    check_audit()
    check_build()
    print()
    if all(results):
        print(f"verify: {len(results)}/{len(results)} checks passed")
    else:
        print(f"verify: {sum(results)}/{len(results)} checks passed")
        sys.exit(1)


if __name__ == "__main__":
    main()
