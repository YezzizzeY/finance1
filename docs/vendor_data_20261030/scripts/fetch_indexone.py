"""从 Index One 取数，每一页原样存成一个 JSON 文件（可中断、可续跑）。

Index One 的预览接口每次最多返回 50 行、50 列，所以按"公司 × 列组 × 日期窗口"分页取。
用法: python fetch_indexone.py <输出目录> <任务>...
任务: reference  fundamentals  prices  macro  fx  commodity
"""
import json, os, sys, time
from pathlib import Path

import indexone_client as c

OUT = Path(sys.argv[1])
TASKS = sys.argv[2:]
HERE = Path(__file__).resolve().parent
TICKERS = [t.strip() for t in open(HERE / "universe_tickers.txt") if t.strip()]
MAIN96 = sorted(p.name for p in (HERE.parent / "datasets/agent_trading_days/pit_cache_v2").iterdir())
KEYS_F = ["id", "symbol", "date", "period", "fiscalYear"]
# 每页 2 个调用；两个进程同时跑时各设 4.2 秒，合计每分钟约 57 个调用，低于 60 的上限
MIN_INTERVAL = float(os.environ.get("I1_MIN_INTERVAL", "2.1"))
_last = [0.0]


def page(path, operation, params):
    """取一页并存盘；已存在则跳过。"""
    path = OUT / path
    if path.exists():
        return json.loads(path.read_text())["rows"]
    wait = MIN_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    rows, msg = c.fetch(operation, params, max_rows=50)
    if len(rows) >= 50:
        raise RuntimeError(f"{path}: 50 行满页，窗口太大，可能有遗漏")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps({"operation": operation, "params": params, "message": msg,
                               "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               "rows": rows}, ensure_ascii=False))
    tmp.rename(path)
    return rows


def reference():
    ids = {}
    for i in range(0, len(TICKERS), 40):
        chunk = TICKERS[i:i + 40]
        rows = page(f"reference/page_{i // 40:03d}.json", "core_securities_reference",
                    {"filters": [{"field": "symbol", "operator": "in", "value": [t + ".US" for t in chunk]}],
                     "is_active": False, "is_listed": False, "drop_duplicates": False})
        # 同一代码有多条记录时，优先选仍在交易的那条（例如 OKE 换过证券编号）
        for r in sorted(rows, key=lambda r: (not r["is_active"], not r["primary_listing"])):
            ids.setdefault(r["symbol"][:-3], r["id"])
    # 人工核对过的映射：SATS 这个代码在 Index One 里被另一家公司重用，按 CIK 0001415404 改到 EchoStar；
    # BK 已改名为 BNY（同一家公司）；PSKY 是派拉蒙与天舞合并后的新公司，Index One 记作 SKYD。
    ids.update({"SATS": "BBG000TGLV00", "BK": "BBG000BD8PN9", "PSKY": "BBG01VS5NK99"})
    missing = [t for t in TICKERS if t not in ids]
    (OUT / "reference/ticker_to_id.json").write_text(json.dumps({"ids": ids, "missing": missing}, indent=1))
    print("reference", len(ids), "missing", missing, flush=True)
    return ids


def ids():
    p = OUT / "reference/ticker_to_id.json"
    return json.loads(p.read_text())["ids"] if p.exists() else reference()


def fundamentals():
    cols = c.call("get_operations", {"operation_ids": ["i1_core_fundamentals"]})["operations"]["i1_core_fundamentals"]["output"]["columns"]
    rest = [x for x in cols if x not in KEYS_F]
    groups = [KEYS_F + rest[i:i + 44] for i in range(0, len(rest), 44)]
    # 季度：2015 年起一次取完（最多 47 行）；年度：1985 年起一次取完（最多 41 行）
    windows = {"quarterly": [("2015-01-01", "2030-01-01")], "annual": [("1985-01-01", "2030-01-01")]}
    for n, (t, i) in enumerate(sorted(ids().items())):
        for st, wins in windows.items():
            for a, b in wins:
                for g, attrs in enumerate(groups):
                    page(f"fundamentals_{st}/{t}/{a[:4]}_g{g}.json", "i1_core_fundamentals",
                         {"storage_type": st, "attributes": attrs,
                          "filters": [{"field": "id", "operator": "eq", "value": i},
                                      {"field": "date", "operator": "gte", "value": a},
                                      {"field": "date", "operator": "lt", "value": b}]})
        print("fundamentals", n + 1, t, flush=True)


def months(a, b, step):
    y, m = int(a[:4]), int(a[5:7])
    while f"{y:04d}-{m:02d}-01" < b:
        y2, m2 = y + (m - 1 + step) // 12, (m - 1 + step) % 12 + 1
        yield f"{y:04d}-{m:02d}-01", min(f"{y2:04d}-{m2:02d}-01", b)
        y, m = y2, m2


def prices():
    m = ids()
    for n, t in enumerate(MAIN96):
        for a, b in months("2017-01-01", "2026-11-01", 2):
            page(f"prices_eod/{t}/{a[:7]}.json", "i1_core_eod",
                 {"filters": [{"field": "id", "operator": "eq", "value": m[t]},
                              {"field": "date", "operator": "gte", "value": a},
                              {"field": "date", "operator": "lt", "value": b}]})
        print("prices", n + 1, t, flush=True)


def macro():
    for a, b in months("1990-01-01", "2031-01-01", 48):
        page(f"macro_us/{a[:4]}.json", "i1_core_macro",
             {"filters": [{"field": "country", "operator": "eq", "value": "US"},
                          {"field": "date", "operator": "gte", "value": a},
                          {"field": "date", "operator": "lt", "value": b}]})
    print("macro done", flush=True)


def series(op, folder, symbols):
    for s in symbols:
        for a, b in months("2015-01-01", "2026-11-01", 1):  # 期货周日也有报价，两个月会超过 50 行
            page(f"{folder}/{s}/{a[:7]}.json", op,
                 {"filters": [{"field": "id", "operator": "eq", "value": s},
                              {"field": "date", "operator": "gte", "value": a},
                              {"field": "date", "operator": "lt", "value": b}]})
        print(folder, s, flush=True)


if __name__ == "__main__":
    for task in TASKS:
        if task == "fx":
            series("i1_core_fx", "fx", sys.argv[sys.argv.index("fx") + 1].split(","))
        elif task == "commodity":
            series("i1_core_commodity", "commodity", sys.argv[sys.argv.index("commodity") + 1].split(","))
        elif task in ("reference", "fundamentals", "prices", "macro"):
            globals()[task]()
