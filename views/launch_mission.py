from __future__ import annotations

import streamlit as st

from components.data import MISSION_METRICS, NOTIFICATIONS, UPCOMING_TASKS
from components.html import badge, metric_cards, page_header
from components.shell import render_demo_notice, render_topbar
from components.state import active_mission


def _process_strip() -> str:
    steps = [
        ("01", "Launch Mission", "Mission setup"),
        ("02", "Creator Search", "Recall & match"),
        ("03", "Creator Compare", "Evidence review"),
        ("04", "Content Studio", "Local variants"),
        ("05", "Outreach Ops", "Execution"),
        ("06", "Growth Review", "Outcome learning"),
    ]
    html = []
    for num, title, note in steps:
        html.append(
            '<div class="is-process-step">'
            f'<span class="is-process-num">{num}</span>'
            f'<span><b>{title}</b><small>{note}</small></span>'
            '</div>'
        )
    return '<div class="is-process-scroll"><div class="is-process">' + "".join(html) + '</div></div>'


def _product_card(mission: dict) -> str:
    markets = " / ".join(mission.get("markets", [mission.get("market", "United States")]))
    return f"""
    <div class="is-card is-product-card">
      <div class="is-product-visual"><div class="is-camera"></div></div>
      <div>
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:10px">
          {badge('Launch Mission','blue')}
          <b style="font-size:15px">{mission['product']}</b>
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
        <div class="is-donut" style="--pct:{mission.get('health_score',86)}"><span>{mission.get('health_score',86)}</span></div>
        <b>Healthy</b><small>On track</small>
      </div>
    </div>
    """


def _workflow_card() -> str:
    steps = [
        ("01", "Mission setup", "Completed", "done"),
        ("02", "Creator match", "In progress", "done"),
        ("03", "Content studio", "In progress", "active"),
        ("04", "Outreach", "Upcoming", ""),
        ("05", "Review", "Upcoming", ""),
        ("06", "Optimization", "Upcoming", ""),
    ]
    items = []
    for num, title, state, cls in steps:
        items.append(
            f'<div class="is-workflow-item {cls}"><div class="is-workflow-icon">{num}</div>'
            f'<b>{title}</b><small>{state}</small></div>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Mission workflow</span>'
        '<span class="is-panel-link">View workflow details →</span></div>'
        '<div class="is-panel-body"><div class="is-workflow">' + "".join(items) + '</div></div></div>'
    )


def _actions_card() -> str:
    actions = [
        ("Approve 10 matched creators", "High fit for US audience & travel"),
        ("Review content briefs", "4 drafts awaiting feedback"),
        ("Boost outreach in Mexico", "Engagement rate showing up"),
        ("Optimize budget allocation", "Shift budget to top-performing markets"),
    ]
    rows = []
    for idx, (title, note) in enumerate(actions, 1):
        rows.append(
            f'<li><span class="is-list-num">{idx}</span><span><b>{title}</b><small>{note}</small></span></li>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Recommended next actions</span>'
        '<span class="is-panel-link">View all →</span></div><div class="is-panel-body"><ul class="is-list">'
        + "".join(rows) + '</ul></div></div>'
    )


def _tasks_notifications() -> str:
    tasks = []
    for month, day, title, note in UPCOMING_TASKS:
        tasks.append(
            '<li><span class="is-list-num" style="border-radius:6px;background:#F1F4F5;color:#4A565E">'
            f'{day}</span><span><b>{title}</b><small>{month} · {note}</small></span></li>'
        )
    notes = []
    for idx, (title, note, when) in enumerate(NOTIFICATIONS):
        notes.append(
            f'<li><span class="is-list-num" style="background:{"#EAF2FF" if idx == 0 else "#E9F8F1" if idx == 1 else "#FFF4E4"};color:#34424A">•</span>'
            f'<span><b>{title}</b><small>{note} · {when}</small></span></li>'
        )
    return (
        '<div class="is-card" style="margin-bottom:10px"><div class="is-panel-head"><span class="is-panel-title">Upcoming tasks</span>'
        '<span class="is-panel-link">View all (8)</span></div><div class="is-panel-body"><ul class="is-list">'
        + "".join(tasks) + '</ul></div></div>'
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Team notifications</span>'
        '<span class="is-panel-link">View all</span></div><div class="is-panel-body"><ul class="is-list">'
        + "".join(notes) + '</ul></div></div>'
    )


def render() -> None:
    render_topbar()
    mission = active_mission()

    left, right = st.columns([1, 0.26], vertical_alignment="top")
    with left:
        st.markdown(
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
            st.button("Export", use_container_width=True)
        with b2:
            if st.button("+ New Mission", type="primary", use_container_width=True):
                st.session_state.show_mission_form = not st.session_state.show_mission_form

    if st.session_state.show_mission_form:
        with st.expander("Create a new launch mission", expanded=True):
            c1, c2, c3 = st.columns(3)
            product = c1.text_input("Product", mission["product"])
            market = c2.selectbox("Primary market", ["United States", "Mexico", "Japan"])
            budget = c3.number_input("Budget (USD)", min_value=10000, value=int(mission["budget_usd"]), step=10000)
            objective = st.text_area("Launch objective", mission["objective"])
            if st.button("Save mission", type="primary"):
                st.session_state.mission = {
                    **mission,
                    "product": product,
                    "market": market,
                    "language": "Spanish" if market == "Mexico" else "English",
                    "budget_usd": budget,
                    "objective": objective,
                }
                st.session_state.show_mission_form = False
                st.success("Mission saved for this demo session.")
                st.rerun()

    st.markdown(_process_strip(), unsafe_allow_html=True)
    st.markdown(_product_card(mission), unsafe_allow_html=True)
    st.markdown(metric_cards(MISSION_METRICS), unsafe_allow_html=True)

    main, side = st.columns([1, 0.34], gap="small", vertical_alignment="top")
    with main:
        c1, c2 = st.columns([1.25, 0.85], gap="small")
        with c1:
            st.markdown(_workflow_card(), unsafe_allow_html=True)
        with c2:
            st.markdown(_actions_card(), unsafe_allow_html=True)
    with side:
        st.markdown(_tasks_notifications(), unsafe_allow_html=True)

    render_demo_notice()
