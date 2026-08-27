"""Claim-underwriting desk copy used on Launch and Growth."""

from __future__ import annotations

from components.html import esc
from components.i18n import t
from services.youtube_service import is_youtube_available


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


def live_lookup_caption() -> str:
    if is_youtube_available():
        return t("Live YouTube Data API results. Attach a channel as evidence; it does not enter the ranked catalog.")
    return t("Set YOUTUBE_API_KEY to search public YouTube channels. The ranked table below remains the demo catalog.")
