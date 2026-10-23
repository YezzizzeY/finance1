# 呈现方式试验（presentation pilot）

**把同样的价格读数换一种写法给大模型交易代理看，它对未来 5 个交易日的预测会不会变？**
这是一个很小的探索性试验，共 300 次运行：5 个模型 × 2 种代理框架 × 6 个交易日 × 每天 5 次。
本仓库附带全部输入、全部运行记录，以及用来核对、重算和重跑的代码。英文版见 [README.md](README.md)。

代理每次只交易一只美股。每天它会看到 7 条价格工具读数：趋势、相对强弱指数、均值回归、平滑异同移动平均、
价格统计、支撑与阻力、波动率。试验不改信息本身，只改写法，共三种：

- **NOLABEL**：去掉“看涨”“偏低”这类文字标签；
- **UNIT5D**：把年化波动率换算成 5 日波动率；
- **PLACEBO**：只打乱字段顺序，用来衡量“文字有任何改动”本身带来的影响。

代理随后给出两个预测：5 日收益率，以及 5 日波动率（一个标准差，单位为百分数）。试验要回答两个问题：
这些改写让预测变化的幅度，是否超过同一题目重复运行时的自然波动？这种影响是否因模型而异，
是否因框架而异？两种框架分别是：我们自己的 32 个工具的调用框架（下称“工具框架”），
以及在只含当日之前数据的文件夹里写代码的 Codex CLI。

## 设计一览

| | |
|---|---|
| 模型 | 5 个能看到推理过程的模型（[PROTOCOL § Models](docs/PROTOCOL.md#models)）：Qwen3-8B、Qwen3.5-9B、Qwen3.8-27B-FP8（本地 vLLM 0.29.0 部署）；DeepSeek（请求名 `deepseek-reasoner`，接口返回的名字是 `deepseek-flash`）；Kimi K3（`kimi-k3`） |
| 框架 | **工具框架**：32 个只给当日之前数据的工具，最多 10 轮，用 `submit_decision` 提交决定。**Codex CLI 0.162.1**：在受限文件夹里读 `prices.csv`、`news.csv`、`account.json`、`task.md`，把决定写进 `decision.json` |
| 交易日 | 6 天，用种子 20261018 从 250 个候选日中抽取。3 个大波动日（\|z\| ≥ 2）：MCHP 2026-08-07、HOOD 2026-04-14、CRWD 2026-08-27；3 个普通日（\|z\| < 1）：VST 2026-05-06、CB 2026-04-22、MRK 2026-05-07 |
| 改写方式 | ORIG（原样，跑两次，用来量自然波动）、NOLABEL、UNIT5D、PLACEBO，每天共 5 次 |
| 运行 | 5 × 2 × 6 × 5 = 300 次。可用 286 次：4 次决定无效，10 次编程代理运行被泄露审计标记 |
| 观察指标 | `expected_vol_pct` 和 `expected_return_pct`；相对 ORIG 与相对 PLACEBO 的变化；把年化数字直接当作 5 日波动率填写（下称“照抄年化数”）；与实际 5 日波动率的差距 |

完整设计见 [docs/PROTOCOL.md](docs/PROTOCOL.md)，工具说明见 [docs/TOOLS.md](docs/TOOLS.md)。

## 主要发现

这是探索性试验：只有 6 天，每种改写每天只跑一次。**下面没有一条是统计检验。**
数字取自 [`results/describe_reasoning_models.json`](results/describe_reasoning_models.json)，
表格、原文摘录和全部规则见[结果页](results/describe_reasoning_models.md)。

<!-- 来源与英文版 README 相同：results/describe_reasoning_models.json 与 results/describe.json -->

- **只有两个小 Qwen 模型会照抄年化数。** 在它们 115 次可用运行中，按严格口径（落在当天四个年化读数的
  最小值乘 0.9 与最大值乘 1.1 之间）出现 9 次，按宽口径（取对数后离年化尺度比离 5 日尺度更近）出现 12 次
  （见 [PROTOCOL § Measures](docs/PROTOCOL.md#measures)）。
  Qwen3.8-27B、DeepSeek、Kimi K3 在两种框架下都没有出现过（171 次中 0 次）。
- **所有模型都注意到了年化读数。三个较大模型从不照抄；两个小 Qwen 在提到年化数的运行中，约每 10 次仍有 1 次照抄。**
  三个较大模型的推理在 171 次中有 136 次提到年化数，这 136 次没有一次照抄，例如“45% × sqrt(5/252) ≈ 6.35%”。
  两个小 Qwen 在 115 次中有 65 次提到，其中 6 次仍然照抄（宽口径 8 次）。
- **UNIT5D 只有在读数是唯一来源时，才能让年化数消失。** Codex 的 UNIT5D 运行没有一次提到年化数
  （28 次中 0 次）。工具框架里，DeepSeek（6 次中 6 次）、Qwen3.8-27B（6 次中 5 次）、Kimi K3（6 次中 1 次）
  仍会提到。原因是它们会调用 `get_risk_budget`（分别在 30 次中的 29、28、16 次），这个工具用年化单位
  报告 20 日波动率，而且任何改写方式都不改它。
- **与 PLACEBO 相比，多数变化都在自然波动之内。** 共 40 组“改写减 PLACEBO”的比较（10 个格子 × 2 种改写
  × 波动率和收益率），有 6 组超过结果页的粗略标准（两倍标准误差）；只看波动率是 20 组中 4 组。
  在这 6 组中，6 天里每天都不高于零的只有两组，都出自 Kimi K3 的 UNIT5D：工具框架里对数波动率低 0.22，
  Codex 里收益率预测低 0.75 个百分点。其余几组要么只靠一天，要么只有 3 天，要么来自照抄年化数
  （见结果页第 4 条说明）。
- **能看出多大的变化，取决于自然波动。** 两次 ORIG 运行的对数波动率之差：Kimi K3 / Codex 和
  Qwen3.8-27B / Codex 为 0.09，DeepSeek 和 Kimi K3 / 工具框架为 0.14 到 0.16，Qwen3.8-27B / 工具框架为
  0.28，两个小 Qwen 为 0.35 到 0.70。约 0.1 的变化只有在最平稳的格子里才看得出来。
- **三个较大模型的准确度与两个不需要代理的简单预测差不多。** 它们的误差（预测与实际 5 日波动率之比取对数后的
  绝对值）平均为 0.39 到 0.41（两种框架都是），比两个简单预测略低：把读数中的 20 日波动率换算成 5 日单位得 0.48，
  S1 先验（登记过的理性模型给当天的 5 日标准差）得 0.43。每个差距都小于该格子按天计算的标准误差（0.08 到 0.15），
  所以这六个格子彼此分不出高下，与两个简单预测也分不出高下。两个小 Qwen 为 0.54 到 0.67。所有格子的预测平均都偏高。
- **框架改变了模型做多少事。** 工具框架里每次运行的工具调用次数：DeepSeek 12.1，Qwen3.8-27B 9.1，
  Kimi K3 3.7，两个小 Qwen 约 1 次。Codex 里用 `prices.csv` 自己算过波动率的运行：DeepSeek 23/23，
  Qwen3.5-9B 25/29，Qwen3.8-27B 23/28，Kimi K3 19/30，Qwen3-8B 0/26。

![提到年化数与照抄年化数](results/figures/mention_vs_paste.svg)

*左：推理中提到当日年化数的运行占比。右：在这些运行中，最终 5 日波动率仍是那个年化数的占比（严格口径）。*

![UNIT5D 减 PLACEBO：波动率预测的变化](results/figures/unit5d_minus_placebo.svg)

*UNIT5D 减 PLACEBO 的对数波动率预测：各天平均值和正负两倍标准误差，灰色带是该格子两次 ORIG 之间的
自然波动。其余三张图和全部输出的说明见 [`results/README.md`](results/README.md)。*

## 复现

| 层级 | 说明什么 | 需要什么 | 用时（只用处理器） |
|---|---|---|---|
| **L0** | 每个输入字节、提示词、工具定义和工具输出都与试验所用的一致 | 只要本仓库 | 约 16 秒 |
| **L1** | 每条记录、每个报告出来的数字都能从运行日志重算出来（四项机制分析的结果从保存的会话重算） | 先解压运行记录（436 MB） | 约 10 秒 + 42 秒 |
| **L2** | 对 150 次编程代理运行重做泄露审计，结论不变 | 先解压运行记录 | 约 6 秒 |
| **L3** | 按同一流程重跑任意“模型 × 框架”格子 | Linux 6.7 以上内核、显卡或接口密钥、Codex 0.162.1 | 每格几分钟到一小时 |

先在仓库根目录用 Python 3.12 安装一次。必须用可编辑方式（`-e`）安装，因为代码按仓库位置寻找
`data/` 和 `records/`：

```sh
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r setup/requirements/runner.txt -e ".[test]"     # 或：make setup
```

```sh
finagent verify --level L0    # 11 of 11 checks passed (L0)
finagent unpack               # 4443 of 4443 files in records/raw match records/MEMBERS.sha256
finagent verify --level L1    # 17 of 17 checks passed (L1)
finagent verify --level L2    # 2 of 2 checks passed (L2)
```

`make verify` 一次做完以上全部：需要时先解压，最后输出 `30 of 30 checks passed (L0, L1, L2)`，在原试验机器
（两颗 Xeon Platinum 8352V）上约 65 秒。`finagent analyze --check` 对 `results/` 的 6 个文件都报告 `same`，
`finagent audit` 报告 `150 of 150 verdicts identical`。每项检查的说明见 [REPRODUCING](docs/REPRODUCING.md)。

**L3：重新运行。** 先按 [docs/REPRODUCING.md](docs/REPRODUCING.md) 准备好机器：沙箱、Codex 0.162.1、
代理用的 Python 环境、vLLM 和模型权重（或接口密钥）。然后跑一个格子：

```sh
export FINAGENT_HOST_ENV=$HOME/finagent-host.env     # 你复制并修改过的 setup/host.example.env
finagent run --model kimi --framework harness --dry-run   # 只写出 30 次运行的输入并检查机器，不联系任何模型
finagent run --model kimi --framework harness             # 30 次运行写入 runs/pilot/raw，中断后可接着跑
finagent analyze --raw runs/pilot/raw --out runs/pilot/results   # 用同样的规则算出新格子的各项指标
```

重跑沿用同一流程，但输出不会逐字节相同：采样、接口背后的模型版本、Codex 按机器生成的提示文字都会变。
[REPRODUCING § Expected differences](docs/REPRODUCING.md#expected-differences) 逐条列出了差异来源。

## 仓库结构

```
.
├── README.md, README.zh-CN.md   本说明（英文、中文）
├── LICENSE                      MIT 许可，只管代码
├── DATA_LICENSE.md              本项目记录与数据采用 CC BY 4.0；第三方材料的条件与新闻文字的声明
├── pyproject.toml, Makefile     finagent 程序包；make setup | unpack | verify | analyze | audit | prompts | figures | test | clean | mechanisms
├── setup/
│   ├── experiment.toml          设计常数：交易日、改写方式、每种的次数、种子、轮数上限、工具结果截断长度、时间上限、并发数
│   ├── models.toml              每个模型一张表：名字、接口地址、请求参数、Codex 设置、vLLM 参数、权重版本
│   ├── host.example.env         新运行用的机器设置：路径、端口、显卡
│   ├── host.recorded.env        原试验机器的设置，重做审计时要用
│   ├── weights/                 三个本地模型每个权重、配置、分词文件的 sha256
│   ├── requirements/            锁定版本的依赖清单：runner.txt、agent-env.txt、vllm.txt
│   └── scripts/                 新运行的机器准备脚本：运行环境、代理环境、Codex 0.162.1、vLLM 环境、权重
├── data/                        全部输入，与原文件逐字节相同：交易日、价格面板、按时间截断的数据缓存（96 只股票）、起始状态、抽样文件
│   ├── prompts/                 模型看到的全部文字，由 finagent prompts 生成（72 个文件）
│   ├── evidence_relations/      CPU 计算的扩展输入内容：交易日全集、真实新闻/数字改写、工具冗余度矩阵、合成双信号贝叶斯基准
│   └── mechanisms/              四项机制分析的输入：保存下来的交易会话和多日轨迹、理性基准表
├── src/finagent/
│   ├── cli.py, config.py        finagent 命令；目录、配置、机器设置
│   ├── data/                    按时间截断的数据缓存、公司行为、实际结果、起始状态
│   ├── harness/                 框架一：32 个工具、提示词、多轮循环、模型客户端、一次运行到一条记录
│   ├── coding/                  框架二：Codex 工作目录与配置、沙箱、转发服务、泄露审计
│   ├── readings.py, arms.py     读数段落与四种改写
│   ├── days.py, records.py      抽取交易日；运行清单、种子、解析决定、写记录
│   ├── promptgen.py             生成 data/prompts/
│   ├── run.py, serve.py         批量运行与 vLLM 启动（L3）
│   ├── analysis/                规则、五模型结果页、运行计数、矢量图
│   ├── evidence_relations/      交易日全集、真实新闻/数字改写、工具冗余度矩阵、合成双信号贝叶斯基准及其三个参照预测模型
│   │                            （`finagent evidence-pool|evidence-real-day|evidence-tools|evidence-synthetic|evidence-reference-models`）
│   ├── mechanisms/              显眼数字、调用位置、调仓对比、思考过程四项分析；结果网页；理论文档
│   │                            （`finagent mech-salience|mech-proximity|mech-position|mech-thinking|mech-page|mech-theory-doc`）
│   └── verify.py                L0 到 L2 的各项检查，以及 finagent unpack
├── records/                     运行证据：runs.jsonl（300 条记录）、11 个运行文件夹压缩包、基础设施日志与检查、哈希
├── results/                     分析输出与图，由 finagent analyze 和 finagent figures 重算
│   ├── evidence_relations/      reference_models/：合成基准的三个非大模型基线（属于分析输出）
│   └── mechanisms/              四项分析各自的 data.json 和 README.md；page/mechanisms.html 结果网页
├── docs/                        PROTOCOL、REPRODUCING、TOOLS、DATA、PROVENANCE、ENVIRONMENT、LIMITATIONS、MECHANISMS、GOOD_THINKING
│                                （good_thinking/ 里是理论文档和它的文献数据）；Codex 材料的 Apache-2.0 全文
└── tests/                       包住各项检查的测试，以及从原代码录下的标准答案
```

## 数据里有什么

| 文件夹 | 内容 | 大小 |
|---|---|---|
| [`data/`](data/README.md) | 交易日、美股日线价格面板及其 Hugging Face 原始快照、每只股票一份按时间截断的缓存（日线、新闻、公司行为；共 96 只股票——6 只用于本次试验，另外 90 只给 `evidence_relations/` 用）、250 份起始会话、登记过的抽样文件 | 937 个文件，171.4 MB |
| [`data/prompts/`](data/prompts/README.md) | 系统提示、工具定义、提醒语、代理指令，以及每天每种改写的工具框架提示和 `task.md` | 72 个文件 |
| [`records/`](records/README.md) | 每次运行的 `record.json`；每次运行的会话或 Codex 日志、转发的请求与回答、系统调用跟踪、工作目录；试跑和审计金丝雀运行；vLLM、转发、批次日志 | 11 个压缩包，压缩后 12.6 MB，解压后 4,443 个文件、436 MB |
| [`results/`](results/README.md) | 五模型结果页、指标、摘录、运行计数、五张图 | 6 个文件和 5 张图 |
| [`data/mechanisms/`](data/mechanisms/README.md) + [`results/mechanisms/`](results/mechanisms/) | 250 个真实交易日上保存下来的 5,000 个工具代理会话（通义千问 3.5-9B 和 3-8B）、2,000 个读数写在提示里的会话、6 份多日交易轨迹、理性基准表，放在 `data/` 下；四项分析的 data.json 和结果网页放在 `results/` 下 | 输入共 7,011 个文件，107.9 MB |
| [`data/evidence_relations/`](data/evidence_relations/) + [`results/evidence_relations/`](results/evidence_relations/) | 交易日全集（197 天、96 只股票）、真实新闻/数字改写（4 组，1,742 行，带已知的正确答案）、工具冗余度矩阵（23 个工具 x 96 只股票 x 约 248 天）、一个合成的双信号贝叶斯基准（30 种条件，153,600 行，以 xz 压缩发布，共 13.0 MB，放在 `data/` 下）及其三个参照预测模型（属于分析输出，放在 `results/` 下） | 详见各子文件夹自己的 README.md |

每个文件都有 sha256，分别记在 `data/MANIFEST.sha256`、`data/mechanisms/MANIFEST.sha256`、`records/SHA256SUMS`、`records/MEMBERS.sha256`。
数据追溯到供应商的来历见 [docs/PROVENANCE.md](docs/PROVENANCE.md)，逐个文件的说明见 [docs/DATA.md](docs/DATA.md)。

> **第三方新闻文字。** `data/`（包括 `data/prompts/`）、`records/`、`tests/fixtures/` 中的新闻标题和摘要取自 Finnhub 公司新闻接口，
> 由原出版方撰写。收录它们只为非商业研究能逐字节复现本试验。版权仍属出版方和 Finnhub，本仓库不声称、
> 也不授予任何使用许可；权利人要求删除的，我们会删除（见 [DATA_LICENSE.md](DATA_LICENSE.md)）。

## 局限

- **规模小。** 只有 6 天，每种改写每天一次。两倍标准误差的标准只依据 4 到 6 对 ORIG 运行，
  所以有些“超出”本来就会偶然出现。
- **各行的设置不完全相同。** 每轮的输出长度上限（2,048 到 16,384）、推理强度、Codex 所用服务端的默认采样
  都因模型而异，跨行比较要小心。改写带来的变化是在同一格子里比的，不受这些差异影响。
- **重跑结果会不同。** vLLM 的批处理与前缀缓存、接口调用没有种子、`deepseek-reasoner` 是别名、
  Codex 自己写进提示的运行日期、时区和随机工作目录，都会改变重跑的输出。
- **沙箱挡住写入和联网，但不挡读取。** 编程代理可以读工作目录以外的文件；审计记下每一次访问，
  被标记的 10 次运行已排除。
- **工具的怪处有意保留。** 财报工具默认股票代码是 AAPL；记忆和校准工具按 1 日涨跌打分；
  `get_risk_budget` 用年化单位报告波动率，任何改写都不改它。

完整的局限及依据见 [docs/LIMITATIONS.md](docs/LIMITATIONS.md)。

## evidence_relations：模型是在权衡信息，还是只是在数信息？

本仓库的第二个、相互独立的扩展，放在 `data/evidence_relations/`（四份输入/基准数据）和 `results/evidence_relations/`
（`reference_models/` 这一项分析输出）两处：只用处理器，不用显卡，不调用任何模型，
不属于上面的试验，也不在 `finagent verify` 的检查范围内。它问的是另一个问题：代理同时看到不止一条证据时，
它会不会去掉重复信息、按可信度加权、忽略过时的重复读数——还是只会数有几条信息，跟着数字最大的那条走？
下面每个数字都来自代码——闭式公式或者对真实行情与新闻数据的穷举遍历——从不来自模型自己的输出，移植自已经核验过、
已经跑过的 `1_overreaction/repro/evidence_relations`，在这里重新独立推导和核对过，不是照搬。
完整设计见 [docs/EVIDENCE_RELATIONS.md](docs/EVIDENCE_RELATIONS.md)。

- **合成双信号贝叶斯基准。** 在 AR(1) 预测任务上加一个第二噪声信号，它与第一个信号的冗余程度 `c` 是已知参数，
  所以贝叶斯最优用法有闭式解。30 种条件，共 153,600 行（训练 76,800 / 验证 38,400 / 测试 38,400），以 xz 压缩发布
  （13.0 MB，解压后 660 MB），sha256 层面与源项目自己的文件逐字节相同。
- **三个参照预测模型。** 在合成基准的测试集（38,400 行）上跑三个确定性的非大模型预测器，让人在任何真实模型被测试之前
  先看清问题的形状：朴素平均法随着两个信号越来越冗余（`c`：0 → 0.95），平均绝对误差变差 39.5%（因为它一直在重复计数
  同一份信息）；"哪个数字大听哪个"的跟随法反而变好 15.0%（原因相反）；贝叶斯最优预测器在每个冗余水平下误差都最低
  （c=0/0.5/0.95 时 MAE 分别为 9.15/10.21/10.61）。
- **真实交易日改写。** 四组改写，用真实标题和真实数字构造，基于和本试验选日子一样的 197 天日池，覆盖全部 96 只
  `data/pit_cache` 股票：`redundancy_copies`（788 行，精确结论——把同一条读数换着法子多写几遍，预测不该变）、
  `already_priced_in`（394 行，有依据的序关系假设——换成更早一天的真实标题，应该比"同一条标题已经体现在今天价格里"
  让预测变化更大）、`stale_news`（394 行，含一处近似推导）、`position_swap_conflict`（280 行里可构造出 166 行——
  只调换顺序，预测不该翻转）。*`already_priced_in` 这组在 2026-10-20 修复过：只允许拼接 day t 之前的标题，绝不拼接
  之后的（修复前的版本有 52/197 行泄漏了未来事件）；本次移植复现的是修复后的版本，并独立确认 197 行里 0 行泄漏。*
- **工具冗余度矩阵。** 把工具框架里 23 个无状态工具，按工具框架调用它们的方式原样调用一遍，走遍全部 96 只股票的
  真实历史行情与新闻（23,777 行"股票 x 交易日"记录，保留 69 个数值字段）。136 组工具两两搭配里，42 组完全互相独立，
  0 组完全冗余；最大的近似重复簇有 22 个字段，横跨 **7** 个不同的工具，全是"今天收盘价"的各种写法（不是早先某个说法
  里的"约 10 个工具"——这个数字我们核对了数据后做了更正，没有照搬下来）。**"整体独立"不等于"每只股票都独立"**：
  这 42 组"独立"工具对里，按单只股票分别算相关系数，范围能到约 −0.97 到 +0.95，所以拿某一组当某只具体股票的
  "独立信息"例子之前，应该先查 `per_ticker_matrix.parquet`。

这是一套基准和一批已经算出来的参照结果，不是真实模型的结果：无论是上面试验用到的五个模型，还是其他任何模型，
目前都还没有在这上面跑过。

```sh
cd finance1
finagent evidence-pool && finagent evidence-real-day && finagent evidence-tools --workers 32   # 日池、真实改写、工具矩阵
finagent evidence-synthetic && finagent evidence-reference-models                               # 合成基准、参照模型
```

或者 `make evidence-pool evidence-real-day evidence-tools evidence-synthetic evidence-reference-models`。
各子文件夹清单见 [data/README.md](data/README.md#evidence_relations)；完整设计、真实改写各组按各自精确程度表述的
正确答案、工具冗余度的方法论，见 `docs/EVIDENCE_RELATIONS.md`。

## 机制分析：代理为什么反应过度？

四项分析，用的是已经跑完、保存下来的代理会话（主要是通义千问 3.5-9B，通义千问 3-8B 做交叉核对），放在
`data/mechanisms/` 和 `results/mechanisms/`：只用处理器，不调用任何模型，不属于上面的试验，但 `finagent verify`
会检查它们（L0 一项数据核对，L1 六项逐字节重算）。每一项都在问：项目之前发现的反应过度，能不能在会话里找到一个具体原因。
完整方法、数字和说明见 [docs/MECHANISMS.md](docs/MECHANISMS.md)。

- **显眼的年化数字：平均看没有影响，但少数会话整个照抄。** 知道理性的 5 日波动之后，年化大数字对 5 日波动预测
  没有额外影响（系数 −0.007，t = −0.36，1,445 个会话）。但 1,445 个会话里有 27 个（1.9%）直接把年化数字当成 5 日波动
  交上来，这些预测平均差了约 5.6 倍，其余会话约 1.9 倍（t = 8.8）。照抄的会话很少，所以照抄比例本身不太准；有没有新闻
  看不出差别（2.2% 对 1.6%，p ≈ 0.43，样本少，检验力弱）。
- **离提交最近的数字：没有影响，而且数据足够看出影响。** 波动率工具是不是最后一个调用，不改变它的数字对预测的影响：
  128 天里两种调用顺序都有，共 420 个会话，斜率差 p = 0.59，按天固定效应 p = 0.73。原计划的第二个检验做不了：
  `get_risk_budget` 和 `get_volatility_stats` 给出的是同一个 20 日数字（32 个会话里 32 个完全相同）。
- **调仓：改动的离散程度是理性规则的约 6.7 倍。** 在 692 个相邻交易日的改动上（只有 2026 年 1 月这一个时间段能对上
  理性基准），代理仓位改动的标准差是一个凯利式理性规则的 6.7 倍，而且方向也对不上（斜率 +0.22，按聚类算的标准误约 0.29；
  秩相关 −0.16）。这个倍数随规则的比例系数 k 变化（k 加倍时 3.4，减半时 10.8）；大事日只有 16 个改动、5 只股票，
  太少，测不出平静日和大事日的区别。
- **思考过程：有新闻时关联的说法更多，但真正的关联很少。** 4,000 段思考文字里，有新闻时“关联信息”的说法（严格口径）
  更常见（63.2% 对 51.7%，z = 7.3）。但人工细读后，大约只有四分之一（17 个里 4 个，95% 置信区间 9.6% 到 47.3%）是在
  真正把两条证据联系起来；同时用到新闻和波动率工具的会话里，只有 2.8% 在同一句话里把两者连起来说。方法是关键词匹配，
  不是经过验证的分类器。

`results/mechanisms/page/mechanisms.html` 用中文展示这四项结果，和研究工作区的网页逐字节相同。
[docs/GOOD_THINKING.md](docs/GOOD_THINKING.md)（也有 Word 版 `docs/good_thinking/good_thinking_20261023.docx`）
从文献出发说明“好的思考”应该是什么：信息分量、信息之间的关系、怎么测，附 44 条逐条独立核对过的文献。

```sh
make mechanisms                # 四个 data.json、结果网页和理论文档（约 30 秒）
finagent mech-thinking --check # 在内存里重算其中一项，和仓库里的文件比对
```

## 许可

代码采用 MIT 许可（[LICENSE](LICENSE)）。本项目自己的运行记录、数据、结果、图和提示文字采用
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 许可。第三方材料沿用各自的条件，详见
[DATA_LICENSE.md](DATA_LICENSE.md)：价格数据集没有注明许可；新闻文字我们没有任何许可；
Codex 的内置说明和工具定义是 Apache-2.0（全文见 [docs/Apache-2.0.txt](docs/Apache-2.0.txt)）。
