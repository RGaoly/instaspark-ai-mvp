from __future__ import annotations

import streamlit as st

from components.html import esc, mission_chip, page_header
from components.positioning import rubric_scorecard_html
from components.i18n import t
from components.shell import open_workspace_page, render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import (
    active_context,
    active_context_label,
    active_mission,
    active_score_weights,
    apply_calibrator_weights,
    creator_state,
    creators,
    performance_events,
    ranking,
    record_performance_event,
    select_creator,
    tracking_assets,
    workflow_board,
    workflow_summary,
)
from components.ui import md
from src.domain import PERIOD_WINDOW_DAYS, attributed_roi, filter_dated_records, filter_performance_events
from src.content_evidence import load_creator_content
from src.evaluation import acceptance_matrix
from src.budget import propose_budget_decision
from src.benchmark import load_report
from src.business_value import compute as compute_business_value
from src.calibrator import propose as propose_calibration
from src.landing_path import landing_path
from src.rubric_scorecard import prove as prove_rubric

_OUTREACH_STATES = {
    "approved",
    "contacted",
    "negotiating",
    "contracted",
    "content_in_review",
    "published",
    "measured",
}


def _kpi_strip(summary: dict[str, int], events: list[dict], budget: float) -> str:
    orders = sum(int(event.get("orders", 0)) for event in events)
    revenue = sum(float(event.get("revenue_usd", 0)) for event in events)
    spend = sum(float(event.get("spend_usd", 0)) for event in events)
    roi = attributed_roi(events)
    adoption_base = max(sum(summary.values()) - summary.get("closed_lost", 0), 1)
    adopted = sum(summary.get(state, 0) for state in ["approved", "contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])
    metrics = [
        ("Shortlist adoption", f"{adopted / adoption_base:.0%}", "From this entry"),
        ("Contacted", str(summary.get("contacted", 0)), "Audited workflow"),
        ("Published", str(summary.get("published", 0)), "Audited workflow"),
        ("Measured", str(summary.get("measured", 0)), "Performance linked"),
        ("Attributed orders", f"{orders:,}", "Filtered recorded events"),
        ("Revenue", f"${revenue:,.0f}", "Filtered recorded events"),
        ("ROI", f"{roi:.2f}x", "Filtered events only · 0x if empty"),
        ("Budget utilization", f"{spend / budget:.0%}" if budget else "—", f"${spend:,.0f} / ${budget:,.0f}"),
    ]
    return '<div class="is-kpi-strip">' + "".join(
        '<div class="is-kpi-mini">'
        f'<label>{esc(label)}</label><strong>{esc(value)}</strong><small>{esc(note)}</small></div>'
        for label, value, note in metrics
    ) + "</div>"


def _funnel(pool: int, summary: dict[str, int], events: list[dict]) -> str:
    active_from = lambda states: sum(summary.get(state, 0) for state in states)
    steps = [
        ("Candidate pool", pool),
        ("Shortlisted", active_from(["shortlisted", "approved", "contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])),
        ("Contacted", active_from(["contacted", "negotiating", "contracted", "content_in_review", "published", "measured"])),
        ("Published", active_from(["published", "measured"])),
        ("Measured events", len(events)),
    ]
    return '<div class="is-funnel">' + "".join(
        '<div class="is-funnel-step"><div class="is-funnel-shape"></div>'
        f'<b>{esc(label)}</b><small>{value}</small></div>' for label, value in steps
    ) + "</div>"


def _creator_names() -> dict[str, str]:
    return {row["creator_id"]: row["creator_name"] for _, row in creators().iterrows()}


def _creator_label(creator_id: str, names: dict[str, str] | None = None) -> str:
    mapping = names if names is not None else _creator_names()
    name = str(mapping.get(creator_id, "") or "").strip()
    if not name or name == creator_id:
        return creator_id
    return f"{name} · {creator_id}"


def _event_recorded_label(event: dict) -> str:
    stamp = str(event.get("recorded_at") or "").strip()
    return stamp[:10] if stamp else "—"


def _performance_table(events: list[dict], names: dict[str, str] | None = None) -> str:
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Content", "Market", "Recorded", "Orders", "Revenue", "Spend"])
    if not events:
        body = '<tr><td colspan="7">No performance events in this period and market.</td></tr>'
    else:
        body = "".join(
            "<tr>"
            f'<td>{esc(_creator_label(str(event.get("creator_id", "—")), names))}</td>'
            f'<td>{esc(event.get("content_asset_id", "—"))}</td>'
            f'<td>{esc(event.get("market", "—"))}</td>'
            f'<td>{esc(_event_recorded_label(event))}</td>'
            f'<td>{int(event.get("orders", 0)):,}</td>'
            f'<td>${float(event.get("revenue_usd", 0)):,.0f}</td>'
            f'<td>${float(event.get("spend_usd", 0)):,.0f}</td></tr>'
            for event in events
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _tracking_table(assets: list[dict], *, any_issued: bool = True, names: dict[str, str] | None = None) -> str:
    head = "".join(f"<th>{h}</th>" for h in ["Creator", "Market", "Coupon", "UTM campaign", "Deeplink"])
    if not assets:
        if any_issued:
            body = '<tr><td colspan="5">No tracking assets in this period and market.</td></tr>'
        else:
            body = '<tr><td colspan="5">No tracking assets issued yet. Approve outreach to mint a coupon and UTM deeplink.</td></tr>'
    else:
        body = "".join(
            "<tr>"
            f'<td>{esc(_creator_label(str(item.get("creator_id", "—")), names))}</td>'
            f'<td>{esc(item.get("market", "—"))}</td>'
            f'<td>{esc(item.get("coupon", "—"))}</td>'
            f'<td>{esc(item.get("utm_campaign", "—"))}</td>'
            f'<td>{esc(item.get("deeplink", "—"))}</td></tr>'
            for item in assets
        )
    return f'<table class="is-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _recordable_creators() -> list[tuple[str, str, dict]]:
    """Approved / coupon-bearing creators for the active entry, names for the form."""

    assets = {item["creator_id"]: item for item in tracking_assets()}
    names = {row["creator_id"]: row["creator_name"] for _, row in creators().iterrows()}
    ordered: list[str] = []
    for creator_id in assets:
        if creator_id not in ordered:
            ordered.append(creator_id)
    for stage, people in workflow_board().items():
        if stage not in _OUTREACH_STATES:
            continue
        for person in people:
            creator_id = person.get("creator_id")
            if creator_id and creator_id not in ordered:
                ordered.append(creator_id)
    return [(creator_id, names.get(creator_id, creator_id), assets.get(creator_id, {})) for creator_id in ordered]


def _next_actions(context: dict, summary: dict[str, int], events: list[dict], assets: list[dict]) -> str:
    actions = []
    if _needs_outreach(summary):
        actions.append(("blue", "Execute", "Contact approved creators", "Approved creators are waiting for outreach.", "Use the button below"))
    if _needs_conversion(summary, events, assets):
        actions.append(
            (
                "orange",
                "Measure",
                "Record the conversion on Growth Review",
                "Coupons are tracking assets, not conversions. ROI stays 0x until an operator records an event.",
                "Use the button below",
            )
        )
    if not actions:
        actions.append(("green", "On track", "Continue the governed workflow", f'Use evidence from {context.get("title", "this entry")} for the next decision.', "Human review"))
    return '<div class="is-budget-actions">' + "".join(
        f'<div class="is-action-card {tone}"><div><span class="is-badge is-badge-{tone}">{esc(tag)}</span></div>'
        f'<h4>{esc(title)}</h4><p>{esc(body)}</p><div class="is-action-impact">{esc(impact)}</div></div>'
        for tone, tag, title, body, impact in actions
    ) + "</div>"


def _needs_outreach(summary: dict[str, int]) -> bool:
    return any(summary.get(state, 0) for state in _OUTREACH_STATES - {"measured"})


def _needs_conversion(summary: dict[str, int], events: list[dict], assets: list[dict]) -> bool:
    return not events and bool(assets or summary.get("published", 0))


def _render_next_action_buttons(summary: dict[str, int], events: list[dict], assets: list[dict]) -> None:
    outreach = _needs_outreach(summary)
    convert = _needs_conversion(summary, events, assets)
    if not outreach and not convert:
        return
    cols = st.columns(2 if outreach and convert else 1)
    index = 0
    if outreach:
        if cols[index].button(t("Open Outreach"), type="primary", key="growth_go_outreach"):
            open_workspace_page("outreach-operations")
        index += 1
    if convert:
        if cols[index].button(t("Record conversion here"), key="growth_go_record"):
            st.session_state["growth_record_event_open"] = True
            st.rerun()


def _perf_event_label(creator_id: str, name: str) -> str:
    return f"{name} · {creator_id}"


def _prefill_record_form(recordable: list[tuple[str, str, dict]], *, force: bool) -> None:
    labels = [_perf_event_label(creator_id, name) for creator_id, name, _ in recordable]
    selected_id = st.session_state.get("selected_creator_id")
    current = st.session_state.get("perf_event_creator")
    if not force and current in labels:
        return
    if not selected_id:
        return
    for creator_id, name, _ in recordable:
        if creator_id == selected_id:
            st.session_state["perf_event_creator"] = _perf_event_label(creator_id, name)
            return


def _render_post_record_handoff() -> None:
    if st.session_state.pop("growth_event_toast", False):
        if st.session_state.pop("growth_moved_to_measured", False):
            st.toast(t("Performance event recorded. Creator moved to Measured."))
        else:
            st.toast(t("Performance event recorded. ROI uses this event, not a forecast."))
    if not st.session_state.get("growth_open_outreach"):
        return
    if st.button(t("Open Outreach"), type="primary"):
        st.session_state.pop("growth_open_outreach", None)
        open_workspace_page("outreach-operations")


def _render_record_form() -> None:
    expand = bool(st.session_state.pop("growth_record_event_open", False))
    with st.expander(t("Record performance event (demo)"), expanded=expand):
        render_write_guard()
        recordable = _recordable_creators()
        if not recordable:
            st.caption(t("Approve a creator first to mint a coupon, then record the conversion here."))
            return
        _prefill_record_form(recordable, force=expand)
        labels = [_perf_event_label(creator_id, name) for creator_id, name, _ in recordable]
        choice = st.selectbox(t("Creator"), labels, key="perf_event_creator")
        selected = recordable[labels.index(choice)]
        creator_id, _name, asset = selected
        coupon = str(asset.get("coupon") or "")
        utm = str(asset.get("deeplink") or asset.get("utm_campaign") or "")
        if coupon:
            st.caption(f'{t("Coupon")}: {coupon}')
        locked = writes_locked()
        with st.form("record_performance_event_form"):
            orders = st.number_input(t("Orders"), min_value=0, step=1, value=0)
            revenue_usd = st.number_input(t("Revenue USD"), min_value=0.0, step=50.0, value=0.0)
            spend_usd = st.number_input(t("Spend USD"), min_value=0.0, step=50.0, value=0.0)
            note = st.text_input(t("Note"), value="")
            submitted = st.form_submit_button(t("Record event"), type="primary", disabled=locked)
        if submitted:
            try:
                before = creator_state(creator_id)
                record_performance_event(
                    creator_id,
                    int(orders),
                    float(revenue_usd),
                    float(spend_usd),
                    coupon=coupon or None,
                    utm=utm or None,
                    note=note.strip() or None,
                )
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                select_creator(creator_id)
                st.session_state["growth_event_toast"] = True
                st.session_state["growth_open_outreach"] = True
                st.session_state["outreach_focus_creator_id"] = creator_id
                if before == "published" and creator_state(creator_id) == "measured":
                    st.session_state["growth_moved_to_measured"] = True
                st.rerun()


def _budget_html(decision: dict) -> str:
    expected = decision.get("expected_value_usd")
    expected_label = "—" if expected is None else f"${float(expected):,.0f} recorded revenue"
    return (
        '<div class="is-card"><div class="is-panel-body">'
        f'<p><b>Action</b><br/>{esc(str(decision.get("action", "observe")))}</p>'
        f'<p><b>Cost</b><br/>${float(decision.get("cost_usd") or 0):,.0f} recorded spend</p>'
        f'<p><b>Expected value</b><br/>{esc(expected_label)} · {esc(str(decision.get("expected_value_status", "not_collected")))}</p>'
        f'<p><b>Uncertainty</b><br/>{esc(str(decision.get("uncertainty", "unmeasured")))}</p>'
        f'<p><b>Approver</b><br/>{esc(str(decision.get("approver", "")))} · human approval required</p>'
        f'<small>{esc(str(decision.get("note", "")))} Model {esc(str(decision.get("model_version", "")))}. Not a viral forecast.</small>'
        "</div></div>"
    )


def _acceptance_html(rows: list[dict]) -> str:
    cells = []
    for row in rows:
        mark = "PASS" if row.get("passed") else "FAIL"
        cells.append(
            "<tr>"
            f"<td>{esc(row.get('dimension', ''))}</td>"
            f"<td>{esc(row.get('target', ''))}</td>"
            f"<td>{esc(str(row.get('value', '')))}</td>"
            f"<td>{mark}</td>"
            f"<td><small>{esc(row.get('detail', ''))}</small></td>"
            "</tr>"
        )
    return (
        '<table class="is-table"><thead><tr>'
        "<th>Dimension</th><th>Target</th><th>Value</th><th>Gate</th><th>Detail</th>"
        "</tr></thead>"
        f"<tbody>{''.join(cells)}</tbody></table>"
    )


def _pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.0f}%"


def _money(value) -> str:
    return f"${float(value or 0):,.0f}"


def _business_value_html(board: dict) -> str:
    metrics = [
        (t("Unevidenced spend blocked"), _money(board.get("unevidenced_spend_blocked_usd")), t("Catalog estimated cost")),
        (
            t("Rule-mix Top 10 unevidenced"),
            f"{int(board.get('rule_top10_unevidenced_n') or 0)} · {_money(board.get('rule_top10_unevidenced_spend_usd'))}",
            t("Would have been authorized"),
        ),
        (t("Top 10 spend-ready"), str(board.get("top10_spend_ready", 0)), t("Grounded DNA claim")),
        (t("Gold-set F1 lift"), f"{float(board.get('gold_f1_lift') or 0):+.4f}", t("vs keyword baseline")),
        (t("False-positive reduction"), _pct(board.get("gold_fp_reduction")), t("Gold set FP")),
        (t("Hours of caption reading replaced"), f"{board.get('hours_saved', 0):.2f} h", t("Process-time model")),
    ]
    kpi = '<div class="is-kpi-strip">' + "".join(
        f'<div class="is-kpi-mini"><label>{esc(label)}</label><strong>{esc(value)}</strong><small>{esc(note)}</small></div>'
        for label, value, note in metrics
    ) + "</div>"
    formulas = "".join(f"<li><small>{esc(item)}</small></li>" for item in board.get("formulas") or [])
    return (
        '<div class="is-card" id="business-value-board" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{t("Quantified business value")}</span>'
        f'<span class="is-panel-link">{esc(str(board.get("ranking_model_version") or ""))}</span></div>'
        '<div class="is-panel-body">'
        f"<p>{esc(board.get('pain') or '')}</p>"
        f"{kpi}"
        f"<ul>{formulas}</ul>"
        f"<small>{esc(board.get('note') or '')} {esc(board.get('process_model') or '')}</small>"
        "</div></div>"
    )


def _landing_html() -> str:
    path = landing_path()
    phases = "".join(
        "<tr>"
        f"<td>{esc(item['week'])}</td>"
        f"<td><b>{esc(item['title'])}</b><br/><small>{esc(item['owner'])}</small></td>"
        f"<td>{esc(item['artifact'])}</td>"
        f"<td><small>{esc(item['exit_gate'])}</small></td>"
        f"<td><small>{esc(item['in_this_demo'])}</small></td>"
        "</tr>"
        for item in path["phases"]
    )
    nxt = "".join(f"<li>{esc(item)}</li>" for item in path["scale_next"])
    out = "".join(f"<li>{esc(item)}</li>" for item in path["out_of_scope"])
    return (
        '<div class="is-card" id="pilot-landing-path" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{t("2-week pilot landing path")}</span>'
        f'<span class="is-panel-link">{esc(path["horizon"])}</span></div>'
        '<div class="is-panel-body">'
        f"<small>{esc(path['closed_loop'])}</small>"
        '<table class="is-table"><thead><tr>'
        f"<th>{t('When')}</th><th>{t('Phase')}</th><th>{t('Artifact')}</th><th>{t('Exit gate')}</th><th>{t('In this demo')}</th>"
        "</tr></thead>"
        f"<tbody>{phases}</tbody></table>"
        f"<p><b>{esc(t('Scale next'))}</b></p><ul>{nxt}</ul>"
        f"<p><b>{esc(t('Out of scope'))}</b></p><ul>{out}</ul>"
        f"<small>{esc(path['note'])}</small>"
        "</div></div>"
    )


def _calibrator_html(proposal: dict) -> str:
    counts = proposal.get("reason_counts") or {}
    count_line = ", ".join(f"{key} ×{value}" for key, value in counts.items()) or t("none")
    rows = []
    current = proposal.get("current_weights") or {}
    proposed = proposal.get("proposed_weights") or {}
    deltas = proposal.get("deltas") or {}
    for key in current:
        rows.append(
            "<tr>"
            f"<td>{esc(key)}</td>"
            f"<td>{current[key]:.2%}</td>"
            f"<td>{proposed.get(key, current[key]):.2%}</td>"
            f"<td>{deltas.get(key, 0):+.2%}</td>"
            "</tr>"
        )
    return (
        '<div class="is-card" id="reason-code-calibrator" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{t("Reason-code calibrator")}</span>'
        f'<span class="is-panel-link">{esc(str(proposal.get("version") or ""))} · {esc(str(proposal.get("status") or ""))}</span></div>'
        '<div class="is-panel-body">'
        f"<small>{esc(t('Reason codes'))}: {esc(count_line)}</small>"
        '<table class="is-table"><thead><tr>'
        f"<th>{t('Driver')}</th><th>{t('Current')}</th><th>{t('Proposed')}</th><th>{t('Delta')}</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        f"<small>{esc(proposal.get('note') or '')}</small>"
        "</div></div>"
    )


def _benchmark_html(report: dict) -> str:
    """Render the committed gold-set report. Numbers come from the file, never from copy."""

    def cell(value) -> str:
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value if value is not None else "")

    arms = list(report.get("arms") or [])
    note = str(report.get("note") or t("No benchmark report. Run scripts/run_benchmark.py."))
    if not arms:
        return (
            '<div class="is-card" id="claim-evidence-benchmark" style="margin-top:10px">'
            f'<div class="is-panel-head"><span class="is-panel-title">{t("Claim-evidence benchmark")}</span>'
            f'<span class="is-panel-link">{t("Gold set is operator-read timedtext")}</span></div>'
            f'<div class="is-panel-body"><small>{esc(note)}</small></div></div>'
        )
    cells = []
    for arm in arms:
        metrics = arm.get("metrics") or {}
        cells.append(
            "<tr>"
            f"<td>{esc(arm.get('arm', ''))}</td>"
            f"<td>{esc(arm.get('status', ''))}</td>"
            f"<td>{esc(cell(metrics.get('precision')))}</td>"
            f"<td>{esc(cell(metrics.get('recall')))}</td>"
            f"<td>{esc(cell(metrics.get('f1')))}</td>"
            f"<td>{esc(cell(metrics.get('quote_grounding_accuracy')))}</td>"
            f"<td><small>tp {esc(str(metrics.get('tp', '')))} · fp {esc(str(metrics.get('fp', '')))} · "
            f"fn {esc(str(metrics.get('fn', '')))} · {esc(str(arm.get('model') or '—'))}</small></td>"
            "</tr>"
        )
    gold = (
        f'{t("Clips")} {esc(str(report.get("gold_n_clips") or ""))} · '
        f'{t("Method")} {esc(str(report.get("gold_method") or ""))} · '
        f'{esc(str(report.get("gold_pack_id") or ""))}'
    )
    return (
        '<div class="is-card" id="claim-evidence-benchmark" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{t("Claim-evidence benchmark")}</span>'
        f'<span class="is-panel-link">{gold}</span></div>'
        '<div class="is-panel-body">'
        f"<small>{esc(note)}</small>"
        '<table class="is-table"><thead><tr>'
        f"<th>{t('Arm')}</th><th>{t('Status')}</th><th>{t('Precision')}</th>"
        f"<th>{t('Recall')}</th><th>{t('F1')}</th><th>{t('Quote grounding')}</th><th>{t('Detail')}</th>"
        "</tr></thead>"
        f"<tbody>{''.join(cells)}</tbody></table></div></div>"
    )


def render() -> None:
    render_topbar()
    context = active_context()
    summary = workflow_summary()
    events = performance_events()
    assets = tracking_assets()
    ranked = ranking()
    budget = float(context.get("budget_usd", 0))
    period_keys = list(PERIOD_WINDOW_DAYS)
    mission_markets = [item for item in (context.get("markets") or [context.get("market")]) if item]
    market_keys = ["All markets", *mission_markets]

    md(
        page_header(
            "Growth Review",
            "Quantified value, 2-week landing path, and the Calibrator close the loop. ROI is recorded events only.",
            "Closed loop",
            "blue",
        ),
        unsafe_allow_html=True,
    )

    value_board = compute_business_value(creators(), active_mission())
    md(rubric_scorecard_html(prove_rubric(creators(), active_mission())), unsafe_allow_html=True)
    md(_business_value_html(value_board), unsafe_allow_html=True)
    md(_landing_html(), unsafe_allow_html=True)

    controls = st.columns([0.48, 0.24, 0.18, 0.1], vertical_alignment="center")
    with controls[0]:
        md(mission_chip(active_context_label()), unsafe_allow_html=True)
    period_key = controls[1].selectbox(
        t("Period"),
        period_keys,
        index=period_keys.index("All recorded events"),
        format_func=lambda key: t(key),
        key="growth_period",
        label_visibility="collapsed",
    )
    market_key = controls[2].selectbox(
        t("Market"),
        market_keys,
        format_func=lambda key: t(key) if key == "All markets" else key,
        key="growth_market",
        label_visibility="collapsed",
    )
    controls[3].button(t("Export"), use_container_width=True, disabled=True, help=t("Not wired in this demo"))

    period_days = PERIOD_WINDOW_DAYS[period_key]
    market_filter = None if market_key == "All markets" else market_key
    filtered_events = filter_performance_events(events, period_days=period_days, market=market_filter)
    filtered_assets = filter_dated_records(
        assets,
        period_days=period_days,
        market=market_filter,
        timestamp_field="created_at",
        market_field="market",
    )

    names = _creator_names()
    md(_kpi_strip(summary, filtered_events, budget), unsafe_allow_html=True)
    st.caption(
        t("ROI uses recorded performance events in the selected period and market. Empty set equals 0x.")
    )

    left, right = st.columns([0.38, 0.62], gap="small")
    with left:
        md(
            '<div class="is-chart"><div class="is-chart-title">Creator funnel</div>'
            + _funnel(len(ranked), summary, filtered_events)
            + "</div>",
            unsafe_allow_html=True,
        )
    with right:
        md(
            '<div class="is-card"><div class="is-panel-head"><span class="is-panel-title">Linked performance events</span>'
            '<span class="is-panel-link">No inferred attribution</span></div>'
            f'<div class="is-panel-body">{_performance_table(filtered_events, names)}</div></div>',
            unsafe_allow_html=True,
        )

    md(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Issued tracking assets</span>'
        '<span class="is-panel-link">Minted on approve · not conversions</span></div>'
        f'<div class="is-panel-body">{_tracking_table(filtered_assets, any_issued=bool(assets), names=names)}</div></div>',
        unsafe_allow_html=True,
    )

    md(
        '<div class="is-card" style="margin-top:10px"><div class="is-panel-head">'
        '<span class="is-panel-title">Next best action</span><span class="is-panel-link">Human approval required</span></div>'
        f'<div class="is-panel-body">{_next_actions(context, summary, events, assets)}</div></div>',
        unsafe_allow_html=True,
    )
    _render_next_action_buttons(summary, events, assets)

    _render_post_record_handoff()
    _render_record_form()

    with st.expander(t("Budget decision"), expanded=False):
        st.caption(t("From recorded performance events only. Empty events keep ROI at 0x. Not a modeled forecast."))
        decision = propose_budget_decision(
            filtered_events,
            sku=str(active_mission().get("product") or ""),
            budget_usd=budget,
        )
        md(_budget_html(decision), unsafe_allow_html=True)

    rows = acceptance_matrix(
        ranked=ranked,
        mission=active_mission(),
        catalog_size=len(creators()),
        posts=load_creator_content(),
        events=events,
    )
    st.caption(
        t("Pytest-backed gates from the current catalog, ranking and events. Not operator interviews.")
    )
    md(
        '<div class="is-card" id="pilot-acceptance-matrix" style="margin-top:10px">'
        f'<div class="is-panel-head"><span class="is-panel-title">{t("Pilot acceptance matrix")}</span>'
        f'<span class="is-panel-link">{t("Same rows as src/evaluation.py")}</span></div>'
        '<div class="is-panel-body">'
        f"<small>{t('Hard gates, evidence, stability, attribution, recall 60, intensive-read Top 20 with labeled_demo timestamps. YouTube overlay: all 60 recalled rows are public channels (catalog_channel), not KYC. Catalog videos, Creator Genome. Human interview adoption ≥70% is not_collected.')}</small>"
        f"{_acceptance_html(rows)}</div></div>",
        unsafe_allow_html=True,
    )
    md(_benchmark_html(load_report()), unsafe_allow_html=True)
    proposal = propose_calibration(
        list(st.session_state.get("decision_log") or []),
        active_score_weights(),
    )
    md(_calibrator_html(proposal), unsafe_allow_html=True)
    if proposal.get("status") in {"ok", "unchanged"}:
        locked = writes_locked() or proposal.get("status") != "ok"
        if st.button(
            t("Apply calibrator weights"),
            type="primary",
            disabled=locked,
            help=t("Human must apply. Never auto-trades. Empty decision log stays skipped."),
        ):
            try:
                apply_calibrator_weights(proposal["proposed_weights"])
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.toast(t("Calibrator weights applied to the Scout mix. Claim coverage still leads the spend-ready cut."))
                st.rerun()

    render_demo_notice()
