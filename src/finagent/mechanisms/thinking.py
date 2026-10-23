"""Mechanism 4 of 4 (thinking): does the agent's reasoning text weigh evidence and relate pieces of evidence to each
other, or does it list tool outputs and jump to a number? CPU only, no model calls, deterministic.

Reads the 4,000 plain FULL_<k>/NO_NEWS_<k> sessions (k=0..3) of the two copied corpora,
data/mechanisms/sessions/newsagent (Qwen3.5-9B) and data/mechanisms/sessions/q3news_s1 (Qwen3-8B, thinking on),
scans each session's full reasoning text with the WEIGHING / RELATIONSHIP phrase lists below (raw, strict and
strict2 tiers), and writes results/mechanisms/thinking/data.json: rates with Wilson 95% intervals by arm, corpus and
distinct-tool count, pooled two-proportion z-tests FULL vs NO_NEWS, an OLS tool-count trend, the same-sentence
news<->volatility connection check (plus its adjacent-sentence-pair sensitivity), the recorded hand-check precision
(with Wilson intervals by formula) and verbatim examples, each checked against its session file.

    finagent mech-thinking [--out PATH] [--check]

Ported from the verified 1_overreaction analysis (results/mech4_20261023/thinking: scratch scripts
mech4_analysis.py, mech4_stats.py and build_final.py, recovered from the original analysis transcript, plus the
2026-10-23 hand corrections, which are computed here rather than typed in). See results/mechanisms/thinking/README.md.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from finagent import config
from finagent.mechanisms import thinking_text as T

SESSIONS = config.DATA / "mechanisms" / "sessions"
CORPORA = (  # (corpus key in data.json, folder, model)
    ("newsagent_20261011", SESSIONS / "newsagent", "Qwen3.5-9B"),
    ("q3news_20261012_S1", SESSIONS / "q3news_s1", "Qwen3-8B (thinking on)"),
)
OUT_DIR = config.RESULTS / "mechanisms" / "thinking"
OUT_FILE = OUT_DIR / "data.json"

# ------------------------------------------------------------------------------------------------ pattern sets
# Exact lists, in the order they were applied and published. The first block of each list is the task
# specification's own examples, the rest are the analyst's extensions; the last WEIGHING pair ("outweighed",
# "marginally") and the last RELATIONSHIP block were added after the first pass. One inert typo entry ("while the
# the", which never matched any text) was removed on 2026-10-23 (patterns._edit_log); a second "corroborate" was a
# duplicate the original de-duplication already dropped.
WEIGHING_PHRASES = (
    "more important", "less important", "significant", "minor", "doesn't change", "does not change",
    "already reflects", "already reflect", "already priced", "not much new", "outweighs", "outweigh", "largely",
    "marginal", "doesn't add much", "does not add much", "carries more weight", "carry more weight",
    "most important", "won't change", "wouldn't change", "already priced in", "already reflected", "nothing new",
    "carries less weight", "weighs more", "weighs less", "weigh more heavily", "weigh less heavily",
    "more weight than", "less weight than", "bigger factor", "biggest factor", "key driver", "main driver",
    "primary driver", "overshadow", "overshadows", "overshadowed", "negligible", "immaterial", "material factor",
    "dominant factor", "limited impact", "minimal impact", "significant impact", "substantial impact",
    "takes precedence", "take precedence", "tips the balance", "tip the balance", "secondary concern",
    "secondary factor", "primary concern", "weigh heavily", "weighs heavily", "weigh against", "weigh in favor",
    "more credible", "less credible", "more reliable", "less reliable", "stronger signal", "weaker signal",
    "carries weight", "bigger concern", "more telling", "less telling", "matters more", "matters less",
    "the bigger risk", "the bigger driver",
    "outweighed", "marginally",
)
RELATIONSHIP_PHRASES = (
    "consistent with", "in line with", "confirms", "corroborates", "contradicts", "conflicts with", "contrary to",
    "on the other hand", "however the", "however, the", "despite the", "while the",
    "confirming", "confirmed", "corroborating", "corroborate", "contradicting", "contradict", "conflicting with",
    "aligns with", "align with", "echoes", "echoing", "reinforces", "reinforcing", "reinforce the", "supports the",
    "support the", "backs up", "backed by", "mirrors", "mirroring", "at odds with", "inconsistent with",
    "diverges from", "diverging from", "in tension with", "offsets", "offsetting", "counterbalances",
    "counterbalancing", "reflects the", "mixed signals", "mixed picture", "jibes with", "matches the",
    "matching the", "in contrast to", "unlike the", "together with", "combined with", "paired with", "whereas the",
    "even though the", "notwithstanding the", "adds to the case", "builds on the", "undercuts", "undercutting",
    "undermines", "undermining", "lines up with", "squares with", "at odds",
    "confirm", "reinforce", "undermine", "undercut", "mirror", "echo", "offset", "aligned with",
)
RELATIONSHIP_REGEXES = (
    ("both...suggest/indicate/confirm/support",
     re.compile(r"\bboth\b[^.?!]{0,80}\b(?:suggest|suggests|indicate|indicates|point to|points to|confirm|confirms"
                r"|support|supports)\b", re.IGNORECASE)),
)
# "strict" drops the generic intensifiers / transition words; "strict2" also drops the "aligns with" family, which the
# hand-check found is mostly "my DECISION aligns with signal X" rather than two pieces of evidence related.
WEIGHING_WEAK = frozenset({"significant", "minor"})
RELATIONSHIP_WEAK = frozenset({"however, the", "however the", "while the", "despite the"})
ALIGN_FAMILY = ("aligns with", "align with", "aligned with")
RELATIONSHIP_WEAK2 = RELATIONSHIP_WEAK | frozenset(ALIGN_FAMILY)

# word-boundary wrap, so "minor" does not match inside "Minority" nor "however, the" the start of "there's"
_PHRASE_RE = {p: re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)
              for p in WEIGHING_PHRASES + RELATIONSHIP_PHRASES}

SESSION_FILE = re.compile(r"^(FULL|NO_NEWS)_(\d+)\.json\.gz$")    # FULL_T06_* (temperature variant) excluded
NEWS_TOOLS = frozenset({"get_news", "get_news_stats", "get_macro_news", "search_news"})
NEWS_TERM = re.compile(r"\bnews\b|\bheadlines?\b", re.IGNORECASE)
VOL_TERM = re.compile(r"\bvolatil\w*\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


# A re.IGNORECASE match of a lower-case ASCII phrase can only involve ASCII text characters, unless the text holds
# one of the few non-ASCII letters that IGNORECASE equates with an ASCII letter (e.g. U+017F long s, U+212A Kelvin
# sign). Without such a character, `phrase in text.lower()` is therefore a necessary condition for a match and is
# used to skip the (slow) regex search; with one, every regex is run. The result is identical either way.
_ASCII_LETTER_I = re.compile(r"[a-z]", re.IGNORECASE)
assert all(p.isascii() and p == p.lower() for p in WEIGHING_PHRASES + RELATIONSHIP_PHRASES)


def _lower_if_safe(text: str) -> str | None:
    if any(ord(ch) > 127 and _ASCII_LETTER_I.fullmatch(ch) for ch in set(text)):
        return None
    return text.lower()


def find_matches(text: str, phrases) -> list[str]:
    """The phrases of `phrases` found in text (case-insensitive, word-bounded), sorted."""
    low = _lower_if_safe(text)
    return sorted({p for p in phrases if (low is None or p in low) and _PHRASE_RE[p].search(text)})


def find_regex_matches(text: str) -> list[str]:
    return [name for name, rx in RELATIONSHIP_REGEXES if rx.search(text)]


def has_marker(text: str) -> bool:
    return bool(find_matches(text, WEIGHING_PHRASES) or find_matches(text, RELATIONSHIP_PHRASES)
                or find_regex_matches(text))


def split_sentences(text: str) -> list[str]:
    """The check-4 'sentence' units: split on newlines, then on . ! ? followed by whitespace, drop empty fragments."""
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if line:
            out.extend(p for p in _SENTENCE_END.split(line) if p.strip())
    return out


def reasoning_text(session: dict) -> str:
    """Every turn's reasoning in trace order, then the submit_decision call's own `reasoning` argument (the last one
    if several), joined with blank lines."""
    parts, submit_reasoning = [], None
    for e in session.get("trace", []):
        if e.get("turn") is not None and "reasoning" in e and e["reasoning"]:
            parts.append(e["reasoning"])
        for tc in e.get("tool_calls") or []:
            if tc.get("name") == "submit_decision":
                args = tc.get("arguments")
                try:
                    if isinstance(args, str):
                        args = json.loads(args)
                    if args.get("reasoning"):
                        submit_reasoning = args["reasoning"]
                except (ValueError, AttributeError):
                    pass
    if submit_reasoning:
        parts.append(submit_reasoning)
    return "\n\n".join(parts)


def news_in_prompt(session: dict) -> bool:
    """The day's prompt has at least one '- [timestamp]' bullet in its COMPANY NEWS block."""
    trace = session.get("trace") or []
    user = trace[0].get("user", "") if trace else ""
    i = user.find("COMPANY NEWS")
    if i == -1:
        return False
    j = user.find("FISCAL POLICY NEWS", i)
    block = user[i:j if j != -1 else len(user)]
    return bool(re.search(r"^- \[", block, re.MULTILINE))


def session_files():
    """(corpus, path, arm, k) for every plain FULL_<k>/NO_NEWS_<k> file, corpora in order, folders and files sorted."""
    for corpus, root, _model in CORPORA:
        for day_dir in sorted((d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")),
                              key=lambda d: d.name):
            for fp in sorted(day_dir.glob("*.json.gz"), key=lambda f: f.name):
                m = SESSION_FILE.match(fp.name)
                if m:
                    yield corpus, fp, m.group(1), int(m.group(2))


def check4_hits(text: str) -> tuple[bool, bool]:
    """(same-sentence connection, 2-sentence-window connection): a news term, a volatility term and a marker in one
    sentence unit, or in a window of two consecutive units joined by a space. The windows are sents[i:i+2] for every
    i, as in the source code, so the last window is a single unit and a one-unit text is still covered; for any text
    with two or more units this is exactly the 'every adjacent pair' rule documented in data.json."""
    sents = split_sentences(text)
    same = any(NEWS_TERM.search(s) and VOL_TERM.search(s) and has_marker(s) for s in sents)
    window = False
    for i in range(len(sents)):
        w = " ".join(sents[i:i + 2])
        if NEWS_TERM.search(w) and VOL_TERM.search(w) and has_marker(w):
            window = True
            break
    return same, window


def process(corpus: str, fp: Path, arm: str, k: int) -> dict:
    with gzip.open(fp, "rt", encoding="utf-8") as f:
        d = json.load(f)
    trace = d.get("trace", [])
    tools = sorted({e["tool"] for e in trace if e.get("tool") and e.get("tool") != "submit_decision"})
    text = reasoning_text(d)
    w = find_matches(text, WEIGHING_PHRASES)
    r = find_matches(text, RELATIONSHIP_PHRASES)
    rx = find_regex_matches(text)
    rec = {
        "corpus": corpus, "arm": arm, "k": k, "day_id": fp.parent.name, "file": config.rel(fp), "text": text,
        "n_distinct_tools": len(tools), "weighing_matches": w, "relationship_matches": r,
        "has_weighing": bool(w), "has_relationship": bool(r or rx),
        "has_weighing_strict": any(m not in WEIGHING_WEAK for m in w),
        "has_relationship_strict": bool(rx) or any(m not in RELATIONSHIP_WEAK for m in r),
        "has_relationship_strict2": bool(rx) or any(m not in RELATIONSHIP_WEAK2 for m in r),
    }
    rec["has_neither"] = not (rec["has_weighing"] or rec["has_relationship"])
    rec["has_neither_strict"] = not (rec["has_weighing_strict"] or rec["has_relationship_strict"])
    used_vol = "get_volatility_stats" in tools
    news = news_in_prompt(d)
    rec["check4_eligible"] = arm == "FULL" and news and bool(NEWS_TERM.search(text)) and used_vol
    rec["check4_same"], rec["check4_window"] = check4_hits(text) if rec["check4_eligible"] else (False, False)
    return rec


def load_records() -> list[dict]:
    return [process(*args) for args in session_files()]


# ------------------------------------------------------------------------------------------------ statistics
def wilson_ci(k: int, n: int, digits: int = 2, z: float = 1.96) -> list[float] | list[None]:
    """Wilson score 95% interval, in percent, rounded to `digits`."""
    if n == 0:
        return [None, None]
    p = k / n
    denom = 1 + z ** 2 / n
    center = p + z ** 2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))
    return [round((center - margin) / denom * 100, digits), round((center + margin) / denom * 100, digits)]


def rate(k: int, n: int, digits: int = 2) -> float | None:
    return None if n == 0 else round(100.0 * k / n, digits)


def two_prop_z(k1: int, n1: int, k2: int, n2: int) -> dict:
    """Pooled two-proportion z-test, normal two-sided p (math.erfc); diff = group 1 - group 2, in points."""
    p1, p2 = k1 / n1, k2 / n2
    pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    return {"diff_pct": round((p1 - p2) * 100, 2), "se_pct": round(se * 100, 2), "z": round(z, 3),
            "p_two_sided": round(math.erfc(abs(z) / math.sqrt(2)), 5)}


def summarize(recs: list[dict]) -> dict:
    n = len(recs)
    kw = sum(1 for r in recs if r["has_weighing"])
    kr = sum(1 for r in recs if r["has_relationship"])
    kn = sum(1 for r in recs if r["has_neither"])
    return {
        "n": n, "k_weighing": kw, "k_relationship": kr, "k_neither": kn,
        "pct_weighing": rate(kw, n), "weighing_ci95": wilson_ci(kw, n),
        "pct_relationship": rate(kr, n), "relationship_ci95": wilson_ci(kr, n),
        "pct_neither": rate(kn, n), "neither_ci95": wilson_ci(kn, n),
        "pct_weighing_strict": rate(sum(1 for r in recs if r["has_weighing_strict"]), n),
        "pct_relationship_strict": rate(sum(1 for r in recs if r["has_relationship_strict"]), n),
        "pct_neither_strict": rate(sum(1 for r in recs if r["has_neither_strict"]), n),
        "pct_relationship_strict2": rate(sum(1 for r in recs if r["has_relationship_strict2"]), n),
    }


def tool_bucket(n: int) -> str:
    return "0-1" if n <= 1 else "2" if n == 2 else "3-4" if n <= 4 else "5-6" if n <= 6 else "7+"


TOOL_BUCKETS = ("0-1", "2", "3-4", "5-6", "7+")


def ols(xs: list[float], ys: list[float], note: str) -> dict:
    """Closed-form OLS of y on x with homoskedastic slope SE (population moments, n-2 residual df)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    vx = sum((x - mx) ** 2 for x in xs) / n
    vy = sum((y - my) ** 2 for y in ys) / n
    slope = cov / vx
    intercept = my - slope * mx
    sse = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    se = math.sqrt(sse / (n - 2) / (n * vx))
    return {"n": n, "pearson_r": round(cov / math.sqrt(vx * vy), 4), "slope_per_extra_tool": round(slope, 4),
            "slope_se": round(se, 4), "slope_t_stat": round(slope / se, 3), "intercept": round(intercept, 4),
            "note": note}


def _sorted(obj):
    if isinstance(obj, dict):
        return {k: _sorted(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_sorted(v) for v in obj]
    return obj


# ------------------------------------------------------------------------------------------------ build
def build(records: list[dict] | None = None) -> dict:
    """The full content of results/mechanisms/thinking/data.json."""
    recs = load_records() if records is None else records
    n_all = len(recs)
    corpora = sorted({r["corpus"] for r in recs})
    arms = sorted({r["arm"] for r in recs})
    by_arm = {a: [r for r in recs if r["arm"] == a] for a in arms}
    full, nn = by_arm["FULL"], by_arm["NO_NEWS"]

    def test(flag: str) -> dict:
        return two_prop_z(sum(1 for r in full if r[flag]), len(full), sum(1 for r in nn if r[flag]), len(nn))

    buckets = defaultdict(list)
    for r in recs:
        buckets[tool_bucket(r["n_distinct_tools"])].append(r)
    rates = {
        "overall": summarize(recs),
        "by_corpus": {c: summarize([r for r in recs if r["corpus"] == c]) for c in corpora},
        "by_arm": {a: summarize(by_arm[a]) for a in arms},
        "by_corpus_arm": {f"{c}__{a}": summarize([r for r in recs if r["corpus"] == c and r["arm"] == a])
                          for c in corpora for a in arms},
        "by_n_distinct_tools_bucket": {b: summarize(buckets.get(b, [])) for b in TOOL_BUCKETS},
        "field_meaning": T.FIELD_MEANING,
    }
    sig = {
        "FULL_vs_NO_NEWS_relationship_raw": test("has_relationship"),
        "FULL_vs_NO_NEWS_relationship_strict2": test("has_relationship_strict2"),
        "FULL_vs_NO_NEWS_weighing_raw": test("has_weighing"),
        "FULL_vs_NO_NEWS_weighing_strict": test("has_weighing_strict"),
        "method": T.SIG_METHOD,
    }
    sig["headline_result"] = T.render_sig_headline(sig["FULL_vs_NO_NEWS_relationship_raw"],
                                                   sig["FULL_vs_NO_NEWS_relationship_strict2"],
                                                   sig["FULL_vs_NO_NEWS_weighing_raw"],
                                                   sig["FULL_vs_NO_NEWS_weighing_strict"])
    xs = [r["n_distinct_tools"] for r in recs]
    ols_raw = ols(xs, [1.0 if r["has_relationship"] else 0.0 for r in recs], T.OLS_RAW_NOTE)
    ols_s2 = ols(xs, [1.0 if r["has_relationship_strict2"] else 0.0 for r in recs], T.OLS_STRICT2_NOTE)
    trend = {"ols_raw": ols_raw, "ols_strict2": ols_s2,
             "headline_result": T.render_trend_headline(ols_raw, ols_s2, rates["by_n_distinct_tools_bucket"])}

    elig = [r for r in recs if r["check4_eligible"]]
    n4 = len(elig)
    k_same = sum(1 for r in elig if r["check4_same"])
    k_window = sum(1 for r in elig if r["check4_window"])
    check4 = {
        "n_eligible": n4, "n_connects_same_sentence": k_same, "rate_pct": rate(k_same, n4),
        "ci95": wilson_ci(k_same, n4), "definition": T.C4_DEFINITION, "sentence_splitting_algorithm": T.C4_SPLIT,
        "window2_sensitivity": {"n_eligible": n4, "n_connects_2sentence_window": k_window,
                                "rate_pct": rate(k_window, n4, 1), "definition": T.C4W_DEFINITION},
    }
    check4["window2_sensitivity"]["interpretation"] = T.render_c4w_interpretation(
        check4["rate_pct"], n4, check4["window2_sensitivity"]["rate_pct"])

    # hand-check: recorded judgments, Wilson intervals by formula (one decimal, as published)
    sessions_with = Counter(m for r in recs for m in r["weighing_matches"] + r["relationship_matches"])
    align_union = sum(1 for r in recs if any(m in ALIGN_FAMILY for m in r["relationship_matches"]))
    w_ci = wilson_ci(T.HC_WEIGHING_GENUINE, T.HC_WEIGHING_SHOWN, digits=1)
    r_ci = wilson_ci(T.HC_RELATIONSHIP_GENUINE_STRICT, T.HC_RELATIONSHIP_SHOWN, digits=1)
    o = rates["overall"]
    handcheck = {
        "method": T.HC_METHOD,
        "finding_1_bug_found_and_fixed": T.HC_BUG,
        "weighing_judgment": {
            "n_sampled_with_a_weighing_match_shown": T.HC_WEIGHING_SHOWN,
            "judged_genuine_quote": T.HCW_JUDGED_GENUINE_QUOTE,
            "judged_genuine": T.HC_WEIGHING_GENUINE,
            "judged_false_positive": T.HC_WEIGHING_FALSE_POSITIVE,
            "rough_precision_pct": rate(T.HC_WEIGHING_GENUINE, T.HC_WEIGHING_SHOWN, 1),
            "rough_precision_pct_wilson95_ci": w_ci,
            "note": T.render_weighing_note(sessions_with["significant"], n_all, w_ci),
        },
        "relationship_judgment": {
            "n_sampled_with_a_relationship_match_shown": T.HC_RELATIONSHIP_SHOWN,
            "judged_genuine_strict_quote": T.render_relationship_strict_quote(r_ci),
            "judged_genuine_strict": T.HC_RELATIONSHIP_GENUINE_STRICT,
            "judged_false_positive_strict": T.HC_RELATIONSHIP_FALSE_POSITIVE_STRICT,
            "rough_precision_strict_pct": rate(T.HC_RELATIONSHIP_GENUINE_STRICT, T.HC_RELATIONSHIP_SHOWN, 1),
            "rough_precision_strict_pct_wilson95_ci": r_ci,
            "dominant_false_positive_pattern": T.render_dominant_false_positive(
                {p: sessions_with[p] for p in ALIGN_FAMILY}, align_union, n_all, o["k_relationship"]),
            "judged_genuine_loose_note": T.render_loose_note(o["pct_relationship"], o["pct_relationship_strict2"]),
        },
    }

    by_file = {(r["corpus"], r["day_id"], Path(r["file"]).name): r for r in recs}

    def example(spec: dict, text_keys: tuple[str, ...]) -> dict:
        r = by_file[spec["session"]]
        for key in text_keys:
            if spec[key] not in r["text"]:
                raise ValueError(f"{r['file']}: {key} is not verbatim in the session's reasoning text")
        out = {k: v for k, v in spec.items() if k != "session"}
        out.update(file=r["file"], corpus=r["corpus"], arm=r["arm"])
        return out

    pure = []
    for spec in T.PURE_LISTING:
        e = example(spec, ("verbatim_excerpt", "then_jumps_to"))
        r = by_file[spec["session"]]
        if not r["has_neither"] or r["n_distinct_tools"] < 3:
            raise ValueError(f"{r['file']} is not a 3+-tool zero-marker session")
        e["n_distinct_tools"] = r["n_distinct_tools"]
        pure.append(e)
    genuine = []
    for spec in T.GENUINE:
        e = example(spec, ("verbatim_quote",))
        r = by_file[spec["session"]]
        missing = set(spec["matched_phrases"]) - set(r["weighing_matches"] + r["relationship_matches"])
        if missing:
            raise ValueError(f"{r['file']}: {sorted(missing)} not matched in that session")
        genuine.append(e)
    q3_neither = [r for r in recs if r["corpus"] == "q3news_20261012_S1" and r["has_neither"]]
    if any(r["n_distinct_tools"] >= 3 for r in q3_neither):
        raise ValueError("examples.note_on_corpus_coverage assumes no 3+-tool zero-marker q3news session")
    examples = {
        "pure_listing_3plus_tools_zero_markers": pure,
        "genuine_weighing_or_relating": genuine,
        "note_on_corpus_coverage": T.render_examples_note(len(q3_neither),
                                                          Counter(r["n_distinct_tools"] for r in q3_neither)),
    }

    n_per = Counter(r["corpus"] for r in recs)
    data = {
        "task": T.TASK,
        "corpora": {
            "newsagent_20261011": {"path": config.rel(CORPORA[0][1]), "model": CORPORA[0][2],
                                   "n_sessions_analyzed": n_per["newsagent_20261011"],
                                   "files_used": T.NEWSAGENT_FILES_USED},
            "q3news_20261012_S1": {"path": config.rel(CORPORA[1][1]), "model": CORPORA[1][2],
                                   "n_sessions_analyzed": n_per["q3news_20261012_S1"],
                                   "files_used": T.Q3_FILES_USED},
            "total_sessions": n_all,
        },
        "patterns": {
            "weighing_phrases": list(WEIGHING_PHRASES),
            "weighing_weak_subset_excluded_in_strict": sorted(WEIGHING_WEAK),
            "relationship_phrases": list(RELATIONSHIP_PHRASES),
            "relationship_weak_subset_excluded_in_strict": sorted(RELATIONSHIP_WEAK),
            "relationship_weak2_subset_excluded_in_strict2": sorted(RELATIONSHIP_WEAK2),
            "relationship_regexes": [{"name": name, "pattern": rx.pattern} for name, rx in RELATIONSHIP_REGEXES],
            "matching_method": T.MATCHING_METHOD,
            "text_unit_analyzed": T.TEXT_UNIT_ANALYZED,
            "_edit_log": list(T.EDIT_LOG),
        },
        "precision_handcheck": handcheck,
        "rates": rates,
        "significance_tests": sig,
        "tool_count_trend": trend,
        "check4_news_volatility_connection": check4,
        "examples": examples,
        "limitations": T.render_limitations(o, check4),
    }
    return _sorted(data)


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent mech-thinking", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_FILE, help=f"output file (default: {config.rel(OUT_FILE)})")
    ap.add_argument("--check", action="store_true", help="compare with --out instead of writing it (exit 1 if different)")
    a = ap.parse_args(argv)
    data = build()
    if a.check:
        same = a.out.is_file() and a.out.read_bytes() == dumps(data).encode("utf-8")
        print(f"{'same' if same else 'DIFFERENT':9s}  {config.rel(a.out)}")
        return 0 if same else 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(dumps(data), encoding="utf-8")
    o, c4 = data["rates"]["overall"], data["check4_news_volatility_connection"]
    print(f"wrote {config.rel(a.out)}: {o['n']} sessions, weighing {o['pct_weighing']}%, relationship "
          f"{o['pct_relationship']}% (strict2 {o['pct_relationship_strict2']}%), check 4 "
          f"{c4['n_connects_same_sentence']}/{c4['n_eligible']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
