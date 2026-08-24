from __future__ import annotations

from datetime import datetime

import streamlit as st

from components import state as state_store
from components.html import badge, esc, mini_kpis, page_header, scorebar
from components.i18n import t
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.ui import md
from src.inbound import OWNERS
from src.scouting import scout_cards
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
        inbound_first = next(
            (
                item.get("opportunity_id")
                for item in st.session_state.opportunities
                if item.get("opportunity_type") == "inbound"
            ),
            None,
        )
        st.session_state.opportunity_detail_id = (
            active_id
            if active_id in available_ids
            else inbound_first or next(iter(available_ids), None)
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


def opportunity_cta_page(creator_id: str) -> str | None:
    """Jump target for Opportunity. Same rules as Outreach; do not fork them."""

    return state_store.next_outreach_action_page(creator_id)


def open_opportunity_cta(creator_id: str, *, creator_name: str | None = None) -> str | None:
    """Prefill the creator and open Growth Review or Content Studio when that is the next action."""

    page = state_store.prepare_next_action_jump(creator_id, creator_name=creator_name)
    if page == "growth-review":
        open_workspace_page("growth-review")
    elif page == "content-studio":
        open_workspace_page("content-studio")
    return page


def advance_opportunity_creator(
    creator_id: str,
    *,
    actor: str,
    reason: str,
    evidence: list[str] | tuple[str, ...] | str,
) -> dict:
    """Advance one legal hop. Never skips; measured still requires recorded events."""

    target = state_store.next_linear_creator_state(creator_id)
    if not target:
        raise ValueError("No next legal hop")
    return state_store.transition_creator_state(
        creator_id,
        target,
        actor=actor,
        reason=reason,
        evidence=evidence,
    )


def _audit_timeline(events: list[dict]) -> str:
    if not events:
        return '<div class="is-card is-card-pad">No workflow events recorded for this creator.</div>'
    cards = []
    for event in reversed(events):
        stamp = event.get("occurred_at") or event.get("timestamp") or ""
        cards.append(
            '<div class="is-card is-card-pad">'
            f'<div class="is-card-title">{esc(_status_label(event["from_state"]))} → '
            f'{esc(_status_label(event["to_state"]))}</div>'
            f'<div class="is-card-caption">{esc(stamp)} · {esc(event["reason"])} · '
            f'{esc(event["actor"])}</div></div>'
        )
    return "".join(cards)


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
        return t("Mission context is active. Select an opportunity below when you want to work from the creator-first entry.")
    return (
        f"{t('Active opportunity')}: {opportunity['title']} · "
        f"{opportunity['market']} · {opportunity['language']}"
    )


def _linked_mission_label(opportunity: dict) -> str:
    linked_id = opportunity.get("linked_mission_id")
    if not linked_id:
        return t("Not linked")
    mission = next(
        (item for item in state_store.missions() if item.get("mission_id") == linked_id),
        None,
    )
    if not mission:
        return str(linked_id)
    return str(mission.get("name") or linked_id)


def _render_mission_link(opportunity: dict, creator: dict) -> None:
    mission_records = state_store.missions()
    if not mission_records:
        st.caption(t("No launch missions are available to link."))
        return
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
        t("Linked launch mission"),
        mission_labels,
        index=mission_labels.index(default_label),
        key=f"opportunity_mission_{opportunity['opportunity_id']}",
    )
    if st.button(
        t("Link mission and preserve opportunity evidence"),
        use_container_width=True,
        disabled=writes_locked(),
    ):
        state_store.link_opportunity_to_mission(
            opportunity["opportunity_id"], mission_by_label[selected_mission]
        )
        state_store.set_active_context("opportunity", opportunity["opportunity_id"])
        st.success(t("Mission linked; the Creator Opportunity remains the active root context."))
        st.rerun()

    if not current_mission_id and st.button(
        t("Create a launch mission from this opportunity"),
        use_container_width=True,
        disabled=writes_locked(),
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
        }
        state_store.save_mission(generated_mission)
        state_store.link_opportunity_to_mission(opportunity["opportunity_id"], mission_id)
        state_store.set_active_context("opportunity", opportunity["opportunity_id"])
        st.success(t("Draft mission created and linked without changing the Opportunity root."))
        st.rerun()


def _inbound_rows(opportunities: list[dict]) -> list[dict]:
    return [item for item in opportunities if item.get("opportunity_type") == "inbound"]


def _signal_rows(opportunities: list[dict]) -> list[dict]:
    return [item for item in opportunities if item.get("opportunity_type") != "inbound"]


def _render_inbound_kpis(inbound: list[dict]) -> None:
    high = sum(1 for item in inbound if item.get("high_potential"))
    sla = sum(1 for item in inbound if item.get("sla_risk"))
    held = sum(1 for item in inbound if item.get("inbound_status") == "held")
    md(
        mini_kpis(
            [
                (t("Inbound corpus"), str(len(inbound)), t("Synthetic mail · not a live mailbox")),
                (t("High potential"), str(high), t("Score ≥ 75 · not spam or impersonation")),
                (t("SLA risk"), str(sla), t("Older unanswered items in the demo clock")),
                (t("Held"), str(held), t("Brand-safety queue · no reply")),
            ]
        ),
        unsafe_allow_html=True,
    )


def _render_inbound_list(opportunities: list[dict], creators_by_id: dict[str, dict]) -> None:
    md("#### " + t("Creator Opportunity Inbox"))
    languages = sorted({item.get("language") for item in opportunities if item.get("language")})
    personas = sorted({item.get("persona") for item in opportunities if item.get("persona")})
    f1, f2 = st.columns(2)
    language = f1.selectbox(t("Language"), ["All", *languages], key="inbound_language_filter")
    persona = f2.selectbox(t("Persona"), ["All", *personas], key="inbound_persona_filter")
    filtered = [
        item
        for item in opportunities
        if (language == "All" or item.get("language") == language)
        and (persona == "All" or item.get("persona") == persona)
    ]
    if not filtered:
        st.info(t("No inbound messages match the selected filters."))
        return
    for opportunity in filtered:
        creator = creators_by_id.get(opportunity.get("creator_id"), {})
        name = (
            creator.get("creator_name")
            or opportunity.get("sender_name")
            or opportunity.get("creator_id")
            or t("New creator")
        )
        is_selected = opportunity["opportunity_id"] == st.session_state.opportunity_detail_id
        tone = "red" if opportunity.get("inbound_status") == "held" else (
            "green" if opportunity.get("high_potential") else "gray"
        )
        with st.container(border=True):
            summary, meta, action = st.columns([0.56, 0.24, 0.20], vertical_alignment="center")
            with summary:
                md(
                    f"**{esc(name)}**  \n"
                    f"{esc(opportunity.get('collaboration_type') or opportunity['title'])} · "
                    f"{esc(opportunity.get('market') or '')}  \n"
                    f"<small>{esc(opportunity['opportunity_id'])} · {esc(opportunity.get('source_channel') or opportunity.get('source') or '')}"
                    f"{' · SLA' if opportunity.get('sla_risk') else ''}</small>",
                    unsafe_allow_html=True,
                )
            with meta:
                score = opportunity.get("opportunity_score")
                md(
                    badge(
                        f"{int(round(float(score)))}" if score is not None else t("Unscored"),
                        tone,
                    ),
                    unsafe_allow_html=True,
                )
                st.caption(_status_label(str(opportunity.get("inbound_status") or opportunity["status"])))
            with action:
                label = t("Selected") if is_selected else t("View")
                if st.button(
                    label,
                    key=f"select_{opportunity['opportunity_id']}",
                    disabled=is_selected,
                    use_container_width=True,
                ):
                    st.session_state.opportunity_detail_id = opportunity["opportunity_id"]
                    st.rerun()


def _render_inbound_extract(opportunity: dict) -> None:
    md("**" + t("Original message") + "**")
    st.text(opportunity.get("raw_content") or t("Original message was not retained."))
    md("**" + t("AI translated") + "**")
    st.caption(t("Pre-authored synthetic translation. Not a live mailbox translator."))
    st.write(opportunity.get("translated_content") or "")
    if opportunity.get("summary"):
        md("**" + t("30-word summary") + "**")
        st.write(opportunity["summary"])
    md("**" + t("AI extracted fields") + "**")
    st.caption(t("Deterministic labeled-footer parse. Not an LLM extractor."))
    facts = st.columns(4)
    facts[0].metric(t("Intent"), opportunity.get("collaboration_type") or "—")
    facts[1].metric(t("Market / language"), f"{opportunity.get('market') or '—'} / {opportunity.get('language') or '—'}")
    price = opportunity.get("asking_price_usd")
    facts[2].metric(t("Asking price"), f"USD {price:g}" if price not in (None, "") else "—")
    facts[3].metric(t("Availability"), opportunity.get("availability") or "—")
    identity = opportunity.get("identity_status") or "unknown"
    md(
        badge(_status_label(identity), "red" if identity in {"impersonation", "spam"} else "blue")
        + " "
        + badge(_status_label(str(opportunity.get("persona") or "")), "gray"),
        unsafe_allow_html=True,
    )
    breakdown = opportunity.get("score_breakdown") or {}
    if breakdown:
        md("**" + t("Opportunity score") + f": {opportunity.get('opportunity_score', '—')}**")
        md(
            scorebar(t("Intent"), float(breakdown.get("intent_strength") or 0))
            + scorebar(t("Content fit"), float(breakdown.get("content_fit") or 0))
            + scorebar(t("Commercial fit"), float(breakdown.get("commercial_fit") or 0))
            + scorebar(t("Brand safety"), float(breakdown.get("brand_safety") or 0)),
            unsafe_allow_html=True,
        )
    mission_id = opportunity.get("recommended_mission_id")
    mission = next(
        (item for item in state_store.missions() if item.get("mission_id") == mission_id),
        None,
    )
    md("**" + t("Recommended mission") + "**")
    st.write(mission.get("name") if mission else t("Not linked"))
    st.caption(t("Evidence-grounded reverse match"))
    md("**" + t("Recommended owner") + "**")
    st.write(opportunity.get("recommended_owner") or opportunity.get("owner") or "—")
    if opportunity.get("reply_draft"):
        md("**" + t("Reply draft") + "**")
        st.caption(t("Local reply draft · external send is disabled in this MVP"))
        st.code(opportunity["reply_draft"])


def _render_inbound_actions(opportunity: dict) -> None:
    locked = writes_locked()
    if opportunity.get("recommended_mission_id") and not opportunity.get("linked_mission_id"):
        if st.button(
            t("Link recommended mission"),
            use_container_width=True,
            disabled=locked,
            key=f"inbound_link_{opportunity['opportunity_id']}",
        ):
            try:
                state_store.link_opportunity_to_mission(
                    opportunity["opportunity_id"], opportunity["recommended_mission_id"]
                )
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.success(t("Mission link saved with score, evidence and model version."))
                st.rerun()
    owner_options = list(OWNERS)
    current_owner = opportunity.get("owner") or owner_options[0]
    if current_owner not in owner_options:
        owner_options = [current_owner, *owner_options]
    selected_owner = st.selectbox(
        t("Assign owner"),
        owner_options,
        index=owner_options.index(current_owner),
        key=f"inbound_owner_{opportunity['opportunity_id']}",
    )
    if st.button(
        t("Assign owner"),
        use_container_width=True,
        disabled=locked or selected_owner == opportunity.get("owner"),
        key=f"inbound_assign_{opportunity['opportunity_id']}",
    ):
        try:
            state_store.assign_inbound_owner(
                opportunity["opportunity_id"],
                selected_owner,
                actor=str(opportunity.get("owner") or "Operator"),
            )
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        else:
            st.success(t("Owner assigned; routing decision added to the audit trail."))
            st.rerun()
    if st.button(
        t("Generate local reply"),
        use_container_width=True,
        disabled=locked or opportunity.get("inbound_status") == "held",
        key=f"inbound_reply_{opportunity['opportunity_id']}",
    ):
        try:
            state_store.generate_inbound_reply(opportunity["opportunity_id"])
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        else:
            st.success(t("Local reply draft · external send is disabled in this MVP"))
            st.rerun()
    if st.button(
        t("Approve draft for Outreach"),
        type="primary",
        use_container_width=True,
        disabled=locked or opportunity.get("identity_status") != "matched",
        key=f"inbound_approve_{opportunity['opportunity_id']}",
    ):
        try:
            state_store.approve_inbound_for_outreach(
                opportunity["opportunity_id"],
                actor=str(opportunity.get("owner") or "Operator"),
                reason="Inbound reply draft approved internally; nothing sent externally.",
            )
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        else:
            st.success(t("Approved draft is now visible in Outreach Operations. Nothing was sent externally."))
            st.rerun()
    st.button(
        t("Send to Creator"),
        use_container_width=True,
        disabled=True,
        help=t("External send is not wired in this demo"),
        key=f"inbound_send_{opportunity['opportunity_id']}",
    )
    st.caption(t("Human approval required before any external reply, price commitment or mission assignment."))


def _render_list(opportunities: list[dict], creators_by_id: dict[str, dict]) -> None:
    md("#### Opportunity pipeline")
    filter_left, filter_right = st.columns(2)
    status_options = ["All", *[_status_label(status) for status in OPPORTUNITY_STATUSES]]
    selected_status = filter_left.selectbox(
        t("Status"), status_options, key="opportunity_status_filter"
    )
    markets = sorted({item["market"] for item in opportunities if item.get("market")})
    selected_market = filter_right.selectbox(
        t("Market"), ["All", *markets], key="opportunity_market_filter"
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
                md(
                    f"**{esc(opportunity['title'])}**  \n"
                    f"{esc(creator_name)} · {esc(opportunity['market'])} · "
                    f"{esc(opportunity['language'])}  \n"
                    f"<small>{esc(opportunity['opportunity_id'])} · {esc(opportunity['source'])}</small>",
                    unsafe_allow_html=True,
                )
            with status_col:
                md(
                    badge(_status_label(opportunity["status"]), _status_tone(opportunity["status"])),
                    unsafe_allow_html=True,
                )
                if (
                    _is_opportunity_context()
                    and st.session_state.get("active_opportunity_id")
                    == opportunity["opportunity_id"]
                ):
                    st.caption(t("Active context"))
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
    creator_name = (
        creator.get("creator_name")
        or opportunity.get("sender_name")
        or opportunity.get("creator_id")
        or t("New creator")
    )
    md("#### Opportunity detail")
    with st.container(border=True):
        title_col, action_col = st.columns([0.72, 0.28], vertical_alignment="top")
        with title_col:
            md(f"### {esc(opportunity['title'])}", unsafe_allow_html=True)
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
                t("Active opportunity") if is_active else t("Activate opportunity"),
                type="primary",
                disabled=is_active,
                use_container_width=True,
            ):
                _activate_opportunity(opportunity["opportunity_id"])
                st.success(t("Creator Opportunity is now the active workspace context."))
                st.rerun()

        facts = st.columns(5)
        facts[0].metric(t("Type"), _status_label(opportunity["opportunity_type"]))
        facts[1].metric(t("Status"), _status_label(opportunity["status"]))
        facts[2].metric(t("Source"), opportunity["source"])
        facts[3].metric(t("Owner"), opportunity["owner"])
        facts[4].metric(t("Linked mission"), _linked_mission_label(opportunity))

        if opportunity.get("opportunity_type") == "inbound":
            _render_inbound_extract(opportunity)
            _render_inbound_actions(opportunity)
            st.divider()

        md("**Opportunity hypothesis**")
        st.write(opportunity["hypothesis"])
        md("**Evidence**")
        if opportunity["evidence"]:
            for item in opportunity["evidence"]:
                md(f"- {esc(item)}", unsafe_allow_html=True)
        else:
            st.caption(t("No evidence has been recorded yet."))

        md("**Suggested next action**")
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
            creator_id = str(opportunity.get("creator_id") or "").strip()
            if not creator_id:
                st.caption(
                    t("New and unmatched senders stay in the inbox until a catalog profile exists.")
                )
            else:
                current_state = state_store.creator_state(creator_id)
                md(f"**{t('Collaboration state')}:** `{_status_label(current_state)}`")
                target = state_store.next_linear_creator_state(creator_id)
                jump_page = opportunity_cta_page(creator_id)
                reason = st.text_input(
                    t("Transition reason"),
                    "Opportunity evidence reviewed by the owner",
                    key=f"opportunity_reason_{opportunity['opportunity_id']}",
                )
                if jump_page == "growth-review":
                    st.info(t("Record a conversion on Growth Review"))
                    st.caption(t("Mark measured only after recording events"))
                elif jump_page == "content-studio":
                    st.info(t("Create a brief in Content Studio"))
                    st.caption(t("Save a brief before advancing to published"))
                elif target == "measured":
                    st.caption(t("Mark measured only after recording events"))
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
                        key=f"opportunity_jump_{opportunity['opportunity_id']}",
                    ):
                        open_opportunity_cta(creator_id, creator_name=creator_name)
                advance_label = (
                    t("Advance to {state}", state=_status_label(target))
                    if target
                    else t("No next legal hop")
                )
                if st.button(
                    advance_label,
                    type="primary" if not jump_page else "secondary",
                    use_container_width=True,
                    disabled=writes_locked() or not target,
                    key=f"opportunity_advance_{opportunity['opportunity_id']}",
                ):
                    try:
                        record = advance_opportunity_creator(
                            creator_id,
                            actor=opportunity["owner"],
                            reason=reason,
                            evidence=opportunity["evidence"] or ["opportunity://manual-review"],
                        )
                    except PermissionError as exc:
                        st.error(str(exc))
                    except ValueError as exc:
                        if state_store.MEASURED_REQUIRES_EVENTS in str(exc):
                            st.info(str(exc))
                        else:
                            st.error(str(exc))
                    else:
                        st.success(
                            t(
                                "Advanced to {state} with an audit event.",
                                state=_status_label(record["state"]),
                            )
                        )
                        st.rerun()
                if "closed_lost" in state_store.allowed_next_creator_states(creator_id):
                    if st.button(
                        t("Reject"),
                        use_container_width=True,
                        disabled=writes_locked(),
                        key=f"opportunity_reject_{opportunity['opportunity_id']}",
                    ):
                        try:
                            state_store.save_decision(
                                creator_id,
                                "Rejected",
                                reason,
                                reason_code="opportunity_rejected",
                                note=opportunity["suggested_action"],
                                evidence=opportunity["evidence"],
                            )
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))
                        else:
                            st.success(t("Rejection recorded with a reason code."))
                            st.rerun()
                st.caption(t("Audit timeline"))
                md(
                    _audit_timeline(state_store.workflow_events_for(creator_id)),
                    unsafe_allow_html=True,
                )

        st.divider()
        _render_mission_link(opportunity, creator)


def _render_create_form(creators: list[dict]) -> None:
    with st.expander(t("Create Opportunity"), expanded=False):
        creator_options = {
            f"{record['creator_name']} · {record['creator_id']}": str(record["creator_id"])
            for record in creators
        }
        current_mission_id = st.session_state.get("active_mission_id")
        with st.form("create_creator_opportunity", clear_on_submit=False):
            c1, c2 = st.columns(2)
            creator_label = c1.selectbox(t("Creator"), list(creator_options))
            title = c2.text_input(t("Opportunity title"))
            source = c1.text_input(t("Source"), placeholder=t("Social listening, nomination, inbound…"))
            owner = c2.text_input(t("Owner"), placeholder=t("Team or operator"))
            opportunity_type = c1.selectbox(
                t("Opportunity type"),
                ["social_signal", "performance_signal", "regional_nomination", "inbound"],
            )
            market = c1.text_input(t("Market"))
            language = c2.text_input(t("Language"))
            hypothesis = st.text_area(
                t("Hypothesis"),
                placeholder=t("Why is this creator an opportunity, and what should the team test?"),
            )
            evidence = st.text_area(
                t("Evidence"),
                placeholder=t("Enter one evidence item per line."),
            )
            suggested_action = st.text_input(
                t("Suggested next action"),
                "Review evidence and qualify the opportunity",
            )
            link_to_mission = st.checkbox(
                t("Link to the current mission"),
                value=False,
                disabled=not bool(current_mission_id),
            )
            submitted = st.form_submit_button(
                "Create opportunity",
                type="primary",
                use_container_width=True,
                disabled=writes_locked(),
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
                st.success(
                    t(
                        "Created {opportunity_id} and set it as the active workspace context.",
                        opportunity_id=opportunity["opportunity_id"],
                    )
                )
                st.rerun()


def _render_scout_cards(opportunities: list[dict]) -> None:
    exclude = {str(item.get("creator_id") or "") for item in opportunities if item.get("creator_id")}
    cards = scout_cards(state_store.creators(), exclude_ids=exclude)
    with st.expander(t("Always-on scout cards"), expanded=False):
        st.caption(
            t("Catalog momentum proxies (7d ≈ inverted decline, 30d ≈ engagement, 90d ≈ consistency). Not a live crawl.")
        )
        if not cards:
            st.info(t("No additional scout cards in this catalog."))
            return
        for card in cards:
            row, action = st.columns([0.78, 0.22], vertical_alignment="center")
            row.markdown(
                f"**{card['creator_name']}** · {card['creator_id']}  \n"
                f"{card['market']} · {card.get('genome_id') or 'no genome'} · scout {card['scout_score']} · "
                f"7d {card['window_7d']} · 30d {card['window_30d']} · 90d {card['window_90d']}"
            )
            if action.button(
                t("Save as opportunity"),
                key=f"scout_save_{card['creator_id']}",
                disabled=writes_locked(),
                use_container_width=True,
            ):
                try:
                    opportunity = create_opportunity(
                        st.session_state.opportunities,
                        creator_id=card["creator_id"],
                        title=f"Scout: {card['creator_name']}",
                        source="catalog_momentum",
                        market=card["market"] or "United States",
                        language=card.get("language") or "English",
                        hypothesis="Catalog momentum proxy rose on 7/30/90 windows. Not a live crawl.",
                        evidence=[card["note"], f"scout_score={card['scout_score']}"],
                        owner="Scout desk",
                        opportunity_type="creator_signal",
                        suggested_action="Qualify this scout card against the active launch mission.",
                    )
                    state_store.save_opportunity(opportunity)
                    st.session_state.opportunity_detail_id = opportunity["opportunity_id"]
                    st.success(t("Saved scout card as {opportunity_id}.", opportunity_id=opportunity["opportunity_id"]))
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))


def render() -> None:
    render_topbar()
    _bootstrap_opportunity_state()
    creators, creators_by_id = _creator_records()
    opportunities = list(st.session_state.opportunities)
    inbound = _inbound_rows(opportunities)
    signals = _signal_rows(opportunities)

    selected = find_opportunity(opportunities, st.session_state.opportunity_detail_id)
    active = find_opportunity(opportunities, st.session_state.get("active_opportunity_id"))

    header_left, header_right = st.columns([0.7, 0.3], vertical_alignment="top")
    with header_left:
        md(
            page_header(
                "Creator Opportunity",
                "Turn inbound creator messages into translated, scored, routed and mission-linked opportunities.",
                "Inbound · Brand-led",
            ),
            unsafe_allow_html=True,
        )
        st.caption(_context_caption(active))
        st.caption(
            t(
                "Synthetic 30-message corpus (EN / ES / DE). Not a live mailbox. Extraction is a labeled footer. Translation is pre-authored. Send stays disabled."
            )
        )
        render_write_guard()
    with header_right:
        st.metric(t("Open opportunities"), len(opportunities))
        if st.button(
            t("Import email"),
            use_container_width=True,
            disabled=writes_locked(),
            help=t("Reload the synthetic inbound corpus. Does not connect a mailbox."),
        ):
            try:
                imported = state_store.import_inbound_corpus()
            except PermissionError as exc:
                st.error(str(exc))
            else:
                st.success(
                    t("Imported {n} synthetic inbound messages.", n=imported["imported"])
                )
                st.rerun()
        st.caption(t("Auto parse: ON"))

    if inbound:
        _render_inbound_kpis(inbound)

    _render_scout_cards(opportunities)
    _render_create_form(creators)
    list_col, detail_col = st.columns([0.48, 0.52], gap="small", vertical_alignment="top")
    with list_col:
        if inbound:
            _render_inbound_list(inbound, creators_by_id)
        with st.expander(t("Non-email signals"), expanded=not inbound):
            _render_list(signals, creators_by_id)
    with detail_col:
        if selected:
            _render_detail(selected, creators_by_id.get(selected.get("creator_id")))
        else:
            st.info("Create an opportunity to begin the creator-first workflow.")

    render_demo_notice()
