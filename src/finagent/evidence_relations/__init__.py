"""Evidence-relations extension of the presentation pilot: how an agent should combine, discount or ignore
pieces of evidence. Two independent families, both CPU only, no GPU, no model calls:

  * **Real-day** (day_pool, real_day_perturbations, tool_redundancy): the day pool over all 96 `data/pit_cache`
    tickers, real-day prompt perturbations with a known ground truth, and an empirical tool-redundancy matrix.
    Every file is produced by pure, deterministic code from `data/` (and the point-in-time caches it carries
    for all 96 tickers, not just the six pilot ones) through finagent's own modules (finagent.days, finagent.
    readings, finagent.arms, finagent.harness.prompts, finagent.harness.toolbox, finagent.data.pit) — nothing
    here reimplements prompt rendering, block parsing, point-in-time cutoffs or tool execution.
  * **Synthetic** (synthetic, bayes, reference_models): a synthetic two-signal Bayesian benchmark with its own
    RNG, no dependency on `data/` or any other finagent module's data -- the redundancy-discount, staleness and
    conflict-resolution questions, with a closed-form Bayes-optimal answer (bayes.py) to check a model, or the
    three deterministic reference forecasters (reference_models.py), against.

Both are ported from the already-verified, already-run 1_overreaction/repro/evidence_relations build
(same math, same seeds); the real-day family onto this repository's own 96-ticker cache and toolbox instead of
that project's, the synthetic family unchanged (it never touched that project's price/news data to begin with).
Every output folder under `ROOT` (the four inputs/benchmark pieces, under data/, since none of this is an input
the pilot itself reads but all of it is still an input/benchmark definition) or under `RESULTS_ROOT` (reference_
models/, an analysis output, under results/) carries its own README.md with the exact design and a source-vs-port
comparison of every count; this package's submodules carry the derivation.

    finagent evidence-pool                day pool: TRAIN/TEST_CORE/TEST_FULL -> data/evidence_relations/day_pool/
    finagent evidence-real-day            the four real_day_perturbations families -> data/evidence_relations/real_day_perturbations/
    finagent evidence-tools               the tool-redundancy matrix -> data/evidence_relations/tool_redundancy/
    finagent evidence-synthetic           the synthetic two-signal benchmark -> data/evidence_relations/synthetic/
    finagent evidence-reference-models    bayes_optimal / counting_naive / salience_follower on its test split
                                           -> results/evidence_relations/reference_models/
"""
from __future__ import annotations

from finagent import config

ROOT = config.EVIDENCE_RELATIONS_DATA          # data/evidence_relations: day_pool/, real_day_perturbations/,
                                                # tool_redundancy/, synthetic/ (inputs/benchmark definitions)
RESULTS_ROOT = config.EVIDENCE_RELATIONS_RESULTS   # results/evidence_relations: reference_models/ (an analysis output)
