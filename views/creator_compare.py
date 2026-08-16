from __future__ import annotations

import streamlit as st

from components.html import avatar, badge, esc, mission_chip, page_header, scorebar
from components.i18n import t
from components.shell import render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_context,
    active_context_label,
    creator_state,
    live_evidence_for,
    ranking,
    save_decision,
    select_creator,
    transition_creator_state,
)
from components.ui import md
from src.audience import overlap_vs_cohort, shortlist_overlap_report


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


def _compare_grid(rows) -> str:
    creators = [row for _, row in rows.iterrows()]
    labels = [
        ("Audience geography", lambda r: _geo_split(r)),
        ("Niche", lambda r: " · ".join(r["topics"][:3])),
        ("Avg views (last 10)", lambda r: f"{int(r['followers']*r['engagement_rate']/100*4)/1000:.0f}K"),
        ("Engagement rate", lambda r: f"{r['engagement_rate']:.1f}%"),
        ("Brand safety", lambda r: f"{r['brand_safety']:.0f}/100"),
        ("Estimated cost", lambda r: f"USD {int(r['estimated_cost_usd']):,}"),
        ("Posting consistency", lambda r: f"{float(r['posting_consistency']) * 100:.0f}%"),
        ("Historical reliability", lambda r: f"{float(r['historical_reliability']) * 100:.0f}%"),
        ("Recommended market", lambda r: r["primary_market"]),
    ]
    cells = [
        '<div class="is-compare-label is-compare-head">'
        '<b>3 creators selected</b><br/><small>Select up to 3 to compare</small></div>'
    ]
    for idx, r in enumerate(creators):
        score = float(r["total_score"])
        fit = "High Fit" if score >= 85 else "Strong Fit" if score >= 80 else "Good Fit"
        tone = "blue" if score >= 85 else "green" if score >= 80 else "gray"
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
    evidence = list(creator.get("evidence", [])[:3])
    while len(evidence) < 3:
        evidence.append("Representative content evidence available for review")
    tags = [
        ("POV", "Nature", "Travel"),
        ("Action", "Product", "Reveal"),
        ("Night", "City", "Lifestyle"),
    ]
    for idx, item in enumerate(evidence):
        tag_html = "".join(f'<span class="is-evidence-tag">{esc(tag)}</span>' for tag in tags[idx])
        items.append(
            f'<div class="is-risk"><div class="is-video" style="width:96px;aspect-ratio:16/9;flex:0 0 96px;border-radius:8px"></div>'
            f'<div><b>{esc(item)}</b>'
            f'<div class="is-evidence-meta">{tag_html}<span class="is-evidence-tag">{42 + idx * 18}s</span></div>'
            f'<small style="margin-top:4px">Matched to {esc(context.get("title", "the active entry"))}</small></div></div>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head">'
        '<span class="is-panel-title">Evidence explorer</span>'
        '<span class="is-panel-link">View more content →</span></div>'
        f'<div class="is-panel-body">{"".join(items)}</div></div>'
    )


def _drivers_panel(creator) -> str:
    drivers = [
        ("Mission fit", creator["audience_fit"], "28%"),
        ("Engagement quality", creator["momentum"], "18%"),
        ("Content relevance", creator["content_fit"], "24%"),
        ("Commercial fit", creator["commercial_fit"], "18%"),
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

    md(_compare_grid(compare), unsafe_allow_html=True)
    focus = compare.iloc[0]
    select_creator(focus["creator_id"])
    focus_state = creator_state(focus["creator_id"])
    compare_rows = compare.to_dict("records")
    overlap_report = shortlist_overlap_report(compare_rows)
    overlap_report["_rows"] = compare_rows
    md(_overlap_panel(overlap_report, focus.to_dict()), unsafe_allow_html=True)
    st.caption(t("Mission fit is market + language. Overlap ≠ mission fit."))

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
    _, a, b, c = st.columns([1, 0.24, 0.22, 0.18])
    with a:
        if focus_state == "qualified":
            if st.button(t("Add to Shortlist"), type="primary", use_container_width=True, disabled=locked):
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
            if st.button(t("Approve Outreach"), type="primary", use_container_width=True, disabled=locked):
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
