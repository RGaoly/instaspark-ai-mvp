"""Positioning copy: why InstaSpark is not TikTok Creator Marketplace."""

from __future__ import annotations

from components.html import esc
from components.i18n import t
from services.youtube_service import is_youtube_available, youtube_status_label


WHY_NOT_TTCM_POINTS = (
    (
        "TTCM books TikTok inventory",
        "TikTok Creator Marketplace already has live TikTok creators, payouts and first-party attribution. This product does not replace that booking rail.",
    ),
    (
        "InstaSpark decides the mix",
        "A hardware launch needs mission-first and inbound-first work on one state machine, across YouTube, Instagram and TikTok — including creators who came to you.",
    ),
    (
        "Spend follows a governed shortlist",
        "Overlap, product-grounded briefs and unique UTM coupons exist so the team does not pay eight creators for two audiences. Live YouTube lookup is optional and labeled; ranking in this demo stays a synthetic catalog unless a key is set.",
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
        f"<h4>{esc(t('TTCM sells a TikTok slot. This workspace decides a cross-platform launch mix.'))}</h4>"
        f"<ul>{points}</ul>"
        f'<small>{esc(t("Live lookup status"))}: {esc(status)}. '
        f'{esc(t("No TikTok or Instagram ingest, no creator payout, no first-party conversion claim."))}</small>'
        "</div>"
    )


def live_lookup_caption() -> str:
    if is_youtube_available():
        return t("Live YouTube Data API results. Attach a channel as evidence; it does not enter the ranked catalog.")
    return t("Set YOUTUBE_API_KEY to search public YouTube channels. The ranked table below remains the demo catalog.")
