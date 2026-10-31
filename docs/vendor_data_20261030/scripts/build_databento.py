"""把 raw/databento_20261030/ 的 CSV 原件整理成 parquet。

用法: python build_databento.py intraday | daily
- intraday: 96 只股票 1 分钟 K 线 -> market/intraday_1m/
- daily:    全美股票日线 -> market/daily/
"""
import glob, io, json, sys
from pathlib import Path

import pandas as pd
import zstandard

DATA = Path(__file__).resolve().parents[1]
RAW = DATA / "raw/databento_20261030"


def read(path):
    with open(path, "rb") as f:
        text = zstandard.ZstdDecompressor().stream_reader(f).read()
    d = pd.read_csv(io.BytesIO(text), dtype={"symbol": "string"})
    d["ts_event"] = pd.to_datetime(d["ts_event"], utc=True)
    return d


def write(d, out, note):
    out.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out, index=False)
    meta = {"rows": len(d), "symbols": int(d["symbol"].nunique()),
            "ts_min_utc": str(d["ts_event"].min()), "ts_max_utc": str(d["ts_event"].max()), **note}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(out.name, meta)


def intraday():
    parts = sorted(glob.glob(str(RAW / "equs_mini_ohlcv1m_96_*.csv.zst")))
    d = pd.concat([read(p) for p in parts], ignore_index=True)
    d = d.drop(columns=["rtype"]).sort_values(["symbol", "ts_event"], kind="stable").reset_index(drop=True)
    dup = d.duplicated(["symbol", "ts_event"]).sum()
    assert dup == 0, f"{dup} 条重复的 (股票, 时间)"
    write(d, DATA / "market/intraday_1m/equs_mini_ohlcv1m_96_20250929_20260925.parquet",
          {"source": "Databento EQUS.MINI ohlcv-1m", "raw_files": [Path(p).name for p in parts],
           "price_adjustment": "未复权（成交原价）",
           "timestamp": "ts_event 是这一分钟开始的时间（UTC）；没有成交的分钟没有记录"})


def daily():
    parts = sorted(glob.glob(str(RAW / "batch_EQUS-*/equs-summary-*.ohlcv-1d.csv.zst")))
    d = pd.concat([read(p) for p in parts], ignore_index=True)
    d = d.drop(columns=["rtype"]).sort_values(["symbol", "ts_event"], kind="stable").reset_index(drop=True)
    d.insert(0, "date", d["ts_event"].dt.strftime("%Y-%m-%d"))
    write(d, DATA / "market/daily/databento_equs_summary_ohlcv1d_20240701_20261028.parquet",
          {"source": "Databento EQUS.SUMMARY ohlcv-1d（各交易所官方收盘汇总）", "raw_files": [Path(p).name for p in parts],
           "price_adjustment": "未复权（成交原价）"})


if __name__ == "__main__":
    {"intraday": intraday, "daily": daily}[sys.argv[1]]()
