"""A minimal OOXML (.docx) writer built on the standard library: headings, body text with inline **bold**, *italic*
and `mono` runs, bullet lists and bordered tables, nothing else.

Ported from the research workspace's repro/docx_writer.py (the project's own code). The XML parts are the same; the
change is that the file is deterministic. Every zip member has the same fixed timestamp (FIXED_TIME), mode and creating
system, in a fixed order, and is stored uncompressed: deflate output is not the same across zlib builds (the
workspace's file was written by a Python linked with zlib-ng, this repository's .venv has zlib 1.3, and the two give
different bytes for the same XML), so a stored zip is the only one whose bytes depend on the content alone.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

FIXED_TIME = (2026, 10, 23, 0, 0, 0)                 # zip member timestamp (the document's date)

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')

CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOCRELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _fonts(ascii_: str, ea: str) -> str:
    return f'<w:rFonts w:ascii="{ascii_}" w:hAnsi="{ascii_}" w:eastAsia="{ea}" w:cs="{ascii_}"/>'


STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {NS}>
<w:docDefaults><w:rPrDefault><w:rPr>{_fonts("Calibri", "SimSun")}<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:before="0" w:after="80"/></w:pPr>
<w:rPr>{_fonts("Calibri", "SimHei")}<w:b/><w:sz w:val="40"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="300"/><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="6" w:color="BFBFBF"/></w:pBdr></w:pPr>
<w:rPr><w:color w:val="595959"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="360" w:after="140"/></w:pPr>
<w:rPr>{_fonts("Calibri", "SimHei")}<w:b/><w:sz w:val="28"/><w:color w:val="1B6B58"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="260" w:after="100"/></w:pPr>
<w:rPr>{_fonts("Calibri", "SimHei")}<w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:before="40" w:after="200"/></w:pPr>
<w:rPr><w:i/><w:color w:val="595959"/><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="Mono"><w:name w:val="Mono"/><w:qFormat/>
<w:rPr>{_fonts("Consolas", "SimSun")}<w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>
<w:tblPr><w:tblBorders>
<w:top w:val="single" w:sz="4" w:color="BFBFBF"/><w:left w:val="none" w:sz="0" w:color="auto"/>
<w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/><w:right w:val="none" w:sz="0" w:color="auto"/>
<w:insideH w:val="single" w:sz="4" w:color="D9D9D9"/><w:insideV w:val="none" w:sz="0" w:color="auto"/>
</w:tblBorders></w:tblPr></w:style>
</w:styles>"""

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)")      # **bold**, *italic*, `mono`


def esc(t: str) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def runs(text: str) -> str:
    """Inline markup: **bold**, *italic*, `mono`. Everything else is a plain run."""
    out = []
    for part in INLINE.split(str(text)):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            out.append(f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{esc(part[2:-2])}</w:t></w:r>')
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append(f'<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">{esc(part[1:-1])}</w:t></w:r>')
        elif part.startswith("`") and part.endswith("`"):
            out.append(f'<w:r><w:rPr><w:rStyle w:val="Mono"/></w:rPr><w:t xml:space="preserve">{esc(part[1:-1])}</w:t></w:r>')
        else:
            out.append(f'<w:r><w:t xml:space="preserve">{esc(part)}</w:t></w:r>')
    return "".join(out)


class Doc:
    def __init__(self) -> None:
        self.body: list[str] = []

    def para(self, text: str = "", style: str | None = None, ind: int = 0) -> None:
        pr = "<w:pPr>"
        if style:
            pr += f'<w:pStyle w:val="{style}"/>'
        if ind:
            pr += f'<w:ind w:left="{ind}" w:hanging="{min(ind, 240)}"/>'
        pr += "</w:pPr>"
        self.body.append(f"<w:p>{pr}{runs(text)}</w:p>")

    def title(self, t: str, sub: str = "") -> None:
        self.para(t, "Title")
        if sub:
            self.para(sub, "Subtitle")

    def h1(self, t: str) -> None:
        self.para(t, "Heading1")

    def h2(self, t: str) -> None:
        self.para(t, "Heading2")

    def caption(self, t: str) -> None:
        self.para(t, "Caption")

    def bullets(self, items: list[str]) -> None:
        for it in items:
            self.para("• " + it, ind=280)

    def table(self, cols: list[str], rows: list[list], widths: list[int] | None = None) -> None:
        n = len(cols)
        widths = widths or [round(100 / n)] * n
        grid = "".join(f'<w:gridCol w:w="{round(w * 92)}"/>' for w in widths)
        out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/>'
               '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>' + grid + "</w:tblGrid>"]

        def cell(txt, w, *, head=False, first=False) -> str:
            shd = '<w:shd w:val="clear" w:fill="F2F5F4"/>' if head else ""
            jc = "" if first else '<w:jc w:val="right"/>'
            pr = ('<w:pPr><w:spacing w:before="40" w:after="40"/>' + jc + "</w:pPr>")
            body = runs(f"**{txt}**" if head else txt)
            return (f'<w:tc><w:tcPr><w:tcW w:w="{round(w * 92)}" w:type="dxa"/>{shd}'
                    f'<w:vAlign w:val="center"/></w:tcPr><w:p>{pr}{body}</w:p></w:tc>')

        out.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>'
                   + "".join(cell(c, widths[i], head=True, first=i == 0) for i, c in enumerate(cols)) + "</w:tr>")
        for row in rows:
            out.append("<w:tr>" + "".join(cell(c, widths[i], first=i == 0) for i, c in enumerate(row)) + "</w:tr>")
        out.append("</w:tbl>")
        self.body.append("".join(out))
        self.body.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')

    def parts(self, title: str = "", creator: str = "1_overreaction") -> list[tuple[str, str]]:
        """The package parts, (name, XML), in the order they are zipped."""
        doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {NS}><w:body>'
               + "".join(self.body)
               + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                 '<w:pgMar w:top="1418" w:right="1276" w:bottom="1418" w:left="1276"/></w:sectPr></w:body></w:document>')
        core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f"<dc:title>{esc(title)}</dc:title><dc:creator>{esc(creator)}</dc:creator>"
                "</cp:coreProperties>")
        return [("[Content_Types].xml", CT), ("_rels/.rels", RELS), ("word/_rels/document.xml.rels", DOCRELS),
                ("word/styles.xml", STYLES), ("word/document.xml", doc), ("docProps/core.xml", core)]

    def to_bytes(self, title: str = "", creator: str = "1_overreaction") -> bytes:
        """The .docx file: the parts stored (not compressed) in a zip whose every member has FIXED_TIME, mode 0600 and
        Unix as the creating system (what zipfile.writestr gives by default, minus the clock and the compression)."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for name, xml in self.parts(title, creator):
                info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                info.compress_type, info.external_attr, info.create_system = zipfile.ZIP_STORED, 0o600 << 16, 3
                z.writestr(info, xml)
        return buf.getvalue()

    def save(self, path: Path, title: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.to_bytes(title))
