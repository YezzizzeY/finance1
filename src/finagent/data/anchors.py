"""The saved starting state of each decision day: the Qwen3-8B S1 anchor sessions on days t-2 and t-1.

Every run of a day starts from the same saved state (data/anchors/<day_id>.json.gz, key "state"): the book, the last
decisions shown in the prompt, and the toolbox state (memory, notes, trades) that the memory tools read.
"""
from __future__ import annotations

import copy

from finagent import config
from finagent.records import load_gz


def state_from_json(js: dict) -> dict:
    """{portfolio, memory, tb_state}: a fresh deep copy whose book is shared by the account and the toolbox state."""
    js = copy.deepcopy(js)
    return {"portfolio": js["portfolio"], "memory": js["memory"], "tb_state": {"portfolio": js["portfolio"], **js["tb_state"]}}


def load_anchor(day_id: str) -> dict:
    return load_gz(config.anchor_file(day_id))


def anchor_state(day_id: str) -> dict:
    return state_from_json(load_anchor(day_id)["state"])
