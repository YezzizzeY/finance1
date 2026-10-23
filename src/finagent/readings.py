"""The PRICE TOOL READINGS block: the outputs of seven price tools on day t, as one labelled section of the day prompt.

compute_block(cache, t) runs each call of BLOCK_CALLS through the harness's own path (toolbox.run_tool on a fresh view, as_of = t,
cut at the tool-result limit), i.e. exactly the string the agent would get by calling that tool on day t. The registered blocks
(data/selection/grounding_blocks.json) were computed this way; insert_block() puts a block just before the prompt's final line.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache

from finagent import config
from finagent.harness import toolbox

# the seven price tools in the order of the block, with the tools' default arguments (get_rsi period 14)
BLOCK_CALLS = (("get_trend_signal", {}), ("get_rsi", {"period": 14}), ("get_mean_reversion_signal", {}), ("get_macd", {}),
               ("get_price_stats", {}), ("get_support_resistance", {}), ("get_volatility_stats", {}))
TOOL_RESULT_CHARS = config.EXPERIMENT["harness"]["tool_result_chars"]
FINAL = "\n\nDecide today's action and call submit_decision."
HEADER = ("PRICE TOOL READINGS (computed for you from the daily price history through today's close; each line is exactly what "
          "the named tool returns today)")
MARKER = "PRICE TOOL READINGS ("
DATE_RX = re.compile(r"20\d\d-\d\d-\d\d")


def _label(name: str, args: dict) -> str:
    return name + (" (" + ", ".join(f"{k} {v}" for k, v in args.items()) + ")" if args else "")


def tool_outputs(cache, t: str) -> list[tuple[str, dict, str]]:
    """[(tool, args, output string)] of BLOCK_CALLS on day t; `cache` is the stock's NewsCache (a fresh view is taken)."""
    view = cache.view()
    as_of = datetime.strptime(t, "%Y-%m-%d")
    state = toolbox.new_state({"cash": 1.0, "shares": 0})          # the seven price tools never read the state
    return [(name, dict(args), toolbox.run_tool(view, as_of, name, dict(args), state)[:TOOL_RESULT_CHARS]) for name, args in BLOCK_CALLS]


def render(outputs: list[tuple[str, dict, str]]) -> str:
    return "\n".join([HEADER] + [f"- {_label(n, a)}: {o}" for n, a, o in outputs])


def compute_block(cache, t: str) -> str:
    return render(tool_outputs(cache, t))


def insert_block(prompt: str, block: str) -> str:
    if prompt.count(FINAL) != 1 or not prompt.endswith(FINAL):
        raise RuntimeError("prompt does not end with the final instruction line exactly once")
    if MARKER in prompt:
        raise RuntimeError("prompt already carries a readings block")
    return prompt[: -len(FINAL)] + "\n\n" + block + FINAL


def block_problems(block: str, t: str) -> list[str]:
    """Checks of one block: seven tool lines, every output valid JSON without an error key, no date after day t."""
    out = []
    lines = block.split("\n")
    if lines[0] != HEADER:
        out.append("header")
    if len(lines) != 1 + len(BLOCK_CALLS):
        out.append(f"{len(lines) - 1} tool lines")
    for (name, args), ln in zip(BLOCK_CALLS, lines[1:]):
        pre = f"- {_label(name, args)}: "
        if not ln.startswith(pre):
            out.append(f"line for {name}"); continue
        try:
            j = json.loads(ln[len(pre):])
        except json.JSONDecodeError:
            out.append(f"{name}: output not JSON"); continue
        if isinstance(j, dict) and "error" in j:
            out.append(f"{name}: tool error {j['error']}")
    late = [d for d in DATE_RX.findall(block) if d > t]
    if late:
        out.append(f"dates after {t}: {late}")
    return out


@lru_cache(maxsize=1)
def registered_blocks() -> dict:
    """{day_id: {"block", "sha256", ...}} of data/selection/grounding_blocks.json (255 days)."""
    return json.loads(config.GROUNDING_BLOCKS.read_text())


def registered_block(day_id: str) -> str:
    return registered_blocks()[day_id]["block"]
