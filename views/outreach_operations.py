from __future__ import annotations

import streamlit as st

from components.html import avatar, badge, esc, mission_chip, page_header
from components.i18n import t
from components.shell import render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_context,
    active_context_label,
    allowed_next_creator_states,
    content_assets_in_review_count,
    live_evidence_for,
    transition_creator_state,
    workflow_board,
    workflow_events,
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
            next_states = person.get("next_states", [])
            next_action = _stage_label(next_states[0]) if next_states else "Complete"
            live_n = len(live_evidence_for(person["creator_id"]))
            live_line = (
                f'<div class="is-kanban-next">{esc(t("Live evidence: {n} attached", n=live_n))}</div>'
                if live_n
                else ""
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
                f'{live_line}'
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
            next_states = person.get("next_states", [])
            next_action = _stage_label(next_states[0]) if next_states else "Complete"
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
        if board.get("measured"):
            st.caption(t("Record the conversion on Growth Review"))
    with head_r:
        people = [person for stage in board.values() for person in stage]
        if people:
            creator_by_label = {
                f'{person["creator_name"]} · {_stage_label(person["state"])}': person
                for person in people
            }
            selected_label = st.selectbox(t("Creator workflow"), list(creator_by_label))
            selected = creator_by_label[selected_label]
            next_states = allowed_next_creator_states(selected["creator_id"])
            if next_states:
                target = st.selectbox(t("Next state"), next_states, format_func=_stage_label)
                reason = st.text_input(t("Transition reason"), "Operator completed the required review")
                render_write_guard()
                if st.button(
                    t("Advance workflow"),
                    type="primary",
                    use_container_width=True,
                    disabled=writes_locked(),
                ):
                    try:
                        transition_creator_state(
                            selected["creator_id"],
                            target,
                            actor=context.get("owner", "Operator"),
                            reason=reason,
                            evidence=[f'outreach://{selected.get("outreach_case_id", "workflow-review")}'],
                        )
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
                    else:
                        st.success(f'Advanced to {_stage_label(target)} with an audit event.')
                        st.rerun()
            if selected.get("coupon"):
                st.caption(f'{t("Coupon")}: {selected["coupon"]}')
                st.caption(selected.get("deeplink", ""))

    tabs = st.tabs(labels(["Workflow Board", "List", "Audit Log", "Stage Metrics"]))
    with tabs[0]:
        md(_kanban(board), unsafe_allow_html=True)
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
