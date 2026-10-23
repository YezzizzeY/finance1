"""One harness session: the model's tool loop on one trading day (one_session) and the day's bookkeeping (day_step).

Messages are [system, user]; up to MAX_TURNS assistant turns plus at most one reminder. A turn cut by the token cap without a
tool call is sent again with the next seed (it counts toward the limit); the first turn without a tool call and without a
decision gets the REMINDER. Tool results are cut at TOOL_RESULT_CHARS. submit_decision is not executed: it is answered with the
exposure the order would produce, and the last submitted order is applied after the session. The session ends after the first
turn whose calls are all submit_decision.
chat(messages, tools, seed) -> choice is the model (finagent.harness.providers). Two hooks carry the arm (finagent.harness.agent):
prompt_hook(prompt) -> prompt adds the readings block, tool_output_hook(name, output) -> output rewrites a tool output.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import datetime

from finagent import config
from finagent.harness import toolbox
from finagent.harness.prompts import MEMORY_DAYS, REMINDER, SYSTEM, build_day_payload, render_prompt

Chat = Callable[[list[dict], list[dict], int], dict]
_H = config.EXPERIMENT["harness"]
MAX_TURNS = _H["max_turns"]
TOOL_RESULT_CHARS = _H["tool_result_chars"]
TURN_SEED_STEP = _H["turn_seed_step"]
REMINDER_SEED_OFFSET = _H["reminder_seed_offset"]


def finite_float(v):
    """A submitted number as a finite float, else None (booleans, lists and strings such as '3.5%' are rejected): what the
    harness executes and stores in the toolbox memory (the record's lenient reading is records.parse_number)."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def n_shares(v) -> int:
    x = finite_float(v)
    return int(x) if x is not None and abs(x) < 1e12 else 0


def apply_order(portfolio: dict, action: str, shares: int, price: float) -> dict:
    """Execute an order at the close, long only: a buy is clamped to the cash, a sell to the shares held; Hold moves nothing."""
    shares = abs(int(shares or 0))
    requested, clamped = shares, None
    action = (action or "").strip().capitalize()
    if action not in ("Buy", "Sell"):
        return {"executed_shares": 0, "requested_shares": requested, "clamped_by": None,
                "unrecognized_action": None if action == "Hold" else action}
    if action == "Buy":
        affordable = int(portfolio["cash"] // price)
        if shares > affordable:
            shares, clamped = affordable, "cash"
        portfolio["shares"] += shares
        portfolio["cash"] -= shares * price
    elif action == "Sell":
        if shares > portfolio["shares"]:
            shares, clamped = portfolio["shares"], "position"
        portfolio["shares"] -= shares
        portfolio["cash"] += shares * price
    return {"executed_shares": shares, "requested_shares": requested, "clamped_by": clamped}


def submit_reply(args: dict, portfolio: dict, price: float) -> str:
    """The answer to submit_decision: the order filled on a copy of the book, and the gap to the target exposure if > 2 pp."""
    action = str(args.get("action") or "Hold").strip().capitalize(); book = dict(portfolio)
    fill = apply_order(book, action, n_shares(args.get("shares")), price); total = book["cash"] + book["shares"] * price
    realised = book["shares"] * price / total * 100 if total else 0.0
    content = f"recorded: {action} {fill['executed_shares']} @ {price:.2f} -> exposure {realised:.1f}% of assets"
    tgt = finite_float(args.get("target_exposure_pct"))
    if tgt is not None and abs(realised - float(tgt)) > 2:
        content += f" | target was {float(tgt):.0f}% — off by {realised - float(tgt):+.1f}pp. To reach {float(tgt):.0f}% you need {int(float(tgt) / 100 * total / price)} shares held in total."
    return content


def _calls_of(msg: dict) -> list[dict]:
    return [{"name": c["function"]["name"], "arguments": c["function"]["arguments"]} for c in (msg.get("tool_calls") or [])]


def one_session(chat: Chat, cache, date: str, prompt: str, seed: int, portfolio: dict, price: float, tb_state: dict,
                tools: list[dict], turns_out: list, meta_out: list | None = None, trace: list | None = None,
                tool_output_hook: Callable[[str, str], str] | None = None):
    """The tool loop of one day; returns (decision = the last submit's arguments or None, names of the other tools called)."""
    as_of = datetime.strptime(date, "%Y-%m-%d")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    decision, called, reminded, turn = None, [], 0, 0
    while turn < MAX_TURNS + reminded:
        turn += 1
        ch = chat(messages, tools, seed + TURN_SEED_STEP * turn)
        msg, finish = ch["message"], ch.get("finish_reason"); calls = msg.get("tool_calls") or []
        sub = [c for c in calls if c["function"]["name"] == "submit_decision"]
        if ch.get("_gen_ids"):                                                # token ids (vLLM only)
            turns_out.append((ch["_prompt_ids"], ch["_gen_ids"]))
            if meta_out is not None:
                meta_out.append({"submit": bool(sub)})
        if trace is not None:
            trace.append({"turn": turn, "finish": finish, "reasoning": msg.get("reasoning") or msg.get("reasoning_content") or "",
                          "content": msg.get("content") or "", "tool_calls": _calls_of(msg)})
        if not calls and finish == "length":
            continue
        if not calls:
            if decision is None and reminded == 0:
                messages.append({"role": "assistant", "content": msg.get("content") or ""})
                messages.append({"role": "user", "content": REMINDER}); reminded += 1
                continue
            break
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            if name == "submit_decision":
                decision = args; content = submit_reply(args, portfolio, price)
            else:
                called.append(name); out = toolbox.run_tool(cache, as_of, name, args, tb_state)
                content = (tool_output_hook(name, out) if tool_output_hook else out)[:TOOL_RESULT_CHARS]
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "name": name, "content": content})
            if trace is not None:
                trace.append({"tool": name, "args": args, "result": content})
        if decision is not None and all(c["function"]["name"] == "submit_decision" for c in calls):
            break                                                             # submitted and nothing else pending
    if decision is None and reminded == 0:
        messages.append({"role": "user", "content": REMINDER}); ch = chat(messages, tools, seed + REMINDER_SEED_OFFSET)
        sub = [c for c in (ch["message"].get("tool_calls") or []) if c["function"]["name"] == "submit_decision"]
        if ch.get("_gen_ids"):
            turns_out.append((ch["_prompt_ids"], ch["_gen_ids"]))
            if meta_out is not None:
                meta_out.append({"submit": bool(sub)})
        if trace is not None:
            trace.append({"turn": "reminder", "reasoning": ch["message"].get("reasoning") or "", "content": ch["message"].get("content") or "",
                          "tool_calls": _calls_of(ch["message"])})
        for call in (ch["message"].get("tool_calls") or []):
            if call["function"]["name"] == "submit_decision":
                try:
                    decision = json.loads(call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    decision = None
                if not isinstance(decision, dict):
                    decision = None
    return decision, called


def day_step(chat: Chat, outcomes, ticker: str, cache, tools: list[dict], st: dict, date: str, seed: int, *,
             trace: list | None = None, prompt_hook: Callable[[str], str] | None = None,
             tool_output_hook: Callable[[str, str], str] | None = None) -> dict:
    """One trading day from state st = {portfolio, memory, tb_state}: the session, then the order; mutates st, returns the step."""
    portfolio, tb_state = st["portfolio"], st["tb_state"]
    payload = build_day_payload(cache, date, {**portfolio}, st["memory"]); price = payload["bars"][0]["close"]
    prompt = render_prompt(payload, ticker)
    if prompt_hook:
        prompt = prompt_hook(prompt)
    turns, meta = [], []
    if trace is not None:
        trace.append({"system": SYSTEM, "user": prompt})
    dec, called = one_session(chat, cache, date, prompt, seed, portfolio, price, tb_state, tools, turns, meta_out=meta, trace=trace,
                              tool_output_hook=tool_output_hook)
    dec = dec or {}
    action = str(dec.get("action") or "Hold").strip().capitalize(); fill = apply_order(portfolio, action, n_shares(dec.get("shares")), price)
    total = portfolio["cash"] + portfolio["shares"] * price; exposure = portfolio["shares"] * price / total
    entry = {"date": date, "action": action, "shares": fill["executed_shares"], "price": price, "total_assets": total, "exposure_pct": exposure * 100}
    st["memory"] = (st["memory"] + [entry])[-MEMORY_DAYS:]

    def f(k):
        return finite_float(dec.get(k))
    tb_state["memory"].append({**entry, "p_up": f("p_up"), "mu": f("expected_return_pct"), "sigma": f("expected_vol_pct"), "reasoning": dec.get("reasoning")})
    tb_state["trades"].append({"date": date, "action": action.lower(), "shares": fill["executed_shares"], "price": price, "total_assets": round(total, 2), "exposure_pct": round(exposure * 100, 1)})
    sg = f("expected_vol_pct"); parsed = None
    if sg is not None and sg > 0:
        parsed = {"sigma": abs(sg), "mu": f("expected_return_pct") or 0.0, "p_up": f("p_up") if f("p_up") is not None else 0.5, "confidence": f("confidence")}
    r1, r5 = outcomes.realised(ticker, date)
    return {"day": date, "parsed": parsed, "real1": r1, "real5": r5, "rv5": outcomes.realised_var5(ticker, date), "exposure": exposure,
            "tools": called, "n_turns": len(turns), "turns": turns, "turn_meta": meta, "submitted": bool(dec), "decision": dec}
