from __future__ import annotations

import streamlit as st

from components.html import avatar, badge, esc, mission_chip, page_header, scorebar
from components.i18n import t
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_context,
    active_context_label,
    creator_state,
    live_evidence_for,
    next_outreach_action_page,
    prepare_next_action_jump,
    ranking,
    save_decision,
    select_creator,
    transition_creator_state,
)
from components.ui import md
from src.audience import overlap_vs_cohort, shortlist_overlap_report
from src.domain import match_fit_label, match_tier
from src.scoring import additive_driver_display, mix_driver_display


def compare_cta_page(creator_id: str) -> str | None:
    """Jump target for Compare. Same rules as Outreach; do not fork them."""

    return next_outreach_action_page(creator_id)


def open_compare_cta(creator_id: str, *, creator_name: str | None = None) -> str | None:
    """Prefill the creator and open Growth Review or Content Studio when that is the next action."""

    page = prepare_next_action_jump(creator_id, creator_name=creator_name)
    if page == "growth-review":
        open_workspace_page("growth-review")
    elif page == "content-studio":
        open_workspace_page("content-studio")
    return page


def _geo_split(row) -> str:
    markets = list(row.get("markets") or [row.get("primary_market")])
    markets = [str(item) for item in markets if str(item).strip()]
    if not markets:
        return "Not declared · demo catalog"
    if len(markets) == 1:
        return f"{markets[0]} 100% · modeled demo split"
    share = 100 // len(markets)
    remainder = 100 - share * len(markets)
    parts = []
    for idx, market in enumerate(markets):
        pct = share + (remainder if idx == 0 else 0)
        parts.append(f"{market} {pct}%")
    return " · ".join(parts) + " · modeled demo split"


def _overlap_panel(report: dict, focus: dict) -> str:
    vs = overlap_vs_cohort(focus, report.get("_rows") or [])
    pair_html = "".join(
        f'<div class="is-check"><i>{int(item["jaccard"] * 100)}</i>'
        f'{esc(item["left_name"])} × {esc(item["right_name"])} · Jaccard {item["jaccard"]:.0%}</div>'
        for item in report.get("pairwise", [])
    ) or '<div class="is-check"><i>—</i>Need two or more creators to compute overlap.</div>'
    lift_html = "".join(
        f'<div class="is-check"><i>+{item["incremental_segments"]}</i>'
        f'{esc(item["creator_name"])} · +{item["marginal_followers"]:,} modeled followers · '
        f'{item["incremental_share"]:.0%} new segments</div>'
        for item in report.get("incremental", [])
    )
    return (
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Shortlist overlap &amp; marginal reach</span>'
        '<span class="is-panel-link">Synthetic cohorts · not platform unique reach</span></div>'
        '<div class="is-panel-body"><div class="is-grid-2">'
        f'<div><div class="is-card-title" style="margin-bottom:6px">Pairwise Jaccard</div>{pair_html}'
        f'<small style="color:#879198;display:block;margin-top:6px">'
        f'Focus vs peers mean {vs["mean_jaccard"]:.0%} · max {vs["max_jaccard"]:.0%}</small></div>'
        f'<div><div class="is-card-title" style="margin-bottom:6px">Incremental reach (ranked order)</div>{lift_html}'
        f'<small style="color:#879198;display:block;margin-top:6px">'
        f'Union {report.get("union_segments", 0)} segments · '
        f'{report.get("sum_marginal_followers", 0):,} modeled unique followers</small></div>'
        "</div></div></div>"
    )


def resolve_compare_focus(compare_ids: list[str], selected_id: str | None) -> str | None:
    """Keep focus on a compared creator; fall back to the first column."""

    ids = [str(item) for item in compare_ids if str(item).strip()]
    if not ids:
        return None
    if selected_id and str(selected_id) in ids:
        return str(selected_id)
    return ids[0]


def _compare_grid(rows, focus_id: str | None = None) -> str:
    creators = [row for _, row in rows.iterrows()]
    labels = [
        ("Audience geography", lambda r: _geo_split(r)),
        ("Niche", lambda r: " · ".join(r["topics"][:3])),
        ("Modeled est. views", lambda r: f"{int(r['followers']*r['engagement_rate']/100*4)/1000:.0f}K"),
        ("Engagement rate", lambda r: f"{r['engagement_rate']:.1f}%"),
        ("Brand safety", lambda r: f"{r['brand_safety']:.0f}/100"),
        ("Estimated cost", lambda r: f"USD {int(r['estimated_cost_usd']):,}"),
        ("Posting consistency", lambda r: f"{float(r['posting_consistency']) * 100:.0f}%"),
        ("Historical reliability", lambda r: f"{float(r['historical_reliability']) * 100:.0f}%"),
        ("Recommended market", lambda r: r["primary_market"]),
    ]
    cells = [
        f'<div class="is-compare-label is-compare-head">'
        f'<b>{len(creators)} creators selected</b><br/><small>Select up to 3 to compare</small></div>'
    ]
    for avatar_idx, r in enumerate(creators):
        score = float(r["total_score"])
        fit = match_fit_label(score)
        tier = match_tier(score)
        tone = {"Excellent": "blue", "Strong": "green", "Moderate": "gray", "Weak": "orange"}.get(tier, "gray")
        focused = bool(focus_id) and str(r["creator_id"]) == str(focus_id)
        cells.append(
            f'<div class="is-compare-head {"selected" if focused else ""}">'
            f'<div class="is-creator-cell">{avatar(r["creator_name"], avatar_idx)}'
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


def _evidence_panel(creator, context: dict) -> str:
    live_rows = live_evidence_for(creator["creator_id"])
    items = []
    for item in live_rows:
        title = item.get("title") or "YouTube"
        url = item.get("url") or ""
        source = item.get("source") or "youtube_data_api"
        items.append(
            f'<div class="is-risk"><div>'
            f'<b><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(title)}</a></b>'
            f'<div class="is-evidence-meta"><span class="is-evidence-tag">{esc(source)}</span></div>'
            f'<small style="margin-top:4px">{esc(url)}</small></div></div>'
        )
    for item in list(creator.get("evidence", [])[:3]):
        items.append(
            f'<div class="is-risk"><div><b>{esc(item)}</b>'
            f'<small style="margin-top:4px">Catalog evidence · {esc(context.get("title", "the active entry"))}</small>'
            "</div></div>"
        )
    if not items:
        items.append(
            '<div class="is-risk"><div><b>No live or catalog evidence attached.</b>'
            "<small>Attach a YouTube channel from Search, or review catalog notes.</small></div></div>"
        )
    return (
        '<div class="is-card"><div class="is-panel-head">'
        '<span class="is-panel-title">Evidence explorer</span>'
        '<span class="is-panel-link">View more content (not wired)</span></div>'
        f'<div class="is-panel-body">{"".join(items)}</div></div>'
    )


def _drivers_panel(creator) -> str:
    mix_rows = "".join(
        f'<div class="is-driver-row">{scorebar(label, score)}'
        f'<span class="is-weight-tag">{esc(weight)}</span></div>'
        for label, score, weight in mix_driver_display(creator)
    )
    additive_rows = "".join(
        f'<div class="is-driver-row"><label>{esc(label)}</label>'
        f'<span>+{value:.1f}</span><span class="is-weight-tag">{esc(note)}</span></div>'
        for label, value, note in additive_driver_display(creator)
    )
    live_chip = (
        badge("Live YouTube evidence attached", "green")
        if float(creator.get("live_proof_bonus") or 0) > 0
        else ""
    )
    return (
        '<div class="is-card"><div class="is-panel-head">'
        '<span class="is-panel-title">Score drivers</span>'
        f'<span class="is-panel-link">{creator["total_score"]:.0f}/100 · rule-based, not LLM</span></div>'
        f'<div class="is-panel-body">{live_chip}{mix_rows}{additive_rows}'
        f'<div style="display:flex;justify-content:flex-end;align-items:baseline;gap:4px;'
        f'margin-top:8px;font-size:22px;font-weight:900;color:#16A36A">{creator["total_score"]:.0f}'
        f'<small style="font-size:9px;color:#879198;font-weight:650">weighted total</small></div>'
        "</div></div>"
    )


def _warning_severity(warning: str) -> str:
    text = str(warning)
    high_markers = ("下滑", "decline", "上限", "报价接近预算", "brand safety", "品牌安全")
    lowered = text.lower()
    if any(marker in text or marker.lower() in lowered for marker in high_markers):
        return "High"
    return "Medium"


def _risk_panel(creator) -> str:
    risks = [str(item) for item in list(creator.get("warnings", [])) if str(item).strip()]
    if not risks:
        return (
            '<div class="is-card"><div class="is-panel-head">'
            '<span class="is-panel-title">Potential risks</span>'
            f'{badge("None recorded", "gray")}</div>'
            '<div class="is-panel-body"><div class="is-risk">'
            "<span><b>No catalog warnings for this creator.</b>"
            "<small>Operator review is still required before outreach.</small></span></div></div></div>"
        )
    levels = [_warning_severity(risk) for risk in risks]
    medium_n = sum(1 for level in levels if level == "Medium")
    high_n = sum(1 for level in levels if level == "High")
    summary = f"{medium_n} Medium · {high_n} High"
    rows = []
    for risk, level in zip(risks, levels):
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
        f'{badge(summary, "orange" if high_n else "gray")}</div>'
        f'<div class="is-panel-body">{"".join(rows)}</div></div>'
    )


def render() -> None:
    render_topbar()
    context = active_context()
    ranked = ranking()
    if ranked.empty:
        if context.get("entry_type") == "opportunity" and not context.get("mission_id"):
            st.warning("Link this Creator Opportunity to a Launch Mission before comparing Match records.")
        else:
            st.warning("No eligible creators available.")
        return

    head_l, head_r = st.columns([1, 0.28], vertical_alignment="top")
    with head_l:
        md(
            page_header(
                "Creator Compare",
                "Compare shortlisted creators and review rationale before approving outreach.",
                "Decision approval",
            ),
            unsafe_allow_html=True,
        )
        md(
            mission_chip(active_context_label(), light=True),
            unsafe_allow_html=True,
        )
    with head_r:
        st.button(t("Export"), use_container_width=True, disabled=True, help=t("Not wired in this demo"))

    name_to_id = {row["creator_name"]: row["creator_id"] for _, row in ranked.head(10).iterrows()}
    default_names = [
        ranked[ranked["creator_id"] == cid].iloc[0]["creator_name"]
        for cid in st.session_state.compare_ids
        if not ranked[ranked["creator_id"] == cid].empty
    ][:3]
    if len(default_names) < 3:
        default_names.extend(
            name
            for name in ranked["creator_name"].tolist()
            if name not in default_names
        )
        default_names = default_names[:3]
    selected_names = st.multiselect(
        "Creators to compare", list(name_to_id), default=default_names, max_selections=3
    )
    compare = (
        ranked.set_index("creator_name").loc[selected_names].reset_index()
        if selected_names
        else ranked.head(3)
    )
    if compare.empty:
        compare = ranked.head(3)

    compare_ids = [str(item) for item in compare["creator_id"].tolist()]
    focus_id = resolve_compare_focus(compare_ids, st.session_state.get("selected_creator_id"))
    focus_names = [str(row["creator_name"]) for _, row in compare.iterrows()]
    focus_index = compare_ids.index(focus_id) if focus_id in compare_ids else 0
    chosen_name = st.radio(
        t("Focus creator"),
        focus_names,
        index=focus_index,
        horizontal=True,
        key="compare_focus_name",
    )
    focus = compare[compare["creator_name"] == chosen_name].iloc[0]
    select_creator(focus["creator_id"])
    md(_compare_grid(compare, focus["creator_id"]), unsafe_allow_html=True)
    focus_state = creator_state(focus["creator_id"])
    compare_rows = compare.to_dict("records")
    overlap_report = shortlist_overlap_report(compare_rows)
    overlap_report["_rows"] = compare_rows
    md(_overlap_panel(overlap_report, focus.to_dict()), unsafe_allow_html=True)
    st.caption(
        t("Mission fit is market + language. Topic overlap is Jaccard. Ranking is rule-based, not LLM.")
    )

    c1, c2, c3 = st.columns([1.05, 0.9, 0.68], gap="small", vertical_alignment="top")
    with c1:
        md(_evidence_panel(focus, context), unsafe_allow_html=True)
    with c2:
        md(_drivers_panel(focus), unsafe_allow_html=True)
    with c3:
        md(_risk_panel(focus), unsafe_allow_html=True)

    md(
        f'<div class="is-action-bar">'
        f'<div><b>Ready to take action on {esc(focus["creator_name"])}?</b>'
        f'<small>Current state: {esc(focus_state.replace("_", " ").title())} · evidence and risks require operator judgment.</small></div>'
        f'<div class="is-action-bar-actions"></div></div>',
        unsafe_allow_html=True,
    )
    locked = writes_locked()
    render_write_guard()
    jump_page = compare_cta_page(focus["creator_id"])
    jump_col, a, b, c = st.columns([1, 0.24, 0.22, 0.18])
    with jump_col:
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
                key="compare_next_action",
            ):
                open_compare_cta(focus["creator_id"], creator_name=focus.get("creator_name"))
    with a:
        if focus_state == "qualified":
            if st.button(
                t("Add to Shortlist"),
                type="primary" if not jump_page else "secondary",
                use_container_width=True,
                disabled=locked,
            ):
                transition_creator_state(
                    focus["creator_id"],
                    "shortlisted",
                    actor=context.get("owner", "Operator"),
                    reason="Evidence reviewed in Creator Compare",
                    evidence=list(focus.get("evidence", [])[:2]),
                )
                st.success("Shortlisted with an audit event. Review once more to approve outreach.")
                st.rerun()
        elif focus_state == "shortlisted":
            if st.button(
                t("Approve Outreach"),
                type="primary" if not jump_page else "secondary",
                use_container_width=True,
                disabled=locked,
            ):
                save_decision(
                    focus["creator_id"],
                    "Approved",
                    "Strong evidence and active-entry fit",
                    reason_code="strong_fit",
                    note="Evidence, score drivers and risks reviewed in Creator Compare.",
                    evidence=list(focus.get("evidence", [])),
                )
                st.success("Approved and linked to one OutreachCase with a unique coupon and UTM deeplink.")
                st.rerun()
        else:
            st.button(t("Approval recorded"), disabled=True, use_container_width=True)
    with b:
        if st.button(t("Request Review"), use_container_width=True, disabled=locked):
            save_decision(
                focus["creator_id"],
                "Review",
                "Additional rights and availability checks",
                reason_code="needs_review",
                note="Rights or availability evidence is incomplete.",
                evidence=list(focus.get("evidence", [])),
            )
            st.info("Review request logged.")
    with c:
        if st.button(
            t("Reject"),
            use_container_width=True,
            disabled=locked or focus_state in {"contracted", "content_in_review", "published", "measured", "closed_lost"},
        ):
            save_decision(
                focus["creator_id"],
                "Rejected",
                "Risk or cost concern",
                reason_code="risk_or_cost",
                note="Rejected after operator review of the active context.",
                evidence=list(focus.get("evidence", [])),
            )
            st.warning("Rejection recorded with a reason code and terminal state.")
            st.rerun()

    render_demo_notice()
