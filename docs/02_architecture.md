# Architecture

```text
launch_mission.json
        │
        ▼
data_loader.py ── creators.csv
        │
        ▼
scoring.py
  - hard gates
  - five-dimension scoring
  - explanation
        │
        ├── Top 10 ranking
        ├── evidence / risks
        └── human decision
                 │
                 ▼
              brief.py
```

MVP 优先证明业务链路、解释能力和评测方法。LLM、向量库、多模态解析和工作流编排将在 V1 之后按证据逐步接入。
