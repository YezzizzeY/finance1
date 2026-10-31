"""下载 Databento 行情原始文件（CSV + zstd 压缩，原样保存）。

用法: python fetch_databento.py <输出目录>
- 96 只主实验股票的 1 分钟 K 线（EQUS.MINI，2025-09-29 至 2026-09-25），按月分段
- 全美股票日线（EQUS.SUMMARY，2024-07-01 至 2026-10-29）
钥匙在运行时从 keys.txt 读取，不写入任何文件。
"""
import base64, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
KEY = re.search(r"db-[A-Za-z0-9]+", next(l for l in open("/srv/shared_home/lmz/ai/keys.txt") if l.lower().startswith("databento"))).group(0)
AUTH = "Basic " + base64.b64encode(f"{KEY}:".encode()).decode()
BASE = "https://hist.databento.com/v0/"
SYMS = sorted(os.listdir(Path(__file__).resolve().parents[1] / "datasets/agent_trading_days/pit_cache_v2"))

def post(ep, **kw):
    req = urllib.request.Request(BASE + ep, urllib.parse.urlencode(kw).encode(), {"Authorization": AUTH})
    return urllib.request.urlopen(req, timeout=1800)

def get(name, **kw):
    dst = OUT / name
    if dst.exists() and dst.stat().st_size > 0:
        return
    cost = float(post("metadata.get_cost", **{k: v for k, v in kw.items() if k in ("dataset", "schema", "start", "end", "symbols", "stype_in")}).read())
    tmp = dst.with_suffix(".part")
    with post("timeseries.get_range", encoding="csv", compression="zstd", map_symbols="true",
              pretty_px="true", pretty_ts="true", **kw) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dst)
    with open(OUT / "requests.jsonl", "a") as log:
        log.write(json.dumps({"file": name, "cost_usd": round(cost, 4), "bytes": dst.stat().st_size,
                              "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kw}) + "\n")
    print(name, f"${cost:.2f}", dst.stat().st_size, flush=True)

months = ["2025-09-29", "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
          "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01", "2026-09-25"]
for a, b in zip(months, months[1:]):
    get(f"equs_mini_ohlcv1m_96_{a}_{b}.csv.zst", dataset="EQUS.MINI", schema="ohlcv-1m",
        start=a, end=b, symbols=",".join(SYMS), stype_in="raw_symbol")
get("equs_summary_ohlcv1d_all_2024-07-01_2026-10-29.csv.zst", dataset="EQUS.SUMMARY", schema="ohlcv-1d",
    start="2024-07-01", end="2026-10-29", symbols="ALL_SYMBOLS", stype_in="raw_symbol")
print("done")
