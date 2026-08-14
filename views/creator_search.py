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
from components.i18n import t
from components.shell import render_demo_notice, render_topbar
from components.state import (
    active_context,
    active_context_label,
    ranking,
    select_creator,
    selected_creator,
    transition_creator_state,
)
from components.ui import md


def _filters(context: dict) -> str:
    market = context.get("market", "Any market")
    language = context.get("language", "Any language")
    topics = " · ".join(context.get("target_topics", [])[:2]) or "Any topic"
    styles = " · ".join(context.get("target_styles", [])[:2]) or "Any style"
    filters = [
        ("Market", market, True),
        ("Platform", "YouTube · IG · TikTok", True),
        ("Followers", "100K – 1M", False),
        ("Avg views", "50K – 500K", False),
        ("Engagement", "≥ 2.5%", True),
        ("Language", language, True),
        ("Commercial", "Open to collab", False),
        ("Risk level", "Low – Medium", False),
        ("Topics", topics, True),
        ("Content style", styles, True),
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


def _detail_panel(creator: dict, context: dict) -> str:
    reasons = list(creator.get("positives", [])[:4])
    defaults = [
        "Eligible under the active entry's hard gates",
        "Evidence requires operator verification before outreach",
        "Commercial terms require direct confirmation",
        "No outcome prediction is treated as observed performance",
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
            <div class="is-donut" style="--pct:{creator['audience_fit']:.0f};width:52px;height:52px"><span>{creator['audience_fit']:.0f}%</span></div>
            <small style="font-size:7px;color:#879198;display:block;margin-top:6px">{esc(context.get('market', 'Target market'))} audience cohort</small>
          </div>
          <div class="is-lift-panel">
            <h4>Observed-input score components</h4>
            {scorebar('Content fit', creator['content_fit'], '#2577F1')}
            {scorebar('Momentum', creator['momentum'])}
            {scorebar('Commercial fit', creator['commercial_fit'], '#F5A623')}
          </div>
        </div>
      </div>
    </div>
    """


def render() -> None:
    render_topbar()
    context = active_context()
    ranked = ranking()
    if ranked.empty:
        if context.get("entry_type") == "opportunity" and not context.get("mission_id"):
            st.warning("Link this Creator Opportunity to a Launch Mission before creating Match records.")
        else:
            st.warning(
                "No creators pass the active entry's gates. Adjust its market, budget, language, or safety threshold."
            )
        return

    head_l, head_r = st.columns([1, 0.42], vertical_alignment="top")
    with head_l:
        md(
            page_header(
                "Creator Search & Match",
                "Find creators whose content, audience and commercial readiness fit the active entry.",
                "Creator discovery",
            ),
            unsafe_allow_html=True,
        )
        md(
            mission_chip(active_context_label()),
            unsafe_allow_html=True,
        )
    with head_r:
        md('<div class="is-header-actions">', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        with b1:
            st.button(t("Save Search"), use_container_width=True)
        with b2:
            if st.button(t("Generate Brief"), type="primary", use_container_width=True):
                creator = selected_creator()
                st.session_state.selected_creator_id = creator["creator_id"]
                st.toast(t("Creator selected for Content Studio"))
        md("</div>", unsafe_allow_html=True)

    md(
        nl_search_shell("Describe the creator profile you need — ranked against the active entry"),
        unsafe_allow_html=True,
    )
    query = st.text_input(
        t("Search creators"),
        value=(
            f"Find creators in {context.get('market', 'the target market')} for "
            f"{', '.join(context.get('target_topics', [])) or 'the active opportunity'}"
        ),
        label_visibility="collapsed",
        key="creator_nl_query",
    )
    _ = query  # keep widget wired for demo interaction; ranking stays mission-aware
    md(_filters(context), unsafe_allow_html=True)

    options = {row["creator_name"]: row["creator_id"] for _, row in ranked.head(10).iterrows()}
    toolbar_left, toolbar_mid, toolbar_right = st.columns([0.65, 0.2, 0.15], vertical_alignment="center")
    with toolbar_left:
        md(
            f'<div style="font-size:12px;color:#69757E;padding-top:6px">'
            f'{min(8, len(ranked))} creators found · context-aware ranking · {ai_badge("Ranked by InstaSpark AI")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with toolbar_mid:
        option_names = list(options)
        selected_id = st.session_state.get("selected_creator_id")
        preferred_name = next(
            (name for name, creator_id in options.items() if creator_id == selected_id),
            option_names[0],
        )
        selected_name = st.selectbox(
            t("Inspect creator"),
            option_names,
            index=option_names.index(preferred_name),
            label_visibility="collapsed",
        )
        select_creator(options[selected_name])
    with toolbar_right:
        st.button(t("Sort: Match score"), use_container_width=True)

    main, aside = st.columns([1, 0.36], gap="small", vertical_alignment="top")
    with main:
        md(_creator_table(ranked), unsafe_allow_html=True)
    with aside:
        creator = selected_creator()
        md(_detail_panel(creator, context), unsafe_allow_html=True)
        a, b, c = st.columns(3)
        if a.button(t("Shortlist"), type="primary", use_container_width=True):
            cid = creator["creator_id"]
            try:
                transition_creator_state(
                    cid,
                    "shortlisted",
                    actor="Olivia Chen",
                    reason="Operator shortlisted from Search & Match",
                    evidence=list(creator.get("evidence", [])[:2]),
                )
                st.toast(t("Added to shortlist with an audit event"))
            except ValueError as exc:
                st.info(str(exc))
        if b.button(t("Compare"), use_container_width=True):
            cid = creator["creator_id"]
            if cid not in st.session_state.compare_ids:
                st.session_state.compare_ids = (st.session_state.compare_ids + [cid])[-3:]
            st.toast(t("Added to compare set"))
        if c.button(t("Generate brief"), use_container_width=True):
            st.session_state.selected_creator_id = creator["creator_id"]
            st.toast(t("Creator selected for Content Studio"))

    render_demo_notice()
