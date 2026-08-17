from __future__ import annotations

from uuid import uuid4

import streamlit as st

from components.html import badge, metric_cards, page_header
from components.i18n import t
from components.positioning import why_not_ttcm_html
from components.shell import render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_mission,
    mission_health_snapshot,
    missions,
    ranking,
    save_mission,
    set_active_context,
    tracking_assets,
    workflow_summary,
    performance_events,
)
from components.ui import md
from src.domain import launch_progress, pipeline_counts


def _progress() -> dict:
    counts = pipeline_counts(workflow_summary())
    return launch_progress(
        shortlisted=counts["shortlisted"],
        approved=counts["approved"],
        tracking_assets=len(tracking_assets()),
        performance_events=len(performance_events()),
    )


def _process_strip(progress: dict) -> str:
    html = []
    for index, step in enumerate(progress["steps"], 1):
        html.append(
            f'<div class="is-process-step {step["status"]}">'
            f'<span class="is-process-num">{index:02d}</span>'
            f'<span><b>{step["title"]}</b><small>{step["note"]}</small></span>'
            "</div>"
        )
    return (
        '<div class="is-process-scroll"><div class="is-process is-process-live">'
        + "".join(html)
        + "</div></div>"
    )


def _product_card(mission: dict, health: dict) -> str:
    markets = " / ".join(mission.get("markets", [mission.get("market", "United States")]))
    score = int(health.get("score", 0))
    return f"""
    <div class="is-card is-product-card">
      <div class="is-product-visual"><div class="is-camera"></div></div>
      <div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
          {badge('Launch Mission','blue')}
          <b style="font-size:16px;letter-spacing:-0.02em">{mission['product']}</b>
        </div>
        <div class="is-product-info">
          <div class="is-field"><label>Target markets</label><strong>{markets}</strong></div>
          <div class="is-field"><label>Campaign dates</label><strong>{mission.get('campaign_dates')}</strong></div>
          <div class="is-field"><label>Mission status</label><strong>{badge(mission.get('status','Active'),'green')}</strong></div>
          <div class="is-field"><label>Launch objective</label><strong>{mission.get('objective')}</strong></div>
          <div class="is-field"><label>Total budget</label><strong>USD {mission.get('budget_usd',0):,.0f}</strong></div>
          <div class="is-field"><label>Owner</label><strong>{mission.get('owner','Olivia Chen')}</strong></div>
        </div>
      </div>
      <div class="is-health">
        <div class="is-donut" style="--pct:{score}"><span>{score}</span></div>
        <b>{health.get("label", "Needs shortlist")}</b>
        <small>{health.get("note", "Computed from the active workflow")}</small>
      </div>
    </div>
    """


def _workflow_card(progress: dict) -> str:
    items = []
    for index, step in enumerate(progress["steps"], 1):
        cls = {"done": "done", "current": "active", "pending": "pending"}.get(step["status"], "")
        items.append(
            f'<div class="is-workflow-item {cls}"><div class="is-workflow-icon">{index:02d}</div>'
            f'<b>{step["title"]}</b><small>{step["note"]}</small></div>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Mission workflow</span>'
        '<span class="is-panel-link">From the active workflow</span></div>'
        '<div class="is-panel-body"><div class="is-workflow is-workflow-live">'
        + "".join(items)
        + "</div></div></div>"
    )


def _actions_card(summary: dict[str, int], market: str, tracking_n: int, events_n: int) -> str:
    actions = [
        (f'Review {summary.get("shortlisted", 0)} currently shortlisted creators', f"Evidence review for {market}"),
        (f'Contact {summary.get("approved", 0)} currently approved creators', "Advance audited outreach cases"),
        (f'{tracking_n} tracking assets issued', "Coupons and UTM links, not conversions"),
        (f'{events_n} performance events recorded', "Sourced conversions only"),
    ]
    rows = []
    for idx, (title, note) in enumerate(actions, 1):
        rows.append(
            f'<li><span class="is-list-num">{idx}</span><span><b>{title}</b><small>{note}</small></span></li>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Recommended next actions</span>'
        '<span class="is-panel-link">Live counts</span></div><div class="is-panel-body"><ul class="is-list">'
        + "".join(rows)
        + "</ul></div></div>"
    )


def _tasks_notifications(mission: dict, progress: dict) -> str:
    owner = mission.get("owner", "Mission owner")
    tasks = []
    for index, task in enumerate(progress["upcoming"], 1):
        tasks.append(
            '<li><span class="is-list-num" style="border-radius:6px;background:#F1F4F5;color:#4A565E">'
            f'{index:02d}</span><span><b>{task["title"]}</b><small>NEXT · {owner} · {task["note"]}</small></span></li>'
        )
    notifications = [
        ("Context synchronized", f'All pages now use {mission.get("name", mission.get("product", "this mission"))}.', "now"),
        ("State machine active", "Every creator transition records actor, reason and evidence.", "now"),
        ("Attribution guardrail", "Unsourced outcomes remain explicitly empty.", "now"),
    ]
    notes = []
    for idx, (title, note, when) in enumerate(notifications):
        notes.append(
            f'<li><span class="is-list-num" style="background:{"#EAF2FF" if idx == 0 else "#E9F8F1" if idx == 1 else "#FFF4E4"};color:#34424A">•</span>'
            f'<span><b>{title}</b><small>{note} · {when}</small></span></li>'
        )
    return (
        '<div class="is-card" style="margin-bottom:10px"><div class="is-panel-head"><span class="is-panel-title">Upcoming tasks</span>'
        '<span class="is-panel-link">From the active workflow</span></div><div class="is-panel-body"><ul class="is-list">'
        + "".join(tasks)
        + "</ul></div></div>"
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Team notifications</span>'
        '</div><div class="is-panel-body"><ul class="is-list">'
        + "".join(notes)
        + "</ul></div></div>"
    )


def render() -> None:
    render_topbar()
    mission_records = missions()
    mission_by_name = {item.get("name", item["mission_id"]): item["mission_id"] for item in mission_records}
    preferred_id = st.session_state.pop("pending_mission_id", st.session_state.get("active_mission_id"))
    mission_names = list(mission_by_name)
    preferred_name = next((name for name, mission_id in mission_by_name.items() if mission_id == preferred_id), mission_names[0])
    selected_name = st.selectbox(
        t("Open launch mission"),
        mission_names,
        index=mission_names.index(preferred_name),
        label_visibility="collapsed",
    )
    set_active_context("mission", mission_by_name[selected_name])
    mission = active_mission()
    summary = workflow_summary()
    ranked = ranking()
    health = mission_health_snapshot()
    tracking_n = len(tracking_assets())
    events_n = len(performance_events())
    progress = _progress()

    left, right = st.columns([1, 0.26], vertical_alignment="top")
    with left:
        md(
            page_header(
                "Launch Mission Dashboard",
                "Realtime overview of global creator growth operations.",
                "Operations overview",
            ),
            unsafe_allow_html=True,
        )
    with right:
        b1, b2 = st.columns(2)
        with b1:
            st.button(t("Export"), use_container_width=True, disabled=True, help=t("Not wired in this demo"))
        with b2:
            if st.button(t("+ New Mission"), type="primary", use_container_width=True, disabled=writes_locked()):
                st.session_state.show_mission_form = not st.session_state.show_mission_form
    render_write_guard()
    with st.expander(t("Why this is not TikTok Creator Marketplace"), expanded=False):
        md(why_not_ttcm_html(), unsafe_allow_html=True)

    if st.session_state.show_mission_form:
        with st.expander(t("Create a new launch mission"), expanded=True):
            c1, c2, c3 = st.columns(3)
            product = c1.text_input(t("Product"), mission["product"])
            market = c2.selectbox(t("Primary market"), ["United States", "Mexico", "Japan"])
            budget = c3.number_input(t("Budget (USD)"), min_value=10000, value=int(mission["budget_usd"]), step=10000)
            objective = st.text_area(t("Launch objective"), mission["objective"])
            if st.button(t("Save mission"), type="primary", disabled=writes_locked()):
                saved = {
                    "mission_id": f"mission_{uuid4().hex[:8]}",
                    "name": f"{product} · {market} Launch",
                    "product": product,
                    "market": market,
                    "markets": [market],
                    "language": "Spanish" if market == "Mexico" else "English",
                    "languages": ["Spanish" if market == "Mexico" else "English"],
                    "budget_usd": budget,
                    "max_cost_usd": mission.get("max_cost_usd", 12000),
                    "min_brand_safety": mission.get("min_brand_safety", 72),
                    "target_topics": mission.get("target_topics", []),
                    "target_styles": mission.get("target_styles", []),
                    "objective": objective,
                    "campaign_dates": mission.get("campaign_dates", "Not scheduled"),
                    "owner": mission.get("owner", "Olivia Chen"),
                    "status": "Draft",
                }
                save_mission(saved)
                st.session_state.pending_mission_id = saved["mission_id"]
                st.session_state.show_mission_form = False
                st.success("Mission saved for this demo session.")
                st.rerun()

    md(_process_strip(progress), unsafe_allow_html=True)
    md(_product_card(mission, health), unsafe_allow_html=True)
    metrics = [
        ("Candidates Pool", str(len(ranked)), "Eligible for this mission", ""),
        ("Shortlisted", str(summary.get("shortlisted", 0)), "Unified workflow", ""),
        ("Approved", str(summary.get("approved", 0)), "Human decisions", ""),
        ("Contacted", str(summary.get("contacted", 0)), "Audited outreach", ""),
        ("Published", str(summary.get("published", 0)), "Linked workflow", ""),
        ("Measured", str(summary.get("measured", 0)), "Sourced events only", ""),
    ]
    md(metric_cards(metrics), unsafe_allow_html=True)

    main, side = st.columns([1, 0.34], gap="small", vertical_alignment="top")
    with main:
        c1, c2 = st.columns([1.25, 0.85], gap="small")
        with c1:
            md(_workflow_card(progress), unsafe_allow_html=True)
        with c2:
            md(_actions_card(summary, mission.get("market", "Target market"), tracking_n, events_n), unsafe_allow_html=True)
    with side:
        md(_tasks_notifications(mission, progress), unsafe_allow_html=True)

    render_demo_notice()
