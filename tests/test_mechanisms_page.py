"""The four-mechanism page (finagent.mechanisms.page): rebuilt byte for byte, and the numbers its text types by hand are
held to the data.json files. (The byte-for-byte rebuild is also the verify check "mechanism page".)"""
from __future__ import annotations

import copy

import pytest

from finagent import config
from finagent.mechanisms import page

FORBIDDEN = bytes.fromhex("6465657066756e64")          # an earlier platform's name, never shipped (lower case)


@pytest.fixture(scope="module")
def data():
    return page.load()


def test_build_reproduces_the_shipped_page(data):
    assert page.build(data).encode("utf-8") == page.OUT_FILE.read_bytes()


def test_main_check_and_write(tmp_path, capsys):
    out = tmp_path / "mechanisms.html"
    assert page.main(["--out", str(out)]) == 0
    assert out.read_bytes() == page.OUT_FILE.read_bytes()
    assert page.main(["--out", str(out), "--check"]) == 0
    out.write_text("<title>x</title>\n")
    assert page.main(["--out", str(out), "--check"]) == 1


def test_every_typed_number_agrees_with_the_data(data):
    rows = page.typed_numbers(data)
    assert len(rows) == page.check_typed_numbers(data) == 72
    assert all(abs(got - typed) <= tol + 1e-9 for _, typed, got, tol in rows)


@pytest.mark.parametrize("change", [
    lambda d: d["salience"]["step3_copied_vs_not_copied"]["newsagent_FULL"]["copied"].update(n=16),
    lambda d: d["position_adjustment"]["headline"]["overall"]["std_ratio"].update(ratio=7.2),
    lambda d: d["thinking"]["rates"]["by_n_distinct_tools_bucket"]["5-6"].update(pct_relationship_strict2=70.0),
    lambda d: d["proximity"]["examples"][0]["sessions"].reverse(),
])
def test_a_changed_number_stops_the_build(data, change):
    d = copy.deepcopy(data)
    change(d)
    with pytest.raises(ValueError, match="no longer matches"):
        page.build(d)


def test_page_has_no_host_paths_or_removed_names():
    text = page.OUT_FILE.read_bytes()
    assert FORBIDDEN not in text.lower()
    assert all(s.encode() not in text for s in ("/srv/", "/home/", "/tmp/", str(config.ROOT)))
