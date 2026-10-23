"""finagent.mechanisms.thinking: the shipped results/mechanisms/thinking/data.json is exactly what build() computes
from data/mechanisms/sessions/, the computation is deterministic, and the matching rules behave as documented."""
from __future__ import annotations

import json

import pytest

from finagent import config
from finagent.mechanisms import thinking as M


@pytest.fixture(scope="module")
def built():
    return M.build()


def test_build_reproduces_shipped_data_json(built):
    assert M.dumps(built) == M.OUT_FILE.read_text(encoding="utf-8")


def test_build_is_deterministic(built):
    assert M.dumps(M.build()) == M.dumps(built)


def test_headline_numbers(built):
    o = built["rates"]["overall"]
    assert (o["n"], o["k_weighing"], o["k_relationship"], o["k_neither"]) == (4000, 2816, 3608, 132)
    c4 = built["check4_news_volatility_connection"]
    w2 = c4["window2_sensitivity"]
    assert (c4["n_eligible"], c4["n_connects_same_sentence"], w2["n_connects_2sentence_window"]) == (916, 26, 191)
    hc = built["precision_handcheck"]
    assert hc["weighing_judgment"]["rough_precision_pct_wilson95_ci"] == [50.5, 89.8]
    assert hc["relationship_judgment"]["rough_precision_strict_pct_wilson95_ci"] == [9.6, 47.3]
    assert len(built["patterns"]["weighing_phrases"]) == 74 and len(built["patterns"]["relationship_phrases"]) == 72


def test_paths_are_repository_relative(built):
    assert str(config.ROOT) not in M.dumps(built)
    assert built["corpora"]["newsagent_20261011"]["path"] == "data/mechanisms/sessions/newsagent"
    for group in ("pure_listing_3plus_tools_zero_markers", "genuine_weighing_or_relating"):
        for e in built["examples"][group]:
            assert not e["file"].startswith("/") and (config.ROOT / e["file"]).is_file()


def test_word_boundaries_and_case():
    assert M.find_matches("A Minority Stake headline", M.WEIGHING_PHRASES) == []
    assert M.find_matches("However, there's also risk", M.RELATIONSHIP_PHRASES) == []
    assert M.find_matches("HOWEVER, THE trend", M.RELATIONSHIP_PHRASES) == ["however, the"]
    assert M.find_matches("rallied significantly", M.WEIGHING_PHRASES) == []
    # the lower-case prefilter must not hide a match through a non-ASCII letter that IGNORECASE folds to ASCII
    assert M.find_matches("a \u017fignificant move", M.WEIGHING_PHRASES) == ["significant"]
    assert M.find_regex_matches("both the trend and RSI suggest a rebound") == [M.RELATIONSHIP_REGEXES[0][0]]


def test_sentence_units():
    text = "- News: buyout\n- Volatility high. Despite the news, vol is low!  Next\n\n   \nlast"
    assert M.split_sentences(text) == ["- News: buyout", "- Volatility high.", "Despite the news, vol is low!", "Next",
                                       "last"]
    assert M.check4_hits("The news is significant and could create volatility.") == (True, True)
    assert M.check4_hits("- Recent news positive\n- Volatility is in a significant regime") == (False, True)


def test_wilson_and_z_closed_forms():
    assert M.wilson_ci(12, 16, digits=1) == [50.5, 89.8]
    assert M.wilson_ci(26, 916) == [1.94, 4.13]
    assert M.wilson_ci(0, 0) == [None, None]
    z = M.two_prop_z(1854, 2000, 1754, 2000)
    assert (z["diff_pct"], z["z"]) == (5.0, 5.318)


def test_output_is_plain_json(built):
    text = M.dumps(built)
    assert text.endswith("}\n") and json.loads(text) == built
