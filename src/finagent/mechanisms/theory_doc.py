"""The theory document (in Chinese): what counts as "good thinking" -- each piece of information moves the judgment
only by its weight given the other pieces (information weight), and how pieces relate (repeat, already priced in,
stale, redundant, synergistic, conflicting) -- with the 44-entry literature appendix.

    finagent mech-theory-doc            docs/good_thinking/good_thinking_theory.json -> docs/good_thinking/good_thinking_20261023.docx
                                        and docs/GOOD_THINKING.md (the same content as Markdown)
    finagent mech-theory-doc --check    write nothing; exit 1 unless both files equal a fresh build byte for byte

Ported from the research workspace's results/lit_20261023/make_doc.py (with its OOXML writer, repro/docx_writer.py,
now finagent.mechanisms.docx_writer). The text of every section is the original's; the appendix is built from
good_thinking_theory.json (44 entries, each re-checked by an independent verifier; the verifier's corrections are
applied there). The content is now one list of blocks, blocks(), written out twice: as the .docx and as Markdown.
The first version of the document (2026-10-23) called the redundancy matrix 22 fields (the size of its largest
near-duplicate cluster; data/evidence_relations/tool_redundancy/pearson_matrix.csv has 69) and said the ~6.7 ratio
was measured against a Kalman rule (it is the Kelly-style target-exposure rule of results/mechanisms/position_adjustment);
both were corrected the same day, in the workspace copy and here, together with the five research notes in
good_thinking_theory.json that repeated the 22. The six XML parts of the .docx are byte-identical to those of the
workspace's corrected 好的思考_理论依据_20261023.docx; the zip around them is deterministic (fixed timestamps, stored
rather than deflated; see docx_writer), so the file itself is the same on every build and every host.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from finagent import config
from finagent.mechanisms import docx_writer as dw

FOLDER = config.DOCS / "good_thinking"
THEORY_JSON = FOLDER / "good_thinking_theory.json"
DOCX = FOLDER / "good_thinking_20261023.docx"
MARKDOWN = config.DOCS / "GOOD_THINKING.md"
DOC_TITLE = "什么是好的思考：信息分量和信息关系的理论依据"          # the .docx core properties title

# The tool-redundancy matrix of data/evidence_relations/tool_redundancy/ (69 x 69 in pearson_matrix.csv).
REDUNDANCY_MATRIX = "69 个字段的冗余矩阵"

STATUS_CN = {"confirmed": "已确认", "corrected": "已更正细节", "wrong": "出处正确，一处说法已更正", "unverifiable": "未能核实"}
FAMILY_CN = {"weight": "信息分量", "relations": "信息关系", "finance": "金融测量", "llm": "大模型"}


class Doc(dw.Doc):
    """Same look as the project's earlier reports, but every table cell is left-aligned (text tables)."""

    def table(self, cols, rows, widths=None):
        n = len(cols)
        widths = widths or [round(100 / n)] * n
        grid = "".join(f'<w:gridCol w:w="{round(w * 92)}"/>' for w in widths)
        out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/>'
               '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>' + grid + "</w:tblGrid>"]

        def cell(txt, w, head=False):
            shd = '<w:shd w:val="clear" w:fill="F2F5F4"/>' if head else ""
            body = dw.runs(f"**{txt}**" if head else txt)
            return (f'<w:tc><w:tcPr><w:tcW w:w="{round(w * 92)}" w:type="dxa"/>{shd}</w:tcPr>'
                    f'<w:p><w:pPr><w:spacing w:before="40" w:after="40" w:line="264" w:lineRule="auto"/></w:pPr>{body}</w:p></w:tc>')

        out.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(cell(c, widths[i], True) for i, c in enumerate(cols)) + "</w:tr>")
        for r in rows:
            out.append("<w:tr>" + "".join(cell(c, widths[i]) for i, c in enumerate(r)) + "</w:tr>")
        out.append("</w:tbl>")
        self.body.append("".join(out))
        self.body.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')


def load(path: Path = THEORY_JSON) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def appendix_rows(data: list[dict]) -> tuple[list[list[str]], dict[str, int]]:
    """One row per entry, verifier corrections applied; status in plain words. Also the count of each status."""
    rows, counts = [], {}
    k = 0
    for fam in data:
        verdicts = fam["verify"]["verdicts"]
        for i, it in enumerate(fam["research"]["items"]):
            v = verdicts[i] if i < len(verdicts) else {}
            st = v.get("status", "unverifiable")
            counts[st] = counts.get(st, 0) + 1
            year = (v.get("corrected_year") or it["year"]).split("(")[0].strip()
            venue = it["venue"]
            idea = it["core_idea_cn"].split("。")[0] + "。"
            k += 1
            rows.append([str(k), FAMILY_CN[fam["family"]], f"{it['authors']}（{year}）", venue, idea, STATUS_CN.get(st, st)])
    return rows, counts


def blocks(data: list[dict]) -> list[tuple]:
    """The document, in order: ("title", text, subtitle), ("h1", text), ("para", text), ("bullets", [items]),
    ("table", columns, rows, widths). Inline **bold** and `mono` as in the text."""
    rows, counts = appendix_rows(data)
    n = len(rows)
    return [
        ("title", "什么是“好的思考”：信息分量和信息关系的理论依据",
         f"2026 年 10 月 23 日 · 共 {n} 条文献，每条由第二个人独立检索核对作者、年份、期刊和公式："
         f"{counts.get('confirmed', 0)} 条完全确认，{counts.get('corrected', 0)} 条更正了细节，"
         f"{counts.get('wrong', 0)} 条出处正确但有一句说法被推翻（见第七节）"),

        ("h1", "一、结论"),
        ("para", "**好的思考：每条信息只按它“在已知其他信息之后还剩下的分量”去改变判断，再按依据的厚薄决定今天动多少。**"),
        ("bullets", [
            "**信息分量有统一单位**：对数似然比（古德的“证据分量”）。重复、已被价格消化、过时、矛盾、协同，都可以换算成同一个单位比较。",
            "**信息关系有统一定义**：一条信息在已知其他信息之后的“条件分量”，和它单独看时的分量之间的差别。",
            "**好不好主要看行为**：在“只改一处信息”的成对实验里，看判断改变得对不对。思考文本只作辅助，因为已有研究表明思维链可以和真实决策脱节。",
        ]),

        ("h1", "二、信息分量：理性的标准是什么"),
        ("table", ["理论", "核心意思", "对“好的思考”的要求"], [
            ["古德的证据分量（1950；1979 年在《生物统计》上追述图灵的战时工作）",
             "分量 = 对数（假设成立时看到这条信息的概率 ÷ 假设不成立时看到它的概率）。只有相互独立的信息，分量才能直接相加；不独立时只能加条件分量。",
             "每条信息只按它的条件分量移动判断。重复的条件分量为 0。"],
            ["凯恩斯的论证权重（1921，《概率论》第六章）",
             "“结论有多可能”和“支撑它的依据有多厚”是两件事。新证据可能降低概率，但总会增加权重。",
             "依据厚的时候，一条新的小信号不应把判断推来推去。"],
            ["卡尔曼增益（1960）；贝茨与格兰杰的预测组合（1969）",
             "理性的更新幅度 = 新信号精度和原判断不确定性之比。多个误差相关的信号要按误差协方差矩阵的逆加权。",
             "“今天该动多少”有理性标准。越相关的信号合起来越像只有一条。"],
            ["布莱克韦尔的信息量排序（1951，1953）；霍华德的信息价值（1966）",
             "信息的价值 = 有了它之后最优决策的期望收益减去没有它时的期望收益。一条信息再显眼，不能改变决策就没有价值。",
             "重复、已消化、过时的信息都是已有信息的“打乱版”，附加价值为 0。"],
            ["沙普利值（1953）；伦德伯格与李（2017）；格拉比施与鲁本斯的两两交互指数（1999）",
             "在其他输入都在的情况下，把总效果公平地分给每个输入。两两交互为负表示冗余，为正表示协同。",
             "可以给每个工具输出算出“在别的工具都在时”的分量，作为注意力分配的目标。"],
            ["西姆斯的理性注意力（2003）；麦科维亚克、马泰卡、维德霍尔特的综述（2023）",
             "处理信息的能力有限，应把注意力用在决策价值最高的信息上。",
             "注意力有限会让决策**既更迟缓又更吵**（核对后更正，见第七节）。"],
        ], [26, 42, 32]),
        ("para", "几个会用到的公式："),
        ("bullets", [
            "古德：后验对数赔率 = 先验对数赔率 + 分量(信息1) + 分量(信息2 | 已知信息1)。",
            "卡尔曼增益：增益 = 原判断方差 ÷（原判断方差 + 新信号噪声方差）。",
            "n 条噪声相同、两两相关系数为 ρ 的信号，等效独立条数 = n ÷ (1 + (n − 1) × ρ)。",
            "年化波动换算成 5 日波动：5 日波动 = 年化波动 × 根号(5 ÷ 252) ≈ 年化波动 × 0.141。照抄年化数字的会话，报出的数大约是该报的 7 倍。",
        ]),

        ("h1", "三、信息之间的关系"),
        ("para", "所有关系都可以归到“条件分量和单独分量的比较”这一个框架下："),
        ("table", ["关系", "判定条件", "理论和实证出处", "我们已有的对应材料"], [
            ["重复报道、同源指标", "条件分量 = 0", "舒姆（1994）证据分类；恩克与齐默尔曼（2019）相关性忽视；德马佐、瓦亚诺斯、兹韦贝尔（2003）说服偏差", "重复新闻扰动；冗余矩阵里高度相关的字段"],
            ["已被价格消化", "已知价格之后，条件分量接近 0", "法玛（1970）有效市场；艾斯特、雷宾、瓦亚诺斯（2019）", "“已消化”扰动（只用交易日之前的新闻）"],
            ["过时新闻", "已知前一天的信息之后，条件分量接近 0", "泰特洛克（2011）：市场确实会对转载的旧闻反应", "“过时”扰动"],
            ["冗余（部分重叠）", "条件分量小于单独分量", "部分信息分解（威廉斯与比尔，2010）；沙普利交互指数为负", REDUNDANCY_MATRIX],
            ["协同（合起来才有用）", "条件分量大于单独分量", "舒姆（1994）；部分信息分解", "合成任务"],
            ["矛盾、冲突", "正负分量相互抵消；要比较来源的可信度", "舒姆（1994）", "合成任务"],
        ], [18, 22, 34, 26]),
        ("para", "另有一套只看“提交的预测”和“事后结果”的计量检验：**预测包含检验**（钟与亨德里，1986；"
                 "哈维、莱伯恩、纽博尔德，1998；费尔与席勒，1990）。如果智能体的预测已经包含了某个工具的全部有用信息，"
                 "把这个工具的预测加进来不会再改进；反之说明这个工具被漏用了，估计出来的系数就是该补上的权重。"),

        ("h1", "四、现成的测量方法"),
        ("para", "下面每一项都有贝叶斯最优参照智能体作为“好”的一端，平均计数型或跟随显眼信息型参照智能体作为“坏”的一端。"),
        ("table", ["测什么", "方法", "出处", "好的标准"], [
            ["分量给得对不对", "对数（后验赔率）= c × 对数似然比 + d × 对数先验赔率，再给重复、已消化、过时三类信息各加一项系数",
             "格雷瑟（1980）；本杰明（2019）综述；CogBench（2024）", "c 和 d 接近 1（建议 0.8 到 1.2）；三类附加系数接近 0（建议 −0.2 到 0.2）"],
            ["是不是只看强度、不看权重", "网格实验：新闻正面比例 × 独立文章数", "格里芬与特沃斯基（1992）", "两个系数都接近 1；人类的文章数系数明显偏小"],
            ["弱信号、强信号", "按信号强弱分组估计推断系数", "奥根布利克、拉扎勒斯、塞勒（2025）", "系数不随信号强弱变化；人类是弱信号推断过度、强信号推断不足"],
            ["有没有重复计算", "重复计数比 = 加第二份同源新闻后的变化 ÷ 加第一份时的变化", "恩克与齐默尔曼（2019）", "低于 0.1；平均计数型约为 1"],
            ["关系判断对不对", "交互对比 = 两条一起改的反应 −（只改第一条 + 只改第二条）", "部分信息分解；沙普利交互指数", "冗余的一对为负，协同的一对为正；平均计数型约为 0"],
            ["改动是不是太多", "信念移动量 ÷ 不确定性下降量（同一个事件的概率序列）", "奥根布利克与雷宾（2021）", "接近 1；明显大于 1 就是过度改动"],
            ["过度反应还是反应不足", "事后误差对预测修正做回归，在单次运行上算，不能只看多次平均", "科伊比翁与戈罗德尼琴科（2015）；博尔达洛、詹纳约利、马、施莱弗（2020）", "系数为 0；负数表示过度反应"],
            ["有没有漏用或照抄", "预测包含检验", "钟与亨德里（1986）等", "智能体包含所有工具的信息；照抄年化数字的会话会被工具反过来“包含”"],
        ], [16, 34, 26, 24]),

        ("h1", "五、专门研究大模型的工作（2023—2026）"),
        ("bullets", [
            "**CogBench**（科达-福尔诺等，国际机器学习大会 2024）：把模型的概率判断拆成先验权重和证据权重，理想值都是 1；正式版测了 40 个模型，发现先写思维链能改善概率推理。我们的分量回归就是它的扩展。",
            "**鞅性质检验**（法尔克、王、霍姆斯，国际机器学习大会 2024）：贝叶斯式的更新，改动量不能被旧信息预测。",
            "**大模型的经济预期**（拜比，2023，工作论文）：大模型的宏观预期反应不足，收益预期外推。",
            "**判断错还是执行错**（孙、王、哈特兰、赫尔曼，预印本 2026）：把损失拆成“判断错”和“从判断到决策这一步错”。我们的智能体同时交预期收益、预期波动和仓位，可以直接这样拆。",
            "**贝叶斯教学**（邱等，《自然·通讯》2026）：让模型模仿贝叶斯模型的更新过程来训练，概率推理变好。这是“训练思考过程”最接近的先例；我们的区别在于真实金融数据里信息之间的关系（重复、已消化、过时、矛盾）。",
            "**思维链不一定忠实**（特平等，神经信息处理系统大会 2023；兰纳姆等，2023；陈等，2025）：推理模型真用了提示线索时，主动承认的比例平均只有约 25% 到 39%。所以不能只靠文本关键词判断思考好坏。",
            "**评价和训练推理步骤**：过程监督（莱特曼等，国际表征学习大会 2024）；推理链的正确性和信息量评分（普拉萨德等，自然语言处理经验方法会议 2023）。",
        ]),

        ("h1", "六、落到我们项目：好的思考怎么打分"),
        ("table", ["层次", "测什么", "用到的现有材料"], [
            ["行为层（主）", "分量回归（c、d 和三类附加系数）、重复计数比、交互对比", "合成任务（似然比已知）；真实交易日的重复、已消化、过时三类扰动"],
            ["改动层", "日间仓位变化与理性仓位规则（凯利式目标仓位）的改动之比（现在约 6.7，好的接近 1）；信念移动量 ÷ 不确定性下降量；修正—误差回归", "连续交易轨迹；理性基准"],
            ["文本层（辅）", "思考里每句“证据甲和证据乙是什么关系”的说法，拿冗余矩阵核对，算准确率和覆盖率；“我的决定符合信号 X”这类自我辩护不算关系、不计分；再查文本说的关系和行为是否一致", f"{REDUNDANCY_MATRIX}；已扫描的 4,000 个会话"],
        ], [16, 50, 34]),
        ("para", "这些材料（合成任务、三类扰动、冗余矩阵、三个参照智能体）都已经放进 finance1 仓库，可以直接套用上面的打分公式。"),

        ("h1", "七、核对说明和还没解决的问题"),
        ("para", "每条文献都由第二个人独立检索、尽量去推翻。改动如下："),
        ("bullets", [
            "**被推翻的一句**：最初整理时写“理性注意力理论认为注意力有限只会让反应更迟缓、不会更吵”。核对者读了原文：注意力有限会让决策既更迟缓又带随机误差。所以**不能排除** 6.7 倍噪声有一部分来自注意力有限。",
            "德马佐、瓦亚诺斯、兹韦贝尔（2003）：一个人的长期影响力不只取决于信息有多准确，还取决于他在网络中的位置。",
            "艾斯特、雷宾、瓦亚诺斯（2019）：理性交易者在场时会减少扭曲（交易量因此上升），不是放大扭曲。",
            "CogBench：预印本初版测了 35 个模型，正式发表版是 40 个。",
            "兰纳姆等（2023）：四种干预里，只有“提前作答”和“加入错误”两种直接度量答案是否依赖思维链。",
            "条件互信息：麦吉尔（1954）交互信息的正负号约定，二手资料说法不一，原文未能读到；本文统一用“冗余为正”的约定。",
        ]),
        ("para", "还没有答案的问题："),
        ("bullets", [
            "6.7 倍噪声的原因还没确定：可能是分量用错，也可能是注意力有限，或者是每天把前一天的判断忘掉。要用第四节的方法分别测。",
            "思考文本里说的关系和实际行为是否一致，还没在真实模型上测过。",
            "证据关系基准还没在真实大模型上跑过。",
        ]),

        ("h1", "附录：文献清单"),
        ("table", ["#", "类别", "作者（年份）", "出处", "核心意思", "核对"], rows, [4, 8, 20, 22, 36, 10]),
    ]


def to_docx(bl: list[tuple]) -> bytes:
    d = Doc()
    for kind, *args in bl:
        {"title": d.title, "h1": d.h1, "para": d.para, "bullets": d.bullets, "table": d.table}[kind](*args)
    return d.to_bytes(title=DOC_TITLE)


def _md_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_markdown(bl: list[tuple]) -> str:
    out = ["<!-- Written by `finagent mech-theory-doc` from docs/good_thinking/good_thinking_theory.json; the same content "
           "as docs/good_thinking/good_thinking_20261023.docx. Edit the code (src/finagent/mechanisms/theory_doc.py), "
           "not this file. -->"]
    for kind, *args in bl:
        if kind == "title":
            out += [f"# {args[0]}", args[1]]
        elif kind == "h1":
            out.append(f"## {args[0]}")
        elif kind == "para":
            out.append(args[0])
        elif kind == "bullets":
            out.append("\n".join(f"- {it}" for it in args[0]))
        elif kind == "table":
            cols, rows = args[0], args[1]
            lines = ["| " + " | ".join(map(_md_cell, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
            lines += ["| " + " | ".join(map(_md_cell, r)) + " |" for r in rows]
            out.append("\n".join(lines))
        else:
            raise ValueError(f"unknown block {kind!r}")
    return "\n\n".join(out) + "\n"


def build(data: list[dict] | None = None) -> dict[Path, bytes]:
    """{output path: its bytes}: the .docx and the Markdown rendering of the same blocks."""
    bl = blocks(load() if data is None else data)
    return {DOCX: to_docx(bl), MARKDOWN: to_markdown(bl).encode("utf-8")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent mech-theory-doc", description="Write the good-thinking theory document "
                                 "(docs/good_thinking/good_thinking_20261023.docx and docs/GOOD_THINKING.md) from "
                                 "docs/good_thinking/good_thinking_theory.json.")
    ap.add_argument("--check", action="store_true", help="compare with the shipped files instead of writing them (exit 1 if different)")
    a = ap.parse_args(argv)
    differ = 0
    for path, data in build().items():
        if a.check:
            same = path.is_file() and path.read_bytes() == data
            differ += not same
            print(f"{'same' if same else 'DIFFERENT':9s}  {config.rel(path)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"wrote {config.rel(path)} ({len(data):,} bytes)")
    return 1 if differ else 0


if __name__ == "__main__":
    raise SystemExit(main())
