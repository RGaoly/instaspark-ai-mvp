from __future__ import annotations

import streamlit as st

from components.html import esc, mission_chip, page_header
from components.i18n import t
from components.shell import render_demo_notice, render_topbar
from components.state import (
    active_context,
    active_context_label,
    performance_events,
    ranking,
    tracking_assets,
    workflow_summary,
)
from components.ui import md


def _kpi_strip(summary: dict[str, int], events: list[dict], budget: float) -> str:
    orders = sum(int(event.get("orders", 0)) for event in events)
    revenue = sum(float(event.get("revenue_usd", 0)) for event in events)
    spend = sum(float(event.get("spend_usd", 0)) for event in events)
    roi = revenue / spend if spend else 0
    adoption_base = max(sum(summary.values()) - summary.get("closed_lost", 0), 1)
    adopted = sum(summary.get(state, 0) for state in ["approved", "contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])
    metrics = [
        ("Shortlist adoption", f"{adopted / adoption_base:.0%}", "From this entry"),
        ("Contacted", str(summary.get("contacted", 0)), "Audited workflow"),
        ("Published", str(summary.get("published", 0)), "Audited workflow"),
        ("Measured", str(summary.get("measured", 0)), "Performance linked"),
        ("Attributed orders", f"{orders:,}", "Recorded events"),
        ("Revenue", f"${revenue:,.0f}", "Recorded events"),
        ("ROI", f"{roi:.2f}x", "Recorded events only · 0x if empty"),
        ("Budget utilization", f"{spend / budget:.0%}" if budget else "—", f"${spend:,.0f} / ${budget:,.0f}"),
    ]
    return '<div class="is-kpi-strip">' + "".join(
        '<div class="is-kpi-mini">'
        f'<label>{esc(label)}</label><strong>{esc(value)}</strong><small>{esc(note)}</small></div>'
        for label, value, note in metrics
    ) + "</div>"


def _funnel(pool: int, summary: dict[str, int], events: list[dict]) -> str:
    active_from = lambda states: sum(summary.get(state, 0) for state in states)
    steps = [
        ("Candidate pool", pool),
        ("Shortlisted", active_from(["shortlisted", "approved", "contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])),
        ("Contacted", active_from(["contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])),
        ("Published", active_from(["published", "measured"])),
        ("Measured events", len(events)),
    ]
    return '<div class="is-funnel">' + "".join(
        '<div class="is-funnel-step"><div class="is-funnel-shape"></div>'
        f'<b>{esc(label)}</b><small>{value}</small></div>' for label, value in steps
    ) + "</div>"


def _performance_table(events: list[dict]) -> str:
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Content", "Market", "Orders", "Revenue", "Spend"])
    if not events:
        body = '<tr><td colspan="6">No performance events recorded for this entry.</td></tr>'
    else:
        body = "".join(
            "<tr>"
            f'<td>{esc(event.get("creator_id", "—"))}</td>'
            f'<td>{esc(event.get("content_asset_id", "—"))}</td>'
            f'<td>{esc(event.get("market", "—"))}</td>'
            f'<td>{int(event.get("orders", 0)):,}</td>'
            f'<td>${float(event.get("revenue_usd", 0)):,.0f}</td>'
            f'<td>${float(event.get("spend_usd", 0)):,.0f}</td></tr>'
            for event in events
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _tracking_table(assets: list[dict]) -> str:
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Coupon", "UTM campaign", "Deeplink"])
    if not assets:
        body = '<tr><td colspan="4">No tracking assets issued yet. Approve outreach to mint a coupon and UTM deeplink.</td></tr>'
    else:
        body = "".join(
            "<tr>"
            f'<td>{esc(item.get("creator_id", "—"))}</td>'
            f'<td>{esc(item.get("coupon", "—"))}</td>'
            f'<td>{esc(item.get("utm_campaign", "—"))}</td>'
            f'<td>{esc(item.get("deeplink", "—"))}</td></tr>'
            for item in assets
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _next_actions(context: dict, summary: dict[str, int], events: list[dict]) -> str:
    actions = []
    if summary.get("approved", 0):
        actions.append(("blue", "Execute", "Contact approved creators", "Approved creators are waiting for outreach.", "Go to Outreach"))
    if summary.get("published", 0) and not events:
        actions.append(("orange", "Measure", "Attach performance evidence", "Published work has no linked attribution event.", "Add data source"))
    if not actions:
        actions.append(("green", "On track", "Continue the governed workflow", f'Use evidence from {context.get("title", "this entry")} for the next decision.', "Human review"))
    return '<div class="is-budget-actions">' + "".join(
        f'<div class="is-action-card {tone}"><div><span class="is-badge is-badge-{tone}">{esc(tag)}</span></div>'
        f'<h4>{esc(title)}</h4><p>{esc(body)}</p><div class="is-action-impact">{esc(impact)} →</div></div>'
        for tone, tag, title, body, impact in actions
    ) + "</div>"


def render() -> None:
    render_topbar()
    context = active_context()
    summary = workflow_summary()
    events = performance_events()
    assets = tracking_assets()
    ranked = ranking()
    budget = float(context.get("budget_usd", 0))

    md(
        page_header(
            "Growth Review",
            "Validate outcomes linked to the active entry; missing data remains explicit.",
            "Outcome learning",
            "blue",
        ),
        unsafe_allow_html=True,
    )

    controls = st.columns([0.48, 0.24, 0.18, 0.1], vertical_alignment="center")
    with controls[0]:
        md(mission_chip(active_context_label()), unsafe_allow_html=True)
    controls[1].selectbox(
        t("Period"),
        [context.get("campaign_dates", "Active entry period"), "All recorded events"],
        label_visibility="collapsed",
    )
    markets = context.get("markets") or [context.get("market", "All markets")]
    controls[2].selectbox(t("Market"), ["All markets", *markets], label_visibility="collapsed")
    controls[3].button(t("Export"), use_container_width=True)

    md(_kpi_strip(summary, events, budget), unsafe_allow_html=True)
    st.caption(
        t("ROI uses recorded performance events only. Empty events equal 0x — this is not a modeled forecast.")
    )

    left, right = st.columns([0.38, 0.62], gap="small")
    with left:
        md(
            '<div class="is-chart"><div class="is-chart-title">Creator funnel</div>'
            + _funnel(len(ranked), summary, events)
            + "</div>",
            unsafe_allow_html=True,
        )
    with right:
        md(
            '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Linked performance events</span>'
            '<span class="is-panel-link">No inferred attribution</span></div>'
            f'<div class="is-panel-body">{_performance_table(events)}</div></div>',
            unsafe_allow_html=True,
        )

    md(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Issued tracking assets</span>'
        '<span class="is-panel-link">Minted on approve · not conversions</span></div>'
        f'<div class="is-panel-body">{_tracking_table(assets)}</div></div>',
        unsafe_allow_html=True,
    )

    md(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Next best action</span><span class="is-panel-link">Human approval required</span></div>'
        f'<div class="is-panel-body">{_next_actions(context, summary, events)}</div></div>',
        unsafe_allow_html=True,
    )

    render_demo_notice()
