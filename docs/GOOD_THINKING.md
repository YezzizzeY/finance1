<!-- Written by `finagent mech-theory-doc` from docs/good_thinking/good_thinking_theory.json; the same content as docs/good_thinking/good_thinking_20261023.docx. Edit the code (src/finagent/mechanisms/theory_doc.py), not this file. -->

# 什么是“好的思考”：信息分量和信息关系的理论依据

2026 年 10 月 23 日 · 共 44 条文献，每条由第二个人独立检索核对作者、年份、期刊和公式：38 条完全确认，5 条更正了细节，1 条出处正确但有一句说法被推翻（见第七节）

## 一、结论

**好的思考：每条信息只按它“在已知其他信息之后还剩下的分量”去改变判断，再按依据的厚薄决定今天动多少。**

- **信息分量有统一单位**：对数似然比（古德的“证据分量”）。重复、已被价格消化、过时、矛盾、协同，都可以换算成同一个单位比较。
- **信息关系有统一定义**：一条信息在已知其他信息之后的“条件分量”，和它单独看时的分量之间的差别。
- **好不好主要看行为**：在“只改一处信息”的成对实验里，看判断改变得对不对。思考文本只作辅助，因为已有研究表明思维链可以和真实决策脱节。

## 二、信息分量：理性的标准是什么

| 理论 | 核心意思 | 对“好的思考”的要求 |
|---|---|---|
| 古德的证据分量（1950；1979 年在《生物统计》上追述图灵的战时工作） | 分量 = 对数（假设成立时看到这条信息的概率 ÷ 假设不成立时看到它的概率）。只有相互独立的信息，分量才能直接相加；不独立时只能加条件分量。 | 每条信息只按它的条件分量移动判断。重复的条件分量为 0。 |
| 凯恩斯的论证权重（1921，《概率论》第六章） | “结论有多可能”和“支撑它的依据有多厚”是两件事。新证据可能降低概率，但总会增加权重。 | 依据厚的时候，一条新的小信号不应把判断推来推去。 |
| 卡尔曼增益（1960）；贝茨与格兰杰的预测组合（1969） | 理性的更新幅度 = 新信号精度和原判断不确定性之比。多个误差相关的信号要按误差协方差矩阵的逆加权。 | “今天该动多少”有理性标准。越相关的信号合起来越像只有一条。 |
| 布莱克韦尔的信息量排序（1951，1953）；霍华德的信息价值（1966） | 信息的价值 = 有了它之后最优决策的期望收益减去没有它时的期望收益。一条信息再显眼，不能改变决策就没有价值。 | 重复、已消化、过时的信息都是已有信息的“打乱版”，附加价值为 0。 |
| 沙普利值（1953）；伦德伯格与李（2017）；格拉比施与鲁本斯的两两交互指数（1999） | 在其他输入都在的情况下，把总效果公平地分给每个输入。两两交互为负表示冗余，为正表示协同。 | 可以给每个工具输出算出“在别的工具都在时”的分量，作为注意力分配的目标。 |
| 西姆斯的理性注意力（2003）；麦科维亚克、马泰卡、维德霍尔特的综述（2023） | 处理信息的能力有限，应把注意力用在决策价值最高的信息上。 | 注意力有限会让决策**既更迟缓又更吵**（核对后更正，见第七节）。 |

几个会用到的公式：

- 古德：后验对数赔率 = 先验对数赔率 + 分量(信息1) + 分量(信息2 | 已知信息1)。
- 卡尔曼增益：增益 = 原判断方差 ÷（原判断方差 + 新信号噪声方差）。
- n 条噪声相同、两两相关系数为 ρ 的信号，等效独立条数 = n ÷ (1 + (n − 1) × ρ)。
- 年化波动换算成 5 日波动：5 日波动 = 年化波动 × 根号(5 ÷ 252) ≈ 年化波动 × 0.141。照抄年化数字的会话，报出的数大约是该报的 7 倍。

## 三、信息之间的关系

所有关系都可以归到“条件分量和单独分量的比较”这一个框架下：

| 关系 | 判定条件 | 理论和实证出处 | 我们已有的对应材料 |
|---|---|---|---|
| 重复报道、同源指标 | 条件分量 = 0 | 舒姆（1994）证据分类；恩克与齐默尔曼（2019）相关性忽视；德马佐、瓦亚诺斯、兹韦贝尔（2003）说服偏差 | 重复新闻扰动；冗余矩阵里高度相关的字段 |
| 已被价格消化 | 已知价格之后，条件分量接近 0 | 法玛（1970）有效市场；艾斯特、雷宾、瓦亚诺斯（2019） | “已消化”扰动（只用交易日之前的新闻） |
| 过时新闻 | 已知前一天的信息之后，条件分量接近 0 | 泰特洛克（2011）：市场确实会对转载的旧闻反应 | “过时”扰动 |
| 冗余（部分重叠） | 条件分量小于单独分量 | 部分信息分解（威廉斯与比尔，2010）；沙普利交互指数为负 | 69 个字段的冗余矩阵 |
| 协同（合起来才有用） | 条件分量大于单独分量 | 舒姆（1994）；部分信息分解 | 合成任务 |
| 矛盾、冲突 | 正负分量相互抵消；要比较来源的可信度 | 舒姆（1994） | 合成任务 |

另有一套只看“提交的预测”和“事后结果”的计量检验：**预测包含检验**（钟与亨德里，1986；哈维、莱伯恩、纽博尔德，1998；费尔与席勒，1990）。如果智能体的预测已经包含了某个工具的全部有用信息，把这个工具的预测加进来不会再改进；反之说明这个工具被漏用了，估计出来的系数就是该补上的权重。

## 四、现成的测量方法

下面每一项都有贝叶斯最优参照智能体作为“好”的一端，平均计数型或跟随显眼信息型参照智能体作为“坏”的一端。

| 测什么 | 方法 | 出处 | 好的标准 |
|---|---|---|---|
| 分量给得对不对 | 对数（后验赔率）= c × 对数似然比 + d × 对数先验赔率，再给重复、已消化、过时三类信息各加一项系数 | 格雷瑟（1980）；本杰明（2019）综述；CogBench（2024） | c 和 d 接近 1（建议 0.8 到 1.2）；三类附加系数接近 0（建议 −0.2 到 0.2） |
| 是不是只看强度、不看权重 | 网格实验：新闻正面比例 × 独立文章数 | 格里芬与特沃斯基（1992） | 两个系数都接近 1；人类的文章数系数明显偏小 |
| 弱信号、强信号 | 按信号强弱分组估计推断系数 | 奥根布利克、拉扎勒斯、塞勒（2025） | 系数不随信号强弱变化；人类是弱信号推断过度、强信号推断不足 |
| 有没有重复计算 | 重复计数比 = 加第二份同源新闻后的变化 ÷ 加第一份时的变化 | 恩克与齐默尔曼（2019） | 低于 0.1；平均计数型约为 1 |
| 关系判断对不对 | 交互对比 = 两条一起改的反应 −（只改第一条 + 只改第二条） | 部分信息分解；沙普利交互指数 | 冗余的一对为负，协同的一对为正；平均计数型约为 0 |
| 改动是不是太多 | 信念移动量 ÷ 不确定性下降量（同一个事件的概率序列） | 奥根布利克与雷宾（2021） | 接近 1；明显大于 1 就是过度改动 |
| 过度反应还是反应不足 | 事后误差对预测修正做回归，在单次运行上算，不能只看多次平均 | 科伊比翁与戈罗德尼琴科（2015）；博尔达洛、詹纳约利、马、施莱弗（2020） | 系数为 0；负数表示过度反应 |
| 有没有漏用或照抄 | 预测包含检验 | 钟与亨德里（1986）等 | 智能体包含所有工具的信息；照抄年化数字的会话会被工具反过来“包含” |

## 五、专门研究大模型的工作（2023—2026）

- **CogBench**（科达-福尔诺等，国际机器学习大会 2024）：把模型的概率判断拆成先验权重和证据权重，理想值都是 1；正式版测了 40 个模型，发现先写思维链能改善概率推理。我们的分量回归就是它的扩展。
- **鞅性质检验**（法尔克、王、霍姆斯，国际机器学习大会 2024）：贝叶斯式的更新，改动量不能被旧信息预测。
- **大模型的经济预期**（拜比，2023，工作论文）：大模型的宏观预期反应不足，收益预期外推。
- **判断错还是执行错**（孙、王、哈特兰、赫尔曼，预印本 2026）：把损失拆成“判断错”和“从判断到决策这一步错”。我们的智能体同时交预期收益、预期波动和仓位，可以直接这样拆。
- **贝叶斯教学**（邱等，《自然·通讯》2026）：让模型模仿贝叶斯模型的更新过程来训练，概率推理变好。这是“训练思考过程”最接近的先例；我们的区别在于真实金融数据里信息之间的关系（重复、已消化、过时、矛盾）。
- **思维链不一定忠实**（特平等，神经信息处理系统大会 2023；兰纳姆等，2023；陈等，2025）：推理模型真用了提示线索时，主动承认的比例平均只有约 25% 到 39%。所以不能只靠文本关键词判断思考好坏。
- **评价和训练推理步骤**：过程监督（莱特曼等，国际表征学习大会 2024）；推理链的正确性和信息量评分（普拉萨德等，自然语言处理经验方法会议 2023）。

## 六、落到我们项目：好的思考怎么打分

| 层次 | 测什么 | 用到的现有材料 |
|---|---|---|
| 行为层（主） | 分量回归（c、d 和三类附加系数）、重复计数比、交互对比 | 合成任务（似然比已知）；真实交易日的重复、已消化、过时三类扰动 |
| 改动层 | 日间仓位变化与理性仓位规则（凯利式目标仓位）的改动之比（现在约 6.7，好的接近 1）；信念移动量 ÷ 不确定性下降量；修正—误差回归 | 连续交易轨迹；理性基准 |
| 文本层（辅） | 思考里每句“证据甲和证据乙是什么关系”的说法，拿冗余矩阵核对，算准确率和覆盖率；“我的决定符合信号 X”这类自我辩护不算关系、不计分；再查文本说的关系和行为是否一致 | 69 个字段的冗余矩阵；已扫描的 4,000 个会话 |

这些材料（合成任务、三类扰动、冗余矩阵、三个参照智能体）都已经放进 finance1 仓库，可以直接套用上面的打分公式。

## 七、核对说明和还没解决的问题

每条文献都由第二个人独立检索、尽量去推翻。改动如下：

- **被推翻的一句**：最初整理时写“理性注意力理论认为注意力有限只会让反应更迟缓、不会更吵”。核对者读了原文：注意力有限会让决策既更迟缓又带随机误差。所以**不能排除** 6.7 倍噪声有一部分来自注意力有限。
- 德马佐、瓦亚诺斯、兹韦贝尔（2003）：一个人的长期影响力不只取决于信息有多准确，还取决于他在网络中的位置。
- 艾斯特、雷宾、瓦亚诺斯（2019）：理性交易者在场时会减少扭曲（交易量因此上升），不是放大扭曲。
- CogBench：预印本初版测了 35 个模型，正式发表版是 40 个。
- 兰纳姆等（2023）：四种干预里，只有“提前作答”和“加入错误”两种直接度量答案是否依赖思维链。
- 条件互信息：麦吉尔（1954）交互信息的正负号约定，二手资料说法不一，原文未能读到；本文统一用“冗余为正”的约定。

还没有答案的问题：

- 6.7 倍噪声的原因还没确定：可能是分量用错，也可能是注意力有限，或者是每天把前一天的判断忘掉。要用第四节的方法分别测。
- 思考文本里说的关系和实际行为是否一致，还没在真实模型上测过。
- 证据关系基准还没在真实大模型上跑过。

## 附录：文献清单

| # | 类别 | 作者（年份） | 出处 | 核心意思 | 核对 |
|---|---|---|---|---|---|
| 1 | 信息分量 | I. J. Good (book 1950); I. J. Good (1979 historical note on A. M. Turing's wartime statistical work)（1950; 1979） | Probability and the Weighing of Evidence, Charles Griffin and Co., London, 1950; Biometrika 66(2):393-396, 1979 | 一条证据对一个假设的“分量”，定义为：假设为真时看到这条证据的概率，除以假设为假时看到它的概率，再取对数。 | 已确认 |
| 2 | 信息分量 | John Maynard Keynes（1921） | A Treatise on Probability, Macmillan and Co., London; Part I, Chapter VI 'The Weight of Arguments' | 凯恩斯把两件事分开：一个结论有多大可能（概率），和支撑这个判断的相关知识有多少（论证的权重）。 | 已确认 |
| 3 | 信息分量 | R. E. Kalman (1960); J. M. Bates and C. W. J. Granger (1969)（1960; 1969） | Journal of Basic Engineering 82(1):35-45 (1960); Operational Research Quarterly 20(4):451-468 (1969, now Journal of the Operational Research Society) | 理性的更新幅度由两种不确定性的比例决定：新信号越准（噪声方差越小）、原有判断越不确定，就该更新得越多。 | 已确认 |
| 4 | 信息分量 | David Blackwell (1951, 1953); Ronald A. Howard (1966)（1951; 1953; 1966） | Proceedings of the Second Berkeley Symposium on Mathematical Statistics and Probability, pp. 93-102 (1951); Annals of Mathematical Statistics 24(2):265-272 (1953); IEEE Transactions on Systems Science and Cybernetics 2(1):22-26 (1966) | 布莱克韦尔：如果信息源乙可以看成是信息源甲再经过一层随机“打乱”（数学上：乙的条件分布 = 甲的条件分布乘一个随机矩阵），那么对任何决策者、任何目标，甲都至少和乙一样有用；反过来也成立。 | 已确认 |
| 5 | 信息分量 | Christopher A. Sims (2003); Bartosz Mackowiak, Filip Matejka, Mirko Wiederholt (2023)（2003; 2023） | Journal of Monetary Economics 50(3):665-690 (2003); Journal of Economic Literature 61(1):226-273 (2023) | 人处理信息的能力有限，所以要选择“看什么、看多仔细”。 | 出处正确，一处说法已更正 |
| 6 | 信息分量 | Lloyd S. Shapley (1953); Scott M. Lundberg and Su-In Lee (2017); Michel Grabisch and Marc Roubens (1999)（1953; 2017; 1999） | Contributions to the Theory of Games II, Annals of Mathematics Studies 28, Princeton University Press, pp. 307-317 (1953); Advances in Neural Information Processing Systems 30 (2017); International Journal of Game Theory 28(4):547-565 (1999) | 把一组输入共同产生的结果公平地分给每个输入：对某个输入，考察它加入所有可能的其他输入组合时带来的边际贡献，再按固定权重平均。 | 已确认 |
| 7 | 信息分量 | Dale Griffin and Amos Tversky（1992） | Cognitive Psychology 24(3):411-435 | 人在判断时主要看证据的“强度”（有多极端，例如推荐信写得多热情、效应有多大），而对证据的“权重”（有多可信，例如写信人是否可靠、样本有多大）考虑不足。 | 已确认 |
| 8 | 信息分量 | Daniel J. Benjamin (2019); framework from David M. Grether (1980)（2019） | Handbook of Behavioral Economics: Applications and Foundations 1, Volume 2, eds. B. D. Bernheim, S. DellaVigna, D. Laibson, Elsevier / North-Holland, pp. 69-186 (2019); Grether: Quarterly Journal of Economics 95(3):537-557 (1980) | 这一章综述人在概率推理上的系统错误。 | 已确认 |
| 9 | 信息分量 | Ned Augenblick, Eben Lazarus, Michael Thaler（2025） | Quarterly Journal of Economics 140(1):335-401 | 人收到新信息时，有时修正过度、有时修正不足；决定是哪一种的关键是信号的强度：对弱信号推断过度，对强信号推断不足。 | 已确认 |
| 10 | 信息分量 | Benjamin Enke and Florian Zimmermann（2019） | Review of Economic Studies 86(1):313-332 | 实验中被试收到相关的信号（几条“信息”其实来自同一个底层信号）。 | 已确认 |
| 11 | 信息分量 | Ned Augenblick and Matthew Rabin（2021） | Quarterly Journal of Economics 136(2):933-985 | 贝叶斯的人得到新信息、改变看法时，平均而言必须同时变得更确定。 | 已确认 |
| 12 | 信息关系 | David A. Schum（1994（2001年西北大学出版社重印）） | Wiley 出版社，纽约（专著）；2001年重印：Northwestern University Press。同一分类的后续概述：Schum, "Classifying Forms and Combinations of Evidence: Necessary in a Science of Evidence"，收录于 Evidence, Inference and Enquiry（英国国家学术院出版，2011） | 舒姆把多条证据之间的关系分成几类。 | 已确认 |
| 13 | 信息关系 | Joseph B. Kadane, David A. Schum；配套方法章节：A. Philip Dawid, David A. Schum, Amanda B. Hepler, "Inference Networks: Bayes and Wigmore"（1996（配套章节2011）） | Wiley 出版社，Wiley Series in Probability and Statistics（专著）；配套章节收录于 Evidence, Inference and Enquiry（英国国家学术院出版，2011） | 两位作者把萨科—万泽蒂案的全部证据画成威格莫尔图：每条证据要经过哪几步推理，才能连到最终要判断的问题上。 | 已确认 |
| 14 | 信息关系 | Thomas M. Cover, Joy A. Thomas（教科书）；William J. McGill（交互信息）（Cover & Thomas 1st ed. 1991; 2nd ed. 2006） | Elements of Information Theory，Wiley 出版社；McGill, "Multivariate Information Transmission"，Psychometrika 第19卷第2期，97-116页 | 一条信息对目标（例如未来5日收益或未来5日波动）有多大价值，不看它单独和目标的互信息，而看在已经知道其他信息以后，它还能再减少多少不确定性，也就是条件互信息。 | 已更正细节 |
| 15 | 信息关系 | Paul L. Williams, Randall D. Beer；正态变量情形：Adam B. Barrett；另一种定义：Nils Bertschinger, Johannes Rauh, Eckehard Olbrich, Jürgen Jost, Nihat Ay（2010（Barrett 2015；Bertschinger 等 2014）） | arXiv 预印本 arXiv:1004.2515（不是正式期刊论文）；Barrett：Physical Review E 第91卷第5期，文章号052802；Bertschinger 等：Entropy 第16卷第4期，2161-2183页 | 两个信息源X1、X2对目标Y的总信息可以拆成四块：只有X1有的（独有1），只有X2有的（独有2），两个都有的（冗余），只有合在一起才有的（协同）。 | 已确认 |
| 16 | 信息关系 | Benjamin Enke, Florian Zimmermann（2019（2017年网上先发）） | The Review of Economic Studies，第86卷第1期，313-332页 | 实验发现：很多人把彼此相关的信号（其实来自同一个底层信号的不同转述）当成相互独立的信号，同一条底层信息被重复计算。 | 已确认 |
| 17 | 信息关系 | Erik Eyster, Matthew Rabin（2010） | American Economic Journal: Microeconomics，第2卷第4期，221-243页 | 在一个接一个做决定的情境里，后来的人能看到前面所有人的行动，但天真地以为每个前人的行动只反映了他自己的私人信号，没意识到前人的行动其实已经吸收了更早那些人的行动。 | 已确认 |
| 18 | 信息关系 | Peter M. DeMarzo, Dimitri Vayanos, Jeffrey Zwiebel（2003） | The Quarterly Journal of Economics，第118卷第3期，909-968页 | 人们在社交网络中反复听到别人的观点，却没考虑到其中有重复：同一条信息可能经过不同路径多次传到自己这里，人们把它当成新信息。 | 已更正细节 |
| 19 | 信息关系 | Pietro Ortoleva, Erik Snowberg（2015） | American Economic Review，第105卷第2期，504-535页 | 把过度自信建模为相关性忽视：人们低估了自己收到的各条信息之间的相关性，以为自己掌握的独立信息比实际多，于是信心过高。 | 已确认 |
| 20 | 信息关系 | Erik Eyster, Matthew Rabin, Dimitri Vayanos（2019） | The Journal of Finance，第74卷第1期，371-399页 | 一部分交易者“受诅咒”：不从价格里推断别人掌握的信息，把自己的私人信息当成价格还没反映的新信息。 | 已更正细节 |
| 21 | 信息关系 | J. M. Bates, C. W. J. Granger；回归形式的推广：Clive W. J. Granger, Ramu Ramanathan（1969（推广 1984）） | Operational Research Quarterly 第20卷第4期，451-468页（该刊后改名 Journal of the Operational Research Society）；推广：Journal of Forecasting 第3卷第2期，197-204页 | 把多个预测合起来通常比单个预测更好，最优权重取决于每个预测误差的方差和误差之间的相关性。 | 已确认 |
| 22 | 信息关系 | Yock Y. Chong, David F. Hendry；David I. Harvey, Stephen J. Leybourne, Paul Newbold；相关回归方法：Ray C. Fair, Robert J. Shiller（1986；1998；1990） | Chong 和 Hendry：The Review of Economic Studies 第53卷第4期，671页起；Harvey、Leybourne、Newbold：Journal of Business and Economic Statistics 第16卷第2期，254-259页；Fair 和 Shiller：American Economic Review 第80卷第3期，375-389页 | 如果预测1已经包含了预测2的全部有用信息，那么把预测2加进组合不会带来任何改进，这就叫预测1“包含”预测2。 | 已确认 |
| 23 | 金融测量 | Olivier Coibion, Yuriy Gorodnichenko（2015） | American Economic Review 105(8): 2644-2678 | 用“事后的预测误差”去对“事前的预测修正幅度”做回归，检验预测者有没有把新信息用足。 | 已确认 |
| 24 | 金融测量 | Pedro Bordalo, Nicola Gennaioli, Yueran Ma, Andrei Shleifer（2020） | American Economic Review 110(9): 2748-2782 | 把上一条的回归放到“每个预测者自己”的层面来做：用某个预测者自己的修正去预测他自己的误差。 | 已确认 |
| 25 | 金融测量 | Pedro Bordalo, Nicola Gennaioli, Andrei Shleifer (2018); Pedro Bordalo, Nicola Gennaioli, Rafael La Porta, Andrei Shleifer (2019)（2018; 2019） | Journal of Finance 73(1): 199-227 (Diagnostic Expectations and Credit Cycles); Journal of Finance 74(6): 2839-2874 (Diagnostic Expectations and Stock Returns) | 代表性启发式的数学版本：人在看到新消息后，会过分看重那些“因为这条消息而变得更可能”的结果。 | 已确认 |
| 26 | 金融测量 | Nicholas Barberis, Andrei Shleifer, Robert Vishny（1998） | Journal of Financial Economics 49(3): 307-343 | 真实世界里盈利冲击是独立的（随机游走），但投资者以为世界在“均值回归”和“趋势延续”两种模式之间切换，并按贝叶斯规则判断现在处于哪种模式。 | 已确认 |
| 27 | 金融测量 | Kent Daniel, David Hirshleifer, Avanidhar Subrahmanyam（1998） | Journal of Finance 53(6): 1839-1885 | 两个偏差：一是过度自信，即高估自己私人信息的精度（以为噪声比实际小），于是对私人信息过度反应、对之后的公开信息相对反应不足；二是有偏的自我归因，即结果好时归功于自己、结果坏时归于运气，所以信心在顺利时上升、在不顺时几乎不降。 | 已确认 |
| 28 | 金融测量 | Eugene F. Fama（1970） | Journal of Finance 25(2): 383-417 | 有效市场的定义：价格已经“完全反映”了信息集 Φ_t 里的所有信息，所以基于 Φ_t 无法预测超出正常预期收益的部分（“公平博弈”）。 | 已确认 |
| 29 | 金融测量 | Victor L. Bernard, Jacob K. Thomas（1989） | Journal of Accounting Research 27 (Supplement): 1-36; companion: Journal of Accounting and Economics 13(4): 305-340 (1990), 'Evidence that stock prices do not fully reflect the implications of current earnings for future earnings' | 把“意外部分”标准化：实际盈利减去按历史规律预期的盈利，再除以过去意外幅度的标准差，得到标准化意外盈利。 | 已确认 |
| 30 | 金融测量 | Paul C. Tetlock (companions: Anastassia Fedyk and James Hodson 2023; Gur Huberman and Tomer Regev 2001)（2011） | Review of Financial Studies 24(5): 1481-1512 (companions: Journal of Financial Economics 149(1): 92-113, 2023, 'When can the market identify old news?'; Journal of Finance 56(1): 387-396, 2001, 'Contagious speculation and a cure for cancer') | 一条新闻的“陈旧度”定义为它与同一公司前十条新闻在文字上的相似度。 | 已确认 |
| 31 | 金融测量 | David Hirshleifer, Siew Hong Teoh (2003); Stefano DellaVigna, Joshua M. Pollet (2009)（2003; 2009） | Journal of Accounting and Economics 36(1-3): 337-386 ('Limited attention, information disclosure, and financial reporting'); Journal of Finance 64(2): 709-749 ('Investor inattention and Friday earnings announcements') | 注意力有限的投资者只处理显眼、容易处理的信息。 | 已确认 |
| 32 | 金融测量 | Brad M. Barber, Terrance Odean（2008） | Review of Financial Studies 21(2): 785-818 | 个人投资者是“引人注意的股票”的净买入者：当天上新闻、成交量异常放大、或单日涨跌极端的股票。 | 已确认 |
| 33 | 金融测量 | Pedro Bordalo, Nicola Gennaioli, Andrei Shleifer（2012; 2022） | Quarterly Journal of Economics 127(3): 1243-1285; Annual Review of Economics 14: 521-544 | 注意力被“显眼”的东西自下而上地吸引，从而扭曲决策权重。 | 已确认 |
| 34 | 金融测量 | Ned Augenblick, Eben Lazarus, Michael Thaler（2025） | Quarterly Journal of Economics 140(1): 335-401 | 人们知道该往哪个方向更新，但对“该更新多少”的估计不精确，于是把信号强度往中间压缩：弱信号被高估（过度推断），强信号被低估（推断不足）。 | 已确认 |
| 35 | 大模型 | Julian Coda-Forno, Marcel Binz, Jane X. Wang, Eric Schulz（2024） | ICML 2024 (Proceedings of Machine Learning Research, volume 235); arXiv 2402.18225 | 用七个经典认知心理学实验给三十五个大语言模型做行为画像。 | 已更正细节 |
| 36 | 大模型 | Fabian Falck, Ziyu Wang, Chris Holmes（2024） | ICML 2024 (Proceedings of Machine Learning Research, volume 235); arXiv 2406.00793 | 真正的贝叶斯学习者必须满足“鞅性质”：在只知道今天信息的情况下，它对“将来自己会怎么想”的平均预期，就等于它今天的想法。 | 已确认 |
| 37 | 大模型 | Leland Bybee（2023） | SSRN working paper (doi 10.2139/ssrn.4430515) | 让大语言模型读1984年到2021年的《华尔街日报》新闻，再问它对各种金融变量和宏观变量的预期，拼成一份“模型版的预期调查”。 | 已确认 |
| 38 | 大模型 | Huaman Sun, Dingcheng Wang, Jason Hartline, Jessica Hullman（2026） | arXiv preprint 2609.38005 | 用统计决策论把大语言模型的决策损失拆成两块。 | 已确认 |
| 39 | 大模型 | Archiki Prasad, Swarnadeep Saha, Xiang Zhou, Mohit Bansal（2023） | EMNLP 2023; arXiv 2304.10703 | 把推理链看成一份非正式的证明，从两个方面打分。 | 已确认 |
| 40 | 大模型 | Tamera Lanham, Anna Chen, Ansh Radhakrishnan, Benoit Steiner, Carson Denison, Danny Hernandez, Dustin Li, Esin Durmus, Evan Hubinger, Jackson Kernion, Kamilė Lukošiūtė, Karina Nguyen, Newton Cheng, Nicholas Joseph, Nicholas Schiefer, Oliver Rausch, Robin Larson, Sam McCandlish, Sandipan Kundu, Saurav Kadavath, Shannon Yang, Thomas Henighan, Timothy Maxwell, Timothy Telleen-Lawton, Tristan Hume, Zac Hatfield-Dodds, Jared Kaplan, Jan Brauner, Samuel R. Bowman, Ethan Perez（2023） | arXiv preprint 2307.13702 | 直接改动思维链，看答案会不会跟着变。 | 已更正细节 |
| 41 | 大模型 | Miles Turpin, Julian Michael, Ethan Perez, Samuel R. Bowman（2023） | NeurIPS 2023; arXiv 2305.04388 | 在输入里加“偏置特征”，例如少样本示例的正确答案总是选项A，或者在提示里暗示某个答案。 | 已确认 |
| 42 | 大模型 | Yanda Chen, Joe Benton, Ansh Radhakrishnan, Jonathan Uesato, Carson Denison, John Schulman, Arushi Somani, Peter Hase, Misha Wagner, Fabien Roger, Vlad Mikulik, Samuel R. Bowman, Jan Leike, Jared Kaplan, Ethan Perez（2025） | arXiv preprint 2505.05410 | 在提示里放六类线索（四类中性的：迎合用户、前后一致、视觉规律、元数据；两类不当的：钻评分器的空子、使用不正当得来的信息），测最先进的推理模型。 | 已确认 |
| 43 | 大模型 | Linlu Qiu, Fei Sha, Kelsey Allen, Yoon Kim, Tal Linzen, Sjoerd van Steenkiste（2026） | Nature Communications 17, article 1238 (2026), doi 10.1038/s41467-025-67998-6; arXiv 2503.17523 | 在一个五轮的航班推荐任务里，大语言模型要从用户每轮的选择中慢慢推断用户偏好，表现远不如贝叶斯模型。 | 已确认 |
| 44 | 大模型 | Hunter Lightman, Vineet Kosaraju, Yura Burda, Harri Edwards, Bowen Baker, Teddy Lee, Jan Leike, John Schulman, Ilya Sutskever, Karl Cobbe（2023） | ICLR 2024; arXiv 2305.20050 | 比较两种训练奖励模型的办法：结果监督（只看最后答案对不对）和过程监督（每一步都标对或错）。 | 已确认 |
