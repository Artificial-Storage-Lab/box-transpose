#!/usr/bin/env python3
"""Build the proposal presentation, proposal.pptx, for upload to Google Slides.

The deck covers the six components the proposal guidelines grade and nothing
else. It is deliberately spare: everything on it is already in
box-transpose.pdf, and a slide that says something the paper does not is a
slide that can go stale on its own.

No number here is typed. The deck reads the same `_generated/*.defs.tex`
macros the paper's prose cites, and the same raw_data rows the paper's table
is built from, through the same helpers in pipeline/. Re-run the experiment
and `make deck` and the slides move with the paper.

    python3 build_deck.py        # writes proposal.pptx
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent          # paper/presentations
PAPER = HERE.parent                             # paper
SECTIONS = PAPER / "sections"
OUT = HERE / "proposal.pptx"

sys.path.insert(0, str(PAPER / "pipeline"))
sys.path.insert(0, str(PAPER / "pipeline" / "tables"))
from _common import median, rows                                # noqa: E402
import gen_table_timeline as timeline                           # noqa: E402

# ── palette ──────────────────────────────────────────────────────────────────
# The paper's own figure colours, so a slide and the chart it summarises are
# the same two colours. Orange is the baseline and the problem; blue is the
# method we are proposing.
INK = RGBColor(0x1C, 0x1B, 0x18)
PAPER_W = RGBColor(0xFF, 0xFF, 0xFF)
MID = RGBColor(0x6B, 0x6A, 0x65)
RULE = RGBColor(0xDD, 0xDB, 0xD6)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
ONDARK = RGBColor(0xF2, 0xF1, 0xEE)

HEAD = "Cambria"
BODY = "Calibri"

W, H = 13.333, 7.5
M = 0.7                                          # page margin
TOP = 1.72                                       # first line under the header


def defs() -> dict[str, str]:
    """Every \\newcommand the pipeline generated, as plain text.

    Values carry LaTeX's thin thousands separator and the odd control
    sequence; both are turned back into something a slide can show.
    """
    out: dict[str, str] = {}
    for f in sorted(SECTIONS.glob("*/_generated/*.defs.tex")):
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*)\}", f.read_text()):
            out[m.group(1)] = m.group(2).replace("{,}", ",")
    assert out, "no generated macros found; run `make defs` first"
    return out


def plain(tex: str) -> str:
    """A SCHEDULE entry as a slide shows it, with the LaTeX taken out."""
    s = tex
    for a, b in [(r"\tau", "\u03c4"), (r"\mu", "\u03bc"),
                 ("D_{post}^{*}", "D_post*"), ("D_{post}", "D_post")]:
        s = s.replace(a, b)
    s = re.sub(r"\\textsc\{([^}]*)\}", r"\1", s)
    return s.replace("$", "")


D = defs()

# ── drawing helpers ──────────────────────────────────────────────────────────
# Geometry is in inches and every box is placed explicitly. There is no
# PowerPoint renderer in this environment, so preview_deck.py re-reads these
# same boxes and draws them; anything that overlaps or overflows is caught
# there rather than on the projector.


def textbox(slide, x, y, w, h, *, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    return tf


def para(tf, text, *, size, bold=False, color=INK, font=BODY, space_after=6,
         align=PP_ALIGN.LEFT, first=False, italic=False, line=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    if line:
        p.line_spacing = line
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font
    r.font.color.rgb = color
    return p


def fill(slide, x, y, w, h, color, *, shape=MSO_SHAPE.RECTANGLE, line=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = color
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if s.has_text_frame:
        s.text_frame.word_wrap = True
    return s


def header(slide, number, title, *, dark=False):
    """The repeated motif: the graded component's number in a filled disc."""
    ink = ONDARK if dark else INK
    disc = fill(slide, M, 0.52, 0.62, 0.62, BLUE, shape=MSO_SHAPE.OVAL)
    tf = disc.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(tf, str(number), size=20, bold=True, color=PAPER_W, font=HEAD,
         align=PP_ALIGN.CENTER, first=True, space_after=0)
    t = textbox(slide, 1.52, 0.5, W - 1.52 - M, 0.72, anchor=MSO_ANCHOR.MIDDLE)
    para(t, title, size=32, bold=True, color=ink, font=HEAD, first=True,
         space_after=0)


def card(slide, x, y, w, h, *, tint=RGBColor(0xF5, 0xF6, 0xF8)):
    return fill(slide, x, y, w, h, tint, shape=MSO_SHAPE.ROUNDED_RECTANGLE)


def stat(slide, x, y, w, value, label, color):
    tf = textbox(slide, x, y, w, 0.95)
    para(tf, value, size=46, bold=True, color=color, font=HEAD, first=True,
         space_after=2)
    tf2 = textbox(slide, x, y + 0.86, w, 0.75)
    para(tf2, label, size=12, color=MID, first=True, space_after=0, line=1.15)


def deck() -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    return prs


def blank(prs, *, dark=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = INK if dark else PAPER_W
    return s


# ── slides ───────────────────────────────────────────────────────────────────

def slide_title(prs):
    s = blank(prs, dark=True)
    tf = textbox(s, M, 2.25, W - 2 * M, 1.9)
    para(tf, "Box Transpose", size=58, bold=True, color=ONDARK, font=HEAD,
         first=True, space_after=4)
    para(tf, "In-place N-dimensional tensor permutation on GPUs",
         size=23, color=RGBColor(0xB9, 0xB6, 0xB0), font=HEAD, italic=True,
         space_after=0)
    fill(s, M, 4.42, 1.5, 0.045, BLUE)
    tf = textbox(s, M, 4.82, W - 2 * M, 1.5)
    para(tf, "Kaveen Jayamanna   \u00b7   Alexis Newman", size=19, bold=True,
         color=ONDARK, first=True, space_after=5)
    para(tf, "Kennesaw State University", size=15,
         color=RGBColor(0xB9, 0xB6, 0xB0), space_after=5)
    para(tf, "CS 8045 Advanced Algorithms   \u00b7   Project Proposal",
         size=15, color=RGBColor(0xB9, 0xB6, 0xB0), space_after=0)
    s.notes_slide.notes_text_frame.text = (
        "Proposal for an in-place GPU tensor permutation system. "
        "Six components follow, numbered to the grading guidelines.")
    return s


def slide_team(prs):
    s = blank(prs)
    header(s, 1, "Team and responsibilities")
    people = [
        ("Kaveen Jayamanna", "KJ", BLUE,
         ["Planner and cost model: the box-swap graph, the shortest-path "
          "search, and the calibrated constants.",
          "The in-place cycle-following CUDA kernel, scalar and vectorised."]),
        ("Alexis Newman", "AN", ORANGE,
         ["Measurement and validation: the throughput micro-benchmark that "
          "calibrates the cost model.",
          "Correctness suite, the end-to-end comparison, and the head-to-head "
          "against prior systems."]),
    ]
    cw = (W - 2 * M - 0.5) / 2
    for i, (name, initials, colour, items) in enumerate(people):
        x = M + i * (cw + 0.5)
        card(s, x, TOP, cw, 3.55)
        disc = fill(s, x + 0.42, TOP + 0.42, 0.78, 0.78, colour,
                    shape=MSO_SHAPE.OVAL)
        dtf = disc.text_frame
        dtf.margin_left = dtf.margin_right = 0
        dtf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(dtf, initials, size=19, bold=True, color=PAPER_W, font=HEAD,
             align=PP_ALIGN.CENTER, first=True, space_after=0)
        tf = textbox(s, x + 1.38, TOP + 0.5, cw - 1.8, 0.6)
        para(tf, name, size=21, bold=True, color=INK, font=HEAD, first=True,
             space_after=0)
        tf = textbox(s, x + 0.42, TOP + 1.52, cw - 0.84, 1.8)
        for j, it in enumerate(items):
            para(tf, it, size=13.5, color=INK, first=(j == 0), space_after=9,
                 line=1.2)
    tf = textbox(s, M, TOP + 3.85, W - 2 * M, 0.5)
    para(tf, "Both members share the write-up and the final presentation. "
             "Every milestone in component 5 names a single owner.",
         size=13, color=MID, italic=True, first=True, space_after=0)
    s.notes_slide.notes_text_frame.text = (
        "Component 1. The split follows where each part of the work sits.")
    return s


def slide_problem(prs):
    s = blank(prs)
    header(s, 2, "Statement of the problem")
    cw = (W - 2 * M - 0.55) / 2

    tf = textbox(s, M, TOP, cw, 1.4)
    para(tf, "permute and transpose are free. The copy afterwards is not.",
         size=19, bold=True, color=INK, font=HEAD, first=True, space_after=10,
         line=1.15)
    tf = textbox(s, M, TOP + 1.0, cw, 2.9)
    for j, t in enumerate([
        "They reorder axes by changing tensor metadata, leaving a strided, "
        "non-contiguous layout.",
        "Downstream operators need a contiguous layout. PyTorch resolves that "
        "with .contiguous(), which allocates a second tensor and copies every "
        "element.",
        "Both tensors exist at once, so a single conversion can approach twice "
        "the footprint of the tensor. That is an out-of-memory failure on a "
        "large tensor, plus heap fragmentation.",
    ]):
        para(tf, t, size=14, color=INK, first=(j == 0), space_after=11,
             line=1.22)

    x = M + cw + 0.55
    card(s, x, TOP, cw, 4.36, tint=RGBColor(0xFD, 0xF1, 0xEC))
    tf = textbox(s, x + 0.42, TOP + 0.38, cw - 0.84, 0.4)
    para(tf, "OBJECTIVES", size=11.5, bold=True, color=ORANGE, first=True,
         space_after=0)
    tf = textbox(s, x + 0.42, TOP + 0.92, cw - 0.84, 3.2)
    for j, t in enumerate([
        "Decompose any permutation into steps that are each a single in-place "
        "matrix transpose.",
        "Choose the cheapest decomposition by search, not the first one found.",
        "Keep auxiliary space independent of the tensor size.",
        "Beat the memory ceiling of .contiguous(), and be no slower where both "
        "fit.",
    ]):
        p = para(tf, t, size=13.5, color=INK, first=(j == 0), space_after=11,
                 line=1.2)
        p.level = 0
    s.notes_slide.notes_text_frame.text = (
        "Component 2. The problem is peak memory, not latency.")
    return s


def slide_hard(prs):
    s = blank(prs)
    header(s, 3, "Why this is hard")
    items = [
        ("No closed form",
         "A matrix transpose has a closed-form index map, so its cycles can be "
         "followed. An arbitrary permutation over r axes does not. Computing "
         "its cycles directly costs \u0398(N) work and \u0398(N) state, which "
         "is what we are trying to avoid."),
        ("Choices are not equal",
         "Each step rewrites the whole buffer, so k steps cost roughly k "
         "passes over memory. A decomposition that is shorter in steps can "
         "still move more bytes. Choosing well is a search problem."),
        ("Access is the cost",
         "A permutation does no arithmetic. Throughput is strongly non-linear "
         "in the stride, so the cost model has to be calibrated against the "
         "hardware rather than counted from operations."),
    ]
    cw = (W - 2 * M - 2 * 0.42) / 3
    for i, (head_, body) in enumerate(items):
        x = M + i * (cw + 0.42)
        card(s, x, TOP, cw, 4.28)
        disc = fill(s, x + 0.42, TOP + 0.45, 0.56, 0.56, INK,
                    shape=MSO_SHAPE.OVAL)
        dtf = disc.text_frame
        dtf.margin_left = dtf.margin_right = 0
        dtf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(dtf, str(i + 1), size=16, bold=True, color=PAPER_W, font=HEAD,
             align=PP_ALIGN.CENTER, first=True, space_after=0)
        tf = textbox(s, x + 0.42, TOP + 1.25, cw - 0.84, 0.86)
        para(tf, head_, size=19, bold=True, color=INK, font=HEAD, first=True,
             space_after=0, line=1.12)
        tf = textbox(s, x + 0.42, TOP + 2.24, cw - 0.84, 1.8)
        para(tf, body, size=13, color=INK, first=True, space_after=0,
             line=1.25)
    tf = textbox(s, M, TOP + 4.55, W - 2 * M, 0.5)
    para(tf, f"The search space is r! orderings of the axes, so an exhaustive "
             f"comparison is out of reach at the ranks that matter.",
         size=13, color=MID, italic=True, first=True, space_after=0)
    s.notes_slide.notes_text_frame.text = "Component 3, part one: difficulty."
    return s


def slide_method(prs):
    s = blank(prs)
    header(s, 3, "Proposed method: adjacent box swaps")

    tf = textbox(s, M, TOP, W - 2 * M, 0.8)
    para(tf, "A box is a run of neighbouring axes treated as one unit. A swap "
             "exchanges two adjacent boxes, and reduces exactly to an in-place "
             "transpose of a rows \u00d7 cols matrix.",
         size=15, color=INK, first=True, space_after=0, line=1.25)

    # The swap, drawn. Axis cells, the two boxes tinted, and the result below.
    cell_w, cell_h, gap = 1.52, 0.78, 0.13
    x0, y0 = M + 0.15, TOP + 1.35
    before = [("a0", RULE), ("a1", BLUE), ("a2", BLUE), ("a3", ORANGE)]
    after = [("a0", RULE), ("a3", ORANGE), ("a1", BLUE), ("a2", BLUE)]
    for row, (cells, label) in enumerate([(before, "before"), (after, "after")]):
        y = y0 + row * 2.05
        tf = textbox(s, M + 0.15, y - 0.32, 2.0, 0.28)
        para(tf, label, size=11, bold=True, color=MID, first=True, space_after=0)
        for i, (name, colour) in enumerate(cells):
            x = x0 + i * (cell_w + gap)
            light = colour in (BLUE, ORANGE)
            box = fill(s, x, y, cell_w, cell_h,
                       colour if light else RGBColor(0xEE, 0xEC, 0xE8),
                       shape=MSO_SHAPE.ROUNDED_RECTANGLE)
            btf = box.text_frame
            btf.margin_left = btf.margin_right = 0
            btf.vertical_anchor = MSO_ANCHOR.MIDDLE
            para(btf, name, size=15, bold=True,
                 color=PAPER_W if light else INK, font=BODY,
                 align=PP_ALIGN.CENTER, first=True, space_after=0)
    arrow = fill(s, x0 + 3.05, y0 + 0.95, 0.56, 0.68,
                 RGBColor(0xC9, 0xC7, 0xC0), shape=MSO_SHAPE.DOWN_ARROW)
    arrow.text_frame.word_wrap = True

    tf = textbox(s, x0 + 6.75, y0 + 0.02, W - M - (x0 + 6.75), 2.9)
    for j, t in enumerate([
        "The blue box is two axes moved as one. That is the move a "
        "single-axis baseline cannot make.",
        "D_post, everything to the right of the swap, is the length of each "
        "contiguous run moved. It decides whether the step is fast, and "
        "whether the vectorised kernel applies.",
        "Edges are weighted by bytes moved over calibrated throughput, and "
        "Dijkstra returns the cheapest decomposition.",
    ]):
        para(tf, t, size=13.5, color=INK, first=(j == 0), space_after=14,
             line=1.25)
    s.notes_slide.notes_text_frame.text = (
        "Component 3, part two: the proposed method.")
    return s


def slide_evidence(prs):
    s = blank(prs, dark=True)
    header(s, 3, "Evidence so far", dark=True)

    tf = textbox(s, M, TOP - 0.12, W - 2 * M, 0.5)
    para(tf, f"{D['planCases']} sampled shape and permutation pairs, ranks "
             f"{D['planRankLo']} to {D['planRankHi']}, planned both ways. "
             f"A working prototype produced these, not an estimate.",
         size=14, color=RGBColor(0xB9, 0xB6, 0xB0), first=True, space_after=0)

    stats = [
        (f"{D['planStepFactor']}\u00d7", "fewer swaps than the\nadjacent baseline", BLUE),
        (f"{D['planByteFactor']}\u00d7", "fewer bytes moved,\nmedian over all pairs", BLUE),
        (f"{D['planBlockShare']}%", "of selected swaps bundle\nmore than one axis", ORANGE),
        (f"{D['planAuxPercent']}%", "of the tensor is the worst\nauxiliary footprint", ORANGE),
    ]
    cw = (W - 2 * M - 3 * 0.35) / 4
    for i, (value, label, colour) in enumerate(stats):
        x = M + i * (cw + 0.35)
        card(s, x, TOP + 0.6, cw, 1.95, tint=RGBColor(0x2B, 0x2A, 0x26))
        tf = textbox(s, x + 0.3, TOP + 0.86, cw - 0.6, 0.85)
        para(tf, value, size=40, bold=True, color=colour, font=HEAD,
             first=True, space_after=0)
        tf = textbox(s, x + 0.3, TOP + 1.7, cw - 0.6, 0.7)
        for j, ln in enumerate(label.split("\n")):
            para(tf, ln, size=11.5, color=RGBColor(0xB9, 0xB6, 0xB0),
                 first=(j == 0), space_after=1, line=1.1)

    # Median swaps per rank, from the same rows the paper's figure uses.
    r = rows("plan_sweep/results")
    by = defaultdict(list)
    for x in r:
        by[(x["planner"], x["rank"])].append(x["steps"])
    ranks = sorted({x["rank"] for x in r})
    med = {k: median(v) for k, v in by.items()}

    tf = textbox(s, M, TOP + 2.95, 5.0, 0.4)
    para(tf, "MEDIAN SWAPS PER PERMUTATION", size=11, bold=True,
         color=RGBColor(0xB9, 0xB6, 0xB0), first=True, space_after=0)

    top = max(max(med.values()), 1)
    bar_w, slot = 0.46, 1.06
    base_y, max_h = TOP + 4.62, 1.35
    for i, rank in enumerate(ranks):
        gx = M + 0.55 + i * slot
        for k, (planner, colour) in enumerate(
                [("adjacent_baseline", ORANGE), ("block_dijkstra", BLUE)]):
            v = med[(planner, rank)]
            h = max(max_h * v / top, 0.05)
            fill(s, gx + k * (bar_w + 0.06), base_y - h, bar_w, h, colour)
            tf = textbox(s, gx + k * (bar_w + 0.06) - 0.08, base_y - h - 0.26,
                         bar_w + 0.16, 0.24)
            para(tf, f"{v:g}", size=10.5, bold=True, color=colour,
                 align=PP_ALIGN.CENTER, first=True, space_after=0)
        tf = textbox(s, gx - 0.08, base_y + 0.08, 2 * bar_w + 0.22, 0.26)
        para(tf, f"rank {rank}", size=11, color=RGBColor(0xB9, 0xB6, 0xB0),
             align=PP_ALIGN.CENTER, first=True, space_after=0)

    lx = M + 6.6
    for k, (name, colour) in enumerate(
            [("adjacent baseline", ORANGE), ("box search (ours)", BLUE)]):
        fill(s, lx, TOP + 3.62 + k * 0.42, 0.26, 0.26, colour)
        tf = textbox(s, lx + 0.4, TOP + 3.62 + k * 0.42, 3.0, 0.3,
                     anchor=MSO_ANCHOR.MIDDLE)
        para(tf, name, size=12.5, color=ONDARK, first=True, space_after=0)
    tf = textbox(s, lx, TOP + 4.42, W - M - lx, 0.68)
    para(tf, f"At rank {D['planRankHi']} the median permutation costs the "
             f"baseline {D['planStepsBaselineTop']} swaps and the search "
             f"{D['planStepsSearchTop']}. The gap widens with rank.",
         size=12.5, color=RGBColor(0xB9, 0xB6, 0xB0), first=True,
         space_after=0, line=1.2)
    s.notes_slide.notes_text_frame.text = (
        "Component 3, part three. Every figure is generated from "
        "raw_data/plan_sweep, which is committed and CPU-only.")
    return s


def slide_setting(prs):
    s = blank(prs)
    header(s, 4, "Simulation setting")
    cw = (W - 2 * M - 0.55) / 2

    tf = textbox(s, M, TOP, cw, 0.4)
    para(tf, "BENCHMARK DESIGN", size=11.5, bold=True, color=BLUE, first=True,
         space_after=0)
    tf = textbox(s, M, TOP + 0.48, cw, 0.95)
    para(tf, "Shapes are not hand-picked. For N elements at rank r, every "
             "valid shape is enumerated by prime-factorising N and spreading "
             "the exponents across the dimensions.",
         size=13.5, color=INK, first=True, space_after=0, line=1.22)

    pic_w = 4.55
    s.shapes.add_picture(str(HERE / "equation-shapes.png"),
                         Inches(M + (cw - pic_w) / 2), Inches(TOP + 1.62),
                         width=Inches(pic_w))

    tf = textbox(s, M, TOP + 2.82, cw, 1.6)
    para(tf, f"We fix N at {D['planElements']} elements and sweep ranks "
             f"{D['planRankLo']} to {D['planRankHi']}, drawing "
             f"{D['planShapesPerRank']} shapes per rank and up to "
             f"{D['planPermsPerShape']} permutations per shape. At rank "
             f"{D['planRankHi']} the space holds {D['planSpaceTop']} shapes, "
             f"so sampling is the only option.",
         size=13, color=INK, first=True, space_after=8, line=1.22)
    para(tf, "This is the construction the Cycle Splitter evaluation uses, so "
             "the two sets of results stay comparable.",
         size=13, color=MID, italic=True, space_after=0, line=1.22)

    x = M + cw + 0.55
    card(s, x, TOP, cw, 2.62)
    tf = textbox(s, x + 0.42, TOP + 0.35, cw - 0.84, 0.4)
    para(tf, "ENVIRONMENT", size=11.5, bold=True, color=BLUE, first=True,
         space_after=0)
    tf = textbox(s, x + 0.42, TOP + 0.9, cw - 0.84, 1.55)
    for j, t in enumerate([
        "Planner and cost model in Python, standard library only. No GPU "
        "needed, so the planner results reproduce anywhere.",
        "Kernel in CUDA C++, JIT-compiled by PyTorch. Pinned in an NGC "
        "container. Development hardware is an RTX PRO 6000 Blackwell.",
    ]):
        para(tf, t, size=12.5, color=INK, first=(j == 0), space_after=8,
             line=1.2)

    card(s, x, TOP + 2.95, cw, 1.9)
    tf = textbox(s, x + 0.42, TOP + 3.32, cw - 0.84, 0.4)
    para(tf, "METRICS", size=11.5, bold=True, color=BLUE, first=True,
         space_after=0)
    tf = textbox(s, x + 0.42, TOP + 3.84, cw - 0.84, 0.9)
    para(tf, "Bytes moved  \u00b7  swap count  \u00b7  auxiliary bytes  \u00b7  "
             "achieved throughput (GB/s)  \u00b7  end-to-end latency and peak "
             "memory against .contiguous()",
         size=12.5, color=INK, first=True, space_after=0, line=1.25)
    s.notes_slide.notes_text_frame.text = (
        "Component 4. Correctness is checked against the framework's own "
        "out-of-place permutation and gates every measurement.")
    return s


def slide_milestones(prs):
    s = blank(prs)
    header(s, 5, "Milestones and timeline")

    tf = textbox(s, M, TOP - 0.12, W - 2 * M, 0.62)
    para(tf, f"{D['timelineWeeksNum']} weeks from proposal to final report. "
             f"Calibration is front-loaded, so every later measurement is read "
             f"through a validated cost model.",
         size=13.5, color=MID, first=True, space_after=0)

    y = TOP + 0.55
    row_h = 0.47
    colour = {"KJ": BLUE, "AN": ORANGE}
    for i, (week, text, owner) in enumerate(timeline.SCHEDULE):
        if i % 2 == 0:
            fill(s, M, y - 0.06, W - 2 * M, row_h, RGBColor(0xF6, 0xF7, 0xF9))
        disc = fill(s, M + 0.12, y - 0.01, 0.35, 0.35, INK, shape=MSO_SHAPE.OVAL)
        dtf = disc.text_frame
        dtf.margin_left = dtf.margin_right = 0
        dtf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(dtf, str(week), size=11, bold=True, color=PAPER_W, font=BODY,
             align=PP_ALIGN.CENTER, first=True, space_after=0)
        tf = textbox(s, M + 0.66, y + 0.025, W - 2 * M - 1.55, 0.38)
        para(tf, plain(text), size=11.5, color=INK, first=True, space_after=0)
        owners = [o for o in owner.replace(",", " ").split()]
        for k, o in enumerate(owners):
            bx = W - M - 0.16 - (len(owners) - k) * 0.62
            chip = fill(s, bx, y + 0.005, 0.54, 0.33,
                        colour[o], shape=MSO_SHAPE.ROUNDED_RECTANGLE)
            ctf = chip.text_frame
            ctf.margin_left = ctf.margin_right = 0
            ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
            para(ctf, o, size=10.5, bold=True, color=PAPER_W, font=BODY,
                 align=PP_ALIGN.CENTER, first=True, space_after=0)
        y += row_h
    s.notes_slide.notes_text_frame.text = (
        "Component 5. Owners match the title page. The schedule lives in "
        "pipeline/tables/gen_table_timeline.py.")
    return s


def slide_refs(prs):
    s = blank(prs)
    header(s, 6, "References")
    refs = [
        ("Catanzaro, Keller, Garland", "A decomposition for in-place matrix "
         "transposition", "PPoPP", "2014"),
        ("G\u00f3mez-Luna, Sung, Chang, Gonz\u00e1lez-Linares, Guil, Hwu",
         "In-place matrix transposition on GPUs", "IEEE TPDS", "2016"),
        ("Gustavson, Karlsson, K\u00e5gstr\u00f6m", "Parallel and cache-efficient "
         "in-place matrix storage format conversion", "ACM TOMS", "2012"),
        ("Sung, Liu, Hwu", "DL: a data layout transformation system for "
         "heterogeneous computing", "InPar", "2012"),
        ("Wu, Tu, Cheng, Lee", "EITHOT: efficient in-place transposition of "
         "high order tensors on GPUs", "ACM TOPC", "2025"),
        ("Cheng, Lee", "ITTPD: in-place tensor transposition with permutation "
         "decomposition on GPUs", "HPCAsia", "2025"),
        ("Rajbhandari, Rasley, Ruwase, He", "ZeRO: memory optimizations toward "
         "training trillion parameter models", "SC20", "2020"),
        ("Dummit, Foote", "Abstract Algebra, 3rd edition", "Wiley", "2003"),
    ]
    # Rows are tall enough for the longest author list and the longest title
    # to wrap to two lines without the rule below cutting through them.
    y = TOP - 0.02
    row_h = 0.585
    for author, title, venue, year in refs:
        tf = textbox(s, M, y, 3.95, row_h - 0.12)
        para(tf, author, size=12, bold=True, color=INK, first=True,
             space_after=0, line=1.12)
        tf = textbox(s, M + 4.12, y, 5.75, row_h - 0.12)
        para(tf, title, size=12, color=INK, first=True, space_after=0,
             line=1.12)
        tf = textbox(s, W - M - 2.2, y, 2.2, row_h - 0.12)
        para(tf, f"{venue}, {year}", size=12, color=MID,
             align=PP_ALIGN.RIGHT, first=True, space_after=0)
        y += row_h
        fill(s, M, y - 0.09, W - 2 * M, 0.012, RULE)
    tf = textbox(s, M, y + 0.14, W - 2 * M, 0.42)
    para(tf, "Full entries with pages and DOIs are in the proposal, along with "
             "three PyTorch sources omitted here for space.",
         size=12, color=MID, italic=True, first=True, space_after=0, line=1.2)
    s.notes_slide.notes_text_frame.text = "Component 6."
    return s


def main() -> None:
    prs = deck()
    slide_title(prs)
    slide_team(prs)
    slide_problem(prs)
    slide_hard(prs)
    slide_method(prs)
    slide_evidence(prs)
    slide_setting(prs)
    slide_milestones(prs)
    slide_refs(prs)
    prs.save(OUT)
    print(f"wrote {OUT.name}  {len(prs.slides.__iter__.__self__._sldIdLst)} slides")


if __name__ == "__main__":
    main()
