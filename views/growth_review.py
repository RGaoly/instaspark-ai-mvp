from __future__ import annotations

import streamlit as st

from components.html import esc, mission_chip, page_header
from components.i18n import t
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_context,
    active_context_label,
    creator_state,
    creators,
    performance_events,
    ranking,
    record_performance_event,
    select_creator,
    tracking_assets,
    workflow_board,
    workflow_summary,
)
from components.ui import md
from src.domain import PERIOD_WINDOW_DAYS, attributed_roi, filter_dated_records, filter_performance_events

_OUTREACH_STATES = {
    "approved",
    "contacted",
    "negotiating",
    "contracted",
    "content_in_review",
    "published",
    "measured",
}


def _kpi_strip(summary: dict[str, int], events: list[dict], budget: float) -> str:
    orders = sum(int(event.get("orders", 0)) for event in events)
    revenue = sum(float(event.get("revenue_usd", 0)) for event in events)
    spend = sum(float(event.get("spend_usd", 0)) for event in events)
    roi = attributed_roi(events)
    adoption_base = max(sum(summary.values()) - summary.get("closed_lost", 0), 1)
    adopted = sum(summary.get(state, 0) for state in ["approved", "contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])
    metrics = [
        ("Shortlist adoption", f"{adopted / adoption_base:.0%}", "From this entry"),
        ("Contacted", str(summary.get("contacted", 0)), "Audited workflow"),
        ("Published", str(summary.get("published", 0)), "Audited workflow"),
        ("Measured", str(summary.get("measured", 0)), "Performance linked"),
        ("Attributed orders", f"{orders:,}", "Filtered recorded events"),
        ("Revenue", f"${revenue:,.0f}", "Filtered recorded events"),
        ("ROI", f"{roi:.2f}x", "Filtered events only · 0x if empty"),
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


def _event_recorded_label(event: dict) -> str:
    stamp = str(event.get("recorded_at") or "").strip()
    return stamp[:10] if stamp else "—"


def _performance_table(events: list[dict]) -> str:
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Content", "Market", "Recorded", "Orders", "Revenue", "Spend"])
    if not events:
        body = '<tr><td colspan="7">No performance events in this period and market.</td></tr>'
    else:
        body = "".join(
            "<tr>"
            f'<td>{esc(event.get("creator_id", "—"))}</td>'
            f'<td>{esc(event.get("content_asset_id", "—"))}</td>'
            f'<td>{esc(event.get("market", "—"))}</td>'
            f'<td>{esc(_event_recorded_label(event))}</td>'
            f'<td>{int(event.get("orders", 0)):,}</td>'
            f'<td>${float(event.get("revenue_usd", 0)):,.0f}</td>'
            f'<td>${float(event.get("spend_usd", 0)):,.0f}</td></tr>'
            for event in events
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _tracking_table(assets: list[dict], *, any_issued: bool = True) -> str:
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Market", "Coupon", "UTM campaign", "Deeplink"])
    if not assets:
        if any_issued:
            body = '<tr><td colspan="5">No tracking assets in this period and market.</td></tr>'
        else:
            body = '<tr><td colspan="5">No tracking assets issued yet. Approve outreach to mint a coupon and UTM deeplink.</td></tr>'
    else:
        body = "".join(
            "<tr>"
            f'<td>{esc(item.get("creator_id", "—"))}</td>'
            f'<td>{esc(item.get("market", "—"))}</td>'
            f'<td>{esc(item.get("coupon", "—"))}</td>'
            f'<td>{esc(item.get("utm_campaign", "—"))}</td>'
            f'<td>{esc(item.get("deeplink", "—"))}</td></tr>'
            for item in assets
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _recordable_creators() -> list[tuple[str, str, dict]]:
    """Approved / coupon-bearing creators for the active entry, names for the form."""

    assets = {item["creator_id"]: item for item in tracking_assets()}
    names = {row["creator_id"]: row["creator_name"] for _, row in creators().iterrows()}
    ordered: list[str] = []
    for creator_id in assets:
        if creator_id not in ordered:
            ordered.append(creator_id)
    for stage, people in workflow_board().items():
        if stage not in _OUTREACH_STATES:
            continue
        for person in people:
            creator_id = person.get("creator_id")
            if creator_id and creator_id not in ordered:
                ordered.append(creator_id)
    return [(creator_id, names.get(creator_id, creator_id), assets.get(creator_id, {})) for creator_id in ordered]


def _next_actions(context: dict, summary: dict[str, int], events: list[dict], assets: list[dict]) -> str:
    actions = []
    if summary.get("approved", 0):
        actions.append(("blue", "Execute", "Contact approved creators", "Approved creators are waiting for outreach.", "Go to Outreach"))
    if not events and (assets or summary.get("published", 0)):
        actions.append(
            (
                "orange",
                "Measure",
                "Record the conversion on Growth Review",
                "Coupons are tracking assets, not conversions. ROI stays 0x until an operator records an event.",
                "Use the expander below",
            )
        )
    if not actions:
        actions.append(("green", "On track", "Continue the governed workflow", f'Use evidence from {context.get("title", "this entry")} for the next decision.', "Human review"))
    return '<div class="is-budget-actions">' + "".join(
        f'<div class="is-action-card {tone}"><div><span class="is-badge is-badge-{tone}">{esc(tag)}</span></div>'
        f'<h4>{esc(title)}</h4><p>{esc(body)}</p><div class="is-action-impact">{esc(impact)}</div></div>'
        for tone, tag, title, body, impact in actions
    ) + "</div>"


def _perf_event_label(creator_id: str, name: str) -> str:
    return f"{name} · {creator_id}"


def _prefill_record_form(recordable: list[tuple[str, str, dict]], *, force: bool) -> None:
    labels = [_perf_event_label(creator_id, name) for creator_id, name, _ in recordable]
    selected_id = st.session_state.get("selected_creator_id")
    current = st.session_state.get("perf_event_creator")
    if not force and current in labels:
        return
    if not selected_id:
        return
    for creator_id, name, _ in recordable:
        if creator_id == selected_id:
            st.session_state["perf_event_creator"] = _perf_event_label(creator_id, name)
            return


def _render_post_record_handoff() -> None:
    if st.session_state.pop("growth_event_toast", False):
        if st.session_state.pop("growth_moved_to_measured", False):
            st.toast(t("Performance event recorded. Creator moved to Measured."))
        else:
            st.toast(t("Performance event recorded. ROI uses this event, not a forecast."))
    if not st.session_state.get("growth_open_outreach"):
        return
    if st.button(t("Open Outreach"), type="primary"):
        st.session_state.pop("growth_open_outreach", None)
        open_workspace_page("outreach-operations")


def _render_record_form() -> None:
    expand = bool(st.session_state.pop("growth_record_event_open", False))
    with st.expander(t("Record performance event (demo)"), expanded=expand):
        render_write_guard()
        recordable = _recordable_creators()
        if not recordable:
            st.caption(t("Approve a creator first to mint a coupon, then record the conversion here."))
            return
        _prefill_record_form(recordable, force=expand)
        labels = [_perf_event_label(creator_id, name) for creator_id, name, _ in recordable]
        choice = st.selectbox(t("Creator"), labels, key="perf_event_creator")
        selected = recordable[labels.index(choice)]
        creator_id, _name, asset = selected
        coupon = str(asset.get("coupon") or "")
        utm = str(asset.get("deeplink") or asset.get("utm_campaign") or "")
        if coupon:
            st.caption(f'{t("Coupon")}: {coupon}')
        locked = writes_locked()
        with st.form("record_performance_event_form"):
            orders = st.number_input(t("Orders"), min_value=0, step=1, value=0)
            revenue_usd = st.number_input(t("Revenue USD"), min_value=0.0, step=50.0, value=0.0)
            spend_usd = st.number_input(t("Spend USD"), min_value=0.0, step=50.0, value=0.0)
            note = st.text_input(t("Note"), value="")
            submitted = st.form_submit_button(t("Record event"), type="primary", disabled=locked)
        if submitted:
            try:
                before = creator_state(creator_id)
                record_performance_event(
                    creator_id,
                    int(orders),
                    float(revenue_usd),
                    float(spend_usd),
                    coupon=coupon or None,
                    utm=utm or None,
                    note=note.strip() or None,
                )
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                select_creator(creator_id)
                st.session_state["growth_event_toast"] = True
                st.session_state["growth_open_outreach"] = True
                st.session_state["outreach_focus_creator_id"] = creator_id
                if before == "published" and creator_state(creator_id) == "measured":
                    st.session_state["growth_moved_to_measured"] = True
                st.rerun()


def render() -> None:
    render_topbar()
    context = active_context()
    summary = workflow_summary()
    events = performance_events()
    assets = tracking_assets()
    ranked = ranking()
    budget = float(context.get("budget_usd", 0))
    period_keys = list(PERIOD_WINDOW_DAYS)
    mission_markets = [item for item in (context.get("markets") or [context.get("market")]) if item]
    market_keys = ["All markets", *mission_markets]

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
    period_key = controls[1].selectbox(
        t("Period"),
        period_keys,
        index=period_keys.index("All recorded events"),
        format_func=lambda key: t(key),
        key="growth_period",
        label_visibility="collapsed",
    )
    market_key = controls[2].selectbox(
        t("Market"),
        market_keys,
        format_func=lambda key: t(key) if key == "All markets" else key,
        key="growth_market",
        label_visibility="collapsed",
    )
    controls[3].button(t("Export"), use_container_width=True, disabled=True, help=t("Not wired in this demo"))

    period_days = PERIOD_WINDOW_DAYS[period_key]
    market_filter = None if market_key == "All markets" else market_key
    filtered_events = filter_performance_events(events, period_days=period_days, market=market_filter)
    filtered_assets = filter_dated_records(
        assets,
        period_days=period_days,
        market=market_filter,
        timestamp_field="created_at",
        market_field="market",
    )

    md(_kpi_strip(summary, filtered_events, budget), unsafe_allow_html=True)
    st.caption(
        t("ROI uses recorded performance events in the selected period and market. Empty set equals 0x.")
    )

    left, right = st.columns([0.38, 0.62], gap="small")
    with left:
        md(
            '<div class="is-chart"><div class="is-chart-title">Creator funnel</div>'
            + _funnel(len(ranked), summary, filtered_events)
            + "</div>",
            unsafe_allow_html=True,
        )
    with right:
        md(
            '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Linked performance events</span>'
            '<span class="is-panel-link">No inferred attribution</span></div>'
            f'<div class="is-panel-body">{_performance_table(filtered_events)}</div></div>',
            unsafe_allow_html=True,
        )

    md(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Issued tracking assets</span>'
        '<span class="is-panel-link">Minted on approve · not conversions</span></div>'
        f'<div class="is-panel-body">{_tracking_table(filtered_assets, any_issued=bool(assets))}</div></div>',
        unsafe_allow_html=True,
    )

    md(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Next best action</span><span class="is-panel-link">Human approval required</span></div>'
        f'<div class="is-panel-body">{_next_actions(context, summary, events, assets)}</div></div>',
        unsafe_allow_html=True,
    )

    _render_post_record_handoff()
    _render_record_form()

    render_demo_notice()
