#!/usr/bin/env python3
"""Table body for tab:timeline: the project schedule, week by week.

Writes two files, the pattern every table renderer follows:

  timeline-table.tex       the tabular body and nothing else
  timeline-table.defs.tex  the numbers the caption and the prose quote

Unlike the other renderers this one reads no raw_data. The schedule is
authorial -- nobody measures it -- so the plan itself lives in SCHEDULE
below and this script's job is to render it and count it.

That is still worth generating rather than typing into the section, for two
reasons. Week numbers are numbers, and a hand-written timeline table would put
a dozen literals into the prose that audit.py would then have to be told to
ignore one by one. And the sentence introducing the table wants to say how
many weeks it covers, which is a fact about the schedule that should move when
the schedule does.

Edit SCHEDULE to change the plan. Nothing else here needs touching.
"""
from __future__ import annotations

from _table import emit_defs, emit_table, generated, notes, tex_int, word

SRC = "tables/gen_table_timeline.py"
NOTE = "Edit SCHEDULE in pipeline/tables/gen_table_timeline.py to change the plan."

# Initials as the title page prints them. Every owner below is checked against
# this list, so a name changed in only one of the two places fails `make defs`
# instead of quietly disagreeing with sections/0-title.tex.
MEMBERS = {"KJ": "Kaveen Jayamanna", "AN": "Alexis Newman"}
BOTH = "KJ, AN"

# (week, milestone, owner). Ownership follows the split on the title page:
# KJ owns the planner and cost model, AN owns measurement and validation, and
# the shared milestones are the ones that are genuinely joint work.
SCHEDULE: list[tuple[int, str, str]] = [
    (1, "Proposal submitted. Planner sweep committed and reproducible.", BOTH),
    (2, "Re-derive $\\tau$ from a $D_{post}$ micro-benchmark on the "
        "evaluation GPU; restore graph pruning.", "AN"),
    (3, "Re-fit $\\mu$ against the $\\tau$-pruned graph. Report the cost "
        "model's error against measured throughput.", "KJ"),
    (4, "Close the fixed-point gap: make search edge weights reflect real "
        "cycle structure, and quantify how much the chosen plans change.", "KJ"),
    (5, "Correctness suite across ranks and shapes, gating every "
        "measurement that follows.", "AN"),
    (6, "End-to-end benchmark against the out-of-place baseline: latency "
        "and peak memory.", "AN"),
    (7, "Head-to-head against the closest prior systems on their reported "
        "shapes.", BOTH),
    (8, "Derive $D_{post}^{*}$ from the comparison and enable routing.", "KJ"),
    (9, "Draft the report: every number generated from committed data.", BOTH),
    (10, "Final report and presentation.", BOTH),
]


def _and(items: list[str]) -> str:
    """Join clauses as prose does, without a colon or a semicolon list."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def main() -> None:
    weeks = [w for w, _, _ in SCHEDULE]
    assert weeks == sorted(set(weeks)), "SCHEDULE has a duplicate or out-of-order week"

    owners = {i for _, _, o in SCHEDULE for i in o.replace(",", " ").split()}
    unknown = owners - set(MEMBERS)
    assert not unknown, \
        f"milestone owner(s) {sorted(unknown)} are not on the title page: {sorted(MEMBERS)}"
    idle = set(MEMBERS) - owners
    assert not idle, f"{sorted(idle)} own no milestone; the guidelines ask for a split"

    body = [
        "\\small",
        # The milestone column is a p{} because its cells are sentences: an
        # `l` column sets them on one line and runs them off the measure,
        # which tabular* does silently. The width is against \linewidth, so
        # this tracks whether the float is one column or two.
        "\\begin{tabular}{@{}c p{0.80\\linewidth} l@{}}",
        "\\toprule",
        "\\textbf{Week} & \\textbf{Milestone} & \\textbf{Owner} \\\\",
        "\\midrule",
        *[f"{w} & {m} & {o} \\\\\n\\addlinespace[1pt]" for w, m, o in SCHEDULE],
        "\\bottomrule",
        "\\end{tabular}",
        *notes(["Weeks are numbered from the week the proposal is submitted.",
                "Owner initials are the team members named on the title page. "
                + _and([f"{k} is {v}" for k, v in sorted(MEMBERS.items())])
                + "."]),
    ]
    emit_table(generated("4-milestones") / "timeline-table.tex", SRC, NOTE, body)

    emit_defs(generated("4-milestones") / "timeline-table.defs.tex", SRC, NOTE, {
        "timelineWeeks": word(len(SCHEDULE)),
        "timelineWeeksNum": tex_int(len(SCHEDULE)),
        "timelineMembers": word(len(MEMBERS)),
    })


if __name__ == "__main__":
    main()
