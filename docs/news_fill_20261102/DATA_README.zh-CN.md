# data/：本项目全部输入数据

这里是本项目全部输入数据的统一存放处。模型运行记录（实验结果、训练产出、轨迹）不放在这里，留在各实验自己的结果文件夹里。

- **按用途分文件夹**：行情、财报、公告、新闻、宏观、构造好的数据集各一个文件夹，原始下载单独放在 `raw/`。
- **每份数据都能重建**：下载和整理脚本在 `_scripts/`。钥匙在运行时从 `keys.txt` 读取，不写进任何文件。
- **每个文件夹都有 `MANIFEST.sha256`**：用 `sha256sum -c MANIFEST.sha256` 可以核对文件有没有损坏或被改动。
- **完整盘点**：在 `_inventory/INVENTORY.md`（中文）和 `_inventory/INVENTORY.csv`。
- **搬迁记录**：2026-10-30 调整过目录，旧路径到新路径的对照在 `_inventory/MOVES_20261030.tsv`；运行 `_inventory/restore_20261030.sh` 可以撤销这次调整。
- **代码不受影响**：现有代码读的都是 `datasets/` 下的文件，这个文件夹没有动。

当前总大小约 3.0 GB（2026-11-02 按股票清理后；其中 `datasets/` 约 1.5 GB、`raw/` 约 1 GB）。

## 目录

| 文件夹 | 内容 |
|---|---|
| `market/daily/` | 日线价格：三份旧面板、道指 30、**全美股票日线（Databento，新）**、**96 只主实验股票的复权日线和市值（Index One，新）** |
| `market/intraday_1m/` | **96 只主实验股票的 1 分钟 K 线（Databento，新）** |
| `market/reference/` | **证券基本资料：行业、上市日期、流通股本、各种代码对照（Index One，新）** |
| `market/membership/` | 标普 500 历史成分股，按月末整理 |
| `fundamentals/` | **季度和年度财报：利润表、资产负债表、现金流量表，带提交时间（Index One，新）** |
| `filings/` | 公司公告：8-K 重大事件、业绩公告及真实公开时间、内部人交易、新闻稿全文 |
| `news/` | 公司新闻：去重打标的主表、时间校正后的索引、逐日覆盖表、道指 30 新闻原始下载（2026-11-02 按单日补抓过缺口） |
| `macro/fred/` | 宏观指标日频表、发布表、历史修订版本 |
| `macro/fed/` | 议息会议、货币政策公告、发布后被改过的页面清单 |
| `macro/indexone/` | **美国月度宏观（通胀、就业、利率、GDP 等）、主要大宗商品和汇率日线（Index One，新）** |
| `datasets/` | 构造好的、实验直接读取的数据集（没有改动） |
| `raw/` | 原始下载，原样保存，按来源和日期分文件夹 |
| `_scripts/` | 下载、整理、核对脚本 |
| `_inventory/` | 盘点、搬迁记录、核对结果 |

## 2026-10-30 新增的数据

| 文件 | 来源 | 范围 | 行数 | 说明 |
|---|---|---|---|---|
| `market/intraday_1m/equs_mini_ohlcv1m_96_20250929_20260925.parquet` | Databento EQUS.MINI | 96 只主实验股票，2025-09-29 至 2026-09-25 | 8,903,030 | 1 分钟 K 线，未复权 |
| `market/daily/databento_equs_summary_ohlcv1d_20240701_20261028.parquet` | Databento EQUS.SUMMARY | 全美 16,586 个代码，2024-07-01 至 2026-10-28 | 6,960,347 | 日线，未复权 |
| `market/daily/indexone_eod_96_20170103_latest.parquet` | Index One | 96 只主实验股票，2017-01-03 至 2026-10-29 | 230,960 | 原价、拆股复权、拆股加分红复权三套价格，带市值 |
| `market/reference/indexone_securities_reference.parquet` | Index One | 647 个代码 | 647 | 行业、上市日期、流通股本、各种代码对照 |
| `fundamentals/indexone_quarterly.parquet` | Index One | 644 只股票，2015 年起 | 27,956 | 季度三大报表，119 个科目，带提交时间 |
| `fundamentals/indexone_annual.parquet` | Index One | 644 只股票，1985 年起 | 18,671 | 年度三大报表，同上 |
| `macro/indexone/country_macro_us_monthly.parquet` | Index One | 1990-01 至 2030-12 | 492 | 美国月度宏观，含 50 行预测值 |
| `macro/indexone/commodity_daily.parquet` | Index One | 13 个品种，2015 年起 | 38,948 | 原油、天然气、金银铜、股指期货、国债期货、美元指数 |
| `macro/indexone/fx_daily.parquet` | Index One | 7 个币种，2015 年起 | 22,545 | 欧元、日元、英镑、人民币、加元、瑞郎、比索兑美元 |

- 原始下载在 `raw/databento_20261030/` 和 `raw/indexone_20261030/`，每页原件都留着，脚本可以从原件重新拼出上面的表。
- Databento 花费 16.46 美元（1 分钟 K 线 5.57，全美日线 10.89），每个文件的花费记在 `raw/databento_20261030/requests.jsonl`。
- 648 个代码里，EQR 在 Index One 查不到；SPY 是基金，没有财报；BK 与 BNY、SATS 与 ECHO 是同一只证券，财报只存一份，所以财报是 644 只。
- 这些数据有使用许可限制，**不能公开分发**。公开的 finance1 仓库里只放脚本、说明和校验结果，不放数据本身。

### 新数据的核对

核对结果在 `_inventory/verify_20261030.json`，由 `_scripts/verify_20261030.py` 生成。

| 核对内容 | 对上的样本 | 日收益差在 0.2% 以内 | 差超过 2% |
|---|---|---|---|
| 1 分钟 K 线（每天最后一根收盘）对主实验日线 | 96 只，23,772 天 | 98.05% | 0.02% |
| Databento 全美日线对主实验日线 | 505 只，278,916 天 | 98.70% | 0.04% |
| Index One 复权日线对主实验日线（stratos） | 96 只，76,666 天 | 99.92% | 0.004% |
| Index One 复权日线对 ext2017 日线 | 96 只，215,465 天 | 99.84% | 0.06% |

- 两份 Databento 数据没有复权，对不上的天主要是除息日，属于正常。
- 证券基本资料里的 CIK 与项目已有的代码—CIK 对照表比了 500 只，500 只一致。
- 财报：2015 年以来 99.9% 的行有证监会接收时间；季度报告期末到提交的中位数是 34 天，年度是 51 天，符合常理。

## 2026-11-02 按股票清理：只保留满足要求的 95 只

`_scripts/restrict_to_universe.py` 把所有按股票组织的表（公告、业绩、内部人交易、新闻稿、财报、复权日线、分钟线、新闻）过滤到 `_inventory/universe_95.txt` 里的 95 只，其余股票的行全部删除；过滤前的原文件复制在 `../archive/data_before_restrict_20261102/`，确认不需要后可以整个目录删掉。每个文件删了多少行记在 `_inventory/restrict_20261102.json`，各文件夹的 `MANIFEST.sha256` 和 `.meta.json` 已同步更新。

没有动的表：Databento 全美日线、标普 500 成分、647 个代码的基本资料、宏观数据。它们不是某只股票的数据，同行比较、板块 ETF、涨跌面工具要用。三份旧价格面板（`us_daily_*`、`dow30/`）和 `datasets/` 也没有动，它们属于更早的实验，是否删除另行决定。

## 按股票的统一覆盖表（2026-11-02）

不分新旧实验，按股票列出每一类数据的起止日期和条数：`_inventory/COVERAGE_BY_TICKER.md`（主实验 96 只的表）和 `_inventory/COVERAGE_BY_TICKER.csv`（647 个代码全表），由 `_scripts/coverage_by_ticker.py` 生成。

"满足现在基准（4_bench）全部要求"指在基准窗口 2025-09-29 至 2026-10-29 内同时具备：复权日线、分钟线、时间校正后的新闻、8-K、业绩公告时间、内部人交易、不落后于 EDGAR 最新 10-Q/10-K 的季报、基本资料。结果 **95 / 96**。不满足的只有 EA（2026-08-10 被收购退市，之后没有价格和新闻）。CRM、CRWD、NVDA、WMT、ORCL、NKE、MCHP 的季报原来缺最近 1 到 2 个季度，已用 EDGAR 的 XBRL 数据补齐（见已知问题）。其余 551 个代码只有公告、内部人交易、基本资料和未复权日线，没有新闻和分钟线，不能进基准。

新闻起始日分两批：道指 30 那批从 2025-09-29 起，其余 67 只从 2025-10-15 起；截止都是 2026-09-18。所以 train 切分最早的一两周里，这 67 只的新闻窗口是空的。

## 2026-11-02 新闻缺口补齐

起因见已知问题"Finnhub 公司新闻有抓取上限造成的缺口"。做法分两步：

- **按单日重抓**（`_scripts/fill_finnhub_news.py`；计划在 `_inventory/news_fill_plan_20261102.json`，日志在 `_inventory/news_fill_20261102.log`）。Finnhub 免费层只能往回取约一年：2026-11-02 当天 2025-11-05 及更早都返回 0 条，2025-11-07 起有，所以补抓范围是 2025-11-07 至 2026-09-18。哪些天要补：道指 30 只在 2026-03-31 之前的每一天（那次按月抓取没记录每次返回多少条，判断不了哪些天完整）；其余按 10 月抓取的调用记录判断——返回不到 150 条的调用其窗口完整，撞上限的调用只从它最早一条起完整，不在任何完整区间内的天都重抓。合计 4,469 次单日调用（NVDA 189 次、AMZN 155、MSFT 153，道指 30 名字每只约 147 次，有 24 只一次都不用补），返回 79,934 条，其中 21,336 条是表里没有的新（股票，文章）对；286 个单日返回 0 条。每次调用记在 `raw/news_finnhub/fetch_state.json`（标签 `s5`，含最早、最晚时间和条数）和 `raw/news_finnhub/finnhub_calls.jsonl`，文章并入 `raw/news_finnhub/raw/<TK>.json`。单线程、每次间隔 1.15 秒；中途两份进程并行过一段，撞了 44 次 429，都已重试成功，计划里的 4,469 天最终每天恰有一次成功调用。
- **重建新闻表**（`_scripts/rebuild_news_tables.py`）。规则代码原样拷贝自原管线：相关性、涨跌描述遮罩、48 小时 Jaccard 0.5 的首发判定（`_scripts/news_lib.py`，是 1_overreaction 里 news_lib.py 的逐字拷贝）；按来源的时间校正规则和三项检验（timefix.py，检验 c 的价格改用 Index One 复权日线）；校正时间顺序下重算首发、首个决策时点 D_min、剔除提到 D_min 之后日期的条目（build.py）。交易日历取 95 只 Index One 日线日期的并集。输出 `news/news_items_flagged.parquet`、`news/items_index.parquet`（新增 `src_pull` 列：`dow30_existing` / `rcf_20261011` / `fill_20261102`）、`news/day_coverage.parquet`（每只股票每个 UTC 日是否落在已知完整的抓取区间内）、`news/time_validation.json`、`news/build_stats.json`。三项时间检验全部通过。旧表在 `../archive/data_before_news_fill_20261102/news/`，前后对比在 `_inventory/news_rebuild_20261102.json`。

结果（kept = 相关、时间可校正且没提到未来日期；交易日按 Index One 日历，train 段 2025-10-06 至 2026-03-11 共 108 天，test 段 2026-03-19 至 2026-09-17 共 126 天）：

| | 补前 | 补后 |
|---|---|---|
| 表中条目（股票 × 文章） | 264,006 | 285,342 |
| 其中 kept | 120,987 | 129,228 |
| NVDA kept | 6,980 | 12,234 |
| NVDA train 段无新闻的交易日 | 93 | 19 |
| NVDA test 段无新闻的交易日 | 7 | 0 |
| AMZN / MSFT / AAPL train 段无新闻的交易日 | 40 / 27 / 26 | 8 / 8 / 7 |
| 2025-11-07 起每只股票每天落在已知完整区间内的比例 | — | 100% |

剩下的空白天全部在 2025-11-07 之前（免费层已取不到），那段只能用 10 月抓到的部分。单日调用返回 150 条以上的有 76 个（NVDA 70、AMZN 4、MSFT 2，`trunc` 标记按 150 条取，偏保守），其中真正顶到 250 条上限的只有 NVDA 的 3 天（2026-03-17、06-01、06-09）：按条目时间看，这 3 天拿到的是 UTC 当天 00:37 到 04:49 之后的全部条目，丢的只是前一天美东晚间的几个小时；其余 73 天最早一条都在 UTC 当天 0 点附近，没有被截。按月看，2026 年 1、2、3 月的 kept 条目各增加约 2,500、2,400、1,700 条，2025 年 11、12 月各约 700 条，其余月份变化很小。`_inventory/COVERAGE_BY_TICKER.*` 已重算（新闻条数和业绩表列有变，后者是今天早些时候重建业绩表的结果）。

没有改的旧文件：`news/ticker_days.parquet`、`corporate_actions.json`、`eligibility_counts.json`、`rcf_coverage.json`、`sample_summary.json` 是 10 月那次构建的产物，按补前的新闻算，只供旧实验对照。

## 构造好的数据集（`datasets/`）

- `ar1_forecasting/`：Gao 等人论文的人工序列任务复刻版。已建好，并独立核验通过。
- `stock_return_forecasting/`：Gao 等人论文的月度收益任务复刻版，用我们自己的价格数据构建。已建好并独立核验通过，但有明显的幸存者偏差（见"已知问题"）。
- `agent_trading_days/`：主实验用的数据。包括 96 只股票按时间点截好的工具数据缓存（`pit_cache_v2/`，唯一一份任何模型运行真正读取过的缓存）、250 天抽样、价格读数块、试点交易日、RCF 新闻事件集、理性基准模型参数、留出股划分。正式数据集在 `assembled/`：训练池 60 天、核心测试池 24 天、扩大测试池 137 天，每天 4 种呈现方式，共 788 组完整提示词和工作区文件。**缺口**：训练池里真正的"大事日"只有 1 天。
- `evidence_relations/`：测模型会不会分辨信息之间的关系（冗余、已被消化、旧消息重复、矛盾信号）。包括合成任务、197 天上的四类真实改动、32 个工具的冗余度矩阵、三个参照智能体的表现。还没有调用任何真实大模型。

## 已知问题

- **三份旧价格面板不能直接合并。** `us_daily_ext2017` 和 `us_daily_stratos_20260924` 的复权基准日不同，同一只股票的价格水平会差一个固定倍数。以前查到 ETN 在 2025-11-05 有一处 0.28% 对不上，**这次用新数据查清了**：这是一次每股 1.04 美元的分红。Index One 把它放在 11-06，`stratos` 放在 11-05，`ext2017` 在这几天里没有做分红调整。三家的未复权收盘价完全一样。哪一天是真正的除息日，还需要用公司公告确认。新的 Index One 复权日线可以当作 96 只股票的统一价格来源。
- **`datasets/stock_return_forecasting/` 有幸存者偏差**：每个月的标普 500 成分股只有约 61% 能找到价格。决定不补退市股票，所以这个问题保留。
- **新闻时间**：`news/news_items_flagged.parquet` 没有做时间校正，使用新闻时间时必须用同目录的 `items_index.parquet` 和 `time_validation.json`。
- **`datasets/agent_trading_days/news_events_rcf/` 是按未校正的新闻时间构建的**，约 15.7% 的相关新闻会因校正换一个窗口，对结论的影响还没有检验。
- **业绩公告时间要用 `filings/edgar__earnings_announce_check.parquet` 的 `safe_public_utc`**，不要用 `edgar__earnings.parquet` 自带的两列。
- **Index One 财报的时间**：回测时要按 `acceptedDate`（证监会接收时间）判断什么时候能看到，不能按报告期末 `date`。1990 年代早期的提交日常常就等于报告期末，不可信。
- **Index One 基本资料是取数当天的状态**：行业、流通股本、流通比例都是 2026-10-30 的值，不是历史时点数据，回测时不能当作当时已知。
- **Index One 财报有个别错行**：BK 有一行报告期末写成 2026-12-31、提交日却是 2026-10-15，明显是数据商标错了；另有 10 行同一报告期出现两个不同的财年标注。使用时按 `acceptedDate` 排序，遇到报告期末晚于提交日的行要剔除。
- **Index One 复权日线没有处理 HON 2026-06-29 的分拆**（2026-11-01 发现）：当天霍尼韦尔把航空业务分拆为 HONA（每 2 股旧 HON 得 1 股 HONA），同时 1 比 2 缩股。Index One 的序列只做了缩股复权，没做分拆复权，复权收盘价从 464.42 跳到 227.80（-51%），而 Databento 未复权价是 232.21 到 227.80。按通常做法把 06-29 之前的历史乘以 (464.42 − 220.19) / 464.42 = 0.5259（220.19 是 HONA 首日收盘价），4_bench 在加载时已这样处理（`bench/data.py` 的 SPINOFF_FACTORS）。逐只股票扫描 2025-09 以来复权日收益超过 25% 的天，只有这一处和 Databento 不一致（IBM 2026-07-14、ORCL 2025-09-10、PLTR 2026-08-04 是真实涨跌）。
- **Index One 季报对非自然年财年的公司缺最近 1 到 2 个季度**（2026-11-02 发现）：和 EDGAR 上最新的 10-Q / 10-K 接收时间比，NVDA、CRM、CRWD、WMT（1 月结财年）落后约 170 到 180 天，即缺两个季度；ORCL、NKE（5 月结）、MCHP（3 月结）落后约 80 天，缺一个季度；EA 是退市。原始下载页（`raw/indexone_20261030/fundamentals_quarterly/`）里也到此为止，是数据商没有更新，不是抓漏。自然年财年的 88 只都是最新的。**已补**（2026-11-02）：从 SEC 的 XBRL 公司事实接口（`raw/edgar_companyfacts_20261102/`，8 家公司）重建了缺的 12 个季度，存成 `fundamentals/edgar_quarterly_supplement.parquet`（和 Index One 同样的列，每季能填 52 到 62 个科目，`source` 列标 `edgar_xbrl`），脚本 `_scripts/build_edgar_quarterly_supplement.py`。4_bench 加载季报时自动拼上。口径按 Index One 对齐：acceptedDate 是纽约时间；资本开支、回购、分红为负数；净利润用归属普通股口径；总债务含租赁负债；EBITDA = 营业利润 + 折旧摊销。用双方都有的最近两个季度核对（`_inventory/edgar_supplement_validation.csv`）：192 个科目里 169 个在 1% 以内；对不上的是总债务（租赁口径差几个百分点）、个别公司的 EBITDA 和营业利润定义、CRWD 的资本开支（Index One 含资本化软件）、MCHP 的分红（Index One 含优先股）；CRWD 2025-10-31 的摊薄每股收益 Index One 给 -0.04，EDGAR 原文是 -0.14，是 Index One 错。
- **Index One 原价（未复权列）在拆股 / 分拆前后有几段是错的**（2026-11-02 发现，逐只股票和 Databento 对照 2024-07 以来的全部原价，偏差超过 1% 的只有这几段）：HON 2026-06-23 至 06-26 原价被提前套上了 1 比 2 缩股因子（444.74，实际 222.37）；HON 2025-10-01 至 10-29 原价和复权价都被提前套上了 Solstice 分拆因子（实际分拆日 10-30），造成 10-01 一个假的 -6% 和 10-01 之前的历史未做分拆调整；CRWD 2026-06-29 至 07-01 原价被提前除以 4（实际拆股日 07-02），且 06-03 至 07-01 的成交量是实际的 4 到 16 倍；LEN 2025-01-17 之前原价比自己的拆股复权价高 3.3%（Databento 和复权价一致）。处理都在 `4_bench/bench/data.py` 加载时完成：原价按 Databento 修正（`RAW_FIXES`），成交量从 2024-07-01 起直接用 Databento 并按数据商口径重算拆股复权成交量，HON 两次分拆前的复权历史按标准因子缩放（`SPINOFF_FACTORS`）。修后 HON 10-01 是 -0.15%、06-29 是 -6.96%，这些天的日线收盘与分钟线收盘一致。数据文件本身没有改。
- **EDGAR 业绩表重建**（2026-11-02）：10-17 那次构建对 95 只里的 31 只缺最近一个季度（SEC 的 companyconcept 接口当时还没出 2026 年二季度的部分 10-Q 事实，三季度 10-Q 在取数之后才提交）。用 2026-11-02 下载的 companyfacts（`raw/edgar_companyfacts_20261102/`，95 只加 5 个前身 CIK）通过同一个构建程序（`_scripts/edgar_build_lib.py`，是原 build_edgar.py 的原样拷贝）重建了 `edgar__earnings_facts`、`edgar__earnings`、`edgar__earnings_announce_check`，脚本 `_scripts/rebuild_edgar_earnings.py`。对照旧表：9,445 个旧行全部复现（数值 100%、首次接收时间 99.8%、SUE 在 0.05 内 99.7%、安全公开时间 100%），新增 96 个股票季度，41 只股票的最新季度往前推进，无丢失。旧表在 `../archive/data_before_earnings_rebuild_20261102/`。重建后仍有几家在 SEC 的 XBRL 接口里本身就没出最新季度（V、DLR、NEE、ED、SRE 的 2026 年二季度，接口里这几家最晚的申报停在 4、5 月；另有 7 家三季度 10-Q 刚提交），对这些季度用 `_scripts/fill_earnings_from_indexone.py` 从 Index One 季报补了每股收益和营收（共 247 行，`acceptance_source = indexone_statement`，`concept = indexone:*`；其中大部分是 FERG、CRH、RDDT、HOOD、UBER、PLTR 等公司成为美国 XBRL 申报人之前的季度），同样的办法也补了 EDGAR 里整段缺某个指标的股票季度（V 的每股收益、TFC 和 FITB 的营收、HAL 两个四季度营收：这些公司在 XBRL 里用的是自定义或别的科目名，构建程序认不出），公开时间用对应的 8-K 业绩公告，同比和 SUE 按原公式算：Index One 和 EDGAR 在近 6 个季度里口径一致（1% 内）的用 EDGAR 历史，否则（主要是银行的营收口径）用 Index One 自己的序列，`comp_source` 标明用了哪个。FERG 2025 年 11 到 12 月的两个月过渡期不是季度，按构建程序定义不收。
- **Finnhub 公司新闻有抓取上限造成的缺口**（2026-11-02 在 4_bench 的 15 只大市值股票深检里发现）：Finnhub 的 company-news 接口每次调用最多返回约 250 条（最新的 250 条），10 月那次抓取（`raw/news_finnhub/fetch_state.json`，`trunc: true` 的调用就是撞了上限）把窗口切成几天一段，热门股一段里仍超过 250 条，于是每段只剩最新的部分，更早的那几天整段丢失；2026-03-31 之前非道指名字只有大窗口抓取，丢得更多。结果（按 `news/items_index.parquet` 里 kept 的条目统计）：NVDA 在 train 段 101 个交易日里 86 天一条新闻都没有，test 段 2026-03-19 到 03-27 共 7 个交易日为空，之后还有 47 个日历日只拿到了当天最新的 250 条（不完整）；AMZN、MSFT、AAPL 在 train 段分别有 33、20、19 个交易日为空（主要是 2026 年 1 到 2 月的几周），test 段只有零散的不完整日；95 只合计 29 只在 test 段有整段缺失（共 320 个日历日）、19 只有不完整日（共 94 个）。其余 11 只大市值股票（AVGO、JPM、WMT、V、JNJ、MA、CSCO、ORCL、CVX、BAC、PLTR）在 test 段没有空白日或只有 1 到 2 天不完整。2026-08-14 到 08-28 全市场新闻量降到平时的一半左右，那两周撞上限的调用反而很少，所以更像来源本身的淡季，不是抓取问题。2026-11-02 用 3 次调用验证：接口现在仍能按单日取回缺的那些天（NVDA 2026-03-19 返回 207 条、03-23 返回 197 条、2025-11-18 到 19 返回 170 条，都没到上限），所以按单日重抓缺失和不完整的日子即可补齐，但补完要重跑新闻管线（去重、相关性、时间校正、首发标记）。**已补**（2026-11-02，见上文"2026-11-02 新闻缺口补齐"）：按单日重抓 4,469 次并重建了新闻表，2025-11-07 起不再有整天缺失；剩下的空白天都在 2025-11-07 之前，免费层已经取不到。
- **1 分钟 K 线来自 Databento 的 EQUS.MINI**：它汇总的是部分交易所，不是全市场合并成交，所以成交量比全市场少；价格是成交原价，没有复权。

## 还没做的事

1. 用新的 Index One 复权日线替换或合并三份旧价格面板（要先定合并方式）。
2. `datasets/agent_trading_days/assembled/` 目前只是环境和提示词的池子，还不是训练轨迹。
3. 训练池大事日稀缺的问题还没解决，要新跑模型生成起始状态。

## 不放进来的东西

- 模型运行的轨迹、决定记录、训练产出：这些是实验结果。
- 可以用代码从这里的数据重新生成的缓存。
- 已被新版本取代的旧数据和明显作废的文件。完整清单和理由见 `_inventory/INVENTORY.md` 的"重复、过期、作废"一节。
