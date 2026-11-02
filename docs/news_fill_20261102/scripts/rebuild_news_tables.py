"""Rebuild news/news_items_flagged.parquet and news/items_index.parquet from the raw Finnhub pulls (2026-11-02, after the single-day fill).

Same definitions as the original build, code copied verbatim where it is a rule:
  * relevance, price-move masking, headline Jaccard first-report rule (48 h, 0.5):   _scripts/news_lib.py (verbatim copy of
    1_overreaction/results/rcf_20261011/scripts/news_lib.py) and flag_items() below (copied from build_events.py);
  * per-source publication-time rules (utc / wall / plus5 / date_only) and their three validation tests:  copied from
    1_overreaction/repro/newsagent/timefix.py; the only adaptation is the price source of test (c): Index One daily bars
    (market/daily/indexone_eod_96_*.parquet) instead of the stratos panel;
  * first_report recomputed in corrected time order, D_min (first decision time 09:00 ET of the next trading day after publication),
    the date scan that drops items naming a date after D_min, kept = not date-flagged and D_min exists:  copied from
    repro/newsagent/build.py (item_table, mentioned_dates, first_decision_tp); the market calendar is the union of the 95 tickers'
    Index One trading days.
Inputs: news/dow30_raw/<TK>.json (Dow-30 monthly pull of 2026-09-25, src_pull dow30_existing), raw/news_finnhub/raw/<TK>.json
(October pull + 2026-11-02 fill; src_pull rcf_20261011 for ids already in the previous table, fill_20261102 for new ids),
raw/news_finnhub/fetch_state.json (call spans -> day_coverage.parquet), _inventory/universe_95.txt.
Outputs (news/): news_items_flagged.parquet, items_index.parquet, time_validation.json, build_stats.json, day_coverage.parquet
(ticker, date, complete: the UTC day lies inside a span known to be complete), MANIFEST.sha256; _inventory/news_rebuild_<date>.json
(before / after comparison). The previous tables are in ../archive/data_before_news_fill_20261102/news/.

    python _scripts/rebuild_news_tables.py [--dry-run]       (run from data/)
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_scripts"))
import news_lib as N  # noqa: E402

ET, UTC = ZoneInfo("America/New_York"), dt.timezone.utc
TP_FMT = "%Y%m%dT%H%M%S"
STAMP = dt.date.today().strftime("%Y%m%d")
EOD = next((ROOT / "market/daily").glob("indexone_eod_96_*.parquet"))
OLD_FLAGGED = ROOT.parent / "archive/data_before_news_fill_20261102/news/news_items_flagged.parquet"
OLD_INDEX = ROOT.parent / "archive/data_before_news_fill_20261102/news/items_index.parquet"
MAX_ITEMS, JACC, LOOKBACK = 12, 0.5, 48 * 3600          # build_events.py constants (first-report rule)
TRUNC_N = 150

# ------------------------------------------------------------------------------------------------- timefix (copied)
SOURCE_RULE = {"Yahoo": "utc", "ChartMill": "utc",
               "Benzinga": "wall", "MarketWatch": "wall", "DowJones": "wall", "CNBC": "wall", "Finnhub": "wall",
               "SeekingAlpha": "plus5", "Fintel": "plus5"}
DEFAULT_RULE = "plus5"
PLUS_S = 5 * 3600


def rule_of(source):
    return SOURCE_RULE.get(source or "", DEFAULT_RULE)


def true_epoch(raw: int, source) -> tuple[int, str]:
    raw = int(raw)
    if raw % 86400 == 0:
        d = dt.datetime.fromtimestamp(raw, UTC).date()
        return int(dt.datetime(d.year, d.month, d.day, 23, 59, tzinfo=ET).timestamp()), "date_only"
    r = rule_of(source)
    if r == "utc":
        return raw, r
    if r == "wall":
        w = dt.datetime.fromtimestamp(raw, UTC).replace(tzinfo=None)
        return int(w.replace(tzinfo=ET).timestamp()), r
    return raw + PLUS_S, r


def true_epochs(raw, source):
    out = [true_epoch(int(e), s) for e, s in zip(raw, source)]
    return np.array([o[0] for o in out], dtype=np.int64), [o[1] for o in out]


NORM = re.compile(r"[^a-z0-9]+")


def _norm(h):
    return NORM.sub(" ", (h or "").lower()).strip()


def _et_hour(e):
    s = pd.to_datetime(np.asarray(e, dtype=np.int64), unit="s", utc=True).tz_convert(ET)
    return (s.hour + s.minute / 60.0).to_numpy()


def test_a(df):
    d = df.assign(norm=[_norm(h) for h in df.headline]); d = d[d.norm.str.len() > 25]
    y = d[d.source == "Yahoo"][["norm", "raw", "epoch"]].rename(columns={"raw": "y_raw", "epoch": "y_epoch"})
    out = {}
    for s, g in d[d.source != "Yahoo"].groupby("source"):
        m = g[["norm", "raw", "epoch"]].merge(y, on="norm"); m = m[(m.y_raw - m.raw).abs() <= 12 * 3600].drop_duplicates(["norm", "raw"])
        if m.empty:
            out[s] = {"pairs": 0}; continue
        raw_off = (m.y_raw - m.raw) / 3600.0; cor_off = (m.y_epoch - m.epoch) / 3600.0
        r = {"pairs": int(len(m)), "median_offset_h_raw": float(raw_off.median()), "median_offset_h_corrected": float(cor_off.median()),
             "share_source_earlier_ge_0.75h_raw": float((raw_off >= 0.75).mean()), "share_source_earlier_ge_0.75h_corrected": float((cor_off >= 0.75).mean())}
        r["applies"] = r["pairs"] >= 20
        r["pass_raw"] = abs(r["median_offset_h_raw"]) <= 0.25 and r["share_source_earlier_ge_0.75h_raw"] <= 0.10
        r["pass"] = abs(r["median_offset_h_corrected"]) <= 0.25 and r["share_source_earlier_ge_0.75h_corrected"] <= 0.10
        out[s] = r
    return out


AFTER = ((16.0, 24.0), (0.0, 9.5))
FAMILIES = [("CNBC biggest moves premarket", "CNBC", r"biggest moves (?:in the )?premarket|biggest moves before the bell", ((4.0, 9.5),)),
            ("CNBC biggest moves midday", "CNBC", r"biggest moves midday", ((11.0, 14.5),)),
            ("CNBC biggest moves after hours", "CNBC", r"biggest moves after (?:hours|the bell)", AFTER),
            ("Benzinga pre-market session movers", "Benzinga", r"pre-?market session", ((4.0, 9.5),)),
            ("Benzinga intraday session movers", "Benzinga", r"intraday session", ((9.5, 16.0),)),
            ("MarketWatch after-close recap vs competitors", "MarketWatch", r"(?:underperforms|outperforms).*competitors", ((16.0, 24.0),)),
            ("ChartMill premarket", "ChartMill", r"pre-?market", ((4.0, 9.5),)),
            ("ChartMill after hours", "ChartMill", r"after[- ]hours|after the (?:bell|close)", AFTER),
            ("Fintel NEW YORK MARKET CLOSE", "Fintel", r"^NEW YORK MARKET CLOSE", ((16.0, 24.0),))]


def _in(h, windows):
    return np.any([(h >= a) & (h < b) for a, b in windows], axis=0)


def test_b(df):
    out = {}
    for name, src, rx, win in FAMILIES:
        g = df[(df.source == src) & df.headline.str.contains(rx, case=False, regex=True)]
        if g.empty:
            out[name] = {"n": 0}; continue
        hr, hc = _et_hour(g.raw), _et_hour(g.epoch)
        r = {"source": src, "n": int(len(g)), "share_in_window_raw": float(_in(hr, win).mean()), "share_in_window_corrected": float(_in(hc, win).mean())}
        r["applies"] = r["n"] >= 10; r["pass_raw"] = r["share_in_window_raw"] >= 0.90; r["pass"] = r["share_in_window_corrected"] >= 0.90
        out[name] = r
    return out


UP = re.compile(r"\b(rises?|rising|rose|gains?|gained|gaining|jumps?|jumped|jumping|soars?|soared|soaring|surges?|surged|surging|climbs?|"
                r"climbed|climbing|rall(?:y|ies|ied|ying)|spikes?|spiked|pops?|popped|higher|advances?|advanced|leaps?|leapt|skyrockets?|"
                r"skyrocketed|rebounds?|rebounded|all-time high|record high|up \d)", re.I)
DN = re.compile(r"\b(falls?|fell|falling|drops?|dropped|dropping|slides?|slid|sliding|plunges?|plunged|plunging|sinks?|sank|sinking|"
                r"tumbles?|tumbled|tumbling|declines?|declined|declining|lower|slumps?|slumped|sell-?off|tanks?|tanked|crash(?:es|ed)?|"
                r"dips?|dipped|retreats?|retreated|slips?|slipped|sheds?|down \d|plummets?|plummeted|sags?|sagged)", re.I)


def stated_direction(h):
    u, d = bool(UP.search(h or "")), bool(DN.search(h or ""))
    return 1 if u and not d else (-1 if d and not u else 0)


def _sessions(tickers, eod):
    out = {}
    for tk, g in eod[eod.ticker.isin(list(tickers))].groupby("ticker"):
        g = g.sort_values("date")
        op = np.array([int(dt.datetime.strptime(x, "%Y-%m-%d").replace(hour=9, minute=30, tzinfo=ET).timestamp()) for x in g.date])
        out[tk] = (op, g.splitAdjOpen.to_numpy(float), g.splitAdjClose.to_numpy(float))
    return out


def _match(sub, e, S):
    nxt, plc = [], []
    for tk, dirn, ee in zip(sub.ticker, sub.dir, e):
        op, O, Cl = S[tk]; i = int(np.searchsorted(op, ee, side="right"))
        if i < 2 or i + 5 >= len(op):
            continue
        nxt.append(dirn * np.sign(np.log(Cl[i] / O[i])) > 0); plc.append(dirn * np.sign(np.log(Cl[i + 5] / O[i + 5])) > 0)
    n = len(nxt)
    return {"n": n, "excess": float(np.mean(nxt) - np.mean(plc)) if n else None}


def test_c(df, eod):
    d = df[df.has_move].copy(); d["dir"] = [stated_direction(h) for h in d.headline]; d = d[d.dir != 0]
    S = _sessions(d.ticker.unique(), eod); d = d[d.ticker.isin(S)]
    out = {}
    for s, g in d.groupby("source"):
        r = {"raw": _match(g, g.raw.to_numpy(np.int64), S), "corrected": _match(g, g.epoch.to_numpy(np.int64), S)}
        for k in (2, 4, 8):
            r[f"corrected_plus{k}h"] = _match(g, g.epoch.to_numpy(np.int64) + k * 3600, S)
        n = r["corrected"]["n"]; r["applies"] = n >= 300
        later = min(r[f"corrected_plus{k}h"]["excess"] for k in (2, 4, 8)) if n else None
        r["drop_when_moved_later_pp"] = None if not n else 100 * (r["corrected"]["excess"] - later)
        r["pass"] = (not r["applies"]) or r["drop_when_moved_later_pp"] <= 1.5
        out[s] = r
    return out


def validate_times(items: pd.DataFrame, eod) -> dict:
    df = items.rename(columns={"datetime": "raw"})[["ticker", "id", "raw", "source", "headline", "relevant", "has_move"]].copy()
    df["raw"] = df.raw.astype(np.int64); df["epoch"], df["rule"] = true_epochs(df.raw, df.source)
    a, b, c = test_a(df), test_b(df), test_c(df, eod)
    verified = defaultdict(list)
    for s, r in a.items():
        if r.get("applies"): verified[s].append("a")
    for name, r in b.items():
        if r.get("applies"): verified[r["source"]].append("b")
    fails = [f"(a) {s}" for s, r in a.items() if r.get("applies") and not r["pass"]]
    fails += [f"(b) {k}" for k, r in b.items() if r.get("applies") and not r["pass"]]
    fails += [f"(c) {s}" for s, r in c.items() if not r["pass"]]
    rules = []
    for s in sorted(df.source.dropna().unique()):
        r = rule_of(s)
        if r in ("utc", "wall") and s != "Yahoo" and not verified.get(s):
            fails.append(f"rule {r} for {s} without a passing test (a) or (b)")
        rules.append({"source": s, "rule": r, "verified_by": sorted(set(verified.get(s, []))), "items": int((df.source == s).sum())})
    return {"note": "rules and tests copied from 1_overreaction/repro/newsagent/timefix.py; test (c) uses Index One daily bars", "rules": rules,
            "date_only_items": int((df.raw % 86400 == 0).sum()), "test_a_yahoo_duplicates": a, "test_b_fixed_format_headlines": b,
            "test_c_next_session_leak_signature": c, "failures_corrected": fails, "pass": not fails}


# ------------------------------------------------------------------------------------------------- build.py pieces (copied)
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MRX = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
R_MDY = re.compile(r"\b" + MRX + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(20\d\d)\b)?")
R_DMY = re.compile(r"\b(\d{1,2})\s+" + MRX + r"\.?,?\s+(20\d\d)\b")
R_ISO = re.compile(r"\b(20\d\d)-(\d{2})-(\d{2})\b")
R_US = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d\d|\d\d)\b")


def mentioned_dates(text, pub):
    out = []
    for m in R_MDY.finditer(text):
        mo = MON[m.group(1)[:3].lower()]; d = int(m.group(2)); y = m.group(3)
        try:
            if y:
                out.append(dt.date(int(y), mo, d))
            else:
                cands = []
                for k in (-1, 0, 1):
                    try: cands.append(dt.date(pub.year + k, mo, d))
                    except ValueError: pass
                if cands: out.append(min(cands, key=lambda c: abs((c - pub).days)))
        except ValueError:
            pass
    for m in R_DMY.finditer(text):
        try: out.append(dt.date(int(m.group(3)), MON[m.group(2)[:3].lower()], int(m.group(1))))
        except ValueError: pass
    for m in R_ISO.finditer(text):
        try: out.append(dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError: pass
    for m in R_US.finditer(text):
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        try: out.append(dt.date(y, int(m.group(1)), int(m.group(2))))
        except ValueError: pass
    return out


def tp_from_epoch(sec):
    return dt.datetime.fromtimestamp(int(sec), tz=UTC).astimezone(ET).strftime(TP_FMT)


class Calendar:
    def __init__(self, days: list[str]):
        self.days = days; self.arr = np.array(days)

    def decision_tp(self, t: str):
        i = self.days.index(t)
        return None if i + 1 >= len(self.days) else dt.datetime.strptime(self.days[i + 1], "%Y-%m-%d").replace(hour=9).strftime(TP_FMT)

    def first_decision_tp(self, tp: str):
        day = f"{tp[:4]}-{tp[4:6]}-{tp[6:8]}"; i = int(np.searchsorted(self.arr, day))
        for j in range(max(0, i - 1), min(len(self.days) - 1, i + 2)):
            D = self.decision_tp(self.days[j])
            if D is not None and D > tp:
                return D
        return None


def flag_items(tk, L):
    """build_events.flag_items, verbatim."""
    rel = N.relevance_rx(tk); pats = N.mask_rx(tk)
    toks = [N.tokset(x["headline"]) for x in L]; ts = [x["datetime"] for x in L]
    j0 = 0
    for i, x in enumerate(L):
        while ts[j0] < ts[i] - LOOKBACK:
            j0 += 1
        x["first_report"] = not any(N.jaccard(toks[i], toks[j]) >= JACC for j in range(j0, i))
        h, s = x["headline"].strip(), (x.get("summary") or "").strip()
        x["relevant"] = N.relevant(tk, rel, h, s)
        hm, k1 = N.mask_text(h, pats)
        if not s or N.tokset(s) == N.tokset(h) or s.lower().startswith(h.lower()[:60]):
            sm, k2 = "", 0
        else:
            sm, k2 = N.mask_text(s, pats)
        x["headline_masked"], x["summary_masked"], x["n_masks"] = hm, sm, k1 + k2
        x["has_move"] = (k1 + k2) > 0


def first_report_corrected(all_items: pd.DataFrame) -> dict:
    out = {}
    for tk, g in all_items.groupby("ticker"):
        g = g[g.headline.fillna("").str.strip() != ""].sort_values(["epoch", "id"])
        toks = [N.tokset(h) for h in g.headline]; ts = g.epoch.to_numpy(); ids = g.id.to_numpy(); j0 = 0
        for i in range(len(g)):
            while ts[j0] < ts[i] - LOOKBACK:
                j0 += 1
            out[(tk, int(ids[i]))] = not any(N.jaccard(toks[i], toks[j]) >= JACC for j in range(j0, i))
    return out


# ------------------------------------------------------------------------------------------------- loading
def load_items(tk: str, old_src: dict) -> list[dict]:
    items = {}
    p = ROOT / "news/dow30_raw" / f"{tk}.json"
    if p.exists():
        for x in json.loads(p.read_text()):
            items[x["id"]] = {**x, "src_pull": "dow30_existing"}
    p = ROOT / "raw/news_finnhub/raw" / f"{tk}.json"
    if p.exists():
        for x in json.loads(p.read_text()):
            items.setdefault(x["id"], {**x, "src_pull": old_src.get((tk, x["id"]), "fill_20261102")})
    L = [x for x in items.values() if x.get("datetime") and (x.get("headline") or "").strip()]
    L.sort(key=lambda x: (x["datetime"], x["id"]))
    return L


def day_coverage(state: dict, universe: list[str], days: list[str]) -> pd.DataFrame:
    """Per (ticker, UTC calendar day): complete = inside a span known complete (a call with n < 150 covers [a, b]; a capped call from
    its oldest item; a single-day fill call of the day counts as complete even when capped, as nothing finer exists)."""
    rows = []
    for tk in universe:
        iv = []
        for c in state.get(tk, {}).get("calls", []):
            if c.get("n") is None:
                continue
            lo, hi = N.day0(c["a"]), N.day0(c["b"]) + 86400
            if c["n"] >= TRUNC_N and c["a"] != c["b"]:
                if c.get("min") is None:
                    continue
                lo = c["min"]
            iv.append((lo, hi))
        iv = N._merge(iv)
        for d in days:
            a = N.day0(d); rows.append({"ticker": tk, "date": d, "complete": any(lo <= a and a + 86400 <= hi for lo, hi in iv)})
    return pd.DataFrame(rows)


def sha(p: Path) -> str:
    h = hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()


def main(dry: bool):
    universe = [l.strip() for l in (ROOT / "_inventory/universe_95.txt").read_text().splitlines() if l.strip()]
    eod = pd.read_parquet(EOD, columns=["ticker", "date", "splitAdjOpen", "splitAdjClose"]); eod["date"] = eod["date"].astype(str).str[:10]
    eod = eod[eod.ticker.isin(universe)]
    cal = Calendar(sorted(eod["date"].unique()))
    old = pd.read_parquet(OLD_FLAGGED, columns=["ticker", "id", "src_pull"]); old_src = {(t, int(i)): s for t, i, s in zip(old.ticker, old.id, old.src_pull)}
    rows = []
    for tk in universe:
        L = load_items(tk, old_src); flag_items(tk, L)
        for x in L:
            rows.append({"ticker": tk, "id": int(x["id"]), "datetime": int(x["datetime"]), "source": x.get("source"), "src_pull": x["src_pull"],
                         "headline": x["headline"], "summary": x.get("summary") or "", "headline_masked": x["headline_masked"],
                         "summary_masked": x["summary_masked"], "first_report": bool(x["first_report"]), "relevant": bool(x["relevant"]),
                         "has_move": bool(x["has_move"]), "n_masks": int(x["n_masks"])})
    I = pd.DataFrame(rows)
    print("items", len(I), "relevant", int(I.relevant.sum()), "by pull", I.src_pull.value_counts().to_dict(), flush=True)
    # ---- time rules
    tv = validate_times(I, eod)
    print("time validation pass:", tv["pass"], tv["failures_corrected"], flush=True)
    # ---- index (relevant items only, corrected times)
    a = I.copy(); a["epoch_raw"] = a.datetime.astype(np.int64); a["epoch"], a["time_rule"] = true_epochs(a.epoch_raw, a.source)
    fr = first_report_corrected(a)
    n = a[a.relevant].copy(); n["first_report_rcf"] = n.first_report
    n["first_report"] = [fr.get((tk, int(i)), True) for tk, i in zip(n.ticker, n.id)]
    n["tp"] = [tp_from_epoch(s) for s in n.epoch]; n["D_min"] = [cal.first_decision_tp(t) for t in n.tp]
    flag, latest = [], []
    for h, s, tp, dmin in zip(n.headline, n.summary.fillna(""), n.tp, n.D_min):
        pub = dt.date(int(tp[:4]), int(tp[4:6]), int(tp[6:8])); ds = mentioned_dates(h + " \n " + s, pub)
        lim = dt.date(int(dmin[:4]), int(dmin[4:6]), int(dmin[6:8])) if dmin else pub
        flag.append(bool([d for d in ds if d > lim])); latest.append(max(ds).isoformat() if ds else None)
    n["date_flag"] = flag; n["latest_mentioned_date"] = latest; n["kept"] = ~n.date_flag & n.D_min.notna()
    n = n.sort_values(["ticker", "tp", "id"]).reset_index(drop=True)
    index = n.drop(columns=["headline", "summary", "headline_masked", "summary_masked"])
    # ---- coverage per day
    state = json.loads((ROOT / "raw/news_finnhub/fetch_state.json").read_text())
    d0, d1 = dt.date(2025, 9, 29), dt.date(2026, 9, 18); days = [(d0 + dt.timedelta(k)).isoformat() for k in range((d1 - d0).days + 1)]
    cov = day_coverage(state, universe, days)
    # ---- comparison with the previous tables
    oi = pd.read_parquet(OLD_INDEX); ok_old = oi[oi.kept]; ok_new = index[index.kept]
    def zero_days(idx, tk, lo, hi):
        have = set(idx[idx.ticker == tk].tp.str[:8]); tds = [d.replace("-", "") for d in cal.days if lo <= d <= hi]
        return sum(1 for d in tds if d not in have)
    TOP = ["NVDA", "AAPL", "MSFT", "AMZN", "AVGO", "JPM", "WMT", "V", "JNJ", "MA", "CSCO", "ORCL", "CVX", "BAC", "PLTR"]
    cmp = {tk: {"kept_before": int((ok_old.ticker == tk).sum()), "kept_after": int((ok_new.ticker == tk).sum()),
                "train_zero_days_before": zero_days(ok_old, tk, "2025-10-06", "2026-03-11"), "train_zero_days_after": zero_days(ok_new, tk, "2025-10-06", "2026-03-11"),
                "test_zero_days_before": zero_days(ok_old, tk, "2026-03-19", "2026-09-17"), "test_zero_days_after": zero_days(ok_new, tk, "2026-03-19", "2026-09-17")} for tk in TOP}
    s5 = [c for v in state.values() for c in v["calls"] if c.get("tag") == "s5"]
    log = {"date": str(dt.date.today()), "items_before": int(len(old)), "items_after": int(len(I)), "relevant_after": int(I.relevant.sum()),
           "kept_before": int(len(ok_old)), "kept_after": int(len(ok_new)), "by_pull": I.src_pull.value_counts().to_dict(),
           "fill_calls": len(s5), "fill_calls_capped_(n>=150)": sum(1 for c in s5 if c.get("trunc")), "fill_calls_n_quantiles": [int(np.percentile([c["n"] for c in s5], q)) for q in (50, 90, 99, 100)] if s5 else None,
           "kept_by_month_before": ok_old.tp.str[:6].value_counts().sort_index().to_dict(), "kept_by_month_after": ok_new.tp.str[:6].value_counts().sort_index().to_dict(),
           "top15": cmp, "time_rules_pass": tv["pass"], "time_rule_counts": index.time_rule.value_counts().to_dict(),
           "date_flag_share": float(n.date_flag.mean()), "first_report_changed_by_correction": int((n.first_report != n.first_report_rcf).sum()),
           "day_coverage_complete_share": {"all": float(cov.complete.mean()), "from_2025-11-07": float(cov[cov.date >= "2025-11-07"].complete.mean()),
                                           "test_2026-03-19..09-18": float(cov[(cov.date >= "2026-03-19")].complete.mean())}}
    print(json.dumps({k: v for k, v in log.items() if k not in ("kept_by_month_before", "kept_by_month_after")}, indent=1, ensure_ascii=False))
    if dry:
        print("(dry run)"); return
    out = ROOT / "news"
    I.to_parquet(out / "news_items_flagged.parquet"); index.to_parquet(out / "items_index.parquet"); cov.to_parquet(out / "day_coverage.parquet", index=False)
    (out / "time_validation.json").write_text(json.dumps(tv, indent=1, default=float))
    stats = {"build": "2026-11-02 rebuild after the single-day Finnhub fill (_scripts/rebuild_news_tables.py)", "tickers": len(universe), "items": int(len(I)),
             "relevant_items": int(len(index)), "date_flagged_dropped": int(index.date_flag.sum()), "kept_items": int(index.kept.sum()),
             "kept_has_move": int((index.kept & index.has_move).sum()), "kept_first_report": int((index.kept & index.first_report).sum()),
             "time_rules_relevant_items": index.time_rule.value_counts().to_dict(), "by_pull": I.src_pull.value_counts().to_dict(),
             "per_ticker": {tk: {"items": int((I.ticker == tk).sum()), "kept": int((index[index.kept].ticker == tk).sum())} for tk in universe}}
    (out / "build_stats.json").write_text(json.dumps(stats, indent=1))
    names = ["news_items_flagged.parquet", "items_index.parquet", "day_coverage.parquet", "time_validation.json", "build_stats.json"]
    mf = out / "MANIFEST.sha256"; lines = [l for l in mf.read_text().splitlines() if not any(l.endswith("/" + nm) for nm in names)]
    lines += [f"{sha(out / nm)}  ./{nm}" for nm in names]; mf.write_text("\n".join(lines) + "\n")
    (ROOT / f"_inventory/news_rebuild_{STAMP}.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n")
    print("written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args(); main(a.dry_run)
