from __future__ import annotations

from uuid import uuid4

import streamlit as st

from components.html import badge, esc, metric_cards, page_header
from components.i18n import t
from components.positioning import paradigm_html
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_mission,
    content_assets_in_review_count,
    creators,
    mission_health_snapshot,
    missions,
    next_outreach_action_page,
    opportunities_for_mission,
    prepare_next_action_jump,
    ranking,
    save_mission,
    set_active_context,
    tracking_assets,
    workflow_board,
    workflow_events,
    workflow_summary,
    performance_events,
)
from components.ui import md
from src.domain import launch_progress, pipeline_counts
from src.landing_path import landing_path
from src.product_dna import load_product_dna


def launch_cta_page(creator_id: str) -> str | None:
    """Jump target for Launch Mission. Same rules as Outreach; do not fork them."""

    return next_outreach_action_page(creator_id)


def open_launch_cta(creator_id: str, *, creator_name: str | None = None) -> str | None:
    """Prefill the creator and open Growth Review or Content Studio when that is the next action."""

    page = prepare_next_action_jump(creator_id, creator_name=creator_name)
    if page == "growth-review":
        open_workspace_page("growth-review")
    elif page == "content-studio":
        open_workspace_page("content-studio")
    return page


def launch_cta_creator() -> dict | None:
    """Selected creator if they have a jump, else the first workflow creator who does."""

    selected_id = st.session_state.get("selected_creator_id")
    if selected_id and launch_cta_page(selected_id):
        ranked = ranking()
        if not ranked.empty:
            matches = ranked[ranked["creator_id"] == selected_id]
            if not matches.empty:
                return matches.iloc[0].to_dict()
        for people in workflow_board().values():
            for person in people:
                if person["creator_id"] == selected_id:
                    return person
        return {"creator_id": selected_id, "creator_name": selected_id}
    for people in workflow_board().values():
        for person in people:
            if launch_cta_page(person["creator_id"]):
                return person
    return None


def _next_action_label(page: str) -> str:
    if page == "growth-review":
        return t("Record a conversion on Growth Review")
    return t("Create a brief in Content Studio")


def _progress() -> dict:
    counts = pipeline_counts(workflow_summary())
    return launch_progress(
        shortlisted=counts["shortlisted"],
        approved=counts["approved"],
        tracking_assets=len(tracking_assets()),
        performance_events=len(performance_events()),
    )


def _product_card(mission: dict, health: dict) -> str:
    markets = " / ".join(mission.get("markets", [mission.get("market", "United States")]))
    score = int(health.get("score", 0))
    return f"""
    <div class="is-card is-product-card">
      <div class="is-product-visual"><div class="is-camera"></div></div>
      <div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
          {badge('Launch Mission','blue')}
          <b style="font-size:16px;letter-spacing:-0.02em">{mission['product']}</b>
        </div>
        <div class="is-product-info">
          <div class="is-field"><label>Target markets</label><strong>{markets}</strong></div>
          <div class="is-field"><label>Campaign dates</label><strong>{mission.get('campaign_dates')}</strong></div>
          <div class="is-field"><label>Mission status</label><strong>{badge(mission.get('status','Active'),'green')}</strong></div>
          <div class="is-field"><label>Launch objective</label><strong>{mission.get('objective')}</strong></div>
          <div class="is-field"><label>Total budget</label><strong>USD {mission.get('budget_usd',0):,.0f}</strong></div>
          <div class="is-field"><label>Owner</label><strong>{mission.get('owner','Olivia Chen')}</strong></div>
        </div>
      </div>
      <div class="is-health">
        <div class="is-donut" style="--pct:{score}"><span>{score}</span></div>
        <b>{health.get("label", "Needs shortlist")}</b>
        <small>{health.get("note", "Computed from the active workflow")}</small>
      </div>
    </div>
    """


def _dna_card() -> str:
    dna = load_product_dna()
    claims = []
    for claim in dna.get("claims") or []:
        proof = " · ".join(str(item) for item in (claim.get("visual_proof") or []) if str(item).strip())
        scenes = " · ".join(str(item) for item in (claim.get("scenes") or []) if str(item).strip())
        claims.append(
            f'<div class="is-field"><label>{esc(claim.get("claim_id", ""))}</label>'
            f'<strong>{esc(claim.get("claim", ""))}</strong>'
            f"<small>{esc(scenes)} · {esc(proof)}</small></div>"
        )
    guardrails = "; ".join(str(item) for item in (dna.get("guardrails") or []) if str(item).strip())
    return f"""
    <div class="is-card" style="margin-top:10px">
      <div class="is-panel-head">
        <span class="is-panel-title">{t("Product DNA")}</span>
        <span class="is-panel-link">{esc(dna.get("dna_id", ""))} · v{esc(str(dna.get("version", "")))}</span>
      </div>
      <div class="is-panel-body">
        <p><b>{esc(dna.get("sku", ""))}</b> · {esc(dna.get("audience", ""))}</p>
        <div class="is-product-info">{"".join(claims)}</div>
        <small>Versionable SKU object with visual-proof claims. Not a copy of mission form fields. Not a live PIM. {esc(guardrails)}</small>
      </div>
    </div>
    """


def _workflow_card(progress: dict) -> str:
    items = []
    for index, step in enumerate(progress["steps"], 1):
        cls = {"done": "done", "current": "active", "pending": "pending"}.get(step["status"], "")
        items.append(
            f'<div class="is-workflow-item {cls}"><div class="is-workflow-icon">{index:02d}</div>'
            f'<b>{step["title"]}</b><small>{step["note"]}</small></div>'
        )
    return (
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Mission workflow</span>'
        '<span class="is-panel-link">From the active workflow</span></div>'
        '<div class="is-panel-body"><div class="is-workflow is-workflow-live">'
        + "".join(items)
        + "</div></div></div>"
    )


def _pipeline_notes(
    *,
    shortlisted: int,
    approved: int,
    tracking_n: int,
    events_n: int,
) -> list[tuple[str, str]]:
    """Live pipeline counts. Next action is the CTA, not a duplicate list."""

    return [
        (f"{int(shortlisted)} currently shortlisted creators", "Unified workflow"),
        (f"{int(approved)} currently approved creators", "Human decisions"),
        (f"{int(tracking_n)} tracking assets issued", "Coupons and UTM links, not conversions"),
        (f"{int(events_n)} performance events recorded", "Sourced conversions only"),
    ]


def _pipeline_notes_html(progress: dict, *, tracking_n: int) -> str:
    steps = {step["id"]: step for step in progress.get("steps", [])}
    notes = _pipeline_notes(
        shortlisted=int(steps.get("shortlist", {}).get("count", 0)),
        approved=int(steps.get("approve", {}).get("count", 0)),
        tracking_n=tracking_n,
        events_n=int(steps.get("measure", {}).get("count", 0)),
    )
    items = []
    accents = ("#EAF2FF", "#E9F8F1", "#FFF4E4", "#F1F4F5", "#EAF2FF")
    for idx, (title, note) in enumerate(notes):
        items.append(
            f'<li><span class="is-list-num" style="background:{accents[idx % len(accents)]};color:#34424A">•</span>'
            f'<span><b>{title}</b><small>{note}</small></span></li>'
        )
    return (
        '<div class="is-card" style="margin-bottom:10px"><div class="is-panel-head"><span class="is-panel-title">Pipeline snapshot</span>'
        '<span class="is-panel-link">Live counts</span></div><div class="is-panel-body"><ul class="is-list">'
        + "".join(items)
        + "</ul></div></div>"
    )


def _creator_names() -> dict[str, str]:
    return {row["creator_id"]: row["creator_name"] for _, row in creators().iterrows()}


def _activity_rows(events: list[dict], names: dict[str, str], *, limit: int = 5) -> list[tuple[str, str]]:
    """Newest-first audit lines for Launch. Empty list is honest."""

    rows: list[tuple[str, str]] = []
    for event in reversed(events[-limit:]):
        creator_id = str(event.get("creator_id") or "")
        name = str(names.get(creator_id) or creator_id)
        title = f"{name}: {event.get('from_state')} → {event.get('to_state')}"
        stamp = str(event.get("occurred_at") or "")[:16]
        note = " · ".join(part for part in [str(event.get("reason") or ""), str(event.get("actor") or ""), stamp] if part)
        rows.append((title, note))
    return rows


def _activity_html(events: list[dict], names: dict[str, str]) -> str:
    rows = _activity_rows(events, names)
    if not rows:
        body = (
            '<ul class="is-list"><li><span class="is-list-num" style="background:#F1F4F5;color:#4A565E">•</span>'
            "<span><b>No workflow events for this mission yet.</b>"
            "<small>Shortlist or approve a creator to start the audit trail.</small></span></li></ul>"
        )
    else:
        items = []
        palettes = ["#EAF2FF", "#E9F8F1", "#FFF4E4"]
        for idx, (title, note) in enumerate(rows):
            color = palettes[idx % 3]
            items.append(
                f'<li><span class="is-list-num" style="background:{color};color:#34424A">•</span>'
                f"<span><b>{esc(title)}</b><small>{esc(note)}</small></span></li>"
            )
        body = '<ul class="is-list">' + "".join(items) + "</ul>"
    return (
        '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Recent workflow activity</span>'
        '<span class="is-panel-link">From the audit trail</span></div><div class="is-panel-body">'
        + body
        + "</div></div>"
    )


def _render_next_action_cta(progress: dict, *, tracking_n: int) -> None:
    target = launch_cta_creator()
    jump_page = launch_cta_page(target["creator_id"]) if target else None
    if jump_page and target:
        if st.button(
            _next_action_label(jump_page),
            type="primary",
            use_container_width=True,
            key="launch_next_action",
        ):
            open_launch_cta(target["creator_id"], creator_name=target.get("creator_name"))
    md(_pipeline_notes_html(progress, tracking_n=tracking_n), unsafe_allow_html=True)
    md(_activity_html(workflow_events(), _creator_names()), unsafe_allow_html=True)


def _landing_html() -> str:
    path = landing_path()
    phases = "".join(
        f'<div class="is-workflow-item pending"><div class="is-workflow-icon">{esc(str(item["week"]))}</div>'
        f'<b>{esc(item["title"])}</b><small>{esc(item["owner"])} · {esc(item["exit_gate"])}</small></div>'
        for item in path["phases"]
    )
    return (
        '<div class="is-card" id="pilot-landing-path"><div class="is-panel-head">'
        f'<span class="is-panel-title">{t("2-week pilot landing path")}</span>'
        f'<span class="is-panel-link">{esc(path["horizon"])}</span></div>'
        f'<div class="is-panel-body"><small>{esc(path["closed_loop"])}</small>'
        f'<div class="is-workflow is-workflow-live" style="margin-top:8px">{phases}</div>'
        f"<small>{esc(path['note'])}</small></div></div>"
    )


def render() -> None:
    render_topbar()
    mission_records = missions()
    mission_by_name = {item.get("name", item["mission_id"]): item["mission_id"] for item in mission_records}
    preferred_id = st.session_state.pop("pending_mission_id", st.session_state.get("active_mission_id"))
    mission_names = list(mission_by_name)
    preferred_name = next((name for name, mission_id in mission_by_name.items() if mission_id == preferred_id), mission_names[0])
    selected_name = st.selectbox(
        t("Open launch mission"),
        mission_names,
        index=mission_names.index(preferred_name),
        label_visibility="collapsed",
    )
    set_active_context("mission", mission_by_name[selected_name])
    mission = active_mission()
    summary = workflow_summary()
    ranked = ranking()
    health = mission_health_snapshot()
    tracking_n = len(tracking_assets())
    in_review_n = content_assets_in_review_count()
    progress = _progress()

    left, right = st.columns([1, 0.26], vertical_alignment="top")
    with left:
        md(
            page_header(
                "Claim-underwriting desk",
                "Authorize spend against named Product DNA claims on public captions — not lookalike retrieval.",
                "Industry paradigm",
            ),
            unsafe_allow_html=True,
        )
    with right:
        b1, b2 = st.columns(2)
        with b1:
            st.button(t("Export"), use_container_width=True, disabled=True, help=t("Not wired in this demo"))
        with b2:
            if st.button(t("+ New Mission"), type="primary", use_container_width=True, disabled=writes_locked()):
                st.session_state.show_mission_form = not st.session_state.show_mission_form
    render_write_guard()
    md(paradigm_html(), unsafe_allow_html=True)

    if st.session_state.show_mission_form:
        with st.expander(t("Create a new launch mission"), expanded=True):
            c1, c2, c3 = st.columns(3)
            product = c1.text_input(t("Product"), mission["product"])
            market = c2.selectbox(t("Primary market"), ["United States", "Mexico", "Japan"])
            budget = c3.number_input(t("Budget (USD)"), min_value=10000, value=int(mission["budget_usd"]), step=10000)
            objective = st.text_area(t("Launch objective"), mission["objective"])
            if st.button(t("Save mission"), type="primary", disabled=writes_locked()):
                saved = {
                    "mission_id": f"mission_{uuid4().hex[:8]}",
                    "name": f"{product} · {market} Launch",
                    "product": product,
                    "market": market,
                    "markets": [market],
                    "language": "Spanish" if market == "Mexico" else "English",
                    "languages": ["Spanish" if market == "Mexico" else "English"],
                    "budget_usd": budget,
                    "max_cost_usd": mission.get("max_cost_usd", 12000),
                    "min_brand_safety": mission.get("min_brand_safety", 72),
                    "target_topics": mission.get("target_topics", []),
                    "target_styles": mission.get("target_styles", []),
                    "objective": objective,
                    "campaign_dates": mission.get("campaign_dates", "Not scheduled"),
                    "owner": mission.get("owner", "Olivia Chen"),
                    "status": "Draft",
                }
                save_mission(saved)
                st.session_state.pending_mission_id = saved["mission_id"]
                st.session_state.show_mission_form = False
                st.success("Mission saved for this demo session.")
                st.rerun()

    md(_product_card(mission, health), unsafe_allow_html=True)
    md(_dna_card(), unsafe_allow_html=True)
    md(_landing_html(), unsafe_allow_html=True)
    metrics = [
        ("Candidates Pool", str(len(ranked)), "Eligible for this mission", ""),
        ("Shortlisted", str(summary.get("shortlisted", 0)), "Unified workflow", ""),
        ("Approved", str(summary.get("approved", 0)), "Human decisions", ""),
        ("Contacted", str(summary.get("contacted", 0)), "Audited outreach", ""),
        ("Published", str(summary.get("published", 0)), "Linked workflow", ""),
        ("Measured", str(summary.get("measured", 0)), "Sourced events only", ""),
        ("Content in review", str(in_review_n), "Saved Content Studio briefs", ""),
    ]
    md(metric_cards(metrics), unsafe_allow_html=True)

    linked_opps = opportunities_for_mission(mission.get("mission_id"))
    with st.container(border=True):
        st.markdown(f"**{t('Linked creator opportunities')}** · {len(linked_opps)}")
        if not linked_opps:
            st.caption(t("No creator opportunities are linked to this mission."))
        else:
            for opportunity in linked_opps:
                row, action = st.columns([0.78, 0.22], vertical_alignment="center")
                status = str(opportunity.get("status") or "discovered").replace("_", " ").title()
                row.markdown(
                    f"**{opportunity.get('title', opportunity['opportunity_id'])}**  \n"
                    f"{opportunity['opportunity_id']} · {opportunity.get('creator_id', '—')} · {status}"
                )
                if action.button(
                    t("Open opportunity"),
                    key=f"open_linked_opp_{opportunity['opportunity_id']}",
                    use_container_width=True,
                ):
                    set_active_context("opportunity", opportunity["opportunity_id"])
                    st.session_state.opportunity_detail_id = opportunity["opportunity_id"]
                    open_workspace_page("creator-opportunity")

    main, side = st.columns([1, 0.34], gap="small", vertical_alignment="top")
    with main:
        md(_workflow_card(progress), unsafe_allow_html=True)
    with side:
        _render_next_action_cta(progress, tracking_n=tracking_n)

    render_demo_notice()
