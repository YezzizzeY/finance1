"""`finagent <command> [args]` (also `python -m finagent`). Each command is a function main(argv) -> exit code in its own module,
imported only when that command runs; `finagent <command> --help` shows its options.
"""
from __future__ import annotations

import importlib
import sys

COMMANDS: dict[str, tuple[str, str]] = {
    "verify":  ("finagent.verify:main", "L0 / L1 / L2 checks of data, prompts, records and analysis (exit 1 on a failure)"),
    "unpack":  ("finagent.verify:unpack", "extract records/archives into records/raw and verify every file hash"),
    "prompts": ("finagent.promptgen:main", "regenerate data/prompts/ (system texts, tool schemas, example prompts and workspaces)"),
    "analyze": ("finagent.analysis:main", "recompute results/ from the shipped records"),
    "figures": ("finagent.analysis.figures:main", "redraw results/figures/*.svg"),
    "audit":   ("finagent.coding.audit:main", "re-audit the coding-agent runs (leakage flags and reasons)"),
    "days":    ("finagent.days:main", "rebuild the day selection and compare it with data/days.json"),
    "serve":   ("finagent.serve:main", "start, stop or check a local vLLM server"),
    "run":     ("finagent.run:main", "run model x framework cells of the pilot into runs/"),
    "smoke":   ("finagent.run:smoke", "one smoke run per model x framework"),
    "evidence-synthetic":        ("finagent.evidence_relations.synthetic:main",
                                  "regenerate the synthetic two-signal Bayesian benchmark (data/evidence_relations/synthetic/)"),
    "evidence-reference-models": ("finagent.evidence_relations.reference_models:main",
                                  "run bayes_optimal / counting_naive / salience_follower on its test split"),
    "evidence-pool":    ("finagent.evidence_relations.pool:main",
                         "rebuild the day pool (TRAIN/TEST_CORE/TEST_FULL) over all 96 pit_cache tickers"),
    "evidence-real-day": ("finagent.evidence_relations.real_day.build_all:main",
                         "rebuild the four real_day_perturbations families (real headlines/numbers, known ground truth)"),
    "evidence-tools":   ("finagent.evidence_relations.tool_redundancy:main",
                         "rebuild the tool-redundancy matrix (23 tools x 96 tickers x ~248 days)"),
    "mech-salience":    ("finagent.mechanisms.salience:main",
                         "salience: does the big annualised vol number pull the 5-day vol forecast? -> results/mechanisms/salience/"),
    "mech-proximity":   ("finagent.mechanisms.proximity:main",
                         "proximity: does calling the vol tool last give its number more weight? -> results/mechanisms/proximity/"),
    "mech-position":    ("finagent.mechanisms.position_adjustment:main",
                         "position changes against a rational sizing rule -> results/mechanisms/position_adjustment/"),
    "mech-thinking":    ("finagent.mechanisms.thinking:main",
                         "weighing / relating language in 4,000 reasoning texts -> results/mechanisms/thinking/"),
    "mech-page":        ("finagent.mechanisms.page:main",
                         "the four-mechanism page (Chinese) from the four data.json -> results/mechanisms/page/mechanisms.html"),
    "mech-theory-doc":  ("finagent.mechanisms.theory_doc:main",
                         "the good-thinking theory document -> docs/good_thinking/*.docx and docs/GOOD_THINKING.md"),
}


def usage() -> str:
    width = max(map(len, COMMANDS))
    return "usage: finagent <command> [args]\n\ncommands:\n" + "\n".join(
        f"  {name:<{width}}  {text}" for name, (_, text) in COMMANDS.items())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        return 0
    name, rest = argv[0], argv[1:]
    if name not in COMMANDS:
        print(f"finagent: unknown command {name!r}\n\n{usage()}", file=sys.stderr)
        return 2
    module, func = COMMANDS[name][0].split(":")
    return int(getattr(importlib.import_module(module), func)(rest) or 0)
