from __future__ import annotations

from datetime import datetime

import streamlit as st

from components import state as state_store
from components.html import badge, esc, page_header
from components.shell import render_demo_notice, render_topbar
from services.opportunity_service import (
    OPPORTUNITY_STATUSES,
    create_opportunity,
    find_opportunity,
    load_opportunities,
)


def _bootstrap_opportunity_state() -> None:
    if "opportunities" not in st.session_state:
        st.session_state.opportunities = load_opportunities()
    if "active_entry_type" not in st.session_state:
        st.session_state.active_entry_type = "mission"
    if "active_opportunity_id" not in st.session_state:
        st.session_state.active_opportunity_id = None

    available_ids = {
        opportunity.get("opportunity_id") for opportunity in st.session_state.opportunities
    }
    selected_id = st.session_state.get("opportunity_detail_id")
    if selected_id not in available_ids:
        active_id = st.session_state.get("active_opportunity_id")
        st.session_state.opportunity_detail_id = (
            active_id if active_id in available_ids else next(iter(available_ids), None)
        )


def _activate_opportunity(opportunity_id: str) -> None:
    set_active_context = getattr(state_store, "set_active_context", None)
    if callable(set_active_context):
        set_active_context("creator_opportunity", opportunity_id)
    else:
        st.session_state.active_entry_type = "opportunity"
        st.session_state.active_opportunity_id = opportunity_id


def _creator_records() -> tuple[list[dict], dict[str, dict]]:
    records = state_store.creators().to_dict("records")
    return records, {str(record["creator_id"]): record for record in records}


def _status_label(status: str) -> str:
    return status.replace("_", " ").title()


def _status_tone(status: str) -> str:
    if status in {"qualified", "shortlisted", "approved", "contracted", "published", "measured"}:
        return "green"
    if status in {"closed_lost"}:
        return "red"
    if status in {"contacted", "negotiating", "content_in_review"}:
        return "blue"
    return "gray"


def _is_opportunity_context() -> bool:
    return st.session_state.get("active_entry_type") in {
        "opportunity",
        "creator_opportunity",
    }


def _context_caption(opportunity: dict | None) -> str:
    if not _is_opportunity_context() or not opportunity:
        return "Mission context is active. Select an opportunity below when you want to work from the creator-first entry."
    return (
        f"Active opportunity: {opportunity['title']} · "
        f"{opportunity['market']} · {opportunity['language']}"
    )


def _render_list(opportunities: list[dict], creators_by_id: dict[str, dict]) -> None:
    st.markdown("#### Opportunity pipeline")
    filter_left, filter_right = st.columns(2)
    status_options = ["All", *[_status_label(status) for status in OPPORTUNITY_STATUSES]]
    selected_status = filter_left.selectbox(
        "Status", status_options, key="opportunity_status_filter"
    )
    markets = sorted({item["market"] for item in opportunities if item.get("market")})
    selected_market = filter_right.selectbox(
        "Market", ["All", *markets], key="opportunity_market_filter"
    )

    filtered = [
        item
        for item in opportunities
        if (selected_status == "All" or _status_label(item["status"]) == selected_status)
        and (selected_market == "All" or item["market"] == selected_market)
    ]
    if not filtered:
        st.info("No opportunities match the selected filters.")
        return

    for opportunity in filtered:
        creator = creators_by_id.get(opportunity["creator_id"], {})
        creator_name = creator.get("creator_name", opportunity["creator_id"])
        is_selected = opportunity["opportunity_id"] == st.session_state.opportunity_detail_id
        with st.container(border=True):
            summary, status_col, action = st.columns([0.64, 0.2, 0.16], vertical_alignment="center")
            with summary:
                st.markdown(
                    f"**{esc(opportunity['title'])}**  \n"
                    f"{esc(creator_name)} · {esc(opportunity['market'])} · "
                    f"{esc(opportunity['language'])}  \n"
                    f"<small>{esc(opportunity['opportunity_id'])} · {esc(opportunity['source'])}</small>",
                    unsafe_allow_html=True,
                )
            with status_col:
                st.markdown(
                    badge(_status_label(opportunity["status"]), _status_tone(opportunity["status"])),
                    unsafe_allow_html=True,
                )
                if (
                    _is_opportunity_context()
                    and st.session_state.get("active_opportunity_id")
                    == opportunity["opportunity_id"]
                ):
                    st.caption("Active context")
            with action:
                label = "Selected" if is_selected else "View"
                if st.button(
                    label,
                    key=f"select_{opportunity['opportunity_id']}",
                    disabled=is_selected,
                    use_container_width=True,
                ):
                    st.session_state.opportunity_detail_id = opportunity["opportunity_id"]
                    st.rerun()


def _render_detail(opportunity: dict, creator: dict | None) -> None:
    creator = creator or {}
    creator_name = creator.get("creator_name", opportunity["creator_id"])
    st.markdown("#### Opportunity detail")
    with st.container(border=True):
        title_col, action_col = st.columns([0.72, 0.28], vertical_alignment="top")
        with title_col:
            st.markdown(f"### {esc(opportunity['title'])}", unsafe_allow_html=True)
            st.caption(
                f"{opportunity['opportunity_id']} · {creator_name} · "
                f"{opportunity['market']} · {opportunity['language']}"
            )
        with action_col:
            is_active = (
                _is_opportunity_context()
                and st.session_state.get("active_opportunity_id")
                == opportunity["opportunity_id"]
            )
            if st.button(
                "Active opportunity" if is_active else "Activate opportunity",
                type="primary",
                disabled=is_active,
                use_container_width=True,
            ):
                _activate_opportunity(opportunity["opportunity_id"])
                st.success("Creator Opportunity is now the active workspace context.")
                st.rerun()

        facts = st.columns(5)
        facts[0].metric("Type", _status_label(opportunity["opportunity_type"]))
        facts[1].metric("Status", _status_label(opportunity["status"]))
        facts[2].metric("Source", opportunity["source"])
        facts[3].metric("Owner", opportunity["owner"])
        linked = opportunity.get("linked_mission_id") or "Not linked"
        facts[4].metric("Linked mission", linked)

        st.markdown("**Opportunity hypothesis**")
        st.write(opportunity["hypothesis"])
        st.markdown("**Evidence**")
        if opportunity["evidence"]:
            for item in opportunity["evidence"]:
                st.markdown(f"- {esc(item)}", unsafe_allow_html=True)
        else:
            st.caption("No evidence has been recorded yet.")

        st.markdown("**Suggested next action**")
        st.write(opportunity["suggested_action"])

        created_at = opportunity.get("created_at", "")
        try:
            created_label = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            created_label = created_at or "Unknown"
        observed_at = opportunity.get("observed_at", "")
        try:
            observed_label = datetime.fromisoformat(observed_at).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            observed_label = observed_at or "Unknown"
        st.caption(f"Observed {observed_label} · Created {created_label}")

        is_active = (
            _is_opportunity_context()
            and st.session_state.get("active_opportunity_id") == opportunity["opportunity_id"]
        )
        if is_active:
            st.divider()
            creator_id = opportunity["creator_id"]
            current_state = state_store.creator_state(creator_id)
            st.markdown(f"**Collaboration state:** `{_status_label(current_state)}`")
            next_states = state_store.allowed_next_creator_states(creator_id)
            if next_states:
                transition_col, reason_col = st.columns([0.35, 0.65])
                target_state = transition_col.selectbox(
                    "Next state",
                    next_states,
                    format_func=_status_label,
                    key=f"opportunity_next_{opportunity['opportunity_id']}",
                )
                reason = reason_col.text_input(
                    "Decision reason",
                    "Opportunity evidence reviewed by the owner",
                    key=f"opportunity_reason_{opportunity['opportunity_id']}",
                )
                if st.button("Apply governed transition", use_container_width=True):
                    try:
                        if target_state == "approved":
                            state_store.save_decision(
                                creator_id,
                                "Approved",
                                reason,
                                reason_code="opportunity_approved",
                                note=opportunity["suggested_action"],
                                evidence=opportunity["evidence"],
                            )
                        elif target_state == "closed_lost":
                            state_store.save_decision(
                                creator_id,
                                "Rejected",
                                reason,
                                reason_code="opportunity_rejected",
                                note=opportunity["suggested_action"],
                                evidence=opportunity["evidence"],
                            )
                        else:
                            state_store.transition_creator_state(
                                creator_id,
                                target_state,
                                actor=opportunity["owner"],
                                reason=reason,
                                evidence=opportunity["evidence"] or ["opportunity://manual-review"],
                            )
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.success(f"Moved to {_status_label(target_state)} with an audit event.")
                        st.rerun()

            mission_records = state_store.missions()
            if mission_records:
                mission_by_label = {
                    mission.get("name", mission["mission_id"]): mission["mission_id"]
                    for mission in mission_records
                }
                current_mission_id = opportunity.get("linked_mission_id")
                mission_labels = list(mission_by_label)
                default_label = next(
                    (label for label, mission_id in mission_by_label.items() if mission_id == current_mission_id),
                    mission_labels[0],
                )
                selected_mission = st.selectbox(
                    "Linked launch mission",
                    mission_labels,
                    index=mission_labels.index(default_label),
                    key=f"opportunity_mission_{opportunity['opportunity_id']}",
                )
                if st.button("Link mission and preserve opportunity evidence", use_container_width=True):
                    state_store.link_opportunity_to_mission(
                        opportunity["opportunity_id"], mission_by_label[selected_mission]
                    )
                    st.success("Mission linked; the Creator Opportunity remains the active root context.")
                    st.rerun()

                if not current_mission_id and st.button(
                    "Create a launch mission from this opportunity",
                    use_container_width=True,
                ):
                    mission_id = f'mission_{opportunity["opportunity_id"].lower().replace("-", "_")}'
                    generated_mission = {
                        "mission_id": mission_id,
                        "name": f'{opportunity["title"]} · Launch Mission',
                        "product": opportunity["title"],
                        "market": opportunity["market"],
                        "markets": [opportunity["market"]],
                        "language": opportunity["language"],
                        "languages": [opportunity["language"]],
                        "max_cost_usd": max(int(creator.get("estimated_cost_usd", 10000) * 1.2), 10000),
                        "min_brand_safety": 60,
                        "target_topics": list(creator.get("topics", [])),
                        "target_styles": list(creator.get("styles", [])),
                        "objective": opportunity["hypothesis"],
                        "budget_usd": 100_000,
                        "campaign_dates": "Not scheduled",
                        "owner": opportunity["owner"],
                        "status": "Draft",
                        "health_score": 0,
                    }
                    state_store.save_mission(generated_mission)
                    state_store.link_opportunity_to_mission(opportunity["opportunity_id"], mission_id)
                    state_store.set_active_context("opportunity", opportunity["opportunity_id"])
                    st.success("Draft mission created and linked without changing the Opportunity root.")
                    st.rerun()


def _render_create_form(creators: list[dict]) -> None:
    with st.expander("Create Opportunity", expanded=False):
        creator_options = {
            f"{record['creator_name']} · {record['creator_id']}": str(record["creator_id"])
            for record in creators
        }
        current_mission_id = st.session_state.get("active_mission_id")
        with st.form("create_creator_opportunity", clear_on_submit=False):
            c1, c2 = st.columns(2)
            creator_label = c1.selectbox("Creator", list(creator_options))
            title = c2.text_input("Opportunity title")
            source = c1.text_input("Source", placeholder="Social listening, nomination, inbound…")
            owner = c2.text_input("Owner", placeholder="Team or operator")
            opportunity_type = c1.selectbox(
                "Opportunity type",
                ["social_signal", "performance_signal", "regional_nomination", "inbound"],
            )
            market = c1.text_input("Market")
            language = c2.text_input("Language")
            hypothesis = st.text_area(
                "Hypothesis",
                placeholder="Why is this creator an opportunity, and what should the team test?",
            )
            evidence = st.text_area(
                "Evidence",
                placeholder="Enter one evidence item per line.",
            )
            suggested_action = st.text_input(
                "Suggested next action",
                "Review evidence and qualify the opportunity",
            )
            link_to_mission = st.checkbox(
                "Link to the current mission",
                value=False,
                disabled=not bool(current_mission_id),
            )
            submitted = st.form_submit_button(
                "Create opportunity", type="primary", use_container_width=True
            )

        if submitted:
            try:
                opportunity = create_opportunity(
                    st.session_state.opportunities,
                    creator_id=creator_options[creator_label],
                    title=title,
                    source=source,
                    market=market,
                    language=language,
                    hypothesis=hypothesis,
                    evidence=evidence,
                    owner=owner,
                    opportunity_type=opportunity_type,
                    suggested_action=suggested_action,
                    linked_mission_id=current_mission_id if link_to_mission else None,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                state_store.save_opportunity(opportunity)
                st.session_state.opportunity_detail_id = opportunity["opportunity_id"]
                st.success(f"Created {opportunity['opportunity_id']} and opened its detail.")
                st.rerun()


def render() -> None:
    render_topbar()
    _bootstrap_opportunity_state()
    creators, creators_by_id = _creator_records()
    opportunities = list(st.session_state.opportunities)

    selected = find_opportunity(opportunities, st.session_state.opportunity_detail_id)
    active = find_opportunity(opportunities, st.session_state.get("active_opportunity_id"))

    header_left, header_right = st.columns([0.7, 0.3], vertical_alignment="top")
    with header_left:
        st.markdown(
            page_header(
                "Creator Opportunity",
                "Capture creator-led signals, evaluate the evidence and turn qualified opportunities into active work.",
                "Creator-first entry",
            ),
            unsafe_allow_html=True,
        )
        st.caption(_context_caption(active))
    with header_right:
        st.metric("Open opportunities", len(opportunities))

    _render_create_form(creators)
    list_col, detail_col = st.columns([0.48, 0.52], gap="small", vertical_alignment="top")
    with list_col:
        _render_list(opportunities, creators_by_id)
    with detail_col:
        if selected:
            _render_detail(selected, creators_by_id.get(selected["creator_id"]))
        else:
            st.info("Create an opportunity to begin the creator-first workflow.")

    render_demo_notice()
