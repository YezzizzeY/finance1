"""The good-thinking theory document (finagent.mechanisms.theory_doc): the .docx is deterministic (fixed timestamps,
stored members), the Markdown carries the same text, and both are rebuilt byte for byte (also the verify check
"theory document")."""
from __future__ import annotations

import io
import re
import zipfile

import pytest

from finagent import config
from finagent.mechanisms import docx_writer, theory_doc

FORBIDDEN = bytes.fromhex("6465657066756e64")          # an earlier platform's name, never shipped (lower case)


@pytest.fixture(scope="module")
def built():
    return theory_doc.build()


def test_build_reproduces_the_shipped_files(built):
    assert set(built) == {theory_doc.DOCX, theory_doc.MARKDOWN}
    for path, data in built.items():
        assert path.read_bytes() == data, config.rel(path)


def test_build_is_deterministic(built):
    assert theory_doc.build() == built


def test_docx_is_a_fixed_stored_zip(built):
    z = zipfile.ZipFile(io.BytesIO(built[theory_doc.DOCX]))
    assert z.testzip() is None
    assert [i.filename for i in z.infolist()] == ["[Content_Types].xml", "_rels/.rels", "word/_rels/document.xml.rels",
                                                  "word/styles.xml", "word/document.xml", "docProps/core.xml"]
    assert {(i.date_time, i.compress_type, i.create_system, i.external_attr) for i in z.infolist()} == {
        (docx_writer.FIXED_TIME, zipfile.ZIP_STORED, 3, 0o600 << 16)}


def test_appendix_counts():
    rows, counts = theory_doc.appendix_rows(theory_doc.load())
    assert len(rows) == 44 and [r[0] for r in rows] == [str(i) for i in range(1, 45)]
    assert counts == {"confirmed": 38, "corrected": 5, "wrong": 1}


def _docx_paragraphs(docx: bytes) -> list[str]:
    xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode("utf-8")
    texts = ["".join(re.findall(r"<w:t [^>]*>([^<]*)</w:t>", p)) for p in re.findall(r"<w:p>.*?</w:p>", xml)]
    unescape = lambda t: t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")  # noqa: E731
    return [unescape(t).removeprefix("• ") for t in texts if t]


def test_markdown_has_the_same_text_as_the_docx(built):
    md = built[theory_doc.MARKDOWN].decode("utf-8")
    plain = re.sub(r"\*\*|`", "", md).replace("\\|", "|")
    paragraphs = _docx_paragraphs(built[theory_doc.DOCX])
    assert len(paragraphs) > 300
    missing = [p for p in paragraphs if p not in plain]
    assert not missing, missing[:3]


def test_no_host_paths_or_removed_names(built):
    for data in [*built.values(), theory_doc.THEORY_JSON.read_bytes()]:
        blob = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml") if data[:2] == b"PK" else data
        assert FORBIDDEN not in blob.lower()
        assert all(s.encode() not in blob for s in ("/srv/", "/home/", "/tmp/", str(config.ROOT)))
