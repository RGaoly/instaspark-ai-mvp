from __future__ import annotations

import streamlit as st

from components.data import OUTREACH_COLUMNS
from components.html import avatar, badge, esc, page_header
from components.shell import render_demo_notice, render_topbar


def _kanban() -> str:
    columns = []
    color_idx = 0
    for stage, people in OUTREACH_COLUMNS.items():
        cards = []
        for person in people:
            name, niche, market, followers, next_action = person
            cards.append(
                '<div class="is-kanban-card">'
                f'<div class="is-kanban-person">{avatar(name,color_idx)}<span><b>{esc(name)}</b><small>@{esc(name.lower().replace(" ",""))}</small></span></div>'
                f'<div class="is-kanban-meta"><span>Market</span><strong>{esc(market)}</strong><span>Niche</span><strong>{esc(niche)}</strong><span>Audience</span><strong>{esc(followers)}</strong></div>'
                f'<div class="is-kanban-next">{esc(next_action)} →</div>'
                '</div>'
            )
            color_idx += 1
        columns.append(
            f'<div class="is-kanban-col"><div class="is-kanban-head"><span>{esc(stage)}</span><span>{len(people)}</span></div>{"".join(cards)}</div>'
        )
    return '<div style="overflow-x:auto"><div class="is-kanban">' + "".join(columns) + '</div></div>'


def render() -> None:
    render_topbar()
    st.markdown(page_header("Outreach Operations", "Manage outreach, replies, samples, approvals, publishing and exception handling.", "Execution collaboration"), unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns([0.45, 0.18, 0.16, 0.21])
    with f1:
        st.caption("Workflow board · one source of truth for creator execution")
    with f2:
        st.selectbox("Market", ["All markets", "United States", "Mexico"], label_visibility="collapsed")
    with f3:
        st.button("Filter", use_container_width=True)
    with f4:
        st.button("+ Start outreach", type="primary", use_container_width=True)

    tabs = st.tabs(["Workflow board", "List view", "Calendar", "Analytics"])
    with tabs[0]:
        st.markdown(_kanban(), unsafe_allow_html=True)
    with tabs[1]:
        st.markdown('<div class="is-card is-card-pad"><div class="is-card-title">Execution list</div><div class="is-card-caption" style="margin-top:6px">The list view reuses the same campaign event model with owner, next action, due date and SLA status.</div></div>', unsafe_allow_html=True)
    with tabs[2]:
        st.markdown('<div class="is-grid-4">' + ''.join(f'<div class="is-card is-card-pad"><div class="is-card-title">May {day}</div><div class="is-card-caption" style="margin-top:6px">{title}</div></div>' for day,title in [(20,"Approve shortlist"),(21,"Brief review"),(22,"Mexico outreach"),(23,"Budget review")]) + '</div>', unsafe_allow_html=True)
    with tabs[3]:
        metrics = [("Reply SLA", "92%", "+4.2%"), ("Draft approval", "78%", "+9.0%"), ("Sample delivered", "84%", "+6.1%"), ("Publish on time", "71%", "+3.4%")]
        st.markdown('<div class="is-grid-4">' + ''.join(f'<div class="is-metric"><div class="is-metric-label">{l}</div><div class="is-metric-value">{v}</div><div class="is-metric-delta">{d}</div></div>' for l,v,d in metrics) + '</div>', unsafe_allow_html=True)

    render_demo_notice()
