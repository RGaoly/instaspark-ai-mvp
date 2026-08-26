# Roadmap

## V0 — Runnable MVP
- [x] 合成达人数据
- [x] 任务输入
- [x] 五维评分
- [x] Top 10 推荐
- [x] 解释与风险
- [x] 人工决策
- [x] Brief 生成
- [x] 单元测试

## V0.1 — Portfolio polish
- [ ] 产品截图与 2 分钟演示视频
- [x] 英文 README
- [x] 验收矩阵在 Growth Review（不是第八页评测中心）
- [ ] 真实用户访谈记录

## P0 — Dual-entry product foundation
- [x] Launch Mission / Creator Opportunity 并列入口
- [x] Mission、Opportunity、Creator、Match、Decision、OutreachCase、ContentAsset、PerformanceEvent 对象契约
- [x] 全工作区统一活动上下文
- [x] Creator collaboration 状态机与审计事件
- [x] Approved → OutreachCase 幂等交接
- [x] P0 结构与领域测试
- [ ] 数据库持久化与多人权限（P1）
- [ ] 公开、无需登录的 Pilot 环境（P2）

## V1 — Evidence-grounded matching
- [x] 接入公开达人主页和公开视频（YouTube catalog_channel + timedtext）
- [ ] ASR / OCR / 视觉标签
- [x] 证据时间戳（公开字幕逐字引用 + labeled_demo 独立层）
- [x] Claim-underwrite spend-ready 切片（覆盖为主，规则混合为约束）
- [ ] 混合召回与向量排序
- [x] 人工标注集（gold_evidence_labels.json manual_read）

## V2 — Workflow and learning
- [ ] 飞书多维表格回写
- [x] 审批闸门和 Reason Code
- [x] Reason Code 校准提案（Calibrator，人工应用）
- [x] 两周试点落地路径写进产品
- [ ] 结果回流自动改权重（本演示不自动交易）
