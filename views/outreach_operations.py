from __future__ import annotations

import streamlit as st

from components.data import OUTREACH_COLUMNS
from components.html import avatar, badge, esc, page_header
from components.shell import render_demo_notice, render_topbar


STAGE_TONES = {
    "Shortlisted": "gray",
    "Contact Drafted": "blue",
    "Outreach Sent": "yellow",
    "Replied": "green",
    "Negotiating": "orange",
}


def _kanban() -> str:
    columns = []
    color_idx = 0
    for stage, people in OUTREACH_COLUMNS.items():
        cards = []
        for person in people:
            name, niche, market, followers, next_action = person
            cards.append(
                '<div class="is-kanban-card">'
                f'<div class="is-kanban-person">{avatar(name, color_idx)}'
                f'<span><b>{esc(name)}</b><small>@{esc(name.lower().replace(" ", ""))}</small></span></div>'
                f'<div class="is-kanban-tags">{badge(niche, "gray")} {badge(market, "blue")}</div>'
                f'<div class="is-kanban-meta">'
                f'<span>Market</span><strong>{esc(market)}</strong>'
                f'<span>Niche</span><strong>{esc(niche)}</strong>'
                f'<span>Audience</span><strong>{esc(followers)}</strong>'
                f'</div>'
                f'<div class="is-kanban-next">{esc(next_action)} →</div>'
                "</div>"
            )
            color_idx += 1
        tone = STAGE_TONES.get(stage, "gray")
        columns.append(
            f'<div class="is-kanban-col">'
            f'<div class="is-kanban-head">'
            f'<span style="display:flex;align-items:center;gap:6px">{esc(stage)} {badge(stage.split()[0], tone)}</span>'
            f'<span class="is-kanban-count">{len(people)}</span></div>'
            f'{"".join(cards)}</div>'
        )
    return '<div style="overflow-x:auto"><div class="is-kanban">' + "".join(columns) + "</div></div>"


def _list_view() -> str:
    rows = []
    for stage, people in OUTREACH_COLUMNS.items():
        for name, niche, market, followers, next_action in people:
            rows.append(
                "<tr>"
                f"<td><div class=\"is-creator-cell\">{avatar(name, len(rows))}"
                f"<span><b>{esc(name)}</b><small>{esc(niche)}</small></span></div></td>"
                f"<td>{esc(stage)}</td>"
                f"<td>{esc(market)}</td>"
                f"<td>{esc(followers)}</td>"
                f"<td><span class=\"is-panel-link\">{esc(next_action)} →</span></td>"
                "</tr>"
            )
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Stage", "Market", "Audience", "Next action"])
    return (
        f'<div class="is-card is-card-pad"><table class="is-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def render() -> None:
    render_topbar()

    head_l, head_r = st.columns([1, 0.22], vertical_alignment="top")
    with head_l:
        st.markdown(
            page_header(
                "Outreach Operations",
                "Manage outreach, replies, samples, approvals, publishing and exception handling.",
                "Execution collaboration",
            ),
            unsafe_allow_html=True,
        )
    with head_r:
        st.button("+ Start outreach", type="primary", use_container_width=True)

    f1, f2, f3 = st.columns([0.55, 0.25, 0.2], vertical_alignment="center")
    with f1:
        st.markdown(
            '<div class="is-view-tabs">'
            '<span class="is-view-tab active">Workflow Board</span>'
            '<span class="is-view-tab">List</span>'
            '<span class="is-view-tab">Calendar</span>'
            '<span class="is-view-tab">Analytics</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    with f2:
        st.selectbox(
            "Market",
            ["All markets", "United States", "Mexico", "Japan"],
            label_visibility="collapsed",
        )
    with f3:
        st.button("Filter", use_container_width=True)

    tabs = st.tabs(["Workflow Board", "List", "Calendar", "Analytics"])
    with tabs[0]:
        st.markdown(_kanban(), unsafe_allow_html=True)
    with tabs[1]:
        st.markdown(_list_view(), unsafe_allow_html=True)
    with tabs[2]:
        events = [
            (20, "Approve shortlist", "US · 11:00"),
            (21, "Brief review", "Ops · 14:00"),
            (22, "Mexico outreach", "LATAM · 10:30"),
            (23, "Budget review", "Finance · 13:30"),
        ]
        st.markdown(
            '<div class="is-grid-4">'
            + "".join(
                f'<div class="is-card is-card-pad"><div class="is-card-title">May {day}</div>'
                f'<div class="is-card-caption" style="margin-top:6px"><b>{esc(title)}</b><br/>{esc(note)}</div></div>'
                for day, title, note in events
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    with tabs[3]:
        metrics = [
            ("Reply SLA", "92%", "+4.2%"),
            ("Draft approval", "78%", "+9.0%"),
            ("Sample delivered", "84%", "+6.1%"),
            ("Publish on time", "71%", "+3.4%"),
        ]
        st.markdown(
            '<div class="is-grid-4">'
            + "".join(
                f'<div class="is-metric"><div class="is-metric-label">{esc(l)}</div>'
                f'<div class="is-metric-value">{esc(v)}</div>'
                f'<div class="is-metric-delta">{esc(d)}</div></div>'
                for l, v, d in metrics
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    render_demo_notice()
