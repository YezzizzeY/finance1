"""One test per check of `finagent verify` (the same functions, finagent.verify.CHECKS). L1 and L2 read the unpacked records
and are skipped until `finagent unpack` has run."""
from __future__ import annotations

import pytest

from finagent import verify


@pytest.mark.parametrize("level, check", [pytest.param(level, fn, id=f"{level}-{name.replace(' ', '_')}")
                                          for level, name, fn in verify.CHECKS])
def test_check(level, check):
    if level != "L0" and not verify.RAW.is_dir():
        pytest.skip("records/raw is missing: run `finagent unpack` first")
    ok, detail = check()
    assert ok, detail
