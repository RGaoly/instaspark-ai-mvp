from __future__ import annotations

import streamlit as st

from components.html import avatar, badge, esc, mission_chip, page_header, scorebar
from components.shell import render_demo_notice, render_topbar
from components.state import ranking, save_decision


def _compare_grid(rows) -> str:
    creators = [row for _, row in rows.iterrows()]
    labels = [
        ("Audience geography", lambda r: f"{r['primary_market']} 62% · Other 38%"),
        ("Niche", lambda r: " · ".join(r["topics"][:3])),
        ("Avg views (last 10)", lambda r: f"{int(r['followers']*r['engagement_rate']/100*4)/1000:.0f}K"),
        ("Engagement rate", lambda r: f"{r['engagement_rate']:.1f}%"),
        ("Brand safety", lambda r: f"{r['brand_safety']:.0f}/100"),
        ("Estimated cost", lambda r: f"USD {int(r['estimated_cost_usd']):,}"),
        ("Predicted publish rate", lambda r: f"{int(45+r['commercial_fit']*.4)}%"),
        ("Predicted orders", lambda r: f"{int(r['total_score']*12):,}"),
        ("Recommended market", lambda r: r["primary_market"]),
    ]
    cells = [
        '<div class="is-compare-label is-compare-head">'
        '<b>3 creators selected</b><br/><small>Select up to 3 to compare</small></div>'
    ]
    for idx, r in enumerate(creators):
        fit = "High Fit" if idx == 0 else "Strong Fit" if r["total_score"] >= 80 else "Good Fit"
        tone = "blue" if idx == 0 else "green" if r["total_score"] >= 80 else "gray"
        cells.append(
            f'<div class="is-compare-head {"selected" if idx == 0 else ""}">'
            f'<div class="is-creator-cell">{avatar(r["creator_name"], idx)}'
            f'<span><b>{esc(r["creator_name"])}</b>'
            f'<div class="is-fit-row">{badge(fit, tone)}</div></span></div>'
            f'<div style="font-size:20px;font-weight:900;margin-top:8px;'
            f'color:{"#16A36A" if r["total_score"] >= 80 else "#F5A623"}">{r["total_score"]:.0f}'
            f'<small style="font-size:8px;color:#879198;font-weight:650"> /100</small></div></div>'
        )
    for label, getter in labels:
        cells.append(f'<div class="is-compare-label">{esc(label)}</div>')
        for r in creators:
            cells.append(f"<div>{esc(getter(r))}</div>")
    return '<div class="is-compare-grid">' + "".join(cells) + "</div>"


def _evidence_panel(creator) -> str:
    evidence = list(creator.get("evidence", [])[:3])
    while len(evidence) < 3:
        evidence.append("Representative content evidence available for review")
    tags = [
        ("POV", "Nature", "Travel"),
        ("Action", "Product", "Reveal"),
        ("Night", "City", "Lifestyle"),
    ]
    items = []
    for idx, item in enumerate(evidence):
        tag_html = "".join(f'<span class="is-evidence-tag">{esc(t)}</span>' for t in tags[idx])
        items.append(
            f'<div class="is-risk"><div class="is-video" style="width:96px;aspect-ratio:16/9;flex:0 0 96px;border-radius:8px"></div>'
            f'<div><b>{esc(item)}</b>'
            f'<div class="is-evidence-meta">{tag_html}<span class="is-evidence-tag">{42 + idx * 18}s</span></div>'
            f'<small style="margin-top:4px">Matched to X5 immersive storytelling brief</small></div></div>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head">'
        '<span class="is-panel-title">Evidence explorer</span>'
        '<span class="is-panel-link">View more content →</span></div>'
        f'<div class="is-panel-body">{"".join(items)}</div></div>'
    )


def _drivers_panel(creator) -> str:
    drivers = [
        ("Audience match", creator["audience_fit"], "28%"),
        ("Engagement quality", creator["momentum"], "18%"),
        ("Content relevance", creator["content_fit"], "24%"),
        ("Performance prediction", creator["commercial_fit"], "18%"),
        ("Brand safety", creator["brand_safety"], "12%"),
    ]
    rows = "".join(
        f'<div class="is-driver-row">{scorebar(label, score)}'
        f'<span class="is-weight-tag">w {weight}</span></div>'
        for label, score, weight in drivers
    )
    return (
        '<div class="is-card"><div class="is-panel-head">'
        '<span class="is-panel-title">Score drivers</span>'
        f'<span class="is-panel-link">{creator["total_score"]:.0f}/100</span></div>'
        f'<div class="is-panel-body">{rows}'
        f'<div style="display:flex;justify-content:flex-end;align-items:baseline;gap:4px;'
        f'margin-top:8px;font-size:22px;font-weight:900;color:#16A36A">{creator["total_score"]:.0f}'
        f'<small style="font-size:9px;color:#879198;font-weight:650">weighted total</small></div>'
        "</div></div>"
    )


def _risk_panel(creator) -> str:
    risks = list(creator.get("warnings", [])[:3])
    while len(risks) < 3:
        risks.append("Confirm availability and usage rights")
    levels = ["Medium", "Medium", "High"]
    rows = []
    for idx, risk in enumerate(risks):
        level = levels[idx]
        cls = " high" if level == "High" else ""
        badge_cls = "high" if level == "High" else "medium"
        rows.append(
            f'<div class="is-risk{cls}"><span class="is-risk-icon">!</span>'
            f'<span><b>{esc(risk)} <span class="is-risk-badge {badge_cls}">{level}</span></b>'
            f'<small>{"Escalate before outreach." if level == "High" else "Review before outreach."}</small></span></div>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head">'
        '<span class="is-panel-title">Potential risks</span>'
        f'{badge("2 Medium · 1 High", "orange")}</div>'
        f'<div class="is-panel-body">{"".join(rows)}</div></div>'
    )


def render() -> None:
    render_topbar()
    ranked = ranking()
    if ranked.empty:
        st.warning("No eligible creators available.")
        return

    head_l, head_r = st.columns([1, 0.28], vertical_alignment="top")
    with head_l:
        st.markdown(
            page_header(
                "Creator Compare",
                "Compare shortlisted creators and review rationale before approving outreach.",
                "Decision approval",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            mission_chip("Insta360 X5 Launch - Japan Active", light=True),
            unsafe_allow_html=True,
        )
    with head_r:
        st.button("Export", use_container_width=True)

    name_to_id = {row["creator_name"]: row["creator_id"] for _, row in ranked.head(10).iterrows()}
    default_names = [
        ranked[ranked["creator_id"] == cid].iloc[0]["creator_name"]
        for cid in st.session_state.compare_ids
        if not ranked[ranked["creator_id"] == cid].empty
    ][:3]
    if len(default_names) < 3:
        default_names = ranked.head(3)["creator_name"].tolist()
    selected_names = st.multiselect(
        "Creators to compare", list(name_to_id), default=default_names, max_selections=3
    )
    compare = ranked[ranked["creator_name"].isin(selected_names)].head(3)
    if compare.empty:
        compare = ranked.head(3)

    st.markdown(_compare_grid(compare), unsafe_allow_html=True)
    focus = compare.iloc[0]

    c1, c2, c3 = st.columns([1.05, 0.9, 0.68], gap="small", vertical_alignment="top")
    with c1:
        st.markdown(_evidence_panel(focus), unsafe_allow_html=True)
    with c2:
        st.markdown(_drivers_panel(focus), unsafe_allow_html=True)
    with c3:
        st.markdown(_risk_panel(focus), unsafe_allow_html=True)

    st.markdown(
        f'<div class="is-action-bar">'
        f'<div><b>Ready to take action on {esc(focus["creator_name"])}?</b>'
        f'<small>Evidence reviewed · score drivers weighted · risks flagged for operator judgment.</small></div>'
        f'<div class="is-action-bar-actions"></div></div>',
        unsafe_allow_html=True,
    )
    _, a, b, c = st.columns([1, 0.24, 0.22, 0.18])
    with a:
        if st.button("Approve Outreach", type="primary", use_container_width=True):
            save_decision(focus["creator_id"], "Approved", "Strong evidence and mission fit")
            st.success("Approved and moved to Outreach Operations.")
    with b:
        if st.button("Request Review", use_container_width=True):
            save_decision(focus["creator_id"], "Review", "Additional rights and availability checks")
            st.info("Review request logged.")
    with c:
        if st.button("Reject", use_container_width=True):
            save_decision(focus["creator_id"], "Rejected", "Risk or cost concern")
            st.warning("Rejection recorded with a reason code.")

    render_demo_notice()
