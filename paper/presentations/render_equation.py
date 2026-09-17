#!/usr/bin/env python3
"""Render Equation (1) of the proposal to a PNG for the slide deck.

The deck shows the same shape-space equation the paper does. Typesetting it
with the paper's own LaTeX rather than approximating it with unicode keeps the
two identical, and means a change to the equation is made in one place.

Writes equation-shapes.png beside this script.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE / "equation-shapes.png"
DPI = 400

# Kept in step with sections/3-simulation-setting.tex by hand. It is three
# lines of math; a generator that parsed the .tex to find them would be more
# machinery than the thing it protects.
BODY = r"""
\documentclass[preview,border=6pt]{standalone}
\usepackage{amsmath}
\usepackage{mathptmx}
\begin{document}
$\displaystyle
s = \left(\prod_{i=1}^m p_i^{b_{i1}},\ \prod_{i=1}^m p_i^{b_{i2}},\ \ldots,\
\prod_{i=1}^m p_i^{b_{ir}}\right)
$
\end{document}
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "eq.tex").write_text(BODY)
        p = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "eq.tex"],
            cwd=d, capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit("pdflatex failed:\n" + p.stdout[-2000:])
        subprocess.run(["pdftoppm", "-png", "-r", str(DPI), "-singlefile",
                        "eq.pdf", "eq"], cwd=d, check=True)
        img = Image.open(d / "eq.png").convert("RGBA")

    # Trim the page white, then make white transparent so the equation sits on
    # whatever the slide's background is.
    grey = img.convert("L")
    box = grey.point(lambda v: 0 if v > 250 else 255).getbbox()
    img = img.crop(box)
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, _ = px[x, y]
            px[x, y] = (r, g, b, 255 - min(r, g, b)) if min(r, g, b) > 200 \
                else (r, g, b, 255)
    img.save(OUT)
    print(f"wrote {OUT.name}  {img.width}x{img.height}px")


if __name__ == "__main__":
    main()
