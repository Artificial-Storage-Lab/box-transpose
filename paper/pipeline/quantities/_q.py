#!/usr/bin/env python3
"""Shared imports for the quantities generators.

A *quantity* is a number the paper's prose states in a sentence -- "we sample
100 shapes", "B is 2.9x faster than A" -- as opposed to a number a table
prints in a cell or a figure draws as a mark. Those belong to
pipeline/tables/ and pipeline/figures/, which each write their own
`<name>.defs.tex` for whatever their caption quotes.

This directory covers what is left: the claims made in running text. They are
the only numbers audit.py polices, because they are the only ones that live in
hand-written prose where a digit could simply be typed.

The plumbing itself is in pipeline/_common.py, shared with the other two
producers so that a quantity and the cell beside it can only ever be computed
and formatted the same way.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import (  # noqa: E402,F401
    EXPERIMENTS, PAPER, RAW, ROOT, SECTIONS, SRC,
    banner, constant, emit, emit_defs, generated, median, number, rows, sci,
    tex_int, word,
)
