"""把 raw/indexone_20261030/ 的分页原件拼成 parquet。

用法: python build_indexone.py reference | fundamentals | prices | macro | series
"""
import glob, json, sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1]
RAW = DATA / "raw/indexone_20261030"
KEYS_F = ["id", "symbol", "date", "period", "fiscalYear"]


def pages(pattern):
    return [json.loads(Path(p).read_text()) for p in sorted(glob.glob(str(RAW / pattern)))]


def id_map():
    m = json.loads((RAW / "reference/ticker_to_id.json").read_text())
    return m["ids"], m["missing"]


def write(d, rel, note):
    out = DATA / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out, index=False)
    meta = {"rows": len(d), "columns": len(d.columns), **note}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(rel, {k: v for k, v in meta.items() if k in ("rows", "columns", "tickers")})


def reference():
    ids, missing = id_map()
    rows = [r for p in pages("reference/page_*.json") + pages("reference/extra_*.json") for r in p["rows"]]
    ref = pd.DataFrame(rows).drop_duplicates("id")
    tick = pd.DataFrame(sorted(ids.items()), columns=["ticker", "id"])
    d = tick.merge(ref, on="id", how="left")
    # 人工改过映射的三只（SATS、BK、PSKY）不在按代码查到的那批里，单独补查的结果在 extra_*.json
    write(d, "market/reference/indexone_securities_reference.parquet",
          {"source": "Index One core_securities_reference", "tickers": len(d), "not_found": missing,
           "manual_mapping": {"SATS": "EchoStar（Index One 代码 ECHO，CIK 0001415404）",
                              "BK": "同一家公司，现代码 BNY", "PSKY": "派拉蒙与天舞合并后的公司，Index One 代码 SKYD"},
           "note": "listed_at/delisted_at/sector/industry/shares_outstanding/float_factor 是取数当天（2026-10-30）的状态，不是历史时点数据"})


def fundamentals():
    ids, _ = id_map()
    tick = {v: k for k, v in ids.items()}
    for st in ("quarterly", "annual"):
        frames, seen = [], set()
        for folder in sorted(glob.glob(str(RAW / f"fundamentals_{st}/*"))):
            # BK 与 BNY、SATS 与 ECHO 是同一只证券，各取过一次，只留一份
            if ids[Path(folder).name] in seen:
                continue
            seen.add(ids[Path(folder).name])
            groups = {}
            for p in sorted(glob.glob(folder + "/*_g*.json")):
                g = p.rsplit("_g", 1)[1][:-5]
                groups.setdefault(g, []).extend(json.loads(Path(p).read_text())["rows"])
            parts = [pd.DataFrame(v) for _, v in sorted(groups.items()) if v]
            if not parts:
                continue
            d = parts[0]
            for x in parts[1:]:
                d = d.merge(x, on=KEYS_F, how="outer")
            frames.append(d)
        d = pd.concat(frames, ignore_index=True)
        d.insert(0, "ticker", d["id"].map(tick))
        d = d.sort_values(["ticker", "date", "period"]).reset_index(drop=True)
        assert not d.duplicated(KEYS_F).any()
        n_fy = int(d.duplicated(["id", "date", "period"], keep=False).sum())
        write(d, f"fundamentals/indexone_{st}.parquet",
              {"source": f"Index One i1_core_fundamentals（{st}）", "tickers": int(d["ticker"].nunique()),
               "rows_same_period_different_fiscalYear": n_fy,
               "same_security": "BK 与 BNY、SATS 与 ECHO 是同一只证券，只存一份，ticker 列用项目里的旧代码 BK 和 SATS",
               "time_columns": "date=报告期末；filingDate=提交日；acceptedDate=SEC 接收时间（美东）。"
                               "用于回测时必须按 acceptedDate 判断可见性；1990 年代早期的提交日常常等于报告期末，不可信"})


def prices():
    ids, _ = id_map()
    tick = {v: k for k, v in ids.items()}
    rows = [r for p in pages("prices_eod/*/*.json") for r in p["rows"]]
    d = pd.DataFrame(rows)
    d.insert(0, "ticker", d["id"].map(tick))
    d = d.sort_values(["ticker", "date"]).reset_index(drop=True)
    assert not d.duplicated(["id", "date"]).any()
    write(d, "market/daily/indexone_eod_96_20170103_latest.parquet",
          {"source": "Index One i1_core_eod", "tickers": int(d["ticker"].nunique()),
           "date_min": d["date"].min(), "date_max": d["date"].max(),
           "price_adjustment": "close 等是成交原价；splitAdj* 只按拆股复权；adj* 按拆股和分红复权"})


def macro():
    rows = [r for p in pages("macro_us/*.json") for r in p["rows"]]
    d = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    write(d, "macro/indexone/country_macro_us_monthly.parquet",
          {"source": "Index One i1_core_macro（country=US）",
           "note": "每月一行；avail_date 是这一行最新数值的保守公布日，回测时按 avail_date 做时点对齐；is_forecast=True 的行是预测值"})


def series():
    for kind in ("commodity", "fx"):
        rows = [r for p in pages(f"{kind}/*/*.json") for r in p["rows"]]
        if not rows:
            continue
        d = pd.DataFrame(rows).sort_values(["id", "date"]).reset_index(drop=True)
        write(d, f"macro/indexone/{kind}_daily.parquet",
              {"source": f"Index One i1_core_{kind}", "series": sorted(d["id"].unique().tolist())})


if __name__ == "__main__":
    for task in sys.argv[1:]:
        globals()[task]()
