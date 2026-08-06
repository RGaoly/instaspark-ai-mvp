# InstaSpark AI MVP

> Evidence-grounded creator matching and localized collaboration brief generation for global product launches.

这是一个面向全球创作者运营场景的 AI 产品作品集项目。托管演示地址：
https://instaspark-ai-mvp.streamlit.app（当前 Streamlit workspace 可能要求访问授权）。

产品支持两个并列入口：

1. **Launch Mission**：从产品、市场与增长目标出发寻找创作者；
2. **Creator Opportunity**：从创作者信号、内容趋势或区域提名出发，再评估和关联任务。

两个入口共享同一套匹配、人工决策、外联和结果复盘工作区。它将活动上下文转化为：

1. 可解释的达人候选排序；
2. 内容证据与风险提示；
3. 人工采纳、驳回与 Reason Code；
4. 多语言合作 Brief；
5. 可回写的决策日志与评测框架。

## Product paths

**Mission-first:** Launch Mission → Creator Match → Evidence Review → Human Decision → OutreachCase

**Creator-first:** Creator Opportunity → Evidence Qualification → Optional Mission Link → Human Decision → OutreachCase

两条路径共用统一状态机：

```text
discovered → qualified → shortlisted → approved → contacted → negotiating
           → contracted → content_in_review → published → measured
```

`closed_lost` 是签约前的终止分支。每次合法迁移都记录操作者、时间、原因、证据和入口上下文。

项目使用公开结构和合成数据，不代表 Insta360 官方产品，也不包含任何内部数据。

## Demo scope

- 示例 SKU：Insta360 X5
- 两个目标市场：United States / Mexico
- 30 位合成达人
- 5 个可解释评分维度
- Top 10 推荐
- 人工采纳/驳回与 Reason Code
- 英语/西班牙语 Brief 生成
- 3 条 Creator Opportunity 合成样例
- Mission / Opportunity 统一活动上下文
- 可验证的状态迁移、审计事件和幂等 OutreachCase

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

运行测试：

```bash
pytest -q
```

## Repository structure

```text
.
├── .github/workflows/tests.yml    # CI test gate
├── app.py                         # 双入口与共享工作区路由
├── components/
│   ├── state.py                   # 活动上下文、状态迁移与 session store
│   ├── shell.py
│   ├── html.py
│   └── theme.py
├── data/
│   ├── creators.csv
│   ├── creator_opportunities.json
│   └── launch_mission.json
├── docs/
│   ├── 00_project_charter.md
│   ├── 01_prd.md
│   ├── 02_architecture.md
│   ├── 03_evaluation.md
│   ├── 04_roadmap.md
│   ├── 05_phase0_architecture.md
│   ├── 05_phase0_ui_system.md
│   └── 06_p0_product_contract.md
├── services/
│   ├── mission_service.py
│   ├── opportunity_service.py
│   ├── matching_service.py
│   ├── content_service.py
│   ├── campaign_service.py
│   └── learning_service.py
├── src/
│   ├── brief.py
│   ├── data_loader.py
│   ├── domain.py                  # 核心对象与统一状态机
│   └── scoring.py
├── views/
│   ├── launch_mission.py
│   ├── creator_opportunity.py
│   ├── creator_search.py
│   ├── creator_compare.py
│   ├── content_studio.py
│   ├── outreach_operations.py
│   └── growth_review.py
└── tests/
    ├── test_scoring.py
    ├── test_domain.py
    ├── test_phase0_ui.py
    ├── test_p0_product_contract.py
    └── test_p0_state_integration.py
```

## P0 boundaries

P0 已建立双入口信息架构、核心对象契约、统一 session 上下文、状态机和审计边界。数据仍为合成数据，状态只保存在当前 Streamlit session；数据库、多用户权限、实时平台采集、真实消息发送、模型生成和归因管线属于后续阶段。完整验收契约见 [`docs/06_p0_product_contract.md`](docs/06_p0_product_contract.md)。

## Deployment

Streamlit Community Cloud 可直接以 `app.py` 为入口、`requirements.txt` 为依赖部署。本地启动是当前的可复现基线。托管实例若重定向到登录页，需由 workspace 管理员开放应用或授予访问权限；仓库本身不会绕过该访问控制。

## Evaluation

核心评测不以“页面数量”为目标，而以证据和可复现性为目标：

- 硬门槛违规数
- Top 10 人工采纳率
- 证据覆盖率
- 推荐理由准确率
- 排序稳定性
- Brief 人工修改距离
- 单次任务耗时

详见 [`docs/03_evaluation.md`](docs/03_evaluation.md)。

## Disclaimer

This is an independent portfolio project based on publicly observable business scenarios and synthetic data. It is not affiliated with, endorsed by, or deployed at Insta360.

## License

MIT
