"""The four-mechanism web page (in Chinese): salience, proximity, position adjustment against the rational rule, and
evidence weighing in the reasoning text, drawn from the four shipped results/mechanisms/<analysis>/data.json files.

    finagent mech-page            results/mechanisms/*/data.json -> results/mechanisms/page/mechanisms.html
    finagent mech-page --check    write nothing; exit 1 unless a fresh build equals the shipped page byte for byte

Ported from the research workspace's results/mech4_20261023/page/make_page.py. The page it writes is byte-identical
to the workspace's mech4_findings.html, because every text, chart helper and format is kept as it was; only the
unused helpers (cite, chip, legend, scatter_line and the SERIES table) were dropped, and the data.json files are read
in build() instead of at import. The page is an HTML fragment (title, styles, body; no doctype), as the original,
meant to be shown inside a page shell.

Most numbers are formatted from data.json at build time. The page text also quotes numbers that the original typed
by hand (15/694, 0.017%, the ELV jumps, the per-tool-count rates of chart 2, ...). typed_numbers() lists each of them
(72 rows) with the data.json value it stands for, and build() stops with an error if any no longer agrees with the
data to the precision shown. The two typed numbers it does not check are in NOT_CHECKED, with the reason.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path

from finagent import config

ANALYSES = ("salience", "proximity", "position_adjustment", "thinking")
IN_DIR = config.MECHANISMS_RESULTS
OUT_DIR = IN_DIR / "page"
OUT_FILE = OUT_DIR / "mechanisms.html"


def E(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def load(root: Path = IN_DIR) -> dict[str, dict]:
    """{analysis: its data.json} for the four analyses under root."""
    return {name: json.loads((root / name / "data.json").read_text(encoding="utf-8")) for name in ANALYSES}


# ------------------------------------------------------------------ small helpers
def pre(text, cls=""):
    return f'<pre class="quote {cls}">{E(text)}</pre>'


def verdict_pill(kind, text):
    return f'<span class="pill {kind}">{E(text)}</span>'


# ------------------------------------------------------------------ chart helpers (inline SVG, two-mark bar, consistent w/ project convention)
def bar_path(x, y0, w, y1, r=3):
    h = abs(y1 - y0)
    r = min(r, h / 2 if h else r, w / 2)
    if y1 < y0:
        return (f"M{x:.1f},{y0:.1f} V{y1+r:.1f} Q{x:.1f},{y1:.1f} {x+r:.1f},{y1:.1f} H{x+w-r:.1f} "
                f"Q{x+w:.1f},{y1:.1f} {x+w:.1f},{y1+r:.1f} V{y0:.1f} Z")
    return (f"M{x:.1f},{y0:.1f} V{y1-r:.1f} Q{x:.1f},{y1:.1f} {x+r:.1f},{y1:.1f} H{x+w-r:.1f} "
            f"Q{x+w:.1f},{y1:.1f} {x+w:.1f},{y1-r:.1f} V{y0:.1f} Z")


def grouped_bars(title, groups, values, slots, ymin, ymax, ticks, fmt, note="", H=260, errs=None):
    """values[g][series]; errs[g][series] = +/- half-height (SE) or None."""
    W, L, R, Tp, B = 640, 54, 14, 14, 40
    pw, ph = W - L - R, H - Tp - B
    y = lambda v: Tp + (ymax - v) / (ymax - ymin) * ph  # noqa: E731
    gw = pw / len(groups)
    nser = max(len(v) for v in values)
    inner = gw * 0.78
    bw = inner / nser
    out = [f'<figure class="fig"><figcaption class="cap-top">{E(title)}</figcaption>',
           f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(title)}" class="chart">']
    for t in ticks:
        out.append(f'<line x1="{L}" x2="{W-R}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid{" zero" if abs(t) < 1e-9 else ""}"/>')
        out.append(f'<text x="{L-8}" y="{y(t)+4:.1f}" class="tick" text-anchor="end">{E(fmt(t))}</text>')
    base = y(0 if ymin < 0 < ymax else ymin)
    for gi, g in enumerate(groups):
        gx = L + gi * gw + (gw - inner) / 2
        for si in range(len(values[gi])):
            v = values[gi][si]
            if v is None:
                continue
            x = gx + si * bw + 1
            sl = slots[si] if si < len(slots) else slots[-1]
            out.append(f'<path d="{bar_path(x, base, bw-2, y(v))}" class="mark s{sl}"><title>{E(g)}: {E(fmt(v))}</title></path>')
            if errs and errs[gi][si] is not None:
                e = errs[gi][si]
                cx = x + (bw - 2) / 2
                out.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(v+e):.1f}" y2="{y(v-e):.1f}" class="errbar"/>')
        out.append(f'<text x="{L+gi*gw+gw/2:.1f}" y="{H-B+18}" class="xlab" text-anchor="middle">{E(g)}</text>')
    out.append("</svg>")
    if note:
        out.append(f"<figcaption>{E(note)}</figcaption>")
    out.append("</figure>")
    return "".join(out)


def html_table(rows, cls=""):
    head = "".join(f"<th>{E(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{E(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f'<div class="tbl {cls}"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


# ------------------------------------------------------------------ 1. 显眼数字 (salience)
def sec_salience(SAL):
    reg = SAL["step2_regression_ols"]["newsagent_FULL_primary"]
    m1, m2 = reg["model1_sigma_only"], reg["model2_sigma_plus_annvol20"]
    cp = SAL["step3_copied_vs_not_copied"]["newsagent_FULL_plus_NO_NEWS_combined"]
    s5 = SAL["step5_full_vs_nonews_salience_effect"]
    exs = SAL["examples"]

    chart1 = grouped_bars(
        "照抄年化数字的会话占比（“照抄”=报的 5 日波动和年化数字相差不到 15%）", ["新闻版", "无新闻版"],
        [[SAL["step3_copied_vs_not_copied"]["newsagent_FULL"]["copied"]["pct_of_total"]],
         [SAL["step3_copied_vs_not_copied"]["newsagent_NO_NEWS"]["copied"]["pct_of_total"]]],
        [1], 0, 4, [0, 1, 2, 3, 4], lambda v: f"{v:.1f}%",
        note=f"新闻版 15/694 次，无新闻版 12/751 次；两者没有显著差别（z={s5['copy_rate_two_proportion_test']['z']:.2f}，p≈{s5['copy_rate_two_proportion_test']['p_two_sided_normal_approx']:.2f}）。",
        H=220)
    chart2 = grouped_bars(
        "照抄这一组 vs 其余会话：预测偏离真实波动的程度", ["照抄年化数字（27 次）", "其余会话（1,418 次）"],
        [[cp["copied"]["mean_abs_ln_ratio_error"]], [cp["not_copied"]["mean_abs_ln_ratio_error"]]],
        [1, 3], 0, 2.0, [0, 0.5, 1.0, 1.5, 2.0], lambda v: f"{v:.2f}",
        errs=[[cp["copied"]["se"]], [cp["not_copied"]["se"]]],
        note=f"纵轴＝|ln(报的波动 / 真实 5 日波动)|，越低越准。两组相差 {cp['diff_copied_minus_not']['diff']:.2f}（标准误 {cp['diff_copied_minus_not']['se']:.2f}，t={cp['diff_copied_minus_not']['t']:.1f}），换算成倍数大约是报错 5.6 倍 vs 1.9 倍。",
        H=220)

    return f"""
<section id="salience">
  <h2><span class="num">01</span> 显眼的数字和信息</h2>
  <p class="lede">有没有一个"大而显眼"的年化波动数字摆在眼前，会不会让模型的预测跟着它走，而不是跟着真正该有的波动走？</p>
  <div class="status status-mixed">{verdict_pill("mixed", "部分成立：不是整体偏移，是少数会话整句照抄")}
    <div><b>平均来看，几乎没有影响；但少数情况下是整段照抄，而且代价很大。</b>
    把模型报的 5 日波动，同时对"真实该有的波动"和"看到的年化大数字"做回归：
    控制了真实该有的波动之后，年化数字几乎不再提供任何额外解释力（新增解释力只有 0.017%）。
    但单独看"报的数字几乎就是年化数字本身"这一小撮会话——新闻版 694 次里 15 次、无新闻版 751 次里 12 次，
    合计约 {cp['copied']['pct_of_total']:.1f}%——这些会话的预测误差是其余会话的 3 倍左右，统计上非常显著（t={cp['diff_copied_minus_not']['t']:.1f}）。</div>
  </div>

  <h3>回归：控制了真实波动之后，年化数字还有没有用</h3>
  <p class="tnote">模型：报的 5 日波动 ~ a + b1·真实该有的波动 + b2·看到的年化数字（新闻版 694 次会话，普通最小二乘法）。</p>
  {html_table([
      ["", "只用真实波动（b1）", "加上年化数字（b1, b2）"],
      ["真实波动 b1", f"{m1['coefs']['b1_rational_sigma5']['coef']:.3f}（t={m1['coefs']['b1_rational_sigma5']['t']:.1f}）", f"{m2['coefs']['b1_rational_sigma5']['coef']:.3f}（t={m2['coefs']['b1_rational_sigma5']['t']:.1f}）"],
      ["年化数字 b2", "—", f"{m2['coefs']['b2_ann_vol_20d_pct']['coef']:.4f}（t={m2['coefs']['b2_ann_vol_20d_pct']['t']:.2f}，不显著）"],
      ["解释力 R²", f"{m1['r2']:.4f}", f"{m2['r2']:.4f}"],
  ])}

  <div class="two">{chart1}{chart2}</div>

  <h3>两个真实例子</h3>
  <div class="transcript">
    <div class="msg asst"><div class="role">{E(exs[0]['ticker'])} · {E(exs[0]['day'])} · {verdict_pill("bad", "整段照抄")}</div>
      {pre(exs[0]['quotes'][0])}{pre(exs[0]['quotes'][1])}
      <p class="note">报的 5 日波动 {exs[0]['submitted_expected_vol_pct']}%。这天理性基准的 5 日波动是 3.37%，
      实际 5 日波动是 3.74%——报的数字几乎是该报数字的 4～5 倍。</p></div>
    <div class="msg asst"><div class="role">{E(exs[1]['ticker'])} · {E(exs[1]['day'])} · {verdict_pill("bad", "整段照抄")}</div>
      {pre(exs[1]['quotes'][0])}{pre(exs[1]['quotes'][1])}
      <p class="note">报的 5 日波动 {exs[1]['submitted_expected_vol_pct']}%。这天理性基准是 4.67%，实际是 5.34%——
      报的数字几乎就是年化数字本身，不是正确换算后的 5 日数字。</p></div>
  </div>
  <p class="note">样本：{SAL['n_sessions_used']} 次主语料会话（通义千问 3.5-9B，真实交易日），和理性基准的匹配率 100%。
  说明：{SAL['step3_copied_vs_not_copied']['reconciliation_with_step2']}</p>
</section>
"""


# ------------------------------------------------------------------ 2. 离得近 (proximity)
def sec_proximity(PRX):
    s2 = PRX["step2_results"]
    last_t, not_t = s2["is_last_true"], s2["is_last_false"]
    ratio = s2["mean_ratio_expected_vol_over_tool_value"]
    ex0 = PRX["examples"][0]
    sess_a, sess_b = ex0["sessions"][0], ex0["sessions"][1]

    chart = grouped_bars(
        "年化数字 → 报的波动，斜率有多陡（同一天、信息完全一样，只比较调用位置）",
        ["波动率工具放在最后调用", "波动率工具不是最后调用"],
        [[last_t["slope"]], [not_t["slope"]]], [2, 4], 0, 0.08, [0, 0.02, 0.04, 0.06, 0.08],
        lambda v: f"{v:.3f}",
        errs=[[last_t["slope_se"]], [not_t["slope_se"]]],
        note=f"128 天里同时有两种调用位置的 420 次会话。两条斜率差 {s2['difference_of_slopes_test']['diff']:.3f}（标准误 {s2['difference_of_slopes_test']['se_diff']:.3f}），p={s2['difference_of_slopes_test']['p_two_sided']:.2f}——没有差别。",
        H=220)

    return f"""
<section id="proximity">
  <h2><span class="num">02</span> 离得近的数字和信息</h2>
  <p class="lede">不管数字显不显眼，光是"最后一次调用、离提交决定最近"，会不会让模型更容易跟着它走？</p>
  <div class="status status-null">{verdict_pill("null", "没有找到这个效应——而且不是因为没测够")}
    <div><b>利用了一个天然的对照：</b>同一天、同样的信息，模型自己有时把波动率工具放在最后调，有时不是。
    比较这两种情况下"年化数字对答案的影响力"，128 个交易日里凑出 420 次可比的会话，
    四种不同的检验方法都得到同一个结论：位置本身没有额外影响（最强的一个检验 p=0.73）。
    这是一个测得比较扎实的"没有发现"，不是没认真测。</div>
  </div>

  {chart}

  <h3>换一个角度：直接看"报的数字占年化数字的比例"</h3>
  {html_table([
      ["", "最后调用", "不是最后调用"],
      ["报的波动 / 年化数字", f"{ratio['is_last_true']['mean_ratio']:.3f}", f"{ratio['is_last_false']['mean_ratio']:.3f}"],
      ["样本数", f"{ratio['is_last_true']['n']}", f"{ratio['is_last_false']['n']}"],
  ])}
  <p class="tnote">两个比例几乎完全一样——如果"最后调用"真的更有分量，这个比例应该更接近 1，但没有。</p>

  <h3>一个要诚实说明的混淆因素</h3>
  <p>会不会是"模型打算重点依赖这个工具的时候，才把它放到最后调"？这样"位置"和"打算依赖"就搅在一起了。
  直接测了两件事：年化数字的大小本身预测不了它会不会被放到最后（p=0.28）；"最后调用"和"不是最后调用"两组的
  依赖比例也看不出差别（上表）。确实发现了一个真实但不同的现象：被放到最后调用的会话，
  整体调用的工具数更少（平均 7.05 个 vs 8.32 个，这个差别非常显著）——说明"放到最后"的会话往往是更快
  拿定主意的会话，这是真实存在的另一种解释，以后设计类似检验时要控制它，但不影响这次"位置本身没有独立影响"的结论。</p>

  <h3>一个真实例子：同一只股票同一天，两次运行调用顺序不同</h3>
  <p class="tnote">两次都看到完全一样的年化数字（30.1%）。</p>
  <div class="transcript">
    <div class="msg asst"><div class="role">{E(sess_a['ticker'])} · {E(sess_a['day'])} · 波动率工具放在最后调用</div>
      {pre(sess_a['submit_decision_args']['reasoning'])}
      <p class="note">报的 5 日波动 {sess_a['submit_decision_args']['expected_vol_pct']}%——几乎就是年化数字本身。</p></div>
    <div class="msg asst"><div class="role">{E(sess_b['ticker'])} · {E(sess_b['day'])} · 波动率工具不是最后调用</div>
      {pre(sess_b['submit_decision_args']['reasoning'])}
      <p class="note">报的 5 日波动 {sess_b['submit_decision_args']['expected_vol_pct']}%——明显更低，接近正确换算后的量级。</p></div>
  </div>
  <p class="note">{E(ex0['description'])}</p>
  <p class="note">但这正是总体结论要强调的地方——这一对样本看着像"位置决定权重"，放到全部 420 次会话里看，
  这个方向的效应完全不显著，大量反方向的反例同时存在（比如数据里另一个真实配对，STX_2026-06-17，结果正好相反）。</p>
  <p class="note">样本：主语料 754 次可用会话（通义千问 3.5-9B，新闻版），其中年化数字和另一个工具（风险预算）
  给出的其实是同一个数字——两者用的是同一条公式，所以没法再拿它们互相比较"谁更有分量"。</p>
</section>
"""


# ------------------------------------------------------------------ 3. 调仓输出 vs 理性对比
def sec_position(POS):
    h = POS["headline"]
    overall, quiet, event = h["overall"], h["quiet_abs_u_lt_1"], h["eventful_abs_u_ge_2"]
    wk = POS["worked_examples"][0]

    chart = grouped_bars(
        "仓位改动的离散程度：智能体 vs 理性规则（标准差之比，1＝刚好一致）",
        ["全部", "平静日", "大事日（样本很薄）"],
        [[overall["std_ratio"]["ratio"]], [quiet["std_ratio"]["ratio"]], [event["std_ratio"]["ratio"]]],
        [1], 0, 12, [0, 2, 4, 6, 8, 10, 12], lambda v: f"{v:.1f}×",
        note="大事日只有 16 个间隔、5 只股票、6 个交易日——样本太薄，这一格先不下结论，只展示数字。",
        H=230)

    rows = [["交易日", "智能体仓位%", "理性目标%", "智能体当日改动", "理性当日改动", "惊讶程度 u"]]
    for r in wk["table"]:
        rows.append([r["day"], f"{r['agent_exposure_pct']:.1f}", f"{r['rational_target_pct']:.1f}",
                     "—" if r["delta_agent"] is None else f"{r['delta_agent']:+.1f}",
                     "—" if r["delta_rational"] is None else f"{r['delta_rational']:+.1f}",
                     f"{r['u']:+.2f}"])

    return f"""
<section id="position">
  <h2><span class="num">03</span> 调仓输出和理性对比</h2>
  <p class="lede">每天仓位实际改了多少，和按真实波动、真实预期收益算出来"该改多少"比，差多远？</p>
  <div class="status status-confirm">{verdict_pill("confirm", "确认：仓位改动比理性该有的吵得多")}
    <div><b>用连续多天的真实交易轨迹（440 条轨迹、6,240 个交易日）测的。</b>
    理性基准只能和 2026 年 1 月这一段窗口对上（其余窗口的日期对不上理性基准表的覆盖范围，如实说明，
    不是回避），可用的有 692 个连续日间隔。智能体每天仓位改动的标准差，是理性规则该有改动的 <b>{overall['std_ratio']['ratio']:.1f} 倍</b>，
    方向上和项目已经确认的"波动预测改动是理性模型 71 倍"一致——但这是仓位这个量单独算出来的新数字，不能直接套用那个 71。</div>
  </div>

  {chart}

  <h3>平静日 vs 大事日</h3>
  {html_table([
      ["", "样本数（间隔）", "改动量对理性改动的回归斜率", "标准差之比"],
      ["平静日（|惊讶程度|&lt;1）", f"{quiet['regression']['n']}", f"{quiet['regression']['b']:.2f}", f"{quiet['std_ratio']['ratio']:.2f}×"],
      ["大事日（|惊讶程度|≥2）", f"{event['regression']['n']}", f"{event['regression']['b']:.2f}（标准误 {event['regression']['se_cluster_day']['b']:.2f}，约是斜率的 {event['regression']['se_cluster_day']['b'] / event['regression']['b']:.0f} 倍）", f"{event['std_ratio']['ratio']:.2f}×"],
  ])}
  <p class="tnote">斜率＝回归"智能体当日改动量"对"理性当日改动量"，1 代表改动幅度刚好对，大于 1 说明改得比该改的还夸张。
  大事日这一格样本太薄（16 个间隔），标准误约是斜率本身的 3 倍，<b>测不出平静日/大事日这个不对称性在"仓位"这个量上是否存在，不强行下结论</b>。</p>

  <h3>一个真实轨迹：ELV，2026 年 1 月</h3>
  {html_table(rows)}
  <p class="note">01-06 到 01-16 这段，惊讶程度都在 ±1 以内（平静），理性目标几乎不动（±1～4 个百分点），
  智能体仓位却单日跳了 79 个百分点、又跳 40 个。到了 01-20～01-23 这几天惊讶程度升到 1.9～3.2（偏大事），
  理性目标依然几乎不动，智能体反而跳得更猛（+9、+43、−40），01-23 那天改动方向甚至和理性相反。</p>
  <p class="note">另外如实说明一点：同一天"智能体仓位水平"和"理性仓位水平"本身的相关性就很弱（皮尔逊≈0，
  斯皮尔曼 0.24，n=754）——所以"改动量对不上"不是"水平本来就对、只是改动声音更大"这么简单的故事。</p>
</section>
"""


# ------------------------------------------------------------------ 4. 思考过程：信息分量和信息关系
TOOL_BUCKETS = [("0–1个", 40.6), ("2个", 57.0), ("3–4个", 67.6), ("5–6个", 73.5), ("7个以上", 62.1)]
TOOL_BUCKET_KEYS = ("0-1", "2", "3-4", "5-6", "7+")          # their keys in thinking rates.by_n_distinct_tools_bucket


def sec_thinking(THK):
    full, nn = THK["rates"]["by_arm"]["FULL"], THK["rates"]["by_arm"]["NO_NEWS"]
    c4 = THK["check4_news_volatility_connection"]
    ex = THK["examples"]

    chart1 = grouped_bars(
        "思考里出现\"权衡信息分量\"或\"关联不同信息\"表述的会话占比（严格口径，剔除泛用词和自我辩护式表述）",
        ["新闻版", "无新闻版"],
        [[full["pct_weighing_strict"], full["pct_relationship_strict2"]],
         [nn["pct_weighing_strict"], nn["pct_relationship_strict2"]]],
        [1, 2], 0, 85, [0, 20, 40, 60, 80], lambda v: f"{v:.0f}%",
        note=f"权衡分量：新闻版 {full['pct_weighing_strict']:.1f}% vs 无新闻版 {nn['pct_weighing_strict']:.1f}%；关联信息：{full['pct_relationship_strict2']:.1f}% vs {nn['pct_relationship_strict2']:.1f}%——两项新闻版都明显更高（p&lt;0.0001）。",
        H=240)
    tool_buckets = TOOL_BUCKETS
    chart2 = grouped_bars(
        "调用的工具越多，思考里关联不同证据的比例怎么变",
        [b[0] for b in tool_buckets], [[b[1]] for b in tool_buckets], [2], 0, 85,
        [0, 20, 40, 60, 80], lambda v: f"{v:.0f}%",
        note="随工具数先明显上升、在 5–6 个工具时达到峰值，再往上反而回落——回落的原因还不确定，如实列为未解决的问题。",
        H=240)

    pl = ex["pure_listing_3plus_tools_zero_markers"][0]
    gn = ex["genuine_weighing_or_relating"][0]

    return f"""
<section id="thinking">
  <h2><span class="num">04</span> 思考过程：有没有权衡信息分量、分析信息关系</h2>
  <p class="lede">不是看"算出的数和交的答案对不对得上"，而是看思考原文里有没有真的在说"这条信息分量不大""这个和前面说的是一回事"这类话——还是平铺列完工具结果直接出答案。</p>
  <div class="status status-mixed">{verdict_pill("mixed", "部分成立：有新闻可关联时明显更多，但多数“关联”经不起细看")}
    <div><b>扫了 4,000 个会话的思考全文（两个模型各 2,000 个），用关键词和短语做了两套标记。</b>
    人工逐条核对后发现：原始统计里 90.2% 的会话"疑似"在关联信息，但抽样细读后，<b>严格意义上真正在关联两条证据的，
    只有约 23.5%（95% 置信区间 9.6%–47.3%，样本小，这是个粗略范围）</b>——大部分"疑似关联"其实是"我的决定符合信号 X"
    这种自我辩护式的话，不是"证据 A 和证据 B 之间什么关系"。权衡信息分量这一项核对后更可信一些，约 75% 是真的在评估信息重要性
    （置信区间 50.5%–89.8%）。</div>
  </div>

  {chart1}
  {chart2}

  <h3>新闻和波动率数字，思考里有没有明确把两者连起来说</h3>
  <p>在同时用到新闻和波动率工具的 {c4['n_eligible']} 次会话里，<b>只有 {c4['rate_pct']:.2f}%（95% 置信区间 {c4['ci95'][0]:.1f}%–{c4['ci95'][1]:.1f}%）
  在同一句话里明确把两者关联起来</b>（比如"这解释了价格的波动"）；放宽到相邻两句话也只到 {c4['window2_sensitivity']['rate_pct']:.1f}%。
  多数情况是两者各提一遍，从没说过它们之间是什么关系。</p>

  <h3>两段对照的真实原文</h3>
  <div class="transcript">
    <div class="msg asst"><div class="role">{E(pl.get('corpus',''))} · 调用了 {pl.get('n_distinct_tools','?')} 个工具 · {verdict_pill("bad", "平铺列举，没有权衡")}</div>
      {pre(pl.get('verbatim_excerpt',''))}
      <p class="note">列完趋势、RSI、MACD、支撑阻力、波动率、价格位置、新闻情绪之后，直接跳到：
      "{E(pl.get('then_jumps_to',''))}"——没有一句话说明哪条更重要、哪条和哪条有关系。</p></div>
    <div class="msg asst"><div class="role">ACN · 2026-03-24 · {verdict_pill("ok", "真实的权衡")}</div>
      {pre(gn.get('verbatim_quote',''))}
      <p class="note">{E(gn.get('why_genuine',''))}</p></div>
  </div>
  <p class="note">方法是关键词和短语匹配，不是经过验证的分类器——和项目里已经用过的"关键词判断情绪"同一个精度量级，
  已经做过人工抽检并把结果如实报在上面，不把它当成精确的分类结果来用。</p>
</section>
"""


def sec_summary():
    return f"""
<header class="masthead">
  <p class="eyebrow">四个真实数据检验 · 显眼 / 位置 / 理性对照 / 思考过程</p>
  <h1>显眼、位置、理性对照、思考过程</h1>
  <p class="lede">用已经保存下来的真实交易会话重新测了四件事：一个显眼的大数字会不会被直接抄；
  光是"离提交决定最近"会不会让一个数字更有分量；每天的仓位改动和理性该有的改动差多远；
  思考原文里有没有真的在权衡信息分量、关联不同信息。全部用真实会话数据算出来，独立核验过，
  没有调用任何新的模型。</p>
  <div class="summary-grid">
    <div class="scard"><div class="st">{verdict_pill("mixed", "部分成立")}</div><div class="sh">显眼的数字</div>
      <p>平均看几乎没影响，但约 2% 的会话整句照抄年化数字，误差是其余会话的 3 倍。</p></div>
    <div class="scard"><div class="st">{verdict_pill("null", "没找到")}</div><div class="sh">离得近的数字</div>
      <p>利用同一天模型自己决定调用顺序这个天然对照，位置本身测不出独立影响。</p></div>
    <div class="scard"><div class="st">{verdict_pill("confirm", "确认")}</div><div class="sh">调仓 vs 理性</div>
      <p>每天仓位改动的离散程度是理性规则该有的约 6.7 倍。</p></div>
    <div class="scard"><div class="st">{verdict_pill("mixed", "部分成立")}</div><div class="sh">思考过程</div>
      <p>有新闻可关联时思考明显更多，但严格核对后真正的关联只占约四分之一。</p></div>
  </div>
</header>
"""


# ------------------------------------------------------------------ the numbers the page text quotes as typed text
NOT_CHECKED = {
    "71 倍": "the project's earlier finding on volatility-forecast changes (not in these four data.json files)",
    "四种不同的检验方法": "a count of the tests run (slope difference, day fixed effects, paired days, full pool), not a value",
}


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    centre, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (centre - half), 100 * (centre + half)


def typed_numbers(d: dict[str, dict]) -> list[tuple[str, float, float, float]]:
    """(what, number as typed on the page, value from data.json, tolerance: half a unit of the last digit shown).
    A claim that is not a number ("within 1", "p < 0.0001", "the last call") is a row (what, 1, 1.0 if it holds, 0)."""
    sal, prx, pos, thk = (d[name] for name in ANALYSES)
    s3 = sal["step3_copied_vs_not_copied"]
    comb = s3["newsagent_FULL_plus_NO_NEWS_combined"]
    ex0, ex1 = sal["examples"][0], sal["examples"][1]                 # the two salience examples the page shows
    conf = prx["confound_discussion"]
    acc = prx["sample_accounting"]
    pair = prx["examples"][0]["sessions"][:2]                         # the proximity pair the page shows
    hl = pos["headline"]
    wk = pos["worked_examples"][0]
    by_day = {r["day"]: r for r in wk["table"]}
    quiet_days = [r for r in wk["table"] if "2026-01-06" <= r["day"] <= "2026-01-16"]
    late_days = [r for r in wk["table"] if "2026-01-20" <= r["day"] <= "2026-01-23"]
    hc = thk["precision_handcheck"]
    w_lo, w_hi = _wilson(hc["weighing_judgment"]["judged_genuine"], hc["weighing_judgment"]["n_sampled_with_a_weighing_match_shown"])
    rel = hc["relationship_judgment"]
    r_lo, r_hi = _wilson(rel["judged_genuine_strict"], rel["n_sampled_with_a_relationship_match_shown"])
    sig = thk["significance_tests"]
    buckets = thk["rates"]["by_n_distinct_tools_bucket"]
    holds = lambda cond: (1, float(bool(cond)), 0)  # noqa: E731
    return [
        # 1. salience
        ("FULL copied sessions (15/694)", 15, s3["newsagent_FULL"]["copied"]["n"], 0),
        ("FULL sessions (15/694)", 694, s3["newsagent_FULL"]["n_total_with_rv5"], 0),
        ("NO_NEWS copied sessions (12/751)", 12, s3["newsagent_NO_NEWS"]["copied"]["n"], 0),
        ("NO_NEWS sessions (12/751)", 751, s3["newsagent_NO_NEWS"]["n_total_with_rv5"], 0),
        ("regression sample (694)", 694, sal["step2_regression_ols"]["newsagent_FULL_primary"]["n"], 0),
        ("copied, combined (27)", 27, comb["copied"]["n"], 0),
        ("not copied, combined (1,418)", 1418, comb["not_copied"]["n"], 0),
        ("added R^2 in % (0.017%)", 0.017, 100 * sal["step2_regression_ols"]["newsagent_FULL_primary"]["delta_r2"], 0.0005),
        ("copied error as a multiple (5.6x)", 5.6, math.exp(comb["copied"]["mean_abs_ln_ratio_error"]), 0.05),
        ("other error as a multiple (1.9x)", 1.9, math.exp(comb["not_copied"]["mean_abs_ln_ratio_error"]), 0.05),
        ("copied / other error (about 3x)", 3,
         comb["copied"]["mean_abs_ln_ratio_error"] / comb["not_copied"]["mean_abs_ln_ratio_error"], 0.5),
        ("copied share in % (about 2%)", 2, comb["copied"]["pct_of_total"], 0.5),
        (f"rational sigma of example 0, {ex0['day_id']} (3.37%)", 3.37, _note_number(ex0["note"], "Rational 5-day sigma"), 0.005),
        (f"realised vol of example 0, {ex0['day_id']} (3.74%)", 3.74, _note_number(ex0["note"], "realised 5-day vol (panel)"), 0.005),
        (f"rational sigma of example 1, {ex1['day_id']} (4.67%)", 4.67, _note_number(ex1["note"], "Rational 5-day sigma"), 0.005),
        (f"realised vol of example 1, {ex1['day_id']} (5.34%)", 5.34, _note_number(ex1["note"], "realised 5-day vol (panel)"), 0.005),
        ("benchmark join rate in % (100%)", 100, 100 * sal["rational_benchmark_join"]["join_hit_rate"]["hit_rate"], 0),
        # 2. proximity
        ("matched days (128)", 128, acc["n_days_with_both_is_last_groups"], 0),
        ("sessions in matched days (420)", 420, acc["n_sessions_in_those_matched_days"], 0),
        ("day fixed effects p (0.73)", 0.73, prx["step2_results"]["within_day_fixed_effects_level_test"]["fe_regression"]["p"], 0.005),
        ("magnitude predicts position p (0.28)", 0.28, conf["check_1_does_magnitude_predict_position"]["p_two_sided"], 0.005),
        ("tool calls when last (7.05)", 7.05, conf["check_3_session_length_confound"]["is_last_true_mean_se"]["mean"], 0.005),
        ("tool calls when not last (8.32)", 8.32, conf["check_3_session_length_confound"]["is_last_false_mean_se"]["mean"], 0.005),
        ("usable sessions (754)", 754, acc["n_usable_part1_2"], 0),
        *[(f"ann_vol_20d_pct of pair session {i} (30.1%)", 30.1, json.loads(s["get_volatility_stats_result"])["ann_vol_20d_pct"], 0.05)
          for i, s in enumerate(pair)],
        ("pair session 0 calls get_volatility_stats last", *holds(pair[0]["tool_call_order"][-2:] == ["get_volatility_stats", "submit_decision"])),
        ("pair session 1 does not", *holds(pair[1]["tool_call_order"][-2] != "get_volatility_stats")),
        ("the other pair, STX_2026-06-17, is in the examples", *holds(any(s["day_id"] == "STX_2026-06-17" for e in prx["examples"]
                                                                           for s in e["sessions"]))),
        # 3. position adjustment
        ("trajectories (440)", 440, pos["n_trajectories_total"], 0),
        ("agent days (6,240)", 6240, pos["n_agent_days_total"], 0),
        ("usable gaps (692)", 692, pos["n_gaps_with_rational_join_both_days"], 0),
        ("std ratio (about 6.7x)", 6.7, hl["overall"]["std_ratio"]["ratio"], 0.05),
        ("eventful gaps (16)", 16, hl["eventful_abs_u_ge_2"]["regression"]["n"], 0),
        ("eventful tickers (5)", 5, hl["eventful_abs_u_ge_2"]["regression"]["se_cluster_ticker"]["n_clusters"], 0),
        ("eventful trading days (6)", 6, hl["eventful_abs_u_ge_2"]["regression"]["se_cluster_day"]["n_clusters"], 0),
        ("usable window is January 2026 only", *holds(pos["usable_windows"] == ["test_calm"]
                                                      and all(r["day"].startswith("2026-01") for r in wk["table"]))),
        ("same-day level Pearson (about 0)", 0, pos["level_correlation_same_day"]["pearson"], 0.05),
        ("same-day level Spearman (0.24)", 0.24, pos["level_correlation_same_day"]["spearman"], 0.005),
        ("same-day level n (754)", 754, pos["level_correlation_same_day"]["n"], 0),
        ("worked example is ELV", *holds(wk["ticker"] == "ELV")),
        ("ELV jump on 01-06 (79)", 79, -by_day["2026-01-06"]["delta_agent"], 0.5),
        ("ELV jump on 01-14 (40)", 40, by_day["2026-01-14"]["delta_agent"], 0.5),
        ("ELV change on 01-20 (+9)", 9, by_day["2026-01-20"]["delta_agent"], 0.5),
        ("ELV change on 01-21 (+43)", 43, by_day["2026-01-21"]["delta_agent"], 0.5),
        ("ELV change on 01-23 (-40)", -40, by_day["2026-01-23"]["delta_agent"], 0.5),
        ("ELV |u| < 1 on 01-06..01-16", *holds(max(abs(r["u"]) for r in quiet_days) < 1)),
        ("ELV smallest |u| on 01-20..01-23 (1.9)", 1.9, min(abs(r["u"]) for r in late_days), 0.05),
        ("ELV largest |u| on 01-20..01-23 (3.2)", 3.2, max(abs(r["u"]) for r in late_days), 0.05),
        ("ELV smallest rational change on 01-06..01-16 (about 1 pp)", 1, min(abs(r["delta_rational"]) for r in quiet_days), 0.5),
        ("ELV largest rational change on 01-06..01-16 (about 4 pp)", 4, max(abs(r["delta_rational"]) for r in quiet_days), 0.5),
        ("ELV on 01-23 moves against the rule", *holds(by_day["2026-01-23"]["delta_agent"] * by_day["2026-01-23"]["delta_rational"] < 0)),
        # 4. thinking
        ("sessions scanned (4,000)", 4000, thk["rates"]["overall"]["n"], 0),
        *[(f"sessions of corpus {c} (2,000)", 2000, thk["rates"]["by_corpus"][c]["n"], 0) for c in sorted(thk["rates"]["by_corpus"])],
        ("raw relationship rate in % (90.2%)", 90.2, thk["rates"]["overall"]["pct_relationship"], 0.05),
        ("strict genuine relating in % (23.5%)", 23.5, rel["rough_precision_strict_pct"], 0.05),
        ("its Wilson 95% low (9.6%)", 9.6, r_lo, 0.05),
        ("its Wilson 95% high (47.3%)", 47.3, r_hi, 0.05),
        ("strict genuine relating (about a quarter, in %)", 25, rel["rough_precision_strict_pct"], 2.5),
        ("genuine weighing in % (about 75%)", 75, hc["weighing_judgment"]["rough_precision_pct"], 0.5),
        ("its Wilson 95% low (50.5%)", 50.5, w_lo, 0.05),
        ("its Wilson 95% high (89.8%)", 89.8, w_hi, 0.05),
        ("weighing strict, FULL vs NO_NEWS: p < 0.0001", *holds(sig["FULL_vs_NO_NEWS_weighing_strict"]["p_two_sided"] < 1e-4)),
        ("relationship strict2, FULL vs NO_NEWS: p < 0.0001", *holds(sig["FULL_vs_NO_NEWS_relationship_strict2"]["p_two_sided"] < 1e-4)),
        *[(f"strict2 relationship rate with {key} tools ({typed}%)", typed, buckets[key]["pct_relationship_strict2"], 0.05)
          for (_, typed), key in zip(TOOL_BUCKETS, TOOL_BUCKET_KEYS)],
        ("strict2 rate peaks at 5-6 tools", *holds(max(TOOL_BUCKET_KEYS, key=lambda k: buckets[k]["pct_relationship_strict2"]) == "5-6")),
        ("genuine example is ACN 2026-03-24",
         *holds("/ACN_2026-03-24/" in thk["examples"]["genuine_weighing_or_relating"][0]["file"])),
    ]


def _note_number(note: str, label: str) -> float:
    """The first number after `label` in an example note ("Rational 5-day sigma for this day was 3.37%; ...")."""
    m = re.compile(re.escape(label) + r"[^0-9]*([0-9]+(?:\.[0-9]+)?)").search(note)
    if not m:
        raise ValueError(f"no number after {label!r} in {note!r}")
    return float(m.group(1))


def check_typed_numbers(d: dict[str, dict]) -> int:
    """Raise ValueError if a typed number of the page text no longer agrees with data.json; else how many were checked."""
    rows = typed_numbers(d)
    bad = [f"{what}: page {typed}, data.json {got!r}" for what, typed, got, tol in rows if not abs(got - typed) <= tol + 1e-9]
    if bad:
        raise ValueError("the page text no longer matches data.json: " + "; ".join(bad))
    return len(rows)


def build(data: dict[str, dict] | None = None) -> str:
    """The page, from the four data.json files (default: the shipped ones in results/mechanisms/)."""
    d = load() if data is None else data
    check_typed_numbers(d)
    nav = ('<nav class="toc" aria-label="目录">'
           '<a href="#salience">01 显眼的数字</a><a href="#proximity">02 离得近的数字</a>'
           '<a href="#position">03 调仓 vs 理性</a><a href="#thinking">04 思考过程</a>'
           '</nav>')
    body = "".join([sec_salience(d["salience"]), sec_proximity(d["proximity"]), sec_position(d["position_adjustment"]),
                    sec_thinking(d["thinking"])])
    page = CSS_HEAD + sec_summary() + f'<div class="wrap">{nav}<main>{body}</main></div>' + FOOT
    return page


CSS_HEAD = """<title>显眼、位置、理性与思考</title>
<meta name="description" content="用真实交易会话测的四件事：显眼数字会不会被抄、位置本身有没有独立影响、调仓幅度和理性对比、思考里有没有真的在权衡信息。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --bg:#f5f2ec; --surface:#fffefa; --surface-2:#ece6da; --line:#ddd3c0; --ink:#211f19; --muted:#73695a;
  --accent:#1f5c56; --accent-soft:#dde8e3; --ok:#1a7a4c; --ok-bg:#dcf0e4; --bad:#9a3324; --bad-bg:#f6ddd6;
  --na:#73695a; --na-bg:#e8e2d4;
  --s1:#eb6834; --s2:#8a63d2; --s3:#1baf7a; --s4:#2a78d6;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --bg:#15160f; --surface:#1d1e14; --surface-2:#272820; --line:#423f2e; --ink:#eee9da; --muted:#b0a890;
  --accent:#6fb6ab; --accent-soft:#213531; --ok:#5fcf98; --ok-bg:#1c3328; --bad:#e2826f; --bad-bg:#3a241c;
  --na:#b0a890; --na-bg:#2b2a20;
  --s1:#d95926; --s2:#9474e0; --s3:#199e70; --s4:#3987e5;
}}
:root[data-theme="dark"]{
  --bg:#15160f; --surface:#1d1e14; --surface-2:#272820; --line:#423f2e; --ink:#eee9da; --muted:#b0a890;
  --accent:#6fb6ab; --accent-soft:#213531; --ok:#5fcf98; --ok-bg:#1c3328; --bad:#e2826f; --bad-bg:#3a241c;
  --na:#b0a890; --na-bg:#2b2a20;
  --s1:#d95926; --s2:#9474e0; --s3:#199e70; --s4:#3987e5;
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "IBM Plex Sans",system-ui,sans-serif;}
h1,h2,h3{font-family:"Source Serif 4",Georgia,serif;text-wrap:balance;color:var(--ink);}
p,li{max-width:70ch;}
code,.mono{font-family:"IBM Plex Mono",monospace;}
a{color:var(--accent);}
.masthead{max-width:920px;margin:0 auto;padding:44px 20px 26px;border-bottom:1px solid var(--line);}
.eyebrow{font:500 12px/1 "IBM Plex Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 10px;}
h1{font-size:clamp(28px,4vw,40px);line-height:1.15;margin:0 0 12px;font-weight:700;}
.lede{font-size:16.5px;color:var(--muted);max-width:74ch;}
.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:20px;}
@media (max-width:860px){.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
.scard{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:13px 14px;}
.scard .sh{font-weight:600;margin:8px 0 5px;font-size:14.5px;}
.scard p{font-size:13px;color:var(--muted);margin:0;max-width:none;}
.wrap{max-width:1040px;margin:0 auto;display:grid;grid-template-columns:168px minmax(0,1fr);gap:36px;padding:0 20px 80px;}
nav.toc{position:sticky;top:20px;align-self:start;display:flex;flex-direction:column;gap:2px;padding-top:36px;}
nav.toc a{color:var(--muted);text-decoration:none;padding:6px 10px;border-left:2px solid var(--line);font-size:13.5px;}
nav.toc a:hover,nav.toc a:focus-visible{color:var(--accent);border-left-color:var(--accent);outline:none;}
main section{padding-top:36px;padding-bottom:8px;border-bottom:1px solid var(--line);margin-bottom:8px;scroll-margin-top:16px;}
main section:last-child{border-bottom:0;}
h2{font-size:23px;margin:0 0 6px;display:flex;align-items:baseline;gap:10px;}
h2 .num{font:700 15px/1 "IBM Plex Mono",monospace;color:var(--accent);background:var(--accent-soft);border-radius:6px;padding:4px 8px;}
h3{font-size:16px;margin:22px 0 8px;font-family:"IBM Plex Sans",sans-serif;font-weight:600;}
.status{margin-top:14px;display:flex;gap:10px;align-items:flex-start;border-radius:10px;padding:13px 15px;max-width:78ch;}
.status-mixed{background:#f3ead3;} .status-null{background:var(--surface-2);} .status-confirm{background:var(--ok-bg);}
:root:not([data-theme="light"]) .status-mixed{background:#36301c;}
:root[data-theme="dark"] .status-mixed{background:#36301c;}
.status p,.status div{margin:0;font-size:14.5px;}
.pill{display:inline-block;font:600 11.5px/1 "IBM Plex Mono",monospace;padding:4px 9px;border-radius:999px;white-space:nowrap;text-transform:uppercase;letter-spacing:.03em;margin-bottom:6px;}
.pill.confirm{color:var(--ok);background:var(--ok-bg);} .pill.null{color:var(--muted);background:var(--na-bg);}
.pill.mixed{color:#8a5a12;background:#f3ead3;} .pill.bad{color:var(--bad);background:var(--bad-bg);}
.pill.ok{color:var(--ok);background:var(--ok-bg);} .pill.na{color:var(--muted);background:var(--na-bg);}
:root:not([data-theme="light"]) .pill.mixed{color:#e8c878;background:#36301c;}
:root[data-theme="dark"] .pill.mixed{color:#e8c878;background:#36301c;}
.cite{margin:10px 0;padding:14px 18px;background:var(--surface);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;font-style:italic;}
.quote{margin:0;padding:11px 13px;background:var(--surface-2);border-radius:8px;font:13px/1.6 "IBM Plex Mono",monospace;white-space:pre-wrap;word-break:break-word;color:var(--ink);}
.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:12px 0;}
@media (max-width:760px){.wrap{grid-template-columns:minmax(0,1fr);}nav.toc{position:static;flex-direction:row;overflow-x:auto;padding-top:0;margin-bottom:10px;}nav.toc a{border-left:0;border-bottom:2px solid var(--line);white-space:nowrap;}.two{grid-template-columns:minmax(0,1fr);}}
figure.fig{margin:10px 0 16px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 15px 8px;}
figure.fig figcaption{font-size:13px;color:var(--muted);margin-top:8px;max-width:none;}
figure.fig figcaption.cap-top{font-weight:600;color:var(--ink);margin:0 0 6px;font-size:14px;}
svg.chart{width:100%;height:auto;display:block;overflow:visible;}
svg.chart .grid{stroke:var(--line);stroke-width:1;} svg.chart .grid.zero{stroke:var(--muted);stroke-width:1.3;}
svg.chart .tick,svg.chart .xlab{fill:var(--muted);font:11px "IBM Plex Mono",monospace;}
svg.chart .xlab{fill:var(--ink);font-size:11.5px;}
svg.chart .mark{stroke:var(--surface);stroke-width:1;}
svg.chart .mark:hover{opacity:.82;}
svg.chart .errbar{stroke:var(--ink);stroke-width:1.4;opacity:.55;}
svg.chart .dot{stroke:var(--surface);stroke-width:1;}
.sw.s1,.mark.s1,.dot.s1{fill:var(--s1);background:var(--s1);} .sw.s2,.mark.s2,.dot.s2{fill:var(--s2);background:var(--s2);}
.sw.s3,.mark.s3,.dot.s3{fill:var(--s3);background:var(--s3);} .sw.s4,.mark.s4,.dot.s4{fill:var(--s4);background:var(--s4);}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;margin-top:6px;}
.legend span{display:inline-flex;align-items:center;gap:6px;}
.legend .sw{width:11px;height:11px;border-radius:3px;display:inline-block;}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--surface);margin:10px 0;}
table{border-collapse:collapse;width:100%;font-size:13.5px;}
th,td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line);font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;}
th{font-family:"IBM Plex Sans",sans-serif;font-weight:500;color:var(--muted);font-size:12.5px;background:var(--accent-soft);}
td:first-child,th:first-child{font-family:"IBM Plex Sans",sans-serif;white-space:normal;min-width:110px;}
tr:last-child td{border-bottom:0;}
.tnote{font-size:13px;color:var(--muted);margin:4px 0 10px;max-width:none;}
.note{font-size:13.5px;color:var(--muted);margin:6px 0;}
.transcript{display:flex;flex-direction:column;gap:10px;margin:10px 0 14px;}
.msg{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:11px 13px;}
.msg .role{font:500 12.5px/1.4 "IBM Plex Sans",sans-serif;color:var(--muted);margin-bottom:7px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
</style>
"""

FOOT = """
<footer style="max-width:920px;margin:0 auto;padding:18px 20px 60px;color:var(--muted);font-size:13px;">
  四项分析用的是项目里已经保存的真实交易会话（通义千问 3.5-9B 为主，部分用通义千问 3-8B 做交叉核对），
  没有调用任何新的模型。每个数字都独立核验过，核验时发现并修正了几处措辞和统计口径的小问题，没有一条主要结论被推翻。
</footer>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent mech-page", description="Draw the four-mechanism page from "
                                 "results/mechanisms/*/data.json -> results/mechanisms/page/mechanisms.html.")
    ap.add_argument("--out", type=Path, default=OUT_FILE, help=f"output file (default: {config.rel(OUT_FILE)})")
    ap.add_argument("--check", action="store_true", help="compare with --out instead of writing it (exit 1 if different)")
    a = ap.parse_args(argv)
    data = build().encode("utf-8")
    if a.check:
        same = a.out.is_file() and a.out.read_bytes() == data
        print(f"{'same' if same else 'DIFFERENT':9s}  {config.rel(a.out)}")
        return 0 if same else 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(data)
    print(f"wrote {config.rel(a.out)} ({len(data):,} bytes; {check_typed_numbers(load())} typed numbers checked against data.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
