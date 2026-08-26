"""Positioning copy: why InstaSpark is not TikTok Creator Marketplace."""

from __future__ import annotations

from components.html import esc
from components.i18n import t
from services.youtube_service import is_youtube_available, youtube_status_label
from src.rubric_scorecard import SCORECARD_ID


WHY_NOT_TTCM_POINTS = (
    (
        "TTCM books TikTok inventory",
        "TikTok Creator Marketplace already has live TikTok creators, payouts and first-party attribution. This product does not replace that booking rail.",
    ),
    (
        "InstaSpark underwrites the mix",
        "A hardware launch needs mission-first and inbound-first work on one state machine. Spend is authorized against named Product DNA claims on public captions, not against a similarity score.",
    ),
    (
        "Spend follows a governed shortlist",
        "Claim coverage, mix overlap, product-grounded briefs and unique UTM coupons exist so the team does not pay eight creators for two audiences or for a claim nobody filmed. Live YouTube lookup is optional and labeled; it never becomes a new ranked catalog row.",
    ),
)

PARADIGM_POINTS = (
    (
        "Not retrieval",
        "Marketplaces retrieve similar creators. This desk underwrites named Product DNA claims against public captions before a dollar is authorized — the same way a credit desk underwrites covenants, not lookalikes.",
    ),
    (
        "AI mints the book",
        "Only EvidenceReader can mint a claim_id from public timedtext. Rules, keywords, and embeddings never substitute. Without the model cache the spend-ready cut is blocked.",
    ),
    (
        "Human signs the policy",
        "Approve, override, and Calibrator weight changes stay on the audit trail. Contact pack plus Advance is the operational handoff. Send to Creator stays disabled.",
    ),
)


def why_not_ttcm_html(*, compact: bool = False) -> str:
    points = "".join(
        f"<li><b>{esc(t(title))}</b> {esc(t(body))}</li>"
        for title, body in WHY_NOT_TTCM_POINTS
    )
    status = t(youtube_status_label())
    cls = "is-scope-note compact" if compact else "is-scope-note"
    return (
        f'<div class="{cls}">'
        f'<div class="is-scope-kicker">{esc(t("Not TikTok Creator Marketplace"))}</div>'
        f"<h4>{esc(t('TTCM sells a TikTok slot. This workspace underwrites a cross-platform launch mix against Product DNA claims.'))}</h4>"
        f"<ul>{points}</ul>"
        f'<small>{esc(t("Live lookup status"))}: {esc(status)}. '
        f'{esc(t("No TikTok or Instagram ingest, no creator payout, no first-party conversion claim."))}</small>'
        "</div>"
    )


def paradigm_html() -> str:
    points = "".join(
        f"<li><b>{esc(t(title))}</b> {esc(t(body))}</li>"
        for title, body in PARADIGM_POINTS
    )
    return (
        '<div class="is-card" id="claim-underwrite-paradigm" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{esc(t("Claim-underwriting desk"))}</span>'
        f'<span class="is-panel-link">{esc(t("Industry analogue: credit underwriting, not creator retrieval"))}</span></div>'
        '<div class="is-panel-body">'
        f"<h4>{esc(t('A creator is spend-ready only when public content grounds a Product DNA claim.'))}</h4>"
        f"<ul>{points}</ul>"
        f"<small>{esc(t('Scout is the rule-mix constraint layer. Evidence Reader is the underwriting book. MatchArbiter will not open the gate on a score alone.'))}</small>"
        "</div></div>"
    )


def rubric_scorecard_html(card: dict) -> str:
    """Four contest dimensions with live 5 / 3 / 1 evidence. Not a marketing badge."""

    rows = list(card.get("dimensions") or [])
    cells = []
    for row in rows:
        met = bool(row.get("met"))
        cls = "is-met" if met else "is-gap"
        gates = "".join(
            f'<li class="{"ok" if item.get("passed") else "fail"}">'
            f'<b>{"5-bar" if item.get("passed") else "gap"}</b> {esc(item.get("detail") or "")}</li>'
            for item in row.get("gates") or []
        )
        cells.append(
            f'<div class="is-rubric-card {cls}" id="rubric-{esc(row.get("id") or "")}">'
            f'<div class="is-rubric-kicker">{int(row.get("weight_pct") or 0)}% · {esc(row.get("title_zh") or "")}</div>'
            f'<div class="is-rubric-score">{int(row.get("points") or 1)}</div>'
            f'<small>{esc(t("vs 5-point bar"))}: {esc(row.get("bar_5") or "")}</small>'
            f'<h4>{esc(t(str(row.get("title") or "")))}</h4>'
            f'<p>{esc(t(str(row.get("claim") or "")))}</p>'
            f'<ul>{gates}</ul>'
            f'<small>{esc(t("Without this"))}: {esc(t(str(row.get("without") or "")))}</small>'
            "</div>"
        )
    status = t("All four 5-point bars are met on live artifacts") if card.get("all_met") else t(
        "A 5-point bar is still open — see the gap row"
    )
    return (
        f'<div class="is-card" id="{SCORECARD_ID}" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{esc(t("Scoring rubric evidence"))}</span>'
        f'<span class="is-panel-link">{esc(status)}</span></div>'
        '<div class="is-panel-body">'
        f'<small>{esc(card.get("note") or "")}</small>'
        f'<div class="is-rubric-grid">{"".join(cells)}</div>'
        f'<small>{esc(t("Workflow"))}: {esc(card.get("workflow") or "")}</small>'
        "</div></div>"
    )


def live_lookup_caption() -> str:
    if is_youtube_available():
        return t("Live YouTube Data API results. Attach a channel as evidence; it does not enter the ranked catalog.")
    return t("Set YOUTUBE_API_KEY to search public YouTube channels. The ranked table below remains the demo catalog.")
