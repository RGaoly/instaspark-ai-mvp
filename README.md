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

## Why this is not TikTok Creator Marketplace

TikTok Creator Marketplace books TikTok creators, pays them, and attributes on TikTok. InstaSpark is the brand-side workspace that sits **before** that booking rail:

1. Dual entry — launch mission and inbound opportunity share one state machine.
2. Mix risk — shortlist Jaccard and product-grounded briefs before spend.
3. Tracking assets — unique UTM coupons minted on approve; ROI stays empty until performance events exist.
4. Optional live lookup — set `YOUTUBE_API_KEY` to search public YouTube channels from Creator Search. Hits attach as labeled evidence; they do **not** enter the ranked catalog.

This demo does not ingest TikTok or Instagram, does not pay creators, and does not claim first-party conversion.

## Demo scope

- 示例 SKU：Insta360 X5
- 两个目标市场：United States / Mexico
- 30 位合成达人
- 5 个可解释评分维度（任务匹配、主题重合、动量、商业匹配、品牌安全）
- 查询词面加权与挂接 YouTube 证据后的小幅加分；YouTube 结果不进入排序目录
- Top 10 推荐
- 人工采纳/驳回与 Reason Code
- 英语/西班牙语 Brief 生成
- 3 条 Creator Opportunity 合成样例
- Mission / Opportunity 统一活动上下文
- 可验证的状态迁移、审计事件和幂等 OutreachCase

## Quick start

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
streamlit run app.py
```

Default login: `admin` / `admin123`. A read-only viewer is available as `demo` / `demo123`.

## 5-minute demo

1. Log in as `admin` / `admin123`. Open **Creator Search & Match**.
2. Ranking is rule-based (mission fit, topic overlap, momentum, commercial fit, brand safety) — not an LLM and not embeddings.
3. Type a name or topic in NL search. That is a **lexical filter + small boost**, not semantic search.
4. Optional: Live YouTube lookup → **Attach as evidence**. The selected catalog creator's match score and the “Live YouTube evidence attached” reason update. YouTube hits do **not** become new ranked creators.

运行测试：

```bash
pytest -q
```

## Repository structure

```text
.
├── .github/workflows/ci.yml       # pytest + Docker build
├── app.py                         # 登录门禁、双入口与共享工作区路由
├── components/
│   ├── auth.py                    # 登录页
│   ├── i18n.py                    # 中英切换
│   ├── state.py                   # 活动上下文、状态迁移、SQLite 镜像
│   ├── shell.py
│   ├── html.py
│   ├── positioning.py             # Why-not-TTCM copy
│   ├── ui.py                      # 本地化 markdown 渲染
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
├── infra/
│   ├── auth.py                    # PBKDF2 用户校验
│   ├── config.py
│   ├── database.py                # SQLite schema
│   └── repository.py
├── services/
│   ├── opportunity_service.py
│   ├── llm_service.py             # OpenAI-compatible provider, template fallback
│   └── youtube_service.py         # optional YouTube Data API lookup
├── src/
│   ├── audience.py                # synthetic shortlist Jaccard
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
```

## P0 boundaries

P0 已建立双入口信息架构、核心对象契约、统一活动上下文、状态机和审计边界。登录、中英切换、SQLite 持久化和 viewer 写保护已经接上：`demo` 账号不能审批；刷新浏览器后，决策日志、外联案件、优惠码和创作者状态会从 `data/instaspark.db` 恢复。排序目录仍为合成数据。YouTube Data API 是可选的实时查询，与目录分开标注。TikTok / Instagram 采集、真实打款和一方归因不属于本演示。完整验收契约见 [`docs/06_p0_product_contract.md`](docs/06_p0_product_contract.md)。

## Deployment

Hosted demo: **https://instaspark-ai-mvp.streamlit.app**. Streamlit Cloud deploys from GitHub `main` (`app.py` + `requirements.txt`). Local `streamlit run app.py` remains the reproducible baseline.

If the hosted app redirects to a Streamlit login page, a workspace admin must make the app public or grant access. This repository cannot bypass that control.

### Streamlit Cloud secrets

After this branch is merged to `main`, Cloud rebuilds automatically. Live YouTube lookup and live Content Studio need secrets on the Cloud app. The running process reads **App settings → Secrets** via `st.secrets` (not only `.env` / `os.environ`). **Never put a real key in GitHub, README, screenshots, or a committed `.env`.**

1. Open [share.streamlit.io](https://share.streamlit.io) and select the app that serves https://instaspark-ai-mvp.streamlit.app.
2. Go to **App settings → Secrets**.
3. Paste TOML using the **same names** as `.env.example`. Click **Save**.
4. After Save, wait about one minute **or** reboot from the Streamlit Cloud menu (three dots → **Reboot**). A greyed-out Save button means there are no pending editor edits — it does **not** mean the running process has already reloaded secrets.

Required for live YouTube lookup on Creator Search:

```toml
YOUTUBE_API_KEY = "..."
```

Optional for live Content Studio (otherwise the studio stays on the deterministic mock):

```toml
LLM_API_KEY = "..."
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
```

`YOUTUBE_API_KEY` only attaches a public channel as labeled evidence. The ranked creator table stays the synthetic demo catalog. Without the YouTube secret, Search still works; the live lookup reports that the key is not configured.

Demo logins (Cloud and local): `admin` / `admin123` can write; `demo` / `demo123` is a read-only viewer.

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Docker and other hosts.

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
