#!/usr/bin/env python3
"""The five-method comparison: runtime, auxiliary memory, and head-to-head.

One row per method over every case of the dpost sweep, plus the count of cases
box transpose is faster on. The memory column is what separates the claim from
a pure speed result, so it is carried at the same precision the prose uses:
bytes where a method needs bytes, megabytes where it needs megabytes.

`.contiguous()` is listed first because it is the thing being replaced, not a
competitor -- it is out of place by construction, and its memory column is the
whole reason this work exists.
"""
from __future__ import annotations

from _table import (emit_defs, emit_table, fmt_ms, generated, median, notes,
                    rows, tex_int)

SRC = "tables/gen_table_methods.py"
NOTE = "Regenerate after any change to raw_data/dpost_sweep/."

METHODS = [
    ("PyTorch \\texttt{.contiguous()}", "contiguous_ms", "contiguous_aux_bytes", False),
    ("Box transpose (ours)",            "box_ms",        "box_aux_bytes",        None),
    ("ITTPD~\\cite{cheng2025ittpd}",    "ittpd_ms",      "ittpd_aux_planned",    True),
    ("Gomez-Luna~\\cite{gomezluna2016inplace}", "gl_apply_ms", "gl_aux_bytes",   True),
    ("Gustavson~\\cite{gustavson2012cycleleader}", "gv_apply_ms", "gv_aux_bytes", True),
]


def fmt_bytes(b: float) -> str:
    """Bytes, kilobytes or megabytes -- whichever keeps the cell honest."""
    if b == 0:
        return "0"
    if b < 1024:
        return f"{b:,.0f}\\,B"
    if b < 1024 ** 2:
        return f"{b / 1024:,.1f}\\,KB"
    return f"{b / 1024 ** 2:,.0f}\\,MB"


def main() -> None:
    r = [x for x in rows("dpost_sweep/results_nvidia_geforce_rtx_2070")
         if x.get("box_correct")]

    body_rows = []
    for label, ms_key, aux_key, compare in METHODS:
        times = [x[ms_key] for x in r if x.get(ms_key) is not None]
        auxes = [x[aux_key] for x in r if x.get(aux_key) is not None]
        if compare is None:
            head = "--"
        else:
            both = [x for x in r if x.get(ms_key) is not None]
            head = f"{sum(1 for x in both if x['box_ms'] < x[ms_key])}/{len(both)}"
        emph = "\\textbf{%s}" if compare is None else "%s"
        body_rows.append(" & ".join([
            label,
            emph % fmt_ms(median(times)),
            emph % fmt_bytes(median(auxes)),
            emph % fmt_bytes(max(auxes)),
            head,
        ]) + " \\\\")

    body = [
        # A plain tabular, not tabular*: this sits in a table* float, and
        # stretching five short columns across the full two-column measure
        # leaves an inch of white between every pair of them. Sized to its
        # content and centred by the float, it reads as one block.
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "Method & Median & Median aux & Peak aux & Box wins \\\\",
        "\\midrule",
        *body_rows,
        "\\bottomrule",
        "\\end{tabular}",
        *notes([
            "Middle-of-the-range values over every case, with no routing: we "
            "run our method on all of them, including the ones our own rule "
            "would turn away.",
            "\\textbf{Box wins} counts cases where box transpose is faster "
            "than that method. Against \\texttt{.contiguous()} that count is "
            "low here precisely because no routing is applied; "
            "Section~\\ref{sec:gate} reports it under the gate.",
            "ITTPD's memory figure comes from its own planner, not from "
            "watching the allocator. On these shapes every block fits in fast "
            "on-chip memory, so it never asks for anything global.",
        ]),
    ]
    emit_table(generated("evaluation") / "methods-table.tex", SRC, NOTE, body)

    box = median([x["box_ms"] for x in r])
    emit_defs(generated("evaluation") / "methods-table.defs.tex", SRC, NOTE, {
        "methTabCases": tex_int(len(r)),
        "methTabIttpdX": f"{median([x['ittpd_ms'] for x in r if x.get('ittpd_ms')]) / box:.1f}",
        "methTabGvX": f"{median([x['gv_apply_ms'] for x in r if x.get('gv_apply_ms')]) / box:.1f}",
        "methTabGlX": f"{median([x['gl_apply_ms'] for x in r if x.get('gl_apply_ms')]) / box:.1f}",
    })


if __name__ == "__main__":
    main()
