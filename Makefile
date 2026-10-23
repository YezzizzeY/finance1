# Every step is one `finagent` command (`python -m finagent --help` lists them all). `make` alone lists the targets.
PY ?= python3.12
PYTHON ?= .venv/bin/python

.PHONY: help setup unpack verify analyze audit prompts figures test clean evidence-pool evidence-real-day evidence-tools \
       evidence-synthetic evidence-reference-models mechanisms mech-salience mech-proximity mech-position mech-thinking \
       mech-page mech-theory-doc
.DEFAULT_GOAL := help

help:     # this list
	@awk -F ':[^#]*# *' '/^[a-z-]+:.*#/ {printf "  %-18s %s\n", $$1, $$2}' Makefile

setup:    # .venv with the pilot's exact runner pins, then this package (editable, with pytest)
	$(PY) -m venv .venv
	.venv/bin/pip install -r setup/requirements/runner.txt
	.venv/bin/pip install -e ".[test]"

unpack:   # records/archives/*.tar.xz -> records/raw/, every file hash-checked
	$(PYTHON) -m finagent unpack

records/raw:
	$(PYTHON) -m finagent unpack

verify: records/raw   # L0 (the repository), L1 (records and results), L2 (the audit)
	$(PYTHON) -m finagent verify

analyze: records/raw  # results/ recomputed from the shipped records
	$(PYTHON) -m finagent analyze

audit: records/raw    # re-audit of the 150 coding-agent runs, with the original host's paths (setup/host.recorded.env)
	$(PYTHON) -m finagent audit

prompts:  # data/prompts/ regenerated from data/ (byte-identical to what the models saw)
	$(PYTHON) -m finagent prompts

figures:  # results/figures/*.svg
	$(PYTHON) -m finagent figures

test: records/raw     # one test per verify check, plus the golden-fixture unit tests
	$(PYTHON) -m pytest -q

clean:    # unpacked records and build leftovers; new runs in runs/ are kept
	rm -rf records/raw build .pytest_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

evidence-pool:      # day pool (TRAIN/TEST_CORE/TEST_FULL, 96 tickers) -> data/evidence_relations/day_pool/pool.jsonl
	$(PYTHON) -m finagent evidence-pool

evidence-real-day: evidence-pool   # the four real_day_perturbations families -> data/evidence_relations/real_day_perturbations/
	$(PYTHON) -m finagent evidence-real-day

evidence-tools:     # tool-redundancy matrix (23 tools x 96 tickers) -> data/evidence_relations/tool_redundancy/
	$(PYTHON) -m finagent evidence-tools --workers 32

evidence-synthetic:          # synthetic two-signal Bayesian benchmark -> data/evidence_relations/synthetic/*.jsonl.xz
	$(PYTHON) -m finagent evidence-synthetic

evidence-reference-models: evidence-synthetic   # bayes_optimal/counting_naive/salience_follower -> results/evidence_relations/reference_models/
	$(PYTHON) -m finagent evidence-reference-models

mechanisms: mech-salience mech-proximity mech-position mech-thinking mech-page mech-theory-doc   # all six below, in order (CPU only, about 30 s)

mech-salience:      # salience of the annualised vol number -> results/mechanisms/salience/data.json
	$(PYTHON) -m finagent mech-salience

mech-proximity:     # calling position of the vol tool -> results/mechanisms/proximity/data.json
	$(PYTHON) -m finagent mech-proximity

mech-position:      # position changes vs the rational sizing rule -> results/mechanisms/position_adjustment/data.json
	$(PYTHON) -m finagent mech-position

mech-thinking:      # weighing / relating language in 4,000 reasoning texts -> results/mechanisms/thinking/data.json
	$(PYTHON) -m finagent mech-thinking

mech-page:          # the four-mechanism page from the four data.json -> results/mechanisms/page/mechanisms.html
	$(PYTHON) -m finagent mech-page

mech-theory-doc:    # the good-thinking theory document -> docs/good_thinking/good_thinking_20261023.docx, docs/GOOD_THINKING.md
	$(PYTHON) -m finagent mech-theory-doc
