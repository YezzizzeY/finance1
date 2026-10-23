"""real_day_perturbations: four families of real-headline / real-number prompt perturbations over the
evidence_relations day pool (finagent.evidence_relations.pool), each with its own claimed ground truth and its own
confidence (exact derivation, documented hypothesis, or approximate). CPU only, no GPU, no model calls.

  redundancy_copies        (redundancy.py)  expected shift is zero — exact derivation
  already_priced_in        (priced_in.py)   ordinal hypothesis — FIXED 2026-10-20 to splice only from before day t
  stale_news                (stale.py)       derived, one documented approximation
  position_swap_conflict   (swap.py)        no-flip — exact (tier 1) / approximate (tier 2)

build_all.py assembles all four under evidence_relations/real_day_perturbations/. Ported from
1_overreaction/repro/evidence_relations/real_day_*.py; see common.py for the shared helpers and
evidence_relations/real_day_perturbations/README.md for the full design.
"""
from __future__ import annotations
