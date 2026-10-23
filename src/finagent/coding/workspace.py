"""The point-in-time workspace of a coding-agent run: prices.csv, news.csv, account.json and task.md of (day, arm), and where
a run lives on the host (<WS_ROOT>/<rid>/work, the agent's cwd, with home/ and tmp/ next to it; its own CODEX_HOME).

task.md = the harness system prompt and day prompt (finagent.harness.prompts, readings block in the arm's form) with the
tool-specific sentences replaced by their file / decision.json equivalents (CODING_REPLACE; each old fragment must occur exactly
once), plus a closing section naming the files and the fields of decision.json (the fields of submit_decision).
  prices.csv    date,open,high,low,close,volume: the daily bars through close t at day t's price level (what the price tools read)
  news.csv      time,headline,summary: every company-news item published before D(t) = 09:00 New York time on the next trading
                day, oldest first (time = YYYYMMDDTHHMMSS New York time, as in the prompt)
  account.json  the ACCOUNT block and the last decisions of the prompt as JSON
The agent's only instruction is AGENT_PROMPT.
"""
from __future__ import annotations

import csv
import io
import json
import secrets
import string
from datetime import datetime
from pathlib import Path

from finagent import config
from finagent.data.pit import news_cache
from finagent.harness.prompts import SYSTEM, day_payload, harness_prompt
from finagent.readings import FINAL as FINAL_HARNESS

FINAL_CODING = "\n\nDecide today's action and write decision.json."
CODING_REPLACE = [
    ("Each user message gives you one trading day's information", "This task gives you one trading day's information"),
    ("You may call the tools to pull more data than the summary contains.",
     "You may read the files in this folder and write and run code to analyse them."),
    ("submit_decision takes the exposure you are targeting (target_exposure_pct) together with\n"
     "the share count that implements it, and replies with the exposure your order actually\n"
     "produces. If that differs from your target, call it again with a corrected share count —\n"
     "the last call is the one that executes.\nFinish every day with submit_decision.",
     "decision.json takes the exposure you are targeting (target_exposure_pct) together with\n"
     "the share count that implements it (one percentage point of exposure in shares is given in\n"
     "the ACCOUNT block). The file you leave in decision.json is the order that executes.\n"
     "Finish the day by writing decision.json."),
    ("With every submit_decision also state your forecast", "In decision.json also state your forecast"),
]
CODING_TAIL = """

FILES IN THIS FOLDER (point-in-time: nothing in them is dated after the information above)
- prices.csv: daily open, high, low, close, volume of {tk} through today's close ({t}), at today's price level
- news.csv: {tk} company news published before 09:00 New York time on the next trading day (time, headline, summary)
- account.json: your account and your last decisions
- task.md: this file

HOW TO WORK
You may read these files and write and run code in this folder. Network access is disabled and you can write only inside this
folder. Use only the information in this folder.

Finish by writing decision.json in this folder: one JSON object with these fields (the fields of submit_decision)
- action: "Buy", "Sell" or "Hold"
- shares: integer number of shares to buy or sell (0 for Hold)
- target_exposure_pct: the exposure you are targeting, percent of total assets
- p_up: probability that the close 5 trading days from now is above today's close, 0-1
- expected_return_pct: the mean 5-day return you expect, percent (may be negative)
- expected_vol_pct: your one-standard-deviation estimate of the 5-day return, percent (5-day one-sd; not annualised and not a
  single-day figure)
- confidence: 0-1, how much information you have for this forecast (how much you would stake on it being accurate)
- reasoning: one or two sentences
"""
AGENT_PROMPT = ("Your task is described in task.md in the current folder. Read it and do it. "
                "Finish by writing decision.json in the current folder.")


def coding_system_text() -> str:
    s = SYSTEM
    for old, new in CODING_REPLACE:
        if s.count(old) != 1:
            raise RuntimeError(f"system fragment not found exactly once: {old[:60]!r}")
        s = s.replace(old, new)
    return s


def task_md(day: dict, arm: str) -> str:
    p = harness_prompt(day, arm)
    if not p.endswith(FINAL_HARNESS):
        raise RuntimeError("prompt does not end with the final instruction line")
    body = p[: -len(FINAL_HARNESS)] + FINAL_CODING
    return ("ROLE AND RULES\n" + coding_system_text() + "\n\n" + "=" * 100 + "\n\n" + body
            + CODING_TAIL.format(tk=day["ticker"], t=day["t"]))


def prices_csv(day: dict) -> str:
    bars = news_cache(day["ticker"]).tool_bars(datetime.strptime(day["t"], "%Y-%m-%d"))
    f = io.StringIO(); w = csv.writer(f, lineterminator="\n")
    w.writerow(["date", "open", "high", "low", "close", "volume"])
    for b in bars:
        w.writerow([b["date"][:10], repr(float(b["open"])), repr(float(b["high"])), repr(float(b["low"])), repr(float(b["close"])),
                    int(b["volume"])])
    return f.getvalue()


def news_items(day: dict) -> list[dict]:
    """Every item of the stock's feed with time_published < D(t), oldest first."""
    c = news_cache(day["ticker"])
    D = c.decision_time(datetime.strptime(day["t"], "%Y-%m-%d"))
    return sorted(c.window("ticker", "0", D), key=lambda i: (i["time_published"], i.get("id", 0)))


def news_csv(day: dict) -> str:
    f = io.StringIO(); w = csv.writer(f, lineterminator="\n")
    w.writerow(["time", "headline", "summary"])
    for i in news_items(day):
        w.writerow([i["time_published"], (i.get("title") or "").replace("\r", " "), (i.get("summary") or "").replace("\r", " ")])
    return f.getvalue()


def account_json(day: dict) -> str:
    payload = day_payload(day)
    price = payload["bars"][0]["close"]; pos = payload["portfolio"]; total = pos["cash"] + pos["shares"] * price
    obj = {"ticker": day["ticker"], "date": day["t"], "close": round(price, 2), "cash": round(pos["cash"], 2), "shares_held": pos["shares"],
           "position_value": round(pos["shares"] * price, 2), "total_assets": round(total, 2),
           "position_pct_of_total_assets": round(pos["shares"] * price / total * 100, 1),
           "shares_per_exposure_point": round(total * 0.01 / price, 1),
           "rules": {"long_only": True, "orders_execute_at": "today's close price", "buy_must_fit_cash": True},
           "last_decisions": [{"date": m["date"], "action": m["action"], "shares": m["shares"], "price": round(m["price"], 2),
                               "exposure_pct": round(m.get("exposure_pct", 0.0), 1), "total_assets": round(m["total_assets"], 0)}
                              for m in payload["memory"]]}
    return json.dumps(obj, indent=1)


def workspace_files(day: dict, arm: str) -> dict[str, str]:
    return {"prices.csv": prices_csv(day), "news.csv": news_csv(day), "account.json": account_json(day), "task.md": task_md(day, arm)}


def new_rid() -> str:
    """A fresh run name: 12 random letters (the agent sees its cwd, so the name shows no date, arm or project)."""
    while True:
        rid = "".join(secrets.choice(string.ascii_lowercase) for _ in range(12))
        if not (Path(config.host("WS_ROOT")) / rid).exists():
            return rid


def run_folders(rid: str) -> dict[str, Path]:
    """The folders of run `rid` on this host: base = WS_ROOT/rid with work (the workspace), home and tmp; its CODEX_HOME."""
    base = Path(config.host("WS_ROOT")) / rid
    return {"base": base, "work": base / "work", "home": base / "home", "tmp": base / "tmp",
            "codex_home": Path(config.host("CODEX_HOME_ROOT")) / "runs" / rid}


def write_workspace(ws: Path, day: dict, arm: str) -> dict:
    ws.mkdir(parents=True, exist_ok=False)
    files = workspace_files(day, arm)
    for name, text in files.items():
        (ws / name).write_text(text, encoding="utf-8")
    return {name: {"chars": len(text)} for name, text in files.items()}

