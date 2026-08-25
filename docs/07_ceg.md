# Claim–Evidence–Guardrail (CEG)

The named agent workflow behind a launch decision. The atomic unit of work is
one Product DNA `claim_id`. A creator is not approved because a score is high;
a creator is approved because named roles advanced specific claims, on a named
engine, with a recorded degraded reason whenever the model was absent.

This is not an eighth navigation page. Compare shows the latest run
(`#ceg-run-trace`). Approve and save-brief persist the trace in session state.

## Roles

| Role | Engine | Advances claims | Purpose |
|---|---|---|---|
| Scout | rule | no | Propose the candidate from catalog momentum or inbound routing. |
| EvidenceReader | model | **yes — the only mint** | Read public YouTube timedtext into grounded claim evidence. |
| MatchArbiter | rule → human | yes (only claims the reader already grounded) | `rule_mix_tfidf_v1` fit plus the claim-evidence approval gate. YouTube never enters ranking. |
| BriefWriter | model → rule template | yes (only grounded claims) | Write the operator artifact. |
| ComplianceGuard | rule | no | Check the artifact against per-claim DNA guardrails. |

Typed contracts live in `src/ceg.py` (`CONTRACT`). Tests in `tests/test_ceg.py`
assert the same five roles, the same engines, and the same degrade reasons.

## Two invariants

1. **No claim without evidence.** Only EvidenceReader can put a `claim_id` into
   a step's `claim_ids`. Rules never mint claim evidence. A rule-only run
   advances zero claims and MatchArbiter blocks.
2. **Degradation is recorded, never hidden.** When a step cannot run on its
   primary engine it keeps its `role`, switches `engine`, and states
   `degraded_reason`. It never silently substitutes a weaker method.

## Degrade matrix

| Role | No `LLM_API_KEY` | No grounded extraction | Human override |
|---|---|---|---|
| Scout | Still rule. Never needs a model. | Unchanged. | Unchanged. |
| EvidenceReader | **Blocks.** `no_model_configured`. Zero claims. **No keyword fallback.** Quotes may span two adjacent timedtext chunks. | Blocks. `no_grounded_extraction_for_creator`. | Not this role. |
| MatchArbiter | Blocks with the gate (`evidence_gate_blocked`). | Same block. | Engine → `human`. Advances **zero** claims. Reason on the audit trail. |
| BriefWriter | Engine → rule template. `no_model_configured`. | Writing before the gate opens is `artifact_written_before_a_claim_was_grounded`. | Template still used if no model. |
| ComplianceGuard | Still rule. Never needs a model. | Skips if no artifact. | A hard finding still blocks; a soft finding needs a human fix. |

Source of truth: `src.ceg.degraded_matrix()`.

## Approval gate

`components/state.save_decision(..., "Approved")` raises `EvidenceGateBlocked`
unless EvidenceReader grounded ≥1 DNA claim with a verbatim caption quote and
timestamp, or an operator recorded an audited override with a reason.

The gate is independent of ranking. Ranking stays `rule_mix_tfidf_v1`.

## One-command start and expected degrade

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app.py
```

Without `LLM_API_KEY` the app still opens. Search, Compare, ranking, and the
state machine work. Content Studio uses the deterministic template. Evidence
Reader and the approval gate stay **blocked** and say so. They do not pretend
keyword overlap is claim evidence.

With a key:

```bash
python -m scripts.run_evidence_reader --workers 6
python -m scripts.run_benchmark
```

The extraction cache is `data/evidence_extractions.json` (no secrets). The
benchmark report is `data/benchmark_report.json`, shown on Growth Review
(`#claim-evidence-benchmark`).
