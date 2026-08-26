# Architecture

```text
launch_mission.json / creator_opportunities.json
        │
        ▼
data_loader.py ── creators.csv (60 public YouTube channel rows)
        │
        ▼
scoring.py · retrieval.py · claim_underwrite.py
  - hard gates (Scout constraint)
  - rule_mix_tfidf_v1 (five mix dimensions + query + live-proof)
  - claim_underwrite_v1 spend-ready cut:
        0.70 × DNA claim coverage from Evidence Reader
      + 0.30 × rule mix
  - YouTube overlay never becomes a new ranked catalog row
        │
        ├── Top 10 spend-ready working cut (claim matrix)
        └── Top 20 intensive-read (catalog_channel timedtext)
                 │
                 ▼
        Claim–Evidence–Guardrail (src/ceg.py)
          Scout (rule)
            → EvidenceReader (model, public timedtext only)
            → MatchArbiter (claim-underwrite + approval gate)
            → BriefWriter (model → template)
            → ComplianceGuard (DNA guardrails)
            → Calibrator (reason codes → weight proposal, never auto-applies)
                 │
                 ▼
        Human approve / override → OutreachCase (contact pack + Advance)
                 │
                 ▼
        Growth Review: rubric scorecard · recorded events · quantified value · landing path · Calibrator
```

Core chain: Evidence Reader reads real caption lines into DNA claim evidence.
The grounding validator drops quotes that are not a verbatim substring of one
caption line (or two adjacent lines). Approve outreach requires a grounded claim.
No key is an explicit block plus an audited override — not a keyword fallback.

The spend-ready cut is `claim_underwrite_v1`. The rule mix stays the Scout
constraint layer (`total_score`). CEG traces live on Creator Compare
(`#ceg-run-trace`). The gold-set benchmark, quantified value board,
2-week landing path, and `#rubric-scorecard` live on Launch and Growth Review.
There is no eighth page.

See [`docs/07_ceg.md`](07_ceg.md) for the typed contracts and degrade matrix.
