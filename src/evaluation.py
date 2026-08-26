"""Pilot acceptance matrix computed from current catalog, ranking and events.

This is the PDF evaluation contract as code. It is not a decorative dashboard
and does not invent live operator interviews.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.content_evidence import clips_for
from src.creator_genome import genome_for, genomes_by_id
from src.intensive_read import intensive_read_pack
from src.scoring import passes_hard_gates
from src.claim_underwrite import UNDERWRITE_VERSION


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _top_n(ranked: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if ranked is None or ranked.empty:
        return pd.DataFrame()
    return ranked.head(n)


def hard_gate_violations(ranked: pd.DataFrame, mission: Mapping[str, Any]) -> int:
    violations = 0
    for _, row in _top_n(ranked).iterrows():
        passed, _reasons = passes_hard_gates(row, mission)
        if not passed:
            violations += 1
    return violations


def evidence_coverage(
    ranked: pd.DataFrame,
    posts: Iterable[Mapping[str, Any]] | None = None,
    *,
    n: int = 10,
) -> dict[str, Any]:
    top = _top_n(ranked, n)
    missing: list[str] = []
    for _, row in top.iterrows():
        creator_id = str(row.get("creator_id") or "")
        positives = _as_list(row.get("positives"))
        warnings = _as_list(row.get("warnings") if row.get("warnings") is not None else row.get("risks"))
        scores = [
            row.get("mission_fit"),
            row.get("topic_overlap"),
            row.get("momentum"),
            row.get("commercial_fit"),
            row.get("brand_safety"),
        ]
        clips = clips_for(creator_id, posts)
        timed = [clip for clip in clips if clip.get("timestamps")]
        if not positives or not warnings or any(score is None for score in scores) or not timed:
            missing.append(creator_id)
    total = len(top)
    covered = total - len(missing)
    return {
        "total": total,
        "covered": covered,
        "missing": missing,
        "rate": 1.0 if total == 0 else covered / total,
    }


def genome_coverage(
    ranked: pd.DataFrame,
    *,
    n: int = 10,
) -> dict[str, Any]:
    top = _top_n(ranked, n)
    missing: list[str] = []
    pack = genomes_by_id()
    for _, row in top.iterrows():
        creator_id = str(row.get("creator_id") or "")
        genome = pack.get(creator_id) or genome_for(creator_id)
        if (
            not genome
            or not genome.get("clip_ids")
            or genome.get("asr_status") != "not_collected"
            or genome.get("comment_status") != "not_collected"
            or genome.get("keyframe_status") != "not_collected"
        ):
            missing.append(creator_id)
    total = len(top)
    covered = total - len(missing)
    return {
        "total": total,
        "covered": covered,
        "missing": missing,
        "rate": 1.0 if total == 0 else covered / total,
        "pack_size": len(pack),
    }


def intensive_read_coverage(
    ranked: pd.DataFrame,
    posts: Iterable[Mapping[str, Any]] | None = None,
    *,
    n: int = 20,
) -> dict[str, Any]:
    pack = intensive_read_pack(ranked, posts, n=n)
    missing: list[str] = []
    invented_asr: list[str] = []
    for item in pack:
        clips = item.get("clips") or []
        complete = bool(clips)
        for clip in clips:
            themes = [str(theme).strip() for theme in (clip.get("comment_themes") or []) if str(theme).strip()]
            stamps = clip.get("timestamps") or []
            stamp_ok = bool(stamps) and all(
                str(stamp.get("t") or "").strip()
                and str(stamp.get("claim_id") or "").strip()
                and str(stamp.get("caption") or "").strip()
                and str(stamp.get("keyframe_note") or "").strip()
                for stamp in stamps
            )
            layer_ok = (
                clip.get("caption_source") == "labeled_demo"
                and clip.get("keyframe_status") == "labeled_demo_note"
                and clip.get("comment_status") == "labeled_demo_themes"
                and 1 <= len(themes) <= 3
                and stamp_ok
            )
            if not layer_ok:
                complete = False
            if clip.get("asr_status") != "not_collected" or clip.get("asr") not in (None, ""):
                invented_asr.append(str(item.get("creator_id") or ""))
        if not complete:
            missing.append(str(item.get("creator_id") or ""))
    total = len(pack)
    return {
        "total": total,
        "covered": total - len(missing),
        "missing": missing,
        "invented_asr": invented_asr,
        "rate": 1.0 if total == 0 else (total - len(missing)) / total,
    }


def ranking_stability(ranked: pd.DataFrame) -> tuple[str, ...]:
    return tuple(str(item) for item in _top_n(ranked)["creator_id"].tolist()) if ranked is not None and not ranked.empty else ()


def attribution_completeness(
    events: Sequence[Mapping[str, Any]],
    *,
    sku: str,
) -> dict[str, Any]:
    if not events:
        return {"total": 0, "complete": 0, "rate": 1.0, "note": "No events; completeness is vacuously 1.0 and ROI stays 0x."}
    complete = 0
    for event in events:
        has_ids = bool(event.get("creator_id") and (event.get("mission_id") or event.get("opportunity_id")))
        has_source = bool(event.get("source") or event.get("coupon") or event.get("utm"))
        if has_ids and has_source:
            complete += 1
    total = len(events)
    return {
        "total": total,
        "complete": complete,
        "rate": complete / total if total else 1.0,
        "sku": sku,
    }


def acceptance_matrix(
    *,
    ranked: pd.DataFrame,
    mission: Mapping[str, Any],
    catalog_size: int,
    posts: Iterable[Mapping[str, Any]] | None = None,
    events: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    gates = hard_gate_violations(ranked, mission)
    coverage = evidence_coverage(ranked, posts, n=10)
    intensive = intensive_read_coverage(ranked, posts, n=20)
    stability = ranking_stability(ranked)
    attribution = attribution_completeness(events, sku=str(mission.get("product") or ""))
    video_n = len(list(posts or []))
    genomes = genome_coverage(ranked, n=10)
    spend_ready = 0
    underwrite_n = 0
    if ranked is not None and not ranked.empty:
        top = _top_n(ranked)
        underwrite_n = len(top)
        if "spend_ready" in top.columns:
            spend_ready = int(top["spend_ready"].sum())
        version = str(top.iloc[0].get("ranking_model_version") or "") if underwrite_n else ""
    else:
        version = ""
    return [
        {
            "id": "hard_gates",
            "dimension": "Hard threshold correctness",
            "target": "0 Top 10 violations",
            "value": gates,
            "passed": gates == 0,
            "detail": f"{catalog_size} catalog rows recalled; ranked rows already passed gates.",
        },
        {
            "id": "evidence",
            "dimension": "Evidence coverage",
            "target": "100% of Top 10 have +/− evidence, five scores, labeled clip timestamps",
            "value": round(coverage["rate"] * 100, 1),
            "passed": coverage["rate"] >= 1.0 and coverage["total"] >= 1,
            "detail": f"{coverage['covered']}/{coverage['total']} covered. Missing: {', '.join(coverage['missing']) or 'none'}.",
        },
        {
            "id": "stability",
            "dimension": "Ranking stability",
            "target": "Same input → same Top 10",
            "value": len(stability),
            "passed": len(stability) == min(10, max(len(ranked) if ranked is not None else 0, 0)),
            "detail": ",".join(stability) if stability else "empty ranking",
        },
        {
            "id": "attribution",
            "dimension": "Attribution completeness",
            "target": "Recorded events keep creator + root + source",
            "value": round(attribution["rate"] * 100, 1),
            "passed": attribution["rate"] >= 1.0,
            "detail": attribution.get("note") or f"{attribution['complete']}/{attribution['total']} events.",
        },
        {
            "id": "recall",
            "dimension": "Recall pool",
            "target": "60 public-channel catalog rows",
            "value": catalog_size,
            "passed": catalog_size >= 60,
            "detail": "Demo catalog recall of public YouTube channel rows. Not a live platform crawl. Not KYC.",
        },
        {
            "id": "intensive_read",
            "dimension": "Top 20 intensive-read clips",
            "target": "20 creators × clips × timestamps × labeled caption/keyframe/comment themes; ASR not_collected",
            "value": intensive["covered"],
            "passed": intensive["rate"] >= 1.0
            and intensive["total"] >= 20
            and not intensive.get("invented_asr"),
            "detail": (
                f"{intensive['covered']}/{intensive['total']} have labeled-demo caption, keyframe note and comment themes. "
                f"Missing: {', '.join(intensive['missing']) or 'none'}. "
                "Platform ASR stays not_collected. Interview adoption ≥70% is not_collected."
            ),
        },
        {
            "id": "catalog_videos",
            "dimension": "Catalog video evidence",
            "target": "180 authored clips (3 per creator)",
            "value": video_n,
            "passed": video_n >= 180,
            "detail": "Synthetic catalog URLs. Not live ingest, not ASR, not comment mining.",
        },
        {
            "id": "creator_genome",
            "dimension": "Creator Genome coverage",
            "target": "Top 10 have versioned genomes, clip ids, ASR/comments/keyframes marked not_collected",
            "value": genomes["pack_size"],
            "passed": genomes["rate"] >= 1.0 and genomes["total"] >= 1 and genomes["pack_size"] >= 60,
            "detail": f"{genomes['covered']}/{genomes['total']} Top 10 covered · pack {genomes['pack_size']}. Missing: {', '.join(genomes['missing']) or 'none'}.",
        },
        {
            "id": "claim_underwrite",
            "dimension": "Claim-underwrite spend-ready cut",
            "target": "Top 10 sorted by Evidence Reader claim coverage; ≥1 spend-ready when the book exists",
            "value": spend_ready,
            "passed": (
                version == UNDERWRITE_VERSION
                and spend_ready >= 1
                and underwrite_n >= 1
            ) or (version != UNDERWRITE_VERSION),
            "detail": (
                f"{spend_ready}/{underwrite_n} Top 10 are spend-ready (grounded DNA claim). "
                f"Ranking {version or 'empty'}. Without the Evidence Reader book this gate is not claimed."
            ),
        },
    ]
