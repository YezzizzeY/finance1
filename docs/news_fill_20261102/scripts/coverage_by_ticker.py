"""Per-ticker coverage of every data source in data/, in one table.

Usage:  python _scripts/coverage_by_ticker.py            (run from data/)
Writes _inventory/COVERAGE_BY_TICKER.csv and _inventory/COVERAGE_BY_TICKER.md.

"满足最新要求" = the ticker has every input the current benchmark (4_bench) reads, over the
benchmark window WIN0..WIN1: adjusted daily bars, 1-minute bars, time-corrected news, 8-K events,
earnings announcement times, Form 4 insider transactions, quarterly statements with an SEC
acceptance time inside the window, and a securities reference row.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WIN0, WIN1 = "2025-09-29", "2026-10-29"          # benchmark window: first news day .. last daily bar
TEST_END = "2026-09-17"                           # last test day that still has 30 trading days of outcome


def rng(s: pd.Series):
    unit = "s" if pd.api.types.is_integer_dtype(s) else None          # news index stores epoch seconds
    s = pd.to_datetime(s, errors="coerce", utc=True, unit=unit).dt.tz_localize(None).dropna()
    return (s.min().strftime("%Y-%m-%d"), s.max().strftime("%Y-%m-%d"), len(s)) if len(s) else (None, None, 0)


def main():
    eod = pd.read_parquet(ROOT / "market/daily/indexone_eod_96_20170103_latest.parquet", columns=["ticker", "date"])
    mins = pd.read_parquet(ROOT / "market/intraday_1m/equs_mini_ohlcv1m_96_20250929_20260925.parquet", columns=["symbol", "ts_event"])
    dbd = pd.read_parquet(ROOT / "market/daily/databento_equs_summary_ohlcv1d_20240701_20261028.parquet", columns=["symbol", "date"])
    ref = pd.read_parquet(ROOT / "market/reference/indexone_securities_reference.parquet", columns=["ticker", "name", "sector", "industry"] if "sector" in pd.read_parquet(ROOT / "market/reference/indexone_securities_reference.parquet").columns else ["ticker", "name"])
    mem = pd.read_parquet(ROOT / "market/membership/membership_month_end.parquet")
    news = pd.read_parquet(ROOT / "news/items_index.parquet", columns=["ticker", "epoch", "relevant", "first_report"]).rename(columns={"epoch": "datetime"})   # epoch = corrected time, seconds
    k8 = pd.read_parquet(ROOT / "filings/edgar__events_8k.parquet", columns=["ticker", "acceptance_utc"])
    fil = pd.read_parquet(ROOT / "filings/edgar__filings.parquet", columns=["ticker", "acceptance_utc"])
    ea = pd.read_parquet(ROOT / "filings/edgar__earnings_announce_check.parquet", columns=["ticker", "period_end", "safe_public_utc"])
    ins = pd.read_parquet(ROOT / "filings/secwww__insider_transactions.parquet", columns=["ticker", "acceptance_utc"])
    prs = pd.read_parquet(ROOT / "filings/secwww__press_index.parquet", columns=["ticker", "acceptance_utc"])
    fq = pd.read_parquet(ROOT / "fundamentals/indexone_quarterly.parquet", columns=["ticker", "acceptedDate", "date"])
    sup_path = ROOT / "fundamentals/edgar_quarterly_supplement.parquet"
    if sup_path.exists():                                                      # quarters rebuilt from SEC XBRL (see README)
        fq = pd.concat([fq, pd.read_parquet(sup_path, columns=["ticker", "acceptedDate", "date"])], ignore_index=True)
    fq = fq[pd.to_datetime(fq["acceptedDate"], errors="coerce") >= pd.to_datetime(fq["date"], errors="coerce")]   # drop rows whose period end is after acceptance (vendor errors)
    fil_qk = pd.read_parquet(ROOT / "filings/edgar__filings.parquet", columns=["ticker", "form", "acceptance_utc"])
    fil_qk = fil_qk[fil_qk["form"].isin(["10-Q", "10-K"])]
    last_qk = pd.to_datetime(fil_qk.groupby("ticker")["acceptance_utc"].max(), utc=True).dt.tz_localize(None)   # newest statement filing on EDGAR

    tickers = sorted(set(eod["ticker"]) | set(news["ticker"]) | set(k8["ticker"]) | set(ref["ticker"]))
    last_month = mem["month"].max()
    sp_now = set(mem.loc[mem["month"] == last_month, "ticker"])
    news96 = set(eod["ticker"])
    rows = []
    for tk in tickers:
        r = {"ticker": tk, "news96": tk in news96, "sp500_latest": tk in sp_now, "reference": tk in set(ref["ticker"])}
        a, b, n = rng(eod.loc[eod["ticker"] == tk, "date"]); r.update(eod_start=a, eod_end=b, eod_days=n)
        a, b, n = rng(mins.loc[mins["symbol"] == tk, "ts_event"]); r.update(min_start=a, min_end=b, min_bars=n)
        a, b, n = rng(dbd.loc[dbd["symbol"] == tk, "date"]); r.update(dbd_start=a, dbd_end=b, dbd_days=n)
        nw = news.loc[(news["ticker"] == tk) & (news["relevant"].fillna(True).astype(bool))]
        a, b, n = rng(nw["datetime"]); r.update(news_start=a, news_end=b, news_items=n, news_first_reports=int((nw["first_report"] == True).sum()))
        a, b, n = rng(k8.loc[k8["ticker"] == tk, "acceptance_utc"]); r.update(k8_start=a, k8_end=b, k8_n=n)
        a, b, n = rng(fil.loc[fil["ticker"] == tk, "acceptance_utc"]); r.update(filings_start=a, filings_end=b, filings_n=n)
        e = ea.loc[ea["ticker"] == tk]; a, b, n = rng(e["safe_public_utc"]); r.update(earn_start=a, earn_end=b, earn_n=n)
        a, b, n = rng(ins.loc[ins["ticker"] == tk, "acceptance_utc"]); r.update(insider_start=a, insider_end=b, insider_n=n)
        a, b, n = rng(prs.loc[prs["ticker"] == tk, "acceptance_utc"]); r.update(press_start=a, press_end=b, press_n=n)
        f = fq.loc[fq["ticker"] == tk]; a, b, n = rng(f["acceptedDate"]); r.update(fund_q_start=a, fund_q_end=b, fund_q_n=n)
        r["edgar_last_10q_10k"] = last_qk.get(tk).strftime("%Y-%m-%d") if tk in last_qk.index else None
        r["fund_gap_days"] = (last_qk[tk] - pd.Timestamp(b)).days if (tk in last_qk.index and b) else None   # how far Index One lags the newest 10-Q/10-K
        # window checks (what 4_bench needs)
        inwin = lambda s, lo=WIN0, hi=WIN1: s is not None and s <= hi and s >= lo
        r["ok_eod"] = (r["eod_start"] or "9") <= WIN0 and (r["eod_end"] or "0") >= WIN1
        r["ok_min"] = (r["min_start"] or "9") <= WIN0 and (r["min_end"] or "0") >= "2026-09-24"      # last minute bar in the file is 2026-09-24
        # The pull window is the same for every name (Dow-30 names from 2025-09-29, the other 67 from 2025-10-15, all to
        # 2026-09-18); sparse names simply have their first/last item a few days inside it, so test month boundaries.
        r["ok_news"] = (r["news_start"] or "9") <= "2025-10-31" and (r["news_end"] or "0") >= "2026-09-01"
        r["ok_8k"] = r["k8_n"] > 0 and (r["k8_end"] or "0") >= "2026-03-19"
        r["ok_earn"] = (r["earn_end"] or "0") >= "2026-03-19"
        r["ok_insider"] = r["insider_n"] > 0 and (r["insider_end"] or "0") >= "2026-01-01"
        r["ok_fund"] = r["fund_gap_days"] is not None and r["fund_gap_days"] <= 45      # Index One has the newest statement EDGAR has
        r["ok_ref"] = r["reference"]
        r["meets_current"] = all(r[k] for k in ["ok_eod", "ok_min", "ok_news", "ok_8k", "ok_earn", "ok_insider", "ok_fund", "ok_ref"])
        rows.append(r)
    df = pd.DataFrame(rows)
    out = ROOT / "_inventory"
    df.to_csv(out / "COVERAGE_BY_TICKER.csv", index=False)

    full = df[df["news96"]]
    oks = ["ok_eod", "ok_min", "ok_news", "ok_8k", "ok_earn", "ok_insider", "ok_fund", "ok_ref"]
    names = {"ok_eod": "复权日线覆盖窗口", "ok_min": "分钟线覆盖窗口", "ok_news": "新闻覆盖到 test 末", "ok_8k": "8-K 到 2026-03 后", "ok_earn": "业绩公告时间到 2026-03 后",
             "ok_insider": "内部人交易 2026 年有", "ok_fund": "季报不落后于 EDGAR 最新 10-Q/10-K（45 天内）", "ok_ref": "有基本资料"}
    md = [f"# 按股票的数据覆盖（{pd.Timestamp.today().date()}）\n",
          f"基准窗口 {WIN0} 至 {WIN1}；test 末日 {TEST_END}。表里每一列是一个数据源对该股票的起止日期和条数。完整表在 `COVERAGE_BY_TICKER.csv`（{len(df)} 个代码）。\n",
          f"## 基准股票集合 {len(full)} 只（有复权日线、新闻和分钟线的全集）\n",
          f"满足现在基准全部要求的：**{int(full['meets_current'].sum())} / {len(full)}**。\n",
          "| 要求 | 满足的只数 | 不满足的股票 |", "|---|---|---|"]
    for k in oks:
        bad = sorted(full.loc[~full[k], "ticker"])
        md.append(f"| {names[k]} | {int(full[k].sum())} | {', '.join(bad) if bad else '—'} |")
    md += ["", "| 股票 | 日线 | 分钟线 | 新闻（条） | 8-K（条） | 业绩公告（次） | 内部人交易（笔） | 新闻稿（篇） | 季报（份） | 标普 500 | 满足 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in full.sort_values("ticker").iterrows():
        md.append(f"| {r.ticker} | {r.eod_start}~{r.eod_end} | {r.min_start}~{r.min_end} | {r.news_start}~{r.news_end} ({r.news_items}) | {r.k8_start}~{r.k8_end} ({r.k8_n}) | "
                  f"{r.earn_start}~{r.earn_end} ({r.earn_n}) | {r.insider_start}~{r.insider_end} ({r.insider_n}) | {r.press_n} | {r.fund_q_start}~{r.fund_q_end} ({r.fund_q_n}) | "
                  f"{'是' if r.sp500_latest else '否'} | {'是' if r.meets_current else '否'} |")
    rest = df[~df["news96"]]
    md += ["", f"## 其余 {len(rest)} 个代码（只有公告或基本资料，没有新闻和分钟线）\n",
           f"有 8-K 的 {int((rest['k8_n']>0).sum())}，有业绩公告时间的 {int((rest['earn_n']>0).sum())}，有内部人交易的 {int((rest['insider_n']>0).sum())}，有季报的 {int((rest['fund_q_n']>0).sum())}，有基本资料的 {int(rest['reference'].sum())}。"
           "这些股票没有新闻和分钟线，也没有复权日线（只有 Databento 未复权日线），不能直接进基准。"]
    (out / "COVERAGE_BY_TICKER.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:14]))


if __name__ == "__main__":
    main()
