"""results/figures/*.svg: five charts of the five-model page, drawn as plain SVG from results/describe_reasoning_models.json.

Each chart has one row per model x framework (harness blue, Codex CLI orange) on a white rounded card, so it reads on light and
dark pages alike. Text widths are estimated from Helvetica / Arial metrics (with a margin for wider fallback fonts); every chart
checks that no two labels overlap and that all text stays on the card. Hovering a mark (SVG opened directly) shows its numbers.

    finagent figures [--results DIR]     read DIR/describe_reasoning_models.json, write DIR/figures/*.svg (default: results/)
"""
from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path

from finagent import config
from finagent.analysis.describe import FW_ORDER, MODEL_ORDER
from finagent.analysis.reasoning import LABEL
from finagent.analysis.report import FW_LABEL

FONT = "Helvetica, Arial, sans-serif"
SERIES = {"harness": "#2a78d6", "coding_agent": "#eb6834"}          # validated pair (CVD separation, contrast) on white
CARD, INK, INK2, MUTED, GRID, AXIS, BAND = "#ffffff", "#0b0b0b", "#52514e", "#6f6d67", "#e1e0d9", "#a8a69e", "#ecebe6"
SOURCE = "Source: results/describe_reasoning_models.json (finagent analyze), drawn by finagent figures."

# Helvetica advance widths (1/1000 em) of printable ASCII, space to tilde; any other character counts as 600
_W = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + [
    278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778,
    722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222,
    222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
SAFETY = 1.12                                                        # fallback sans faces (e.g. DejaVu Sans) run wider


def text_width(s: str, size: float, bold: bool = False) -> float:
    w = sum(_W[ord(c) - 32] if 32 <= ord(c) < 127 else 600 for c in s) * size / 1000
    return w * SAFETY * (1.07 if bold else 1.0)


# ------------------------------------------------------------------------------------------------ SVG builder
class Svg:
    """Collects SVG elements and the box of every text, so that a finished chart can prove its labels do not collide."""

    def __init__(self, width: int, title: str, desc: str):
        self.width, self.title, self.desc = width, title, desc
        self.parts: list[str] = []
        self.boxes: list[tuple[float, float, float, float, str]] = []

    def add(self, element: str) -> None:
        self.parts.append(element)

    def text(self, x: float, y: float, s: str, size: float = 12, fill: str = INK, anchor: str = "start", bold: bool = False,
             halo: bool = False) -> float:
        """Draws s with its baseline at y; returns its estimated width."""
        w = text_width(s, size, bold)
        x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        self.boxes.append((x0, y - 0.78 * size, x0 + w, y + 0.24 * size, s))
        extra = (' font-weight="bold"' if bold else "") + (f' stroke="{CARD}" stroke-width="3" paint-order="stroke"' if halo else "")
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:g}" fill="{fill}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')
        return w

    def rect(self, x: float, y: float, w: float, h: float, fill: str, tip: str = "", rx: float = 0) -> None:
        attrs = f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"' + (f' rx="{rx:g}"' if rx else "")
        self.add(f"<rect {attrs}><title>{escape(tip)}</title></rect>" if tip else f"<rect {attrs}/>")

    def bar(self, x: float, y: float, w: float, h: float, fill: str, tip: str, opacity: float = 1) -> None:
        """A horizontal bar growing from x: square at the baseline, 4 px rounded at the data end."""
        if w <= 0:
            return
        r = min(4.0, w, h / 2)
        d = (f"M{x:.1f},{y:.1f}h{w - r:.1f}a{r:g},{r:g} 0 0 1 {r:g},{r:g}v{h - 2 * r:.1f}a{r:g},{r:g} 0 0 1 {-r:g},{r:g}"
             f"h{r - w:.1f}z")
        extra = f' opacity="{opacity:g}"' if opacity != 1 else ""
        self.add(f'<path d="{d}" fill="{fill}"{extra}><title>{escape(tip)}</title></path>')

    def dot(self, x: float, y: float, fill: str, tip: str) -> None:
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{fill}" stroke="{CARD}" stroke-width="2"><title>{escape(tip)}</title></circle>')

    def line(self, x1: float, y1: float, x2: float, y2: float, stroke: str, width: float = 1) -> None:
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width:g}"/>')

    def render(self, height: float) -> str:
        h = math.ceil(height)
        for x0, y0, x1, y1, s in self.boxes:
            if not (4 <= x0 <= x1 <= self.width - 4 and 4 <= y0 <= y1 <= h - 4):
                raise ValueError(f"text off the card: {s!r}")
        for i, a in enumerate(self.boxes):
            for b in self.boxes[i + 1:]:
                if not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]):
                    raise ValueError(f"labels overlap: {a[4]!r} / {b[4]!r}")
        return "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{h}" viewBox="0 0 {self.width} {h}" '
                          f'font-family="{FONT}" role="img" aria-labelledby="title desc">',
                          f'<title id="title">{escape(self.title)}</title>', f'<desc id="desc">{escape(self.desc)}</desc>',
                          f'<rect width="{self.width}" height="{h}" rx="14" fill="{CARD}"/>', *self.parts, "</svg>", ""])


# ------------------------------------------------------------------------------------------------ data
class Page:
    """The metric records of describe_reasoning_models.json, looked up by model key, framework and metric name."""

    def __init__(self, path: Path):
        self.rows = {(r["model"], r["framework"], r["metric"]): (r["value"], r["n"]) for r in json.loads(path.read_text())}

    def get(self, m: str, f: str, metric: str) -> tuple:
        """(value, n) of one metric of one model x framework."""
        return self.rows[(LABEL[m], FW_LABEL[f], metric)]

    def count(self, m: str, f: str, metric: str) -> tuple[int, int]:
        """(k, n) of a share: shares are k / n rounded to 3 decimals, so round(share * n) is k exactly (n < 500)."""
        v, n = self.get(m, f, metric)
        return (round(v * n) if n else 0), n

    def baseline(self, name: str) -> float:
        return self.rows[(f"baseline: {name}", "-", "mean_abs_ln_vol_forecast_over_realised5d")][0]


class Scale:
    """Linear map from data values in [lo, hi] to x pixels in [x0, x1]."""

    def __init__(self, lo: float, hi: float, x0: float, x1: float):
        self.lo, self.hi, self.x0, self.x1 = lo, hi, x0, x1

    def __call__(self, v: float) -> float:
        return self.x0 + (v - self.lo) / (self.hi - self.lo) * (self.x1 - self.x0)


# ------------------------------------------------------------------------------------------------ shared layout
ROW_H, ROW_GAP, GROUP_GAP, MARK_H = 16, 4, 14, 12        # one row per model x framework, two rows per model
LEFT = 118                                               # the model labels end here; plots start here
LEGEND = [(SERIES["harness"], "harness"), (SERIES["coding_agent"], "Codex CLI")]


def cell_name(m: str, f: str) -> str:
    return f"{config.MODELS[m]['label']} / {FW_LABEL[f]}"


def header(svg: Svg, subtitle: list[str], legend: list[tuple[str, str]]) -> float:
    """Title, subtitle lines and a one-row legend of (swatch colour, text); returns the y where the plot may start."""
    svg.text(20, 30, svg.title, size=16, bold=True)
    y = 30
    for s in subtitle:
        y += 18
        svg.text(20, y, s, fill=INK2)
    y += 26
    x = 20
    for colour, label in legend:
        svg.rect(x, y - 9, 12, 12, colour, rx=3)
        x += 18 + svg.text(x + 18, y + 1, label, fill=INK2) + 22
    return y + 22


def rows(svg: Svg, top: float) -> tuple[list[tuple[str, str, float]], float]:
    """Writes the model labels; returns (model, framework, row centre y) of the ten rows and the y below the last row."""
    out, y = [], top
    for m in MODEL_ORDER:
        svg.text(LEFT - 10, y + ROW_H + ROW_GAP / 2 + 4, config.MODELS[m]["label"], anchor="end")
        for f in FW_ORDER:
            out.append((m, f, y + ROW_H / 2))
            y += ROW_H + ROW_GAP
        y += GROUP_GAP - ROW_GAP
    return out, y - GROUP_GAP


def x_axis(svg: Svg, sc: Scale, ticks: list[float], top: float, bottom: float, label: str, fmt) -> None:
    """Hairline grid at the ticks (the zero line darker), tick labels and the axis title below the plot."""
    for t in ticks:
        svg.line(sc(t), top, sc(t), bottom, AXIS if t == 0 else GRID)
        svg.text(sc(t), bottom + 16, fmt(t), size=11, fill=MUTED, anchor="middle")
    svg.text((sc.x0 + sc.x1) / 2, bottom + 36, label, fill=INK2, anchor="middle")


def footer(svg: Svg, y: float, notes: list[str]) -> float:
    """Notes and the source line below the axis title; returns the card height."""
    for s in notes + [SOURCE]:
        y += 17
        svg.text(20, y, s, size=11, fill=MUTED)
    return y + 16


def pct(v: float) -> str:
    return f"{v * 100:.0f}%"


def signed(v: float, digits: int = 1) -> str:
    return "0" if v == 0 else f"{v:+.{digits}f}".replace("-", "−")


# ------------------------------------------------------------------------------------------------ the five charts
def paste_rate(p: Page) -> str:
    svg = Svg(720, "Annualised figure submitted as the 5-day volatility",
              "Share of usable runs per model and framework whose 5-day volatility forecast is an annualised reading of the day "
              "(strict rule), and the runs the broad rule (annual scale) adds.")
    top = header(svg, ["Share of usable runs whose expected_vol_pct is one of the day's four annualised readings.",
                       "Solid: strict rule (0.9 min to 1.1 max of the readings); light: runs the broad rule (annual scale) adds."],
                 LEGEND + [("#b9b7b0", "added by the broad rule")])
    sc = Scale(0, 0.2, LEFT, 560)
    layout, bottom = rows(svg, top)
    x_axis(svg, sc, [0, 0.05, 0.1, 0.15, 0.2], top - 6, bottom + 6, "share of usable runs", pct)
    for m, f, cy in layout:
        (ks, n), (kb, _) = p.count(m, f, "pasted_annualised_strict_share"), p.count(m, f, "pasted_annualised_broad_share")
        y, tip = cy - MARK_H / 2, f"{cell_name(m, f)}: strict {ks}/{n}, broad {kb}/{n}"
        svg.bar(sc(0), y, sc(ks / n) - sc(0), MARK_H, SERIES[f], tip)
        if kb > ks:
            x = sc(ks / n) + (2 if ks else 0)                        # 2 px card-coloured gap between the two segments
            svg.bar(x, y, sc(kb / n) - x, MARK_H, SERIES[f], tip, opacity=0.35)
        svg.text(sc(kb / n) + 6, cy + 4, f"{ks}/{n}" + (f"  (broad {kb})" if kb != ks else ""), size=11, fill=INK2, halo=True)
    return svg.render(footer(svg, bottom + 42, ["Labels: strict pastes / usable runs (broad count where it differs)."]))


def mention_vs_paste(p: Page) -> str:
    svg = Svg(760, "Mentioning the annualised figure vs submitting it",
              "Left: share of usable runs whose reasoning output mentions an annualised figure of the day (rule any). Right: among "
              "those runs, the share whose final 5-day volatility is still that annualised figure (strict rule).")
    top = header(svg, ["Left: usable runs whose reasoning output mentions an annualised figure of the day (rule any).",
                       "Right: of those runs, the ones whose final 5-day vol is still an annualised figure (strict rule)."], LEGEND)
    panels = [(Scale(0, 1, LEFT, 400), "reasoning_mentions_annualised_any_share", "mentions it: share of usable runs"),
              (Scale(0, 1, 470, 700), "among_mention_any_submits_annualised_strict_share", "still submits it: share of those runs")]
    layout, bottom = rows(svg, top)
    for sc, metric, axis_label in panels:
        x_axis(svg, sc, [0, 0.25, 0.5, 0.75, 1], top - 6, bottom + 6, axis_label, pct)
        for m, f, cy in layout:
            k, n = p.count(m, f, metric)
            share = k / n if n else 0
            svg.bar(sc(0), cy - MARK_H / 2, sc(share) - sc(0), MARK_H, SERIES[f], f"{cell_name(m, f)}: {k}/{n}")
            svg.text(sc(share) + 6, cy + 4, f"{k}/{n}", size=11, fill=INK2, halo=True)
    return svg.render(footer(svg, bottom + 42, ["Labels: runs, k of n. The mention and paste rules are defined in "
                                                "describe_reasoning_models.md."]))


def shift_vs_placebo(p: Page, arm: str, domain: tuple[float, float]) -> str:
    edit = {"UNIT5D": "readings in 5-day units", "NOLABEL": "readings without their labels"}[arm]
    metric = f"shift_{arm}_minus_PLACEBO_lnvol"
    svg = Svg(760, f"{arm} minus PLACEBO: shift of the volatility forecast",
              f"Per model and framework: mean over days of ln(5-day vol forecast) of the {arm} run ({edit}) minus the PLACEBO "
              "run, with whiskers of 2 SE and a band of the ORIG run-to-run noise.")
    top = header(svg, [f"Per day: ln(5-day vol forecast) of the {arm} run ({edit}) minus that of the PLACEBO run.",
                       "Dot: mean over days; whisker: ±2 SE; grey band: ± the row's mean |ln(ORIG run 0 / ORIG run 1)|."],
                 LEGEND + [(BAND, "ORIG run-to-run noise")])
    sc = Scale(*domain, LEFT, 600)
    svg.text(sc.x1 + 24, top + 2, "mean (days)", size=11, fill=MUTED)
    layout, bottom = rows(svg, top + 14)
    for m, f, cy in layout:
        noise = p.get(m, f, "orig_run_to_run_abs_diff_lnvol")[0]
        svg.rect(sc(-noise), cy - ROW_H / 2, sc(noise) - sc(-noise), ROW_H, BAND, f"{cell_name(m, f)}: ORIG run-to-run {noise:.3f}")
    ticks = [t / 2 for t in range(math.ceil(domain[0] * 2), math.floor(domain[1] * 2) + 1)]
    x_axis(svg, sc, ticks, top + 8, bottom + 6, f"ln(vol forecast): {arm} run minus PLACEBO run", signed)
    for m, f, cy in layout:
        (mean, n), se = p.get(m, f, metric), p.get(m, f, f"{metric}_se")[0]
        star = "*" if p.get(m, f, f"{metric}_outside_noise")[0] else ""
        svg.line(sc(mean - 2 * se), cy, sc(mean + 2 * se), cy, SERIES[f], 2)
        svg.dot(sc(mean), cy, SERIES[f], f"{cell_name(m, f)}: {mean:+.3f}, SE {se:.3f}, {n} days")
        svg.text(sc.x1 + 24, cy + 4, f"{signed(mean, 2)}{star} ({n})", size=11, fill=INK2)
    return svg.render(footer(svg, bottom + 42, [
        "* = |mean| > 2 SE, the page's crude mark (sigma from 4 to 6 ORIG pairs). Days: those with the ORIG, edit and PLACEBO runs usable.",
        "Positive: the edit raised the volatility forecast more than the placebo edit did."]))


def accuracy(p: Page) -> str:
    readings, prior = p.baseline("readings ann_vol_20d x sqrt(5/252)"), p.baseline("S1 rational prior sigma5")
    svg = Svg(760, "Accuracy of the 5-day volatility forecast",
              "Mean absolute log error of the 5-day volatility forecast against the realised 5-day volatility, per model and "
              f"framework, with the readings' 20-day vol in 5-day units ({readings:.3f}) and the S1 prior ({prior:.3f}) as references.")
    top = header(svg, ["Mean |ln(forecast / realised 5-day vol)| over usable runs; lower is better.",
                       "Vertical lines: two forecasts that need no agent, scored on the same 6 days."], LEGEND)
    sc = Scale(0, 0.8, LEFT, 580)
    svg.text(sc(prior) - 5, top + 4, f"S1 prior {prior:.2f}", size=11, fill=INK2, anchor="end")
    svg.text(sc(readings) + 5, top + 4, f"readings' 20-day vol × √(5/252) {readings:.2f}", size=11, fill=INK2)
    svg.text(sc.x1 + 24, top + 22, "mean [SE]", size=11, fill=MUTED)
    layout, bottom = rows(svg, top + 32)
    x_axis(svg, sc, [0, 0.2, 0.4, 0.6, 0.8], top + 24, bottom + 6, "mean |ln(forecast / realised)|", lambda t: f"{t:.1f}")
    for m, f, cy in layout:
        (v, n), se = p.get(m, f, "mean_abs_ln_vol_forecast_over_realised5d"), p.get(m, f, "mean_abs_ln_vol_err_se_over_days")[0]
        svg.bar(sc(0), cy - MARK_H / 2, sc(v) - sc(0), MARK_H, SERIES[f], f"{cell_name(m, f)}: {v:.3f} over {n} runs, SE {se:.3f}")
        svg.text(sc.x1 + 24, cy + 4, f"{v:.2f} [{se:.2f}]", size=11, fill=INK2)
    for v in (prior, readings):
        svg.line(sc(v), top + 10, sc(v), bottom + 6, INK2, 1.5)
    return svg.render(footer(svg, bottom + 42, ["SE: standard deviation of the 6 day means / sqrt(6)."]))


def shift_domain(p: Page) -> tuple[float, float]:
    """One x range for both shift charts, covering every whisker and noise band, widened to half units."""
    ends = []
    for arm in ("UNIT5D", "NOLABEL"):
        metric = f"shift_{arm}_minus_PLACEBO_lnvol"
        for m in MODEL_ORDER:
            for f in FW_ORDER:
                mean, se = p.get(m, f, metric)[0], p.get(m, f, f"{metric}_se")[0]
                noise = p.get(m, f, "orig_run_to_run_abs_diff_lnvol")[0]
                ends += [mean - 2 * se, mean + 2 * se, -noise, noise]
    return math.floor(min(ends) * 2) / 2, math.ceil(max(ends) * 2) / 2


def figures(p: Page) -> dict[str, str]:
    """file name -> SVG text."""
    dom = shift_domain(p)
    return {"paste_rate.svg": paste_rate(p), "mention_vs_paste.svg": mention_vs_paste(p),
            "unit5d_minus_placebo.svg": shift_vs_placebo(p, "UNIT5D", dom),
            "nolabel_minus_placebo.svg": shift_vs_placebo(p, "NOLABEL", dom), "accuracy.svg": accuracy(p)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent figures", description="Redraw results/figures/*.svg from the results JSON.")
    ap.add_argument("--results", type=Path, default=config.RESULTS, help="results folder (default: results/)")
    a = ap.parse_args(argv)
    out = a.results / "figures"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in figures(Page(a.results / "describe_reasoning_models.json")).items():
        (out / name).write_text(text, encoding="utf-8")
        print(out / name)
    return 0
