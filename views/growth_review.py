from __future__ import annotations

import streamlit as st

from components.data import GROWTH_KPIS
from components.html import esc, mission_chip, page_header, pct_width
from components.shell import render_demo_notice, render_topbar


def _kpi_strip() -> str:
    cards = []
    for label, value, note in GROWTH_KPIS:
        cards.append(
            '<div class="is-kpi-mini">'
            f'<label>{esc(label)}</label><strong>{esc(value)}</strong><small>{esc(note)}</small>'
            "</div>"
        )
    cards.append(
        '<div class="is-kpi-mini has-donut">'
        "<div>"
        "<label>Budget utilization</label>"
        "<strong>78%</strong>"
        "<small>$56.5K / $64K</small>"
        "</div>"
        '<div class="is-mini-donut" style="--pct:78"><span>78</span></div>'
        "</div>"
    )
    return '<div class="is-kpi-strip">' + "".join(cards) + "</div>"


def _funnel() -> str:
    steps = [
        ("Candidate pool", "30"),
        ("Matched", "10"),
        ("Contacted", "6"),
        ("Published", "2"),
        ("Attributed orders", "342"),
    ]
    return (
        '<div class="is-funnel">'
        + "".join(
            f'<div class="is-funnel-step"><div class="is-funnel-shape"></div>'
            f"<b>{esc(name)}</b><small>{esc(value)}</small></div>"
            for name, value in steps
        )
        + "</div>"
    )


def _bar_chart() -> str:
    groups = [
        ("Travel", 112, 92),
        ("Adventure", 82, 72),
        ("Tech", 58, 64),
        ("Lifestyle", 46, 54),
        ("Micro", 34, 38),
    ]
    max_value = max(max(a, b) for _, a, b in groups)
    html = []
    for label, revenue, roi in groups:
        html.append(
            '<div class="is-bar-group">'
            f'<div class="is-bar blue" style="height:{pct_width(revenue, max_value)}%"></div>'
            f'<div class="is-bar green" style="height:{pct_width(roi, max_value)}%"></div>'
            f'<span class="is-bar-label">{esc(label)}</span></div>'
        )
    return '<div class="is-bar-chart">' + "".join(html) + "</div>"


def _market_table() -> str:
    rows = [
        ("🇺🇸 US", "$280,000", "$200,172", "128", "2,164", "$258,410", "5.2x"),
        ("🇲🇽 Mexico", "$120,000", "$90,432", "72", "1,136", "$116,340", "4.0x"),
        ("🇯🇵 Japan", "$80,000", "$59,262", "57", "492", "$106,340", "3.6x"),
    ]
    head = "".join(f"<th>{h}</th>" for h in ["Market", "Budget", "Spent", "Published", "Orders", "Revenue", "ROI"])
    body = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows)
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _content_table() -> str:
    rows = [
        ("POV action & stunts", "3.2M", "4.8%", "$161K", "6.1x"),
        ("Trip cameras", "2.6M", "5.4%", "$113K", "4.3x"),
        ("AI edit & hyperlapse", "2.1M", "4.1%", "$93K", "4.1x"),
        ("Tech reviews", "1.8M", "3.6%", "$72K", "3.2x"),
    ]
    head = "".join(f"<th>{h}</th>" for h in ["Content angle", "Views", "Eng. rate", "Revenue", "ROI"])
    body = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows)
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _attribution_donut() -> str:
    return """
    <div style="display:grid;grid-template-columns:110px 1fr;gap:12px;align-items:center">
      <div class="is-donut" style="--pct:78;width:105px;height:105px;background:conic-gradient(#2577F1 0 45%,#16A36A 45% 67%,#7B61FF 67% 87%,#62C6C9 87% 100%)">
        <span style="font-size:12px;text-align:center">3,842<br/><small style="font-size:6px">orders</small></span>
      </div>
      <div class="is-card-caption">
        ● Affiliate link 45.3%<br/><br/>
        ● Coupon codes 21.9%<br/><br/>
        ● Product page assisted 19.9%<br/><br/>
        ● View-through lift 12.8%
      </div>
    </div>
    """


def _budget_actions() -> str:
    actions = [
        ("green", "Increase", "Increase US travel creators", "Highest ROI cohort at 5.2x and strong order quality.", "+$64K revenue"),
        ("orange", "Reduce", "Reduce low-publish cohorts", "Low publish rate and rising coordination cost.", "-$34K spend"),
        ("blue", "Replicate", "Replicate Mexico POV angle", "Action content drives high ROI in Mexico.", "+$30K revenue"),
        ("", "Custom", "Create custom action", "Build a new budget action from operator strategy.", "Human review"),
    ]
    return (
        '<div class="is-budget-actions">'
        + "".join(
            f'<div class="is-action-card {tone}">'
            f'<div style="margin-bottom:5px"><span class="is-badge is-badge-{"green" if tone=="green" else "orange" if tone=="orange" else "blue" if tone=="blue" else "gray"}">{esc(tag)}</span></div>'
            f"<h4>{esc(title)}</h4><p>{esc(body)}</p>"
            f'<div class="is-action-impact">{esc(impact)} →</div></div>'
            for tone, tag, title, body, impact in actions
        )
        + "</div>"
    )


def render() -> None:
    render_topbar()
    st.markdown(
        page_header(
            "Growth Review",
            "Validate creator marketing outcomes and guide budget allocation.",
            "Outcome learning",
            "blue",
        ),
        unsafe_allow_html=True,
    )

    controls = st.columns([0.38, 0.22, 0.2, 0.1, 0.1], vertical_alignment="center")
    with controls[0]:
        st.markdown(
            mission_chip("Mission: Insta360 X5 AntiGravity AI Launch"),
            unsafe_allow_html=True,
        )
    controls[1].selectbox(
        "Period",
        ["May 1 - May 31, 2026", "Apr 1 - Apr 30, 2026", "Q1 2026"],
        label_visibility="collapsed",
    )
    controls[2].selectbox(
        "Market",
        ["All markets", "United States", "Mexico", "Japan"],
        label_visibility="collapsed",
    )
    controls[3].button("Export", use_container_width=True)
    controls[4].button("Filters", use_container_width=True)

    st.markdown(_kpi_strip(), unsafe_allow_html=True)

    r1c1, r1c2 = st.columns([0.42, 0.58], gap="small")
    with r1c1:
        st.markdown(
            '<div class="is-chart"><div class="is-chart-title">Creator funnel</div>'
            + _funnel()
            + "</div>",
            unsafe_allow_html=True,
        )
    with r1c2:
        st.markdown(
            '<div class="is-chart"><div class="is-chart-title">Creator cohort performance &nbsp; '
            '<span style="color:#2577F1">■ Revenue</span> '
            '<span style="color:#16A36A">■ ROI</span></div>'
            + _bar_chart()
            + "</div>",
            unsafe_allow_html=True,
        )

    r2c1, r2c2, r2c3 = st.columns([0.34, 0.34, 0.32], gap="small")
    with r2c1:
        st.markdown(
            '<div class="is-card"><div class="is-panel-head">'
            '<span class="is-panel-title">Market performance</span>'
            '<span class="is-panel-link">View all →</span></div>'
            f'<div class="is-panel-body">{_market_table()}</div></div>',
            unsafe_allow_html=True,
        )
    with r2c2:
        st.markdown(
            '<div class="is-card"><div class="is-panel-head">'
            '<span class="is-panel-title">Content breakdown</span>'
            '<span class="is-panel-link">View all →</span></div>'
            f'<div class="is-panel-body">{_content_table()}</div></div>',
            unsafe_allow_html=True,
        )
    with r2c3:
        st.markdown(
            '<div class="is-card"><div class="is-panel-head">'
            '<span class="is-panel-title">Attribution breakdown</span></div>'
            f'<div class="is-panel-body">{_attribution_donut()}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Budget actions · Next best action</span>'
        '<span class="is-panel-link">Human approval required</span></div>'
        f'<div class="is-panel-body">{_budget_actions()}</div></div>',
        unsafe_allow_html=True,
    )

    render_demo_notice()
