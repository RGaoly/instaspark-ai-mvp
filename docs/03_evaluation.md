# Evaluation Plan

Offline gates are implemented in `src/evaluation.py` and asserted by
`tests/test_acceptance_matrix.py`. Growth Review shows the same matrix as a
default read-only board (`#pilot-acceptance-matrix`). It is not a separate
Evaluation page and not a live operator-interview dashboard.

## 离线评测

1. 硬门槛：市场、语言、预算或品牌安全不合格的候选不得进入 Top 10。
2. 排序检查：高匹配达人应显著高于低匹配达人。
3. 解释覆盖：每名 Top 10 候选至少有一条正向证据、一条风险、五项分数和标注时间戳。
4. 稳定性：同样输入多次运行结果一致。
5. 召回池：60 行公开 YouTube 频道目录（不是 KYC，不是 live crawl）；精读 Top 20 均有标注片段；目录视频 180 条。
6. Creator Genome：Top 10 均有版本化基因组、clip 索引，且 ASR/评论/关键帧标记为 not_collected。
7. 归因：已录入效果事件保留 creator、任务/机会根和来源；空事件 ROI 仍为 0x。

YouTube 精读叠加层：60 行目录的身份就是对应公开频道（`catalog_channel`，名字 + `youtube_channel_id`），片段是该频道公开上传，**不是 KYC**。叠加层**不**进入排序。 `attached_channel` 仍是运营当场挂接。

## 人工评测

邀请 2–3 位内容或达人运营从业者：

- 盲评 Top 10 是否愿意进入 shortlist
- 判断推荐理由是否真实、有用
- 记录驳回 Reason Code
- 对比人工筛选耗时与系统辅助耗时
- 评价 Brief 的可执行性与修改量

本演示不伪造这些访谈结果。

## Claim-evidence gold set

`data/gold_evidence_labels.json` is operator-read public timedtext
(`method: manual_read`), not model output and not the keyword baseline.
Twelve clips × four Product DNA claims = 48 claim labels.

`scripts/run_benchmark.py` scores two arms against that gold set:

1. Keyword baseline (`src/benchmark.py` `CLAIM_KEYWORDS`) over the same caption lines.
2. Evidence Reader cache (`data/evidence_extractions.json`). If no model and no
   cache, the model arm is `not_run_no_model` — it is not silently replaced by
   keywords.

Metrics are precision / recall / F1 plus quote-grounding accuracy (predicted
positive quotes that are a verbatim substring of one caption line or two
adjacent caption lines). Growth
Review renders `data/benchmark_report.json` at `#claim-evidence-benchmark`.
The view does not hard-code the numbers.

Ranking is the Scout constraint layer, not the claim-evidence gold-set
benchmark. The spend-ready cut is claim-underwritten from the Evidence Reader
cache and is a separate gate in the acceptance matrix. YouTube overlay is not
part of this benchmark. Empty performance events still keep ROI at 0x.

Growth Review also renders a quantified value board (`#business-value-board`)
from catalog costs, the extraction cache, and the gold-set report. Hours use a
documented process-time model (120 seconds per public caption body). Spend uses
`estimated_cost_usd`. Neither is a customer ROI or an operator interview.
The headline number is unevidenced spend blocked versus the Scout lookalike
Top 10, not hours.

## MVP 目标

| 指标 | 目标 |
|---|---:|
| 硬门槛违规 | 0 |
| 解释覆盖率 | 100% |
| Top 10 采纳率 | ≥ 60% |
| 推荐理由准确率 | ≥ 80% |
| Brief 严重事实错误 | 0 |
| 单次任务运行时间 | < 5 秒 |

以上均为作品集阶段目标，不代表真实企业基线。访谈类指标在验收矩阵中保持 `not_collected`。
