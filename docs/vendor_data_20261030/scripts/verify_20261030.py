"""核对 2026-10-30 新增的数据，结果写到 _inventory/verify_20261030.json。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1]
out = {}


def ret_match(a, b, key):
    """两份价格按 (股票, 日期) 对齐后，比较日收益率。"""
    j = a.merge(b, on=["symbol", "date"]).sort_values(["symbol", "date"])
    j["ra"] = j.groupby("symbol")["pa"].pct_change()
    j["rb"] = j.groupby("symbol")["pb"].pct_change()
    d = (j["ra"] - j["rb"]).abs().dropna()
    out[key] = {"pairs": int(len(d)), "symbols": int(j["symbol"].nunique()),
                "median_abs_diff": float(d.median()), "share_within_0.2pct": float((d < 0.002).mean()),
                "share_over_2pct": float((d > 0.02).mean())}
    return j


stratos = pd.read_parquet(DATA / "market/daily/us_daily_stratos_20260924.parquet")
stratos = pd.DataFrame({"symbol": stratos["Ticker"], "date": pd.to_datetime(stratos["Date"]).dt.strftime("%Y-%m-%d"),
                        "pb": stratos["Close"]})

# 1. 1 分钟 K 线：每天常规交易时段最后一根的收盘价，对比主实验日线
m = pd.read_parquet(DATA / "market/intraday_1m/equs_mini_ohlcv1m_96_20250929_20260925.parquet")
et = m["ts_event"].dt.tz_convert("America/New_York")
mins = et.dt.hour * 60 + et.dt.minute
r = m[(mins >= 570) & (mins < 960)].assign(date=et.dt.strftime("%Y-%m-%d"))
c = r.groupby(["symbol", "date"])["close"].last().rename("pa").reset_index()
ret_match(c, stratos, "intraday_1m_vs_stratos_daily")
del m, r

# 2. 全市场日线（未复权）对比主实验日线（已复权）：除息日和拆股日以外应一致
d = pd.read_parquet(DATA / "market/daily/databento_equs_summary_ohlcv1d_20240701_20261028.parquet",
                    columns=["date", "symbol", "close"])
ret_match(d.rename(columns={"close": "pa"}), stratos, "databento_daily_vs_stratos_daily")

# 3. Index One 日线（拆股和分红复权）对比主实验日线
p = DATA / "market/daily/indexone_eod_96_20170103_latest.parquet"
if p.exists():
    i1 = pd.read_parquet(p, columns=["ticker", "date", "adjClose"]).rename(columns={"ticker": "symbol", "adjClose": "pa"})
    j = ret_match(i1, stratos, "indexone_adj_vs_stratos_daily")
    ext = pd.read_parquet(DATA / "market/daily/us_daily_ext2017.parquet")
    ext = pd.DataFrame({"symbol": ext["Ticker"], "date": pd.to_datetime(ext["Date"]).dt.strftime("%Y-%m-%d"), "pb": ext["Close"]})
    ret_match(i1, ext, "indexone_adj_vs_ext2017_daily")

# 4. 基本资料：Index One 的 CIK 与项目已有的代码—CIK 对照表
ref = pd.read_parquet(DATA / "market/reference/indexone_securities_reference.parquet")
ec = pd.read_csv(DATA / "filings/edgar__ticker_cik.csv")
k = ref.merge(ec[["ticker", "cik"]], on="ticker", suffixes=("_i1", "_edgar"))
k = k[k["cik_i1"].notna()]
same = k["cik_i1"].astype(int) == k["cik_edgar"].astype(int)
out["reference_cik_check"] = {"tickers_compared": int(len(k)), "same_cik": int(same.sum()),
                              "different": k.loc[~same, "ticker"].tolist()}

# 5. 财报覆盖
for st in ("quarterly", "annual"):
    p = DATA / f"fundamentals/indexone_{st}.parquet"
    if p.exists():
        f = pd.read_parquet(p, columns=["ticker", "date", "filingDate", "acceptedDate"])
        n = f.groupby("ticker").size()
        lag = (pd.to_datetime(f["filingDate"]) - pd.to_datetime(f["date"])).dt.days
        rec = f[f["date"] >= "2015-01-01"]
        out[f"fundamentals_{st}"] = {"tickers": int(n.size), "rows": int(len(f)), "median_rows_per_ticker": float(n.median()),
                                     "date_min": f["date"].min(), "date_max": f["date"].max(),
                                     "median_days_period_end_to_filing_since_2015": float(lag[f["date"] >= "2015-01-01"].median()),
                                     "share_rows_with_acceptedDate_since_2015": float(rec["acceptedDate"].notna().mean())}

(DATA / "_inventory/verify_20261030.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps(out, indent=1, ensure_ascii=False))
