from __future__ import annotations

import streamlit as st

from components.html import avatar, badge, esc, mission_chip, page_header
from components.i18n import t
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    CONTACT_PACK_STATES,
    MEASURED_REQUIRES_EVENTS,
    active_context,
    active_context_label,
    contact_pack_for,
    content_assets_in_review_count,
    format_contact_pack,
    live_evidence_for,
    next_linear_creator_state,
    next_outreach_action_page,
    prepare_growth_review_record,
    refresh_outreach_message,
    select_creator,
    transition_creator_state,
    workflow_board,
    workflow_events,
    workflow_events_for,
)
from components.ui import labels, md


STAGE_TONES = {
    "shortlisted": "gray",
    "approved": "blue",
    "contacted": "yellow",
    "negotiating": "orange",
    "contracted": "green",
    "content_in_review": "blue",
    "published": "green",
    "measured": "green",
    "closed_lost": "gray",
}


def _stage_label(stage: str) -> str:
    return stage.replace("_", " ").title()


def _next_action_label(person: dict) -> str:
    page = next_outreach_action_page(person["creator_id"])
    if page == "growth-review":
        return t("Record a conversion on Growth Review")
    if page == "content-studio":
        return t("Create a brief in Content Studio")
    target = person.get("next_state")
    if not target:
        target = next(
            (state for state in person.get("next_states", []) if state != "closed_lost"),
            None,
        )
    if not target:
        return t("Complete")
    return _stage_label(target)


def _open_next_action_page(person: dict, page: str) -> None:
    if page == "growth-review":
        prepare_growth_review_record(
            person["creator_id"],
            choice_label=f'{person["creator_name"]} · {person["creator_id"]}',
        )
        open_workspace_page("growth-review")
        return
    select_creator(person["creator_id"])
    open_workspace_page("content-studio")


def _kanban(board: dict[str, list[dict]]) -> str:
    columns = []
    color_idx = 0
    for stage, people in board.items():
        cards = []
        for person in people:
            name = person["creator_name"]
            topics = " · ".join(person.get("topics", [])[:2]) or "Creator"
            market = person.get("primary_market", "—")
            followers = f'{int(person.get("followers", 0)) / 1000:.0f}K'
            next_action = _next_action_label(person)
            live_n = len(live_evidence_for(person["creator_id"]))
            live_line = (
                f'<div class="is-kanban-next">{esc(t("Live evidence: {n} attached", n=live_n))}</div>'
                if live_n
                else ""
            )
            pack_line = ""
            if person.get("state") in CONTACT_PACK_STATES and person.get("coupon"):
                preview = (person.get("outreach_message") or "").splitlines()
                preview_text = next((line for line in preview if line.strip()), t("Copy below"))
                pack_line = (
                    f'<div class="is-kanban-next">{esc(t("Contact pack"))}: '
                    f'{esc(preview_text[:72])}</div>'
                )
            cards.append(
                '<div class="is-kanban-card">'
                f'<div class="is-kanban-person">{avatar(name, color_idx)}'
                f'<span><b>{esc(name)}</b><small>{esc(person["creator_id"])}</small></span></div>'
                f'<div class="is-kanban-tags">{badge(topics, "gray")} {badge(market, "blue")}</div>'
                f'<div class="is-kanban-meta"><span>Market</span><strong>{esc(market)}</strong>'
                f'<span>Audience</span><strong>{esc(followers)}</strong>'
                f'<span>Case</span><strong>{esc(person.get("outreach_case_id", "Pending approval"))}</strong>'
                f'<span>Coupon</span><strong>{esc(person.get("coupon") or "Issued on approve")}</strong>'
                f'<span>Owner</span><strong>{esc(person.get("owner", "Not assigned"))}</strong></div>'
                f'{live_line}{pack_line}'
                f'<div class="is-kanban-next">Next: {esc(next_action)} →</div></div>'
            )
            color_idx += 1
        tone = STAGE_TONES.get(stage, "gray")
        label = _stage_label(stage)
        columns.append(
            '<div class="is-kanban-col">'
            f'<div class="is-kanban-head"><span style="display:flex;align-items:center;gap:6px">'
            f'{esc(label)} {badge(label.split()[0], tone)}</span>'
            f'<span class="is-kanban-count">{len(people)}</span></div>{"".join(cards)}</div>'
        )
    if not columns:
        return '<div class="is-card is-card-pad">No creators have entered this workflow yet.</div>'
    return '<div style="overflow-x:auto"><div class="is-kanban">' + "".join(columns) + "</div></div>"


def _list_view(board: dict[str, list[dict]]) -> str:
    rows = []
    for stage, people in board.items():
        for person in people:
            name = person["creator_name"]
            topics = " · ".join(person.get("topics", [])[:2]) or "Creator"
            next_action = _next_action_label(person)
            rows.append(
                "<tr>"
                f'<td><div class="is-creator-cell">{avatar(name, len(rows))}'
                f'<span><b>{esc(name)}</b><small>{esc(topics)}</small></span></div></td>'
                f'<td>{esc(_stage_label(stage))}</td>'
                f'<td>{esc(person.get("primary_market", "—"))}</td>'
                f'<td>{esc(person.get("outreach_case_id", "Pending approval"))}</td>'
                f'<td>{esc(person.get("owner", "Not assigned"))}</td>'
                f'<td><span class="is-panel-link">{esc(next_action)} →</span></td></tr>'
            )
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Stage", "Market", "OutreachCase", "Owner", "Next action"])
    return (
        f'<div class="is-card is-card-pad"><table class="is-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _event_log(events: list[dict]) -> str:
    if not events:
        return '<div class="is-card is-card-pad">No workflow events recorded for this entry.</div>'
    cards = []
    for event in reversed(events[-12:]):
        cards.append(
            '<div class="is-card is-card-pad">'
            f'<div class="is-card-title">{esc(event["creator_id"])} · '
            f'{esc(_stage_label(event["from_state"]))} → {esc(_stage_label(event["to_state"]))}</div>'
            f'<div class="is-card-caption">{esc(event["reason"])} · {esc(event["actor"])} · '
            f'{esc(event["occurred_at"])}</div></div>'
        )
    return '<div class="is-grid-3">' + "".join(cards) + "</div>"


def _audit_timeline(events: list[dict]) -> str:
    if not events:
        return '<div class="is-card is-card-pad">No workflow events recorded for this creator.</div>'
    cards = []
    for event in reversed(events):
        stamp = event.get("occurred_at") or event.get("timestamp") or ""
        cards.append(
            '<div class="is-card is-card-pad">'
            f'<div class="is-card-title">{esc(_stage_label(event["from_state"]))} → '
            f'{esc(_stage_label(event["to_state"]))}</div>'
            f'<div class="is-card-caption">{esc(stamp)} · {esc(event["reason"])} · '
            f'{esc(event["actor"])}</div></div>'
        )
    return "".join(cards)


def _pack_people(board: dict[str, list[dict]]) -> list[dict]:
    people = []
    for stage, items in board.items():
        if stage in CONTACT_PACK_STATES:
            people.extend(items)
    return people


def _render_contact_pack(person: dict, *, key_prefix: str) -> None:
    creator_id = person["creator_id"]
    try:
        pack = contact_pack_for(creator_id)
    except ValueError:
        st.caption(t("No outreach contact pack until a creator is approved."))
        return
    source = pack.get("source") or ""
    tone = pack.get("tone") or ""
    caption = t("Copy pack")
    if source or tone:
        caption = f"{caption} · {source} · {tone}".strip(" ·")
    st.caption(caption)
    st.code(format_contact_pack(pack))
    if pack.get("brief_excerpt"):
        st.caption(f'{t("Brief excerpt")}: {pack["brief_excerpt"][:120]}')
    else:
        st.caption(t("No brief saved yet"))
    if writes_locked():
        render_write_guard()
    actions = st.columns(2)
    with actions[0]:
        if st.button(
            t("Refresh outreach message"),
            use_container_width=True,
            disabled=writes_locked(),
            key=f"{key_prefix}_refresh_{creator_id}",
        ):
            try:
                refresh_outreach_message(creator_id)
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.success(t("Outreach message refreshed. Nothing was sent externally."))
                st.rerun()
    with actions[1]:
        st.button(
            t("Send to Creator"),
            use_container_width=True,
            disabled=True,
            help=t("External send is not wired in this demo"),
            key=f"{key_prefix}_send_{creator_id}",
        )


def render() -> None:
    render_topbar()
    context = active_context()
    board = workflow_board()

    head_l, head_r = st.columns([1, 0.4], vertical_alignment="top")
    with head_l:
        md(
            page_header(
                "Outreach Operations",
                "Move creators through one governed workflow with auditable state changes.",
                "Execution collaboration",
            ),
            unsafe_allow_html=True,
        )
        md(mission_chip(active_context_label()), unsafe_allow_html=True)
        in_review_n = content_assets_in_review_count()
        st.caption(t("Content assets in review: {n}", n=in_review_n))
        if any(
            next_outreach_action_page(person["creator_id"]) == "growth-review"
            for people in board.values()
            for person in people
        ):
            st.caption(t("Record a conversion on Growth Review"))
    with head_r:
        people = [person for stage in board.values() for person in stage]
        if people:
            creator_by_label = {
                f'{person["creator_name"]} · {_stage_label(person["state"])}': person
                for person in people
            }
            labels = list(creator_by_label)
            jumped = bool(st.session_state.pop("outreach_focus_creator_id", None))
            selected_id = st.session_state.get("selected_creator_id")
            preferred = next(
                (label for label, person in creator_by_label.items() if person["creator_id"] == selected_id),
                labels[0],
            )
            current_choice = st.session_state.get("outreach_creator_workflow")
            if jumped or current_choice not in creator_by_label:
                st.session_state["outreach_creator_workflow"] = preferred
            selected_label = st.selectbox(t("Creator workflow"), labels, key="outreach_creator_workflow")
            selected = creator_by_label[selected_label]
            select_creator(selected["creator_id"])
            target = next_linear_creator_state(selected["creator_id"])
            jump_page = next_outreach_action_page(selected["creator_id"])
            if jump_page == "growth-review":
                st.info(t("Record a conversion on Growth Review"))
                st.caption(t("Mark measured only after recording events"))
            elif jump_page == "content-studio":
                st.info(t("Create a brief in Content Studio"))
                st.caption(t("Save a brief before advancing to published"))
            reason = st.text_input(t("Transition reason"), "Operator completed the required review")
            render_write_guard()
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
                    key="jump_selected_creator",
                ):
                    _open_next_action_page(selected, jump_page)
            advance_label = (
                t("Advance to {state}", state=_stage_label(target))
                if target
                else t("No next legal hop")
            )
            if st.button(
                advance_label,
                type="primary" if not jump_page else "secondary",
                use_container_width=True,
                disabled=writes_locked() or not target,
                key="advance_selected_creator",
            ):
                try:
                    transition_creator_state(
                        selected["creator_id"],
                        target,
                        actor=context.get("owner", "Operator"),
                        reason=reason,
                        evidence=[f'outreach://{selected.get("outreach_case_id", "workflow-review")}'],
                    )
                except PermissionError as exc:
                    st.error(str(exc))
                except ValueError as exc:
                    if MEASURED_REQUIRES_EVENTS in str(exc):
                        st.info(str(exc))
                    else:
                        st.error(str(exc))
                else:
                    st.success(t("Advanced to {state} with an audit event.", state=_stage_label(target)))
                    st.rerun()
            st.caption(t("Audit timeline"))
            md(_audit_timeline(workflow_events_for(selected["creator_id"])), unsafe_allow_html=True)
            if selected.get("state") in CONTACT_PACK_STATES:
                st.caption(t("Generate a copyable outreach pack. Nothing is sent externally."))
                _render_contact_pack(selected, key_prefix="selected")
            elif selected.get("coupon"):
                st.caption(f'{t("Coupon")}: {selected["coupon"]}')
                st.caption(selected.get("deeplink", ""))

    tabs = st.tabs(labels(["Workflow Board", "List", "Audit Log", "Stage Metrics"]))
    with tabs[0]:
        md(_kanban(board), unsafe_allow_html=True)
        pack_people = _pack_people(board)
        if pack_people:
            st.subheader(t("Contact packs"))
            st.caption(t("Use the copy control on the pack. External send stays disabled."))
            for person in pack_people:
                title = f'{person["creator_name"]} · {t("Contact pack")}'
                with st.expander(title, expanded=False):
                    _render_contact_pack(person, key_prefix="board")
        else:
            st.caption(t("No outreach contact pack until a creator is approved."))
    with tabs[1]:
        md(_list_view(board), unsafe_allow_html=True)
    with tabs[2]:
        md(_event_log(workflow_events()), unsafe_allow_html=True)
    with tabs[3]:
        metrics = [(_stage_label(stage), str(len(people)), "Current entry") for stage, people in board.items()]
        metrics.insert(0, ("Content assets in review", str(content_assets_in_review_count()), "Saved briefs · 0 is honest"))
        if len(metrics) == 1:
            metrics.append(("Workflow records", "0", "Start by shortlisting a creator"))
        md(
            '<div class="is-grid-4">'
            + "".join(
                f'<div class="is-metric"><div class="is-metric-label">{esc(label)}</div>'
                f'<div class="is-metric-value">{esc(value)}</div><div class="is-metric-delta">{esc(note)}</div></div>'
                for label, value, note in metrics
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    render_demo_notice()
