# InstaSpark AI MVP

> Evidence-grounded creator matching and localized collaboration brief generation for global product launches.

这是一个面向全球新品上市场景的 AI 产品作品集项目。访问网页看成品：https://instaspark-ai-mvp.streamlit.app
它将一个产品任务转化为：

1. 可解释的达人候选排序；
2. 内容证据与风险提示；
3. 人工采纳、驳回与 Reason Code；
4. 多语言合作 Brief；
5. 可回写的决策日志与评测框架。

## Golden path

**Launch Mission → Creator Match → Evidence Review → Human Decision → Brief Generation**

项目使用公开结构和合成数据，不代表 Insta360 官方产品，也不包含任何内部数据。

## Demo scope

- 示例 SKU：Insta360 X5
- 两个目标市场：United States / Mexico
- 30 位合成达人
- 5 个可解释评分维度
- Top 10 推荐
- 人工采纳/驳回与 Reason Code
- 英语/西班牙语 Brief 生成

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
├── app.py
├── data/
│   ├── creators.csv
│   └── launch_mission.json
├── docs/
│   ├── 00_project_charter.md
│   ├── 01_prd.md
│   ├── 02_architecture.md
│   ├── 03_evaluation.md
│   └── 04_roadmap.md
├── src/
│   ├── brief.py
│   ├── data_loader.py
│   └── scoring.py
└── tests/
    └── test_scoring.py
```

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
