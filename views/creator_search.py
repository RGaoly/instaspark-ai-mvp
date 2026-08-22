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
    next_outreach_action_page,
    prepare_next_action_jump,
    ranking,
    select_creator,
    selected_creator,
    transition_creator_state,
)
from components.ui import labels, md
from src.audience import overlap_vs_cohort
from src.catalog_filters import filter_ranked_creators, unique_catalog_values
from src.domain import declared_platforms, match_label, match_tier
from src.scoring import additive_driver_display, mix_driver_display
from services.youtube_service import search_channels, youtube_status_label
from views.content_studio import _catalog_join


def search_cta_page(creator_id: str) -> str | None:
    """Jump target for Search. Same rules as Outreach; do not fork them."""

    return next_outreach_action_page(creator_id)


def _platform_line(creator: dict, live_rows: list) -> str:
    platforms = declared_platforms(creator, live_rows)
    market = str(creator.get("primary_market") or "").strip()
    bits = list(platforms) if platforms else [t("No platform fields in the demo catalog")]
    if market:
        bits.append(market)
    return " · ".join(bits)


def open_search_cta(creator_id: str, *, creator_name: str | None = None) -> str | None:
    """Prefill the creator and open Growth Review or Content Studio when that is the next action."""

    page = prepare_next_action_jump(creator_id, creator_name=creator_name)
    if page == "growth-review":
        open_workspace_page("growth-review")
    elif page == "content-studio":
        open_workspace_page("content-studio")
    return page


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
    open_lookup = bool(st.session_state.pop("search_youtube_open", False))
    with st.expander(f"{t('Live YouTube lookup')} · {t(youtube_status_label())}", expanded=open_lookup):
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
        "Topic overlap",
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
        mission_fit = float(row.get("mission_fit", row.get("audience_fit", 0)))
        topic_overlap = float(row.get("topic_overlap", row.get("content_fit", 0)))
        live_chip = (
            f'<div style="margin-top:2px">{badge("Live YouTube evidence attached", "green")}</div>'
            if float(row.get("live_proof_bonus") or 0) > 0
            else ""
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
            f'<td><b>{mission_fit:.1f}</b>{dots(mission_fit)}</td>'
            f'<td><b>{topic_overlap:.1f}</b>{dots(topic_overlap)}</td>'
            f'<td><b>{row["commercial_fit"]:.1f}</b>{dots(row["commercial_fit"])}</td>'
            f'<td><div style="display:flex;align-items:center;gap:5px">'
            f'{score_ring(row["total_score"])}'
            f'<small style="color:#16825D;font-weight:850">{tier}</small></div>{live_chip}</td>'
            "</tr>"
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _scored_reasons(creator: dict) -> list[str]:
    return [str(item).strip() for item in list(creator.get("positives") or []) if str(item).strip()]


def _catalog_risks(creator: dict) -> list[str]:
    raw = creator.get("warnings")
    if raw is None:
        raw = creator.get("risks")
    return [str(item).strip() for item in list(raw or []) if str(item).strip()]


def _live_evidence_html(live_rows: list) -> str:
    if live_rows:
        return "".join(
            f'<div class="is-reason"><span class="is-reason-icon">▶</span>'
            f'<span><b>{esc(item.get("title", "YouTube"))}</b>'
            f'<small>{esc(item.get("source", "youtube_data_api"))} · {esc(item.get("url", ""))}</small></span></div>'
            for item in live_rows[:3]
        )
    return (
        '<small style="color:#879198">'
        "No live YouTube evidence attached. Lookup is optional and labeled."
        "</small>"
    )


def _detail_header_html(creator: dict, live_rows: list) -> str:
    score = float(creator["total_score"])
    live_chip = (
        badge("Live YouTube evidence attached", "green")
        if live_rows or float(creator.get("live_proof_bonus") or 0) > 0
        else ""
    )
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-profile-head">
          {avatar(creator['creator_name'], 2, 'profile')}
          <div>
            <div class="is-profile-name">{esc(creator['creator_name'])} {badge('Demo catalog','gray')} {live_chip}</div>
            <div class="is-socials">{esc(_platform_line(creator, live_rows))}</div>
          </div>
          <div class="is-detail-score">
            {score_ring(score)}
            <span class="is-match-label">{esc(match_label(score))}</span>
          </div>
        </div>
      </div>
    </div>
    """


def _why_recommended_html(creator: dict, live_rows: list) -> str:
    reasons = _scored_reasons(creator)
    if reasons:
        reason_html = "".join(
            '<div class="is-reason"><span class="is-reason-icon">✓</span>'
            f"<span><b>{esc(reason)}</b></span></div>"
            for reason in reasons[:6]
        )
    else:
        reason_html = (
            '<div class="is-reason"><span class="is-reason-icon">·</span>'
            "<span><b>No scored reasons for this creator.</b>"
            "<small>Score drivers below still come from the rule-based mix.</small></span></div>"
        )
    mix_html = "".join(
        f'<div class="is-driver-row">{scorebar(label, value)}'
        f'<span class="is-weight-tag">{esc(weight)}</span></div>'
        for label, value, weight in mix_driver_display(creator)
    )
    additive_html = "".join(
        f'<div class="is-driver-row"><label>{esc(label)}</label>'
        f'<span>+{value:.1f}</span><span class="is-weight-tag">{esc(note)}</span></div>'
        for label, value, note in additive_driver_display(creator)
    )
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-card-title" style="margin-bottom:6px">Top reasons</div>
        {reason_html}
        <div class="is-card-title" style="margin:10px 0 6px">Score drivers</div>
        {mix_html}
        {additive_html}
        <div class="is-card-title" style="margin:10px 0 6px">Live platform evidence</div>
        {_live_evidence_html(live_rows)}
      </div>
    </div>
    """


def _audience_html(creator: dict, cohort: list[dict]) -> str:
    overlap = overlap_vs_cohort(creator, cohort)
    overlap_pct = round(overlap["mean_jaccard"] * 100)
    mission_fit = float(creator.get("mission_fit") or creator.get("audience_fit") or 0)
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-lift-panel">
          <h4>Shortlist overlap</h4>
          <div class="is-donut" style="--pct:{overlap_pct};width:52px;height:52px"><span>{overlap_pct}%</span></div>
          <small style="font-size:7px;color:#879198;display:block;margin-top:6px">
          {overlap['peers']} shortlist peers · synthetic cohorts, not platform unique reach.</small>
        </div>
        <div class="is-lift-panel" style="margin-top:10px">
          <h4>Mission fit</h4>
          <div class="is-donut" style="--pct:{mission_fit:.0f};width:52px;height:52px"><span>{mission_fit:.0f}</span></div>
          <small style="font-size:7px;color:#879198;display:block;margin-top:6px">
          Market + language mix driver already used in ranking.</small>
        </div>
      </div>
    </div>
    """


def _content_style_html(creator: dict) -> str:
    styles = esc(_catalog_join(creator.get("styles")))
    topics = esc(_catalog_join(creator.get("topics")))
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-card-title" style="margin-bottom:6px">Content style</div>
        <p>{styles}</p>
        <div class="is-card-title" style="margin:10px 0 6px">Topics</div>
        <p>{topics}</p>
        <small style="color:#879198">Same catalog fields as Content Studio.</small>
      </div>
    </div>
    """


def _risk_html(creator: dict) -> str:
    risks = _catalog_risks(creator)
    if not risks:
        body = (
            '<div class="is-risk"><span><b>No catalog warnings for this creator.</b>'
            "<small>Operator review is still required before outreach.</small></span></div>"
        )
    else:
        body = "".join(
            '<div class="is-risk"><span class="is-risk-icon">!</span>'
            f"<span><b>{esc(risk)}</b></span></div>"
            for risk in risks
        )
    return f"""
    <div class="is-card">
      <div class="is-panel-body">
        <div class="is-card-title" style="margin-bottom:6px">Potential risks</div>
        {body}
      </div>
    </div>
    """


def _render_detail_aside(creator: dict, cohort: list[dict]) -> None:
    live_rows = live_evidence_for(creator["creator_id"])
    md(_detail_header_html(creator, live_rows), unsafe_allow_html=True)
    why_tab, audience_tab, style_tab, risk_tab = st.tabs(
        labels(["Why recommended", "Audience", "Content style", "Risk"])
    )
    with why_tab:
        md(_why_recommended_html(creator, live_rows), unsafe_allow_html=True)
    with audience_tab:
        md(_audience_html(creator, cohort), unsafe_allow_html=True)
    with style_tab:
        md(_content_style_html(creator), unsafe_allow_html=True)
    with risk_tab:
        md(_risk_html(creator), unsafe_allow_html=True)


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
            nl_search_shell("Lexical filter + small boost against the demo catalog — not semantic search"),
            unsafe_allow_html=True,
        )
    query = st.text_input(
        t("Search creators"),
        value="",
        placeholder=t("Name, topic, style, or country"),
        label_visibility="collapsed",
        key="creator_nl_query",
    )
    st.caption(t("NL query is a lexical filter + small boost, not semantic search."))
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
            f'{len(visible)} creators found · rule-based ranking · not LLM / embeddings · demo catalog · {ai_badge("Not an LLM ranker")}'
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
        st.caption(
            t("Mission fit is market + language. Topic overlap is Jaccard. Ranking is rule-based, not LLM.")
        )
    with aside:
        creator = selected_creator()
        shortlist_ids = list(st.session_state.get("shortlist_ids") or [])
        if not shortlist_ids:
            shortlist_ids = visible.head(3)["creator_id"].tolist()
        cohort = visible[visible["creator_id"].isin(shortlist_ids)].to_dict("records")
        if not cohort:
            cohort = visible.head(3).to_dict("records")
        _render_detail_aside(creator, cohort)
        jump_page = search_cta_page(creator["creator_id"])
        if jump_page:
            jump_label = (
                t("Record a conversion on Growth Review")
                if jump_page == "growth-review"
                else t("Create a brief in Content Studio")
            )
            if st.button(
                jump_label,
                type="primary",
                use_container_width=True,
                key="search_next_action",
            ):
                open_search_cta(creator["creator_id"], creator_name=creator.get("creator_name"))
        a, b, c = st.columns(3)
        locked = writes_locked()
        render_write_guard()
        if a.button(
            t("Shortlist"),
            type="primary" if not jump_page else "secondary",
            use_container_width=True,
            disabled=locked,
        ):
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
