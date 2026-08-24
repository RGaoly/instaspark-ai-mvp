# Evaluation Plan

Offline gates are implemented in `src/evaluation.py` and asserted by
`tests/test_acceptance_matrix.py`. Growth Review shows the same matrix as a
read-only expander. It is not a live operator-interview dashboard.

## 离线评测

1. 硬门槛：市场、语言、预算或品牌安全不合格的候选不得进入 Top 10。
2. 排序检查：高匹配达人应显著高于低匹配达人。
3. 解释覆盖：每名 Top 10 候选至少有一条正向证据、一条风险、五项分数和标注时间戳。
4. 稳定性：同样输入多次运行结果一致。
5. 召回池：合成目录 60 人；精读 Top 20 均有标注片段；目录视频 180 条。
6. Creator Genome：Top 10 均有版本化基因组、clip 索引，且 ASR/评论/关键帧标记为 not_collected。
7. 归因：已录入效果事件保留 creator、任务/机会根和来源；空事件 ROI 仍为 0x。

## 人工评测

邀请 2–3 位内容或达人运营从业者：

- 盲评 Top 10 是否愿意进入 shortlist
- 判断推荐理由是否真实、有用
- 记录驳回 Reason Code
- 对比人工筛选耗时与系统辅助耗时
- 评价 Brief 的可执行性与修改量

本演示不伪造这些访谈结果。

## 人工评测

邀请 2–3 位内容或达人运营从业者：

- 盲评 Top 10 是否愿意进入 shortlist
- 判断推荐理由是否真实、有用
- 记录驳回 Reason Code
- 对比人工筛选耗时与系统辅助耗时
- 评价 Brief 的可执行性与修改量

## MVP 目标

| 指标 | 目标 |
|---|---:|
| 硬门槛违规 | 0 |
| 解释覆盖率 | 100% |
| Top 10 采纳率 | ≥ 60% |
| 推荐理由准确率 | ≥ 80% |
| Brief 严重事实错误 | 0 |
| 单次任务运行时间 | < 5 秒 |

以上均为作品集阶段目标，不代表真实企业基线。
