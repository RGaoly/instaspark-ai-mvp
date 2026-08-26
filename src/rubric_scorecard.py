"""Judge-facing proof against the four 5-point scoring bars.

The contest 评分细则 are:

* AI 应用创新性 30% — 5 = 行业级新范式 (not tool assembly)
* 业务价值 30% — 5 = 直击痛点，收益显著 (quantified, visible)
* AI 应用深度 20% — 5 = 离开 AI 方案不成立
* 方案完整度与可落地性 20% — 5 = 闭环清晰有落地路径

This module does not award points as copy. It checks live catalog, Evidence
Reader book, gold-set report, CEG contracts, and the 2-week landing path, then
returns the evidence Launch and Growth Review render at ``#rubric-scorecard``.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from src.business_value import compute as compute_value
from src.ceg import CONTRACT, ENGINE_MODEL, ROLE_CALIBRATOR, ROLE_EVIDENCE_READER, ROLES, WORKFLOW_VERSION
from src.claim_underwrite import UNDERWRITE_VERSION, pack_is_available, underwrite_score
from src.evidence_reader import empty_pack, gate_state, load_pack
from src.landing_path import landing_path
from src.scoring import rank_creators

# "收益显著" vs "方向明确但量化不足": blocked catalog spend, not a forecast.
SIGNIFICANT_BLOCKED_USD = 10_000
SCORECARD_ID = "rubric-scorecard"
SCORECARD_VERSION = "rubric_scorecard_v1"

DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "innovation",
        "weight_pct": 30,
        "title": "AI application innovation",
        "title_zh": "AI 应用创新性",
        "bar_5": "行业级新范式",
        "bar_3": "有巧思但常见",
        "bar_1": "工具简单拼装",
        "claim": (
            "Creator spend is underwritten like credit: named Product DNA claims "
            "against public captions, not lookalike retrieval."
        ),
        "without": "A TF-IDF marketplace with an LLM caption add-on.",
        "anchors": ("#claim-underwrite-paradigm", "#claim-underwrite-matrix", "#ceg-run-trace"),
    },
    {
        "id": "value",
        "weight_pct": 30,
        "title": "Business value",
        "title_zh": "业务价值",
        "bar_5": "直击痛点，收益显著",
        "bar_3": "方向明确但量化不足",
        "bar_1": "停留在概念",
        "claim": (
            "Hardware launches pay creators to film named SKU claims. Similarity "
            "ranking authorizes spend on captions that never grounded those claims."
        ),
        "without": "A conceptual 'AI matching saves time' slide with no formula.",
        "anchors": ("#business-value-board", "#claim-evidence-benchmark"),
    },
    {
        "id": "depth",
        "weight_pct": 20,
        "title": "AI application depth",
        "title_zh": "AI 应用深度",
        "bar_5": "离开 AI 方案不成立",
        "bar_3": "有效增益但非核心",
        "bar_1": "可被人力平替",
        "claim": (
            "Only EvidenceReader can mint a claim_id. Without the model book the "
            "spend-ready cut and the approval gate stay blocked. Keywords never open them."
        ),
        "without": "Rules still shortlist; AI only writes a nicer brief.",
        "anchors": ("#claim-underwrite-matrix", "#ceg-run-trace"),
    },
    {
        "id": "completeness",
        "weight_pct": 20,
        "title": "Completeness and feasibility",
        "title_zh": "方案完整度与可落地性",
        "bar_5": "闭环清晰有落地路径",
        "bar_3": "环节完整但需补齐",
        "bar_1": "零散缺关键环节",
        "claim": (
            "Mission/Opportunity → claim-underwritten Match → Decision → Brief → "
            "contact pack + Advance → recorded events → Calibrator. Two-week pilot."
        ),
        "without": "A demo that ends at a ranked table, with Send as a missing link.",
        "anchors": ("#pilot-landing-path", "#reason-code-calibrator"),
    },
)


def _gate(gate_id: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"id": gate_id, "passed": bool(ok), "detail": detail}


def _points(gates: list[dict[str, Any]]) -> int:
    if not gates:
        return 1
    passed = sum(1 for item in gates if item["passed"])
    if passed == len(gates):
        return 5
    if passed == 0:
        return 1
    return 3


def prove(
    catalog: pd.DataFrame,
    mission: Mapping[str, Any],
    *,
    pack: Mapping[str, Any] | None = None,
    report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return live evidence for each 5-point bar. ``all_met`` is the 5/5/5/5 claim."""

    book = pack if pack is not None else load_pack()
    board = compute_value(catalog, mission, pack=book, report=report)
    path = landing_path()
    underwritten = rank_creators(catalog, mission, evidence_pack=book)
    scout_only = rank_creators(catalog, mission, evidence_pack=empty_pack())
    available = pack_is_available(book)
    reader = next(item for item in CONTRACT if item.role == ROLE_EVIDENCE_READER)
    grounded_ids = {str(item) for item in (book.get("grounded_creator_ids") or [])}
    unevidenced_id = ""
    if catalog is not None and not catalog.empty:
        for creator_id in catalog["creator_id"].astype(str):
            if creator_id not in grounded_ids:
                unevidenced_id = creator_id
                break
    probe_id = unevidenced_id or "C000"
    unevidenced_gate = gate_state(probe_id, book, available=True) if unevidenced_id else {
        "blocked": False,
        "status": "missing",
    }
    empty_gate = gate_state(probe_id, empty_pack(), available=False)
    closed = str(path.get("closed_loop") or "")
    loop_tokens = ("Mission", "claim-underwritten", "Decision", "Brief", "contact pack", "Advance", "Calibrator")
    out_of_scope = " ".join(path.get("out_of_scope") or [])

    innovation_gates = [
        _gate(
            "underwrite_ranks",
            available and (underwritten["ranking_model_version"] == UNDERWRITE_VERSION).all()
            if not underwritten.empty
            else False,
            f"Spend-ready ranking is {UNDERWRITE_VERSION} when the book exists.",
        ),
        _gate(
            "not_lookalike",
            underwrite_score(100, 0) > underwrite_score(0, 100),
            "Claim coverage outranks a perfect rule-mix lookalike (0.70 vs 0.30).",
        ),
        _gate(
            "ceg_six_roles",
            WORKFLOW_VERSION == "ceg_v2" and list(ROLES)[-1] == ROLE_CALIBRATOR and len(ROLES) == 6,
            f"Named CEG workflow {WORKFLOW_VERSION}: {' → '.join(ROLES)}.",
        ),
        _gate(
            "order_changes",
            (not underwritten.empty)
            and (not scout_only.empty)
            and list(underwritten.head(10)["creator_id"]) != list(scout_only.head(10)["creator_id"]),
            "Claim-underwrite Top 10 is not the Scout lookalike Top 10.",
        ),
    ]
    value_gates = [
        _gate(
            "blocked_spend",
            float(board.get("unevidenced_spend_blocked_usd") or 0) >= SIGNIFICANT_BLOCKED_USD,
            (
                f"Rule-mix Top 10 would authorize "
                f"${float(board.get('rule_top10_unevidenced_spend_usd') or 0):,.0f} on unevidenced rows; "
                f"claim-underwrite blocks ${float(board.get('unevidenced_spend_blocked_usd') or 0):,.0f}."
            ),
        ),
        _gate(
            "spend_ready_cut",
            int(board.get("top10_spend_ready") or 0) >= 1,
            f"{int(board.get('top10_spend_ready') or 0)} of Top 10 are spend-ready (grounded DNA claim).",
        ),
        _gate(
            "gold_f1",
            (board.get("gold_f1_lift") is not None) and float(board.get("gold_f1_lift") or 0) > 0,
            f"Gold-set F1 lift {board.get('gold_f1_lift')} vs keyword baseline (manual_read timedtext).",
        ),
        _gate(
            "hours_formula",
            float(board.get("hours_saved") or 0) > 0 and board.get("eligible_clips", 0) >= 1,
            (
                f"{board.get('hours_saved')} h process-time model = "
                f"{board.get('eligible_clips')} clips × {board.get('seconds_per_caption_body')}s / 3600. "
                "Not an interview."
            ),
        ),
    ]
    depth_gates = [
        _gate(
            "live_book",
            available,
            "The running desk has a model-produced underwriting book. An empty book is a blocked desk, not a keyword product.",
        ),
        _gate(
            "empty_book_blocks_cut",
            (not scout_only.empty) and int(scout_only["spend_ready"].sum()) == 0,
            "Empty Evidence Reader book → zero spend-ready rows. Keyword rules cannot open the cut.",
        ),
        _gate(
            "reader_is_model",
            reader.engine == ENGINE_MODEL and "keyword" in reader.degraded_behaviour.lower(),
            "EvidenceReader is a model role. No keyword fallback; it blocks and advances zero claims.",
        ),
        _gate(
            "gate_blocks_unevidenced",
            bool(unevidenced_gate.get("blocked")),
            f"Unevidenced creator {unevidenced_id or '—'} approval gate: {unevidenced_gate.get('status')}.",
        ),
        _gate(
            "no_model_blocks_gate",
            bool(empty_gate.get("blocked")),
            f"No model + empty book: gate status {empty_gate.get('status')}. Human override is audited, not silent.",
        ),
    ]
    completeness_gates = [
        _gate(
            "four_phases",
            len(path.get("phases") or []) == 4
            and all(item.get("exit_gate") and item.get("in_this_demo") for item in path.get("phases") or []),
            "2-week path has four phases, each with an owner, artifact, exit gate, and demo mapping.",
        ),
        _gate(
            "closed_loop",
            all(token in closed for token in loop_tokens),
            closed,
        ),
        _gate(
            "handoff_not_send",
            "Live mailbox send" in out_of_scope or "Send to Creator" in out_of_scope,
            "Send to Creator stays disabled. Contact pack plus Advance is the operational handoff.",
        ),
        _gate(
            "scale_next",
            len(path.get("scale_next") or []) >= 4 and len(path.get("roles") or []) >= 3,
            f"Scale-next {len(path.get('scale_next') or [])} steps · {len(path.get('roles') or [])} operating roles.",
        ),
    ]

    by_id = {item["id"]: item for item in DIMENSIONS}
    rows = []
    for dim_id, gates in (
        ("innovation", innovation_gates),
        ("value", value_gates),
        ("depth", depth_gates),
        ("completeness", completeness_gates),
    ):
        meta = by_id[dim_id]
        points = _points(gates)
        rows.append(
            {
                **meta,
                "points": points,
                "met": points == 5,
                "gates": gates,
                "evidence": [item["detail"] for item in gates],
            }
        )

    return {
        "scorecard_id": SCORECARD_ID,
        "version": SCORECARD_VERSION,
        "all_met": all(row["met"] for row in rows),
        "points": {row["id"]: row["points"] for row in rows},
        "dimensions": rows,
        "value": {
            "unevidenced_spend_blocked_usd": board.get("unevidenced_spend_blocked_usd"),
            "rule_top10_unevidenced_spend_usd": board.get("rule_top10_unevidenced_spend_usd"),
            "rule_top10_unevidenced_n": board.get("rule_top10_unevidenced_n"),
            "top10_spend_ready": board.get("top10_spend_ready"),
            "hours_saved": board.get("hours_saved"),
            "gold_f1_lift": board.get("gold_f1_lift"),
            "gold_fp_reduction": board.get("gold_fp_reduction"),
            "ranking_model_version": board.get("ranking_model_version"),
        },
        "workflow": " → ".join(ROLES),
        "closed_loop": closed,
        "note": (
            "Points follow the contest 5 / 3 / 1 bars. They are computed from this "
            "catalog, book, gold set, CEG contracts, and landing path — not from copy."
        ),
    }
