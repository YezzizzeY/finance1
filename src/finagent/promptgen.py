"""`finagent prompts`: write every text the models saw into data/prompts/, or check that the files there are still exact.

  harness_system.txt  coding_system.txt  agent_prompt.txt  permissions.txt  reminder.txt  tools.json (the 32 schemas, indented)
  examples/<day_id>/{prices.csv, news.csv, account.json}               the coding workspace files (the same for every arm)
  examples/<day_id>/<ARM>/{harness_prompt.txt, task.md}                the first user message of the harness and task.md
Texts are written byte for byte (UTF-8, no added newline), so `sha256sum` of a file is the hash of the text.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from finagent import config, days
from finagent.coding import workspace
from finagent.coding.codex import PERMISSIONS_TEXT
from finagent.harness import prompts


def prompt_files() -> dict[str, str]:
    """{path relative to data/prompts/: text}."""
    out = {"harness_system.txt": prompts.SYSTEM, "coding_system.txt": workspace.coding_system_text(),
           "agent_prompt.txt": workspace.AGENT_PROMPT, "permissions.txt": PERMISSIONS_TEXT, "reminder.txt": prompts.REMINDER,
           "tools.json": json.dumps(prompts.harness_tools(), indent=1, ensure_ascii=False) + "\n"}
    for d in days.load():
        ex = f"examples/{d['day_id']}"
        out[f"{ex}/prices.csv"] = workspace.prices_csv(d)
        out[f"{ex}/news.csv"] = workspace.news_csv(d)
        out[f"{ex}/account.json"] = workspace.account_json(d)
        for arm in config.ARMS:
            out[f"{ex}/{arm}/harness_prompt.txt"] = prompts.harness_prompt(d, arm)
            out[f"{ex}/{arm}/task.md"] = workspace.task_md(d, arm)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent prompts", description="Regenerate data/prompts/ (or --check it).")
    ap.add_argument("--check", action="store_true", help="compare with the files in data/prompts/ instead of writing")
    ap.add_argument("--out", type=Path, default=config.PROMPTS, help="target folder (default: data/prompts/)")
    a = ap.parse_args(argv)
    files = prompt_files()
    if a.check:
        bad = [rel for rel, text in files.items()
               if not (a.out / rel).exists() or (a.out / rel).read_bytes() != text.encode("utf-8")]
        extra = sorted({q.relative_to(a.out).as_posix() for q in a.out.rglob("*") if q.is_file()} - set(files) - {"README.md"})
        print(f"{len(files) - len(bad)} of {len(files)} files in {a.out} are exact" + "".join(f"\n  differs: {x}" for x in bad)
              + "".join(f"\n  not generated: {x}" for x in extra))
        return 1 if bad or extra else 0
    for rel, text in files.items():
        p = a.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {a.out}")
    return 0
