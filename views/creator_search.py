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
from components.positioning import live_lookup_caption, why_not_ttcm_html
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_context,
    active_context_label,
    attach_live_evidence,
    live_evidence_for,
    ranking,
    select_creator,
    selected_creator,
    transition_creator_state,
)
from components.ui import md
from src.audience import overlap_vs_cohort
from src.catalog_filters import filter_ranked_creators, unique_catalog_values
from src.domain import match_label, match_tier
from services.youtube_service import search_channels, youtube_status_label


def _render_catalog_filters(ranked) -> tuple[list[str], list[str], list[str]]:
    market_options = unique_catalog_values(ranked, "primary_market") or unique_catalog_values(ranked, "markets")
    language_options = unique_catalog_values(ranked, "languages")
    topic_options = unique_catalog_values(ranked, "topics")
    f1, f2, f3 = st.columns(3)
    markets = f1.multiselect(t("Market"), market_options, key="search_filter_markets")
    languages = f2.multiselect(t("Language"), language_options, key="search_filter_languages")
    topics = f3.multiselect(t("Topics"), topic_options, key="search_filter_topics")
    return markets, languages, topics


def _render_live_lookup(context: dict) -> None:
    default_query = (
        " ".join(context.get("target_topics") or [])
        or str(context.get("product") or "action camera")
    )
    with st.expander(f"{t('Live YouTube lookup')} · {t(youtube_status_label())}", expanded=False):
        md(why_not_ttcm_html(compact=True), unsafe_allow_html=True)
        st.caption(live_lookup_caption())
        query = st.text_input(t("YouTube query"), value=default_query, key="youtube_lookup_query")
        if st.button(t("Search YouTube"), use_container_width=True, key="youtube_lookup_go"):
            st.session_state["_youtube_lookup"] = search_channels(query)
        result = st.session_state.get("_youtube_lookup")
        if not result:
            return
        if result.get("error"):
            st.info(result["error"])
        for item in result.get("items") or []:
            cols = st.columns([0.46, 0.16, 0.16, 0.22], vertical_alignment="center")
            cols[0].markdown(f"**{item['title']}**")
            cols[1].caption(str(item.get("country") or "—"))
            subscribers = item.get("subscriber_count")
            cols[2].caption(f"{subscribers:,} subs" if subscribers else "Subs hidden")
            if cols[3].button(
                t("Attach as evidence"),
                key=f"yt_attach_{item['channel_id']}",
                disabled=writes_locked() or not st.session_state.get("selected_creator_id"),
            ):
                try:
                    attach_live_evidence(st.session_state.selected_creator_id, item)
                    st.toast(t("YouTube channel attached as evidence"))
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))


def _creator_table(ranked) -> str:
    headers = [
        "",
        "Creator",
        "Niche & market",
        "Followers",
        "Modeled est. views",
        "Eng. rate",
        "Mission fit",
        "Content fit",
        "Commercial",
        "Match score",
    ]
    head = "".join(f"<th>{h}</th>" for h in headers)
    rows = []
    for idx, row in ranked.iterrows():
        selected = row["creator_id"] == st.session_state.selected_creator_id
        name = row["creator_name"]
        topics = " · ".join(row["topics"][:2])
        tier = match_tier(row["total_score"])
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


def _detail_panel(creator: dict, context: dict, cohort: list[dict]) -> str:
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
        "Operator caveat",
    ]
    reason_html = "".join(
        '<div class="is-reason"><span class="is-reason-icon">✓</span>'
        f'<span><b>{esc(reason_labels[i])}</b><small>{esc(reason)}</small></span></div>'
        for i, reason in enumerate(reasons)
    )
    overlap = overlap_vs_cohort(creator, cohort)
    overlap_pct = round(overlap["mean_jaccard"] * 100)
    score = float(creator["total_score"])
    live_rows = live_evidence_for(creator["creator_id"])
    live_html = (
        "".join(
            f'<div class="is-reason"><span class="is-reason-icon">▶</span>'
            f'<span><b>{esc(item.get("title", "YouTube"))}</b>'
            f'<small>{esc(item.get("source", "youtube_data_api"))} · {esc(item.get("url", ""))}</small></span></div>'
            for item in live_rows[:3]
        )
        if live_rows
        else '<small style="color:#879198">No live YouTube evidence attached. Lookup is optional and labeled.</small>'
    )
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-profile-head">
          {avatar(creator['creator_name'], 2, 'profile')}
          <div>
            <div class="is-profile-name">{esc(creator['creator_name'])} {badge('Demo catalog','gray')}</div>
            <div class="is-socials">Instagram · TikTok · YouTube · {esc(creator.get('primary_market',''))}</div>
          </div>
          <div class="is-detail-score">
            {score_ring(score)}
            <span class="is-match-label">{esc(match_label(score))}</span>
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
        <div class="is-grid-2" style="margin-top:10px">
          <div class="is-lift-panel">
            <h4>Shortlist overlap</h4>
            <div class="is-donut" style="--pct:{overlap_pct};width:52px;height:52px"><span>{overlap_pct}%</span></div>
            <small style="font-size:7px;color:#879198;display:block;margin-top:6px">
            Mean Jaccard vs {overlap['peers']} shortlist peers · synthetic cohorts, not platform unique reach.
            Audience–mission fit (score driver) is {creator['audience_fit']:.0f}.</small>
          </div>
          <div class="is-lift-panel">
            <h4>Observed-input score components</h4>
            {scorebar('Content fit', creator['content_fit'], '#2577F1')}
            {scorebar('Momentum', creator['momentum'])}
            {scorebar('Commercial fit', creator['commercial_fit'], '#F5A623')}
          </div>
        </div>
        <div class="is-card-title" style="margin:10px 0 6px">Live platform evidence</div>
        {live_html}
      </div>
    </div>
    """


def render() -> None:
    render_topbar()
    context = active_context()
    ranked = ranking()

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
            st.button(
                t("Save Search"),
                use_container_width=True,
                disabled=True,
                help=t("Not wired in this demo"),
            )
        with b2:
            if st.button(t("Generate Brief"), type="primary", use_container_width=True):
                if not ranked.empty:
                    creator = selected_creator()
                    st.session_state.selected_creator_id = creator["creator_id"]
                    open_workspace_page("content-studio")
        md("</div>", unsafe_allow_html=True)

    _render_live_lookup(context)
    if ranked.empty:
        if context.get("entry_type") == "opportunity" and not context.get("mission_id"):
            st.warning(t("Link this Creator Opportunity to a Launch Mission before creating Match records."))
        else:
            st.warning(
                "No creators pass the active entry's gates. Adjust its market, budget, language, or safety threshold."
            )
        render_demo_notice()
        return

    md(
        nl_search_shell("Describe the creator profile you need — ranked against the active entry"),
        unsafe_allow_html=True,
    )
    query = st.text_input(
        t("Search creators"),
        value="",
        placeholder=t("Name, topic, style, or country"),
        label_visibility="collapsed",
        key="creator_nl_query",
    )
    st.caption(t("Filters the demo catalog; ranking stays mission-aware rules."))
    markets, languages, topics = _render_catalog_filters(ranked)
    visible = filter_ranked_creators(
        ranked,
        query=query,
        markets=markets,
        languages=languages,
        topics=topics,
    )
    if visible.empty:
        st.info(t("No creators in the demo catalog match these filters."))
        render_demo_notice()
        return

    options = {row["creator_name"]: row["creator_id"] for _, row in visible.iterrows()}
    toolbar_left, toolbar_mid, toolbar_right = st.columns([0.65, 0.2, 0.15], vertical_alignment="center")
    with toolbar_left:
        md(
            f'<div style="font-size:12px;color:#69757E;padding-top:6px">'
            f'{len(visible)} creators found · rule-based ranking · demo catalog · {ai_badge("Not an LLM ranker")}'
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
        st.button(
            t("Sort: Match score"),
            use_container_width=True,
            disabled=True,
            help=t("Results are already ranked by match score"),
        )

    main, aside = st.columns([1, 0.36], gap="small", vertical_alignment="top")
    with main:
        md(_creator_table(visible), unsafe_allow_html=True)
        st.caption(t("Mission fit is market + language. Overlap ≠ mission fit."))
    with aside:
        creator = selected_creator()
        shortlist_ids = list(st.session_state.get("shortlist_ids") or [])
        if not shortlist_ids:
            shortlist_ids = visible.head(3)["creator_id"].tolist()
        cohort = visible[visible["creator_id"].isin(shortlist_ids)].to_dict("records")
        if not cohort:
            cohort = visible.head(3).to_dict("records")
        md(_detail_panel(creator, context, cohort), unsafe_allow_html=True)
        a, b, c = st.columns(3)
        locked = writes_locked()
        render_write_guard()
        if a.button(t("Shortlist"), type="primary", use_container_width=True, disabled=locked):
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
            except (ValueError, PermissionError) as exc:
                st.info(str(exc))
        if b.button(t("Compare"), use_container_width=True):
            cid = creator["creator_id"]
            if cid not in st.session_state.compare_ids:
                st.session_state.compare_ids = (st.session_state.compare_ids + [cid])[-3:]
            open_workspace_page("creator-compare")
        if c.button(t("Generate brief"), use_container_width=True):
            st.session_state.selected_creator_id = creator["creator_id"]
            open_workspace_page("content-studio")

    render_demo_notice()
