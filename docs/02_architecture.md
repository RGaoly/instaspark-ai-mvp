# Architecture

```text
launch_mission.json / creator_opportunities.json
        │
        ▼
data_loader.py ── creators.csv (60 public YouTube channel rows)
        │
        ▼
scoring.py · retrieval.py
  - hard gates
  - rule_mix_tfidf_v1 (five mix dimensions + query + live-proof)
  - YouTube lookup never enters ranking
        │
        ├── Top 10 working cut
        └── Top 20 intensive-read (catalog_channel timedtext)
                 │
                 ▼
        Claim–Evidence–Guardrail (src/ceg.py)
          Scout (rule)
            → EvidenceReader (model, public timedtext only)
            → MatchArbiter (rule + approval gate)
            → BriefWriter (model → template)
            → ComplianceGuard (DNA guardrails)
                 │
                 ▼
        Human approve / override → OutreachCase → Growth Review
```

Core chain: Evidence Reader reads real caption lines into DNA claim evidence.
The grounding validator drops quotes that are not a verbatim substring of one
caption line. Approve outreach requires a grounded claim. No key is an explicit
block plus an audited override — not a keyword fallback.

Ranking stays `rule_mix_tfidf_v1`. CEG traces live on Creator Compare
(`#ceg-run-trace`). The gold-set benchmark lives on Growth Review
(`#claim-evidence-benchmark`). There is no eighth page.

See [`docs/07_ceg.md`](07_ceg.md) for the typed contracts and degrade matrix.
