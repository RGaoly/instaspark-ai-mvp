# InstaSpark AI MVP

> Claim-underwriting for creator spend: public captions must ground Product DNA claims before a dollar is authorized.

这是一个面向全球创作者运营场景的 AI 产品作品集项目。托管演示地址：
https://instaspark-ai-mvp.streamlit.app（当前 Streamlit workspace 可能要求访问授权）。

产品支持两个并列入口：

1. **Launch Mission**：从产品、市场与增长目标出发寻找创作者；
2. **Creator Opportunity**：从创作者信号、内容趋势或区域提名出发，再评估和关联任务。

两个入口共享同一套**卖点核保**、人工决策、外联和结果复盘工作区。它将活动上下文转化为：

1. 以 Product DNA `claim_id` 为原子单位的核保排序（不是找相似达人）；
2. Evidence Reader 从公开字幕读出的 claim 级证据与风险提示；
3. 人工采纳、驳回与 Reason Code；
4. 只使用已落地卖点的多语言合作 Brief；
5. 可回写的决策日志、联络包交接，以及原因码校准。验收矩阵、量化收益和两周落地路径在 Growth Review 默认展示，没有单独评测页。

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

TikTok Creator Marketplace books TikTok creators, pays them, and attributes on TikTok. InstaSpark is the brand-side **claim-underwriting desk** that sits **before** that booking rail:

1. Dual entry — launch mission and inbound opportunity share one state machine.
2. Claim underwrite — Search orders the spend-ready cut by Evidence Reader DNA claim coverage, not by embeddings or follower lookalikes. Mix risk (shortlist Jaccard) and product-grounded briefs sit on top.
3. Tracking assets — unique UTM coupons minted on approve; ROI stays empty until performance events exist.
4. Optional live lookup — set `YOUTUBE_API_KEY` to search public YouTube channels from Creator Search. Hits attach as labeled evidence; they do **not** enter the ranked catalog.

Industry analogue: a credit desk underwrites named covenants against documents. This desk underwrites named Product DNA claims against public captions. Without the Evidence Reader book, the spend-ready cut is blocked.

This demo does not ingest TikTok or Instagram, does not pay creators, and does not claim first-party conversion.

## Demo scope

- 示例 SKU：Insta360 X5
- 两个目标市场：United States / Mexico
- 60 位公开 YouTube 频道目录行（召回池，不是 KYC）；硬门槛后排序；Top 10 为工作切片
- 180 条合成目录视频（每人 3 条），带标注时间戳，映射到 Product DNA claim；**不是 ASR / OCR / 评论挖掘**
- 版本化 Product DNA 对象（卖点、场景、画面证据、护栏）
- 版本化 Creator Genome 包（60 人；7/30/90 代理；clip 索引；ASR/评论/关键帧/年龄/成交标记为 not_collected）
- 5 个可解释 Scout 维度（任务匹配、主题重合、动量、商业匹配、品牌安全）作为约束层；spend-ready 切片按 `claim_underwrite_v1`（0.70 卖点覆盖 + 0.30 规则混合）排序
- 查询词面加权、稀疏 TF-IDF 余弦加分（不是神经网络嵌入，也不是大模型排序）留在 Scout 层；挂接 YouTube 证据后的小幅加分；YouTube 结果不进入排序目录
- Top 10 推荐；Top 20 精读看标注时间戳。60 行目录的 `creator_name` 就是公开频道标题，并带 `youtube_channel_id`；精读 ownership 为 `catalog_channel`（该行就是该频道的公开上传，不是 KYC）。`attached_channel` 仍是运营当场挂接
- Evidence Reader Agent（`src/evidence_reader.py`）：把公开 YouTube 字幕正文（`downloaded_public_timedtext`，103 条）和 Product DNA claim 一起交给大模型，产出 claim 级结构化证据（claim_id / supported / confidence / 逐字引用 / 时间戳 / 矛盾点 / 品牌安全标记）。落地校验器接受单行字幕原文，或 YouTube 拆成相邻两行的原文拼接；三行以上拼接和编造句子会丢弃。模型如实声明 unsupported 会计入 `declared_unsupported`，不算幻觉。没有模型 key 时返回 `unavailable_no_model`，**不会**退化成关键词匹配假装证据。缓存在 `data/evidence_extractions.json`（版本化，无任何密钥），由 `scripts/run_evidence_reader.py` 生成
- **Claim–Evidence–Guardrail (CEG)**：Scout → EvidenceReader → MatchArbiter → BriefWriter → ComplianceGuard → Calibrator。具名 typed 契约在 `src/ceg.py`；批准或保存简报会写入运行轨迹，展示在 Creator Compare（`#ceg-run-trace`），不是第八页。无模型时 EvidenceReader 阻断、零 claim；BriefWriter 降级到确定性模板并记录 `degraded_reason`；Calibrator 在没有原因码时跳过，绝不自动改权重
- 外联审批闸门：批准某位创作者的外联，必须有 Evidence Reader 给出的 claim 级证据（≥1 条成立的 DNA claim + 通过校验的引用与时间戳）。没有模型时 UI 明说抽取不可用、规则无法替代，闸门进入显式阻断态；只能由带理由的人工覆盖放行，覆盖写入审批审计流水；Viewer 仍然只读
- Gold set + 双臂基准：`data/gold_evidence_labels.json` 是运营人工阅读字幕（`manual_read`），不是模型输出。`scripts/run_benchmark.py` 对关键词基线 vs Evidence Reader 缓存计算 P/R/F1 与引用落地准确率；报告 `data/benchmark_report.json` 展示在 Growth Review（`#claim-evidence-benchmark`），页面不写死数字
- pytest 验收矩阵（硬门槛、证据覆盖、稳定性、归因、召回 60、精读 Top 20、180 条视频）；展示在 Growth Review，不是第八页
- 人工采纳/驳回与 Reason Code
- 英语/西班牙语 Brief 生成；镜头清单来自 Product DNA
- 目录动量侦察卡片（7/30/90 代理，不是实时抓取）
- 3 条 Creator Opportunity 非邮件信号 + 30 封合成入站来信（英 / 西 / 德；含 KOL、MCN、Affiliate、渠道商、垃圾邮件与身份冒用）
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

Walk the real operator path. The spend-ready cut is claim-underwritten from the Evidence Reader cache. Scout (rule mix + TF-IDF) is the constraint layer, not an LLM ranker. ROI is recorded events only. **Send to Creator** stays disabled; the contact pack plus Advance is the operational handoff. There is no Evaluation page — the acceptance matrix, quantified value board, and 2-week landing path live on Growth Review.

1. Log in as `admin` / `admin123`. Open **Launch Mission**. The **Scoring rubric evidence** board (`#rubric-scorecard`) maps the four contest 5-point bars to live artifacts. Product DNA is on the dashboard (versioned SKU claims), not hidden. Expand **Why this is not TikTok Creator Marketplace** if needed.
2. Open **Creator Opportunity**. The default fold is the **Inbound inbox** (30 synthetic EN/ES/DE messages: parse, score, route, mission link). Import email reloads that corpus; it is not a live mailbox. Always-on scout cards sit **below** the inbox and save as catalog-momentum opportunities.
3. Open **Creator Search & Match**. The catalog recall is **60** public YouTube channel rows (name + channel id, not KYC); hard gates then **claim-underwrite**; Top 10 is the spend-ready working cut with a creator × DNA claim matrix. The **Top 20 intensive-read board** is on this page (not collapsed). Clips are that row's channel uploads (`catalog_channel`).
4. Optional: Live YouTube lookup → **Attach as evidence**. That is `attached_channel` for intensive-read. Hits do **not** become new ranked creators.
5. Open **Creator Compare**. Review shortlist overlap (Jaccard) and the **Outreach approval gate**. Approve is enabled only when Evidence Reader grounded a DNA claim (or after an audited override). Approve records a **Claim–Evidence–Guardrail** trace on this page (`#ceg-run-trace`) and mints a unique coupon / UTM tracking asset.
6. Open **Content Studio** → **Generate Brief** and save it. Shot list comes from Product DNA. Saving a brief appends another CEG run. **Open Outreach** appears after a saved brief. **Send to Creator** stays disabled.
7. On **Outreach Operations**, expand **Contact pack** and copy the message + coupon + UTM. **Advance** through legal hops. When the creator is published with 0 events, open **Growth Review**: the same rubric scorecard, quantified value (blocked unevidenced spend first), and 2-week landing path sit above the funnel. Record a conversion (ROI stays 0x until that event), then read the **Pilot acceptance matrix**, **Claim-evidence benchmark**, and **Reason-code calibrator**.

Without `LLM_API_KEY` the app still starts. Scout ranking, Search browse, and the state machine work. Evidence Reader, the approval gate, and the spend-ready cut stay blocked and say so — they do not fall back to keywords. Content Studio uses the deterministic template. The committed extraction cache is a prior model run and keeps the spend-ready cut live for this demo. With a key, regenerate the cache and the report:

```bash
python -m scripts.run_evidence_reader --workers 6
python -m scripts.run_benchmark
```

Typed contracts and the degrade matrix: [`docs/07_ceg.md`](docs/07_ceg.md).

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
│   ├── creator_content.json       # 180 authored clips + timestamps
│   ├── creator_genome.json        # versionable Creator Genome pack
│   ├── creator_opportunities.json
│   ├── inbound_messages.json
│   ├── launch_mission.json
│   ├── evidence_extractions.json  # Evidence Reader 缓存（版本化，无密钥）
│   ├── gold_evidence_labels.json  # 人工阅读字幕的 gold set
│   ├── benchmark_report.json      # 关键词基线 vs Evidence Reader
│   └── product_dna.json           # versionable SKU visual-proof object
├── docs/
│   ├── 00_project_charter.md
│   ├── 01_prd.md
│   ├── 02_architecture.md
│   ├── 03_evaluation.md
│   ├── 04_roadmap.md
│   ├── 05_phase0_architecture.md
│   ├── 05_phase0_ui_system.md
│   ├── 06_p0_product_contract.md
│   └── 07_ceg.md                  # Claim-Evidence-Guardrail 契约与降级矩阵
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
│   ├── budget.py                  # BudgetDecision from recorded events only
│   ├── business_value.py          # Quantified value from catalog + book + gold set
│   ├── calibrator.py              # Reason codes → mix-weight proposal
│   ├── claim_underwrite.py        # Spend-ready cut from Evidence Reader coverage
│   ├── content_evidence.py        # authored clip timestamps, not ASR
│   ├── creator_genome.py
│   ├── data_loader.py
│   ├── domain.py                  # 核心对象与统一状态机
│   ├── evaluation.py              # pytest acceptance matrix
│   ├── evidence_reader.py         # Evidence Reader Agent + 引用落地校验 + 审批闸门判定
│   ├── ceg.py                     # Claim-Evidence-Guardrail typed 契约与编排
│   ├── benchmark.py               # gold set P/R/F1：关键词基线 vs Evidence Reader
│   ├── inbound.py                 # 入站来信抽取、身份、评分、派单
│   ├── landing_path.py            # 2-week pilot operating model
│   ├── product_dna.py
│   ├── retrieval.py               # sparse TF-IDF cosine, not neural embeddings
│   ├── rubric_scorecard.py        # Live 5-point bars vs contest 评分细则
│   ├── scoring.py
│   └── scouting.py                # catalog momentum cards, not a live crawl
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

Required for Evidence Reader, the outreach approval gate, and live Content Studio (otherwise the reader/gate stay blocked, and the studio stays on the deterministic template):

```toml
LLM_API_KEY = "..."
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
```

`YOUTUBE_API_KEY` only attaches a public channel as labeled evidence. The ranked creator table stays the synthetic demo catalog. Without the YouTube secret, Search still works; the live lookup reports that the key is not configured.

Demo logins (Cloud and local): `admin` / `admin123` can write; `demo` / `demo123` is a read-only viewer.

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Docker and other hosts.

## Evaluation

核心评测不以“页面数量”为目标，而以证据和可复现性为目标。验收矩阵由 `tests/test_acceptance_matrix.py` 对当前目录、排序和效果事件计算，在 **Growth Review 默认展示**（`#pilot-acceptance-matrix`），不是单独评测页，也不是装饰仪表盘：

- 硬门槛违规数（Top 10 = 0）
- 证据覆盖率（Top 10 含正负证据、五维分数、标注时间戳）
- Top 20 精读片段覆盖
- 召回池 60、目录视频 180
- 排序稳定性（同输入同 Top 10）
- 归因完整性（事件保留 creator + root + source）
- Claim 证据基准（gold set `manual_read`；关键词基线 vs Evidence Reader；P/R/F1 + 引用落地准确率）
- Claim-underwrite spend-ready 切片（Top 10 按证据账本覆盖排序；无账本则不声称该闸门）
- 量化业务价值（字幕精读工时模型、无证据投放阻断额、金标集 F1 提升；公式写在页面上）
- Top 10 人工采纳率、推荐理由准确率、Brief 人工修改距离、单次任务耗时仍需运营盲评，本演示不伪造访谈结果

详见 [`docs/03_evaluation.md`](docs/03_evaluation.md)。

## Disclaimer

This is an independent portfolio project based on publicly observable business scenarios and synthetic data. It is not affiliated with, endorsed by, or deployed at Insta360.

## License

MIT
