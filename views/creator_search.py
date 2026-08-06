from __future__ import annotations

import streamlit as st

from components.html import (
    ai_badge,
    avatar,
    badge,
    dots,
    esc,
    mission_chip,
    nl_search_shell,
    page_header,
    score_ring,
    scorebar,
)
from components.shell import render_demo_notice, render_topbar
from components.state import ranking, select_creator, selected_creator


def _filters() -> str:
    filters = [
        ("Market", "US + Mexico", True),
        ("Platform", "YouTube · IG · TikTok", True),
        ("Followers", "100K – 1M", False),
        ("Avg views", "50K – 500K", False),
        ("Engagement", "≥ 2.5%", True),
        ("Language", "EN + ES", True),
        ("Commercial", "Open to collab", False),
        ("Risk level", "Low – Medium", False),
        ("Content style", "POV · Travel", True),
    ]
    chips = [
        f'<div class="is-filter-chip{" active" if active else ""}">{esc(label)}'
        f'<span class="is-chip-caret">⌄</span><b>{esc(value)}</b></div>'
        for label, value, active in filters
    ]
    chips.append('<div class="is-filter-chip" style="min-width:74px">More filters<b>＋</b></div>')
    return '<div class="is-filter-row">' + "".join(chips) + "</div>"


def _creator_table(ranked) -> str:
    headers = [
        "",
        "Creator",
        "Niche & market",
        "Followers",
        "Avg views",
        "Eng. rate",
        "Audience fit",
        "Content fit",
        "Commercial",
        "Match score",
    ]
    head = "".join(f"<th>{h}</th>" for h in headers)
    rows = []
    for idx, row in ranked.head(8).iterrows():
        selected = row["creator_id"] == st.session_state.selected_creator_id
        name = row["creator_name"]
        topics = " · ".join(row["topics"][:2])
        tier = (
            "Excellent"
            if row["total_score"] >= 85
            else "Very good"
            if row["total_score"] >= 78
            else "Good"
        )
        rows.append(
            f'<tr class="{"is-selected" if selected else ""}">'
            f'<td>{"●" if selected else "○"}</td>'
            f'<td><div class="is-creator-cell">{avatar(name, idx)}'
            f'<span><b>{esc(name)}</b><small>@{esc(name.lower().replace(" ", ""))}</small></span></div></td>'
            f'<td><b>{esc(topics or "Outdoor")}</b><br/>'
            f'<small style="color:#879198">{esc(row["primary_market"])}</small></td>'
            f'<td>{int(row["followers"]) / 1000:.0f}K</td>'
            f'<td>{int(row["followers"] * row["engagement_rate"] / 100 * 4) / 1000:.0f}K</td>'
            f'<td>{row["engagement_rate"]:.1f}%</td>'
            f'<td><b>{row["audience_fit"]:.1f}</b>{dots(row["audience_fit"])}</td>'
            f'<td><b>{row["content_fit"]:.1f}</b>{dots(row["content_fit"])}</td>'
            f'<td><b>{row["commercial_fit"]:.1f}</b>{dots(row["commercial_fit"])}</td>'
            f'<td><div style="display:flex;align-items:center;gap:5px">'
            f'{score_ring(row["total_score"])}'
            f'<small style="color:#16825D;font-weight:850">{tier}</small></div></td>'
            "</tr>"
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _detail_panel(creator: dict) -> str:
    reasons = list(creator.get("positives", [])[:4])
    defaults = [
        "Strong audience overlap with action-camera buyers",
        "Recent POV travel content matches X5 launch narrative",
        "Commercial readiness and brand safety above threshold",
        "Predicted performance lift vs category baseline",
    ]
    while len(reasons) < 4:
        reasons.append(defaults[len(reasons)])
    reason_labels = [
        "Audience–mission fit",
        "Content evidence",
        "Commercial readiness",
        "Predicted lift",
    ]
    reason_html = "".join(
        '<div class="is-reason"><span class="is-reason-icon">✓</span>'
        f'<span><b>{esc(reason_labels[i])}</b><small>{esc(reason)}</small></span></div>'
        for i, reason in enumerate(reasons)
    )
    score = float(creator["total_score"])
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-profile-head">
          {avatar(creator['creator_name'], 2, 'profile')}
          <div>
            <div class="is-profile-name">{esc(creator['creator_name'])} {badge('Verified','blue')}</div>
            <div class="is-socials">Instagram · TikTok · YouTube · {esc(creator.get('primary_market',''))}</div>
          </div>
          <div class="is-detail-score">
            {score_ring(score)}
            <span class="is-match-label">Excellent Match</span>
          </div>
        </div>
        <div class="is-tabs">
          <span class="is-tab active">Why recommended</span>
          <span class="is-tab">Audience</span>
          <span class="is-tab">Content style</span>
          <span class="is-tab">Risk</span>
        </div>
        <div class="is-card-title" style="margin-bottom:6px">Top reasons</div>
        {reason_html}
        <div class="is-card-title" style="margin:10px 0 6px">Example content evidence</div>
        <div class="is-video-row"><div class="is-video"></div><div class="is-video"></div><div class="is-video"></div></div>
        <div class="is-grid-2" style="margin-top:10px">
          <div class="is-lift-panel">
            <h4>Audience overlap</h4>
            <div class="is-donut" style="--pct:83;width:52px;height:52px"><span>83%</span></div>
            <small style="font-size:7px;color:#879198;display:block;margin-top:6px">US outdoor + travel cohort</small>
          </div>
          <div class="is-lift-panel">
            <h4>Estimated performance lift</h4>
            {scorebar('Views', 76, '#2577F1')}
            {scorebar('Engagement', 82)}
            {scorebar('Conversions', 68, '#F5A623')}
          </div>
        </div>
      </div>
    </div>
    """


def render() -> None:
    render_topbar()
    ranked = ranking()
    if ranked.empty:
        st.warning(
            "No creators pass the current mission gates. Adjust market, budget, or safety threshold on Launch Mission."
        )
        return

    head_l, head_r = st.columns([1, 0.42], vertical_alignment="top")
    with head_l:
        st.markdown(
            page_header(
                "Creator Search & Match",
                "Find creators whose content, audience and commercial readiness fit the launch mission.",
                "Creator discovery",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            mission_chip("Mission: Insta360 X5 / US + Mexico"),
            unsafe_allow_html=True,
        )
    with head_r:
        st.markdown('<div class="is-header-actions">', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        with b1:
            st.button("Save Search", use_container_width=True)
        with b2:
            if st.button("Generate Brief", type="primary", use_container_width=True):
                creator = selected_creator()
                st.session_state.selected_creator_id = creator["creator_id"]
                st.toast("Creator selected for Content Studio")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        nl_search_shell("Describe the creator profile you need — ranked against the active mission"),
        unsafe_allow_html=True,
    )
    query = st.text_input(
        "Search creators",
        value="Find mid-tier creators for cycling, surfing and travel who can demonstrate immersive POV storytelling",
        label_visibility="collapsed",
        key="creator_nl_query",
    )
    _ = query  # keep widget wired for demo interaction; ranking stays mission-aware
    st.markdown(_filters(), unsafe_allow_html=True)

    options = {row["creator_name"]: row["creator_id"] for _, row in ranked.head(10).iterrows()}
    toolbar_left, toolbar_mid, toolbar_right = st.columns([0.65, 0.2, 0.15], vertical_alignment="center")
    with toolbar_left:
        st.markdown(
            f'<div style="font-size:12px;color:#69757E;padding-top:6px">'
            f'{min(8, len(ranked))} creators found · mission-aware ranking · {ai_badge("Ranked by InstaSpark AI")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with toolbar_mid:
        selected_name = st.selectbox("Inspect creator", list(options), label_visibility="collapsed")
        select_creator(options[selected_name])
    with toolbar_right:
        st.button("Sort: Match score", use_container_width=True)

    main, aside = st.columns([1, 0.36], gap="small", vertical_alignment="top")
    with main:
        st.markdown(_creator_table(ranked), unsafe_allow_html=True)
    with aside:
        creator = selected_creator()
        st.markdown(_detail_panel(creator), unsafe_allow_html=True)
        a, b, c = st.columns(3)
        if a.button("Shortlist", type="primary", use_container_width=True):
            cid = creator["creator_id"]
            if cid not in st.session_state.shortlist_ids:
                st.session_state.shortlist_ids.append(cid)
            st.toast("Added to shortlist")
        if b.button("Compare", use_container_width=True):
            cid = creator["creator_id"]
            if cid not in st.session_state.compare_ids:
                st.session_state.compare_ids = (st.session_state.compare_ids + [cid])[-3:]
            st.toast("Added to compare set")
        if c.button("Generate brief", use_container_width=True):
            st.session_state.selected_creator_id = creator["creator_id"]
            st.toast("Creator selected for Content Studio")

    render_demo_notice()
