from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

from infra import repository
from infra.auth import require_write
from infra.config import SCORE_WEIGHTS
from infra.database import init_db, reset_db
from src.data_loader import load_creators, load_mission
from src.domain import (
    HEALTH_SHORTLISTED_STATES,
    WORKFLOW_STATES,
    EntryType,
    can_transition,
    mission_health,
    parse_iso_datetime,
    pipeline_counts,
    transition_event,
)
from src.scoring import rank_creators


ROOT = Path(__file__).resolve().parents[1]
CREATORS_PATH = ROOT / "data" / "creators.csv"
MISSION_PATH = ROOT / "data" / "launch_mission.json"
OPPORTUNITIES_PATH = ROOT / "data" / "creator_opportunities.json"

# Session keys mirrored into SQLite so a browser refresh does not discard
# operator work. Derived caches such as `matches` are recomputed instead.
_PERSISTED_KEYS = (
    "mission",
    "missions",
    "opportunities",
    "active_entry_type",
    "active_mission_id",
    "active_opportunity_id",
    "shortlist_ids",
    "selected_creator_id",
    "compare_ids",
    "decision_log",
    "creator_workflows",
    "outreach_cases",
    "content_assets",
    "performance_events",
    "brief_version",
    "live_evidence",
)

ENTRY_ALIASES = {
    "mission": EntryType.LAUNCH_MISSION.value,
    "launch_mission": EntryType.LAUNCH_MISSION.value,
    "opportunity": EntryType.CREATOR_OPPORTUNITY.value,
    "creator_opportunity": EntryType.CREATOR_OPPORTUNITY.value,
}


@st.cache_data(show_spinner=False)
def _load_creators():
    return load_creators(CREATORS_PATH)


@st.cache_data(show_spinner=False)
def _load_default_mission() -> dict[str, Any]:
    return load_mission(MISSION_PATH)


@st.cache_data(show_spinner=False)
def _load_default_opportunities() -> list[dict[str, Any]]:
    if not OPPORTUNITIES_PATH.exists():
        return []
    data = json.loads(OPPORTUNITIES_PATH.read_text(encoding="utf-8"))
    return list(data.get("opportunities", data) if isinstance(data, dict) else data)


def _mission_seed() -> dict[str, Any]:
    raw = _load_default_mission()
    market = raw.get("market", "United States")
    return {
        **raw,
        "name": raw.get("name", f'{raw.get("product", "Product")} Global Launch'),
        "markets": raw.get("markets", [market, "Mexico"]),
        "languages": raw.get("languages", [raw.get("language", "English")]),
        "campaign_dates": raw.get("campaign_dates", "May 12 - Jul 12, 2026"),
        "budget_usd": raw.get("budget_usd", 1_250_000),
        "owner": raw.get("owner", "Olivia Chen"),
        "status": raw.get("status", "Active"),
    }


def _scope_key(entry_type: str, entry_id: str, creator_id: str) -> str:
    return f"{entry_type}:{entry_id}:{creator_id}"


def _current_root() -> tuple[str, str]:
    entry_type = ENTRY_ALIASES.get(
        st.session_state.get("active_entry_type", EntryType.LAUNCH_MISSION.value)
    )
    if entry_type == EntryType.LAUNCH_MISSION.value:
        return entry_type, st.session_state.active_mission_id
    return entry_type, st.session_state.active_opportunity_id


def _seed_workflows() -> dict[str, dict[str, Any]]:
    mission = _mission_seed()
    entry_type = EntryType.LAUNCH_MISSION.value
    mission_id = mission["mission_id"]
    eligible_ids = rank_creators(_load_creators(), mission)["creator_id"].tolist()
    shortlist = set(eligible_ids[:3])
    records = {}
    for creator_id in eligible_ids:
        state = "shortlisted" if creator_id in shortlist else "qualified"
        records[_scope_key(entry_type, mission_id, creator_id)] = {
            "creator_id": creator_id,
            "entry_type": entry_type,
            "entry_id": mission_id,
            "state": state,
            "events": [],
        }
    return records


def _creator_market(creator_id: str) -> str | None:
    matches = creators()[creators()["creator_id"] == creator_id]
    if matches.empty:
        return None
    market = matches.iloc[0].get("primary_market")
    text = str(market).strip() if market is not None else ""
    return text or None


def _as_recorded_at(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    parsed = parse_iso_datetime(value)
    if parsed is None:
        raise ValueError("recorded_at must be a timezone-aware ISO timestamp")
    return parsed.isoformat()


def persist_state() -> None:
    """Mirror the persisted session keys into SQLite."""
    for key in _PERSISTED_KEYS:
        if key in st.session_state:
            repository.save_state(key, st.session_state[key])


def reset_demo() -> None:
    """Clear persisted state and session so the next run reseeds from defaults."""
    require_write()
    reset_db()
    for key in (*_PERSISTED_KEYS, "matches", "_state_restored", "show_mission_form"):
        st.session_state.pop(key, None)


def bootstrap_state() -> None:
    init_db()
    mission = _mission_seed()
    eligible_ids = rank_creators(_load_creators(), mission)["creator_id"].tolist()
    shortlist_ids = eligible_ids[:3]
    defaults: dict[str, Any] = {
        "mission": mission,
        "missions": {mission["mission_id"]: mission},
        "opportunities": _load_default_opportunities(),
        "active_entry_type": EntryType.LAUNCH_MISSION.value,
        "active_mission_id": mission["mission_id"],
        "active_opportunity_id": None,
        "shortlist_ids": shortlist_ids,
        "selected_creator_id": shortlist_ids[0] if shortlist_ids else (eligible_ids[0] if eligible_ids else None),
        "compare_ids": shortlist_ids,
        "decision_log": [],
        "matches": {},
        "creator_workflows": _seed_workflows(),
        "outreach_cases": [],
        "content_assets": [],
        "performance_events": [],
        "brief_version": 1,
        "show_mission_form": False,
        "live_evidence": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(value)

    if not st.session_state.get("_state_restored"):
        stored = repository.load_all_state()
        for key, value in stored.items():
            if key in _PERSISTED_KEYS:
                st.session_state[key] = value
        st.session_state["_state_restored"] = True
        if not stored:
            persist_state()
    st.session_state.setdefault("live_evidence", [])


def creators():
    return _load_creators().copy()


def missions() -> list[dict[str, Any]]:
    return [deepcopy(mission) for mission in st.session_state.missions.values()]


def opportunity_records() -> list[dict[str, Any]]:
    return deepcopy(list(st.session_state.opportunities))


def _opportunity_by_id(opportunity_id: str | None) -> dict[str, Any] | None:
    return next(
        (item for item in st.session_state.opportunities if item.get("opportunity_id") == opportunity_id),
        None,
    )


def _shortlist_ids_from_workflows(entry_type: str, entry_id: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for record in st.session_state.creator_workflows.values():
        if (
            record.get("entry_type") == entry_type
            and record.get("entry_id") == entry_id
            and record.get("state") in HEALTH_SHORTLISTED_STATES
        ):
            creator_id = record.get("creator_id")
            if creator_id and creator_id not in seen:
                seen.add(creator_id)
                ordered.append(creator_id)
    return ordered


def opportunities_for_mission(mission_id: str | None) -> list[dict[str, Any]]:
    """Opportunities linked to this mission. Empty is honest."""

    if not mission_id:
        return []
    return deepcopy(
        [
            item
            for item in st.session_state.opportunities
            if item.get("linked_mission_id") == mission_id
        ]
    )


def active_context() -> dict[str, Any]:
    """Return one defensive, page-safe view of the active root context."""

    entry_type, entry_id = _current_root()
    creator_id = st.session_state.get("selected_creator_id")
    if entry_type == EntryType.LAUNCH_MISSION.value:
        mission = st.session_state.missions.get(entry_id)
        if mission is None:
            raise ValueError(f"Unknown active mission: {entry_id}")
        market = mission.get("market") or (mission.get("markets") or [""])[0]
        return deepcopy(
            {
                **mission,
                "entry_type": entry_type,
                "entry_id": entry_id,
                "mission_id": entry_id,
                "opportunity_id": None,
                "creator_id": creator_id,
                "title": mission.get("name", mission.get("product", "Launch Mission")),
                "label": f'Mission · {mission.get("name", mission.get("product", entry_id))} · {market}',
            }
        )

    opportunity = _opportunity_by_id(entry_id)
    if opportunity is None:
        raise ValueError(f"Unknown active opportunity: {entry_id}")
    linked_mission_id = opportunity.get("linked_mission_id")
    linked = st.session_state.missions.get(linked_mission_id, {}) if linked_mission_id else {}
    origin_creator_id = opportunity.get("creator_id")
    creator_id = creator_id or origin_creator_id
    creator_match = creators()[creators()["creator_id"] == origin_creator_id]
    creator = creator_match.iloc[0].to_dict() if not creator_match.empty else {}
    market = opportunity.get("market") or linked.get("market", "")
    language = opportunity.get("language") or linked.get("language", "English")
    return deepcopy(
        {
            **linked,
            **opportunity,
            "entry_type": entry_type,
            "entry_id": entry_id,
            "mission_id": linked_mission_id,
            "opportunity_id": entry_id,
            "creator_id": creator_id,
            "origin_creator_id": origin_creator_id,
            "market": market,
            "markets": [market],
            "language": language,
            "title": opportunity.get("title", "Creator Opportunity"),
            "label": f'Opportunity · {opportunity.get("title", entry_id)} · {market}',
            "target_topics": opportunity.get("target_topics") or linked.get("target_topics") or creator.get("topics", []),
            "target_styles": opportunity.get("target_styles") or linked.get("target_styles") or creator.get("styles", []),
            "product": linked.get("product", opportunity.get("title", "Creator-led opportunity")),
            "objective": opportunity.get("hypothesis", linked.get("objective", "Validate this creator-led opportunity.")),
            "max_cost_usd": linked.get("max_cost_usd", 15000),
            "min_brand_safety": linked.get("min_brand_safety", 60),
            "budget_usd": linked.get("budget_usd", 0),
        }
    )


def active_context_label() -> str:
    return str(active_context()["label"])


def set_active_context(entry_type: str, entry_id: str) -> dict[str, Any]:
    normalized = ENTRY_ALIASES.get(str(entry_type).strip().lower())
    if normalized is None:
        raise ValueError(f"Unsupported entry type: {entry_type}")
    if normalized == EntryType.LAUNCH_MISSION.value:
        if entry_id not in st.session_state.missions:
            raise ValueError(f"Unknown mission: {entry_id}")
        st.session_state.active_mission_id = entry_id
        st.session_state.active_opportunity_id = None
        mission_rank = rank_creators(creators(), st.session_state.missions[entry_id])
        eligible_ids = mission_rank["creator_id"].tolist() if not mission_rank.empty else []
        eligible_set = set(eligible_ids)
        workflow_shortlist = [
            creator_id
            for creator_id in _shortlist_ids_from_workflows(normalized, entry_id)
            if creator_id in eligible_set
        ]
        if workflow_shortlist:
            st.session_state.shortlist_ids = workflow_shortlist
        else:
            current = [
                creator_id
                for creator_id in st.session_state.get("shortlist_ids", [])
                if creator_id in eligible_set
            ]
            st.session_state.shortlist_ids = current or eligible_ids[:3]
        if st.session_state.get("selected_creator_id") not in eligible_ids:
            st.session_state.selected_creator_id = eligible_ids[0] if eligible_ids else None
        st.session_state.compare_ids = [
            creator_id for creator_id in st.session_state.get("compare_ids", []) if creator_id in eligible_ids
        ][:3]
        if not st.session_state.compare_ids:
            st.session_state.compare_ids = eligible_ids[:3]
    else:
        opportunity = _opportunity_by_id(entry_id)
        if opportunity is None:
            raise ValueError(f"Unknown opportunity: {entry_id}")
        origin = opportunity.get("creator_id")
        st.session_state.active_opportunity_id = entry_id
        st.session_state.selected_creator_id = origin
        st.session_state.compare_ids = [origin] if origin else []
        st.session_state.shortlist_ids = [origin] if origin else []
        st.session_state.active_entry_type = normalized
        if origin:
            _ensure_workflow_record(origin, opportunity.get("status", "discovered"))
    st.session_state.active_entry_type = normalized
    persist_state()
    return active_context()


def save_mission(mission: dict[str, Any]) -> dict[str, Any]:
    require_write()
    mission_id = str(mission.get("mission_id", "")).strip()
    if not mission_id:
        raise ValueError("mission_id is required")
    record = deepcopy(mission)
    st.session_state.missions[mission_id] = record
    st.session_state.mission = record
    set_active_context(EntryType.LAUNCH_MISSION.value, mission_id)
    return deepcopy(record)


def save_opportunity(opportunity: dict[str, Any]) -> dict[str, Any]:
    require_write()
    opportunity_id = str(opportunity.get("opportunity_id", "")).strip()
    if not opportunity_id:
        raise ValueError("opportunity_id is required")
    records = [item for item in st.session_state.opportunities if item.get("opportunity_id") != opportunity_id]
    records.append(deepcopy(opportunity))
    st.session_state.opportunities = records
    set_active_context(EntryType.CREATOR_OPPORTUNITY.value, opportunity_id)
    return deepcopy(opportunity)


def link_opportunity_to_mission(opportunity_id: str, mission_id: str) -> dict[str, Any]:
    require_write()
    if mission_id not in st.session_state.missions:
        raise ValueError(f"Unknown mission: {mission_id}")
    opportunity = _opportunity_by_id(opportunity_id)
    if opportunity is None:
        raise ValueError(f"Unknown opportunity: {opportunity_id}")
    opportunity["linked_mission_id"] = mission_id
    persist_state()
    return deepcopy(opportunity)


def active_mission() -> dict[str, Any]:
    """Return the effective scoring/content context for either root entry."""

    context = active_context()
    return {
        **context,
        "market": context.get("market") or (context.get("markets") or ["United States"])[0],
        "language": context.get("language", "English"),
        "max_cost_usd": context.get("max_cost_usd", 12000),
        "min_brand_safety": context.get("min_brand_safety", 72),
        "target_topics": context.get("target_topics", []),
        "target_styles": context.get("target_styles", []),
        "product": context.get("product", context.get("title", "Creator opportunity")),
        "objective": context.get("objective", context.get("hypothesis", "Validate this creator-led opportunity.")),
    }


def _live_evidence_creator_ids() -> set[str]:
    entry_type, entry_id = _current_root()
    return {
        str(item.get("creator_id"))
        for item in st.session_state.get("live_evidence", [])
        if item.get("creator_id")
        and item.get("entry_type") == entry_type
        and item.get("entry_id") == entry_id
    }


def ranking():
    context = active_context()
    if context["entry_type"] == EntryType.OPPORTUNITY.value and not context.get("mission_id"):
        return rank_creators(creators(), active_mission()).iloc[0:0]
    ranked = rank_creators(
        creators(),
        active_mission(),
        SCORE_WEIGHTS,
        query=str(st.session_state.get("creator_nl_query") or ""),
        live_evidence_ids=_live_evidence_creator_ids(),
    )
    for _, row in ranked.iterrows():
        creator_id = row["creator_id"]
        key = _scope_key(context["entry_type"], context["entry_id"], creator_id)
        st.session_state.matches[key] = {
            "match_id": f'match_{context["entry_id"]}_{creator_id}',
            "creator_id": creator_id,
            "entry_type": context["entry_type"],
            "entry_id": context["entry_id"],
            "mission_id": context.get("mission_id"),
            "opportunity_id": context.get("opportunity_id"),
            "score": float(row["total_score"]),
            "gate_passed": True,
            "rationale": list(row.get("positives", [])),
            "evidence": list(row.get("evidence", [])),
        }
    return ranked


def match_for_creator(creator_id: str) -> dict[str, Any] | None:
    entry_type, entry_id = _current_root()
    key = _scope_key(entry_type, entry_id, creator_id)
    if key not in st.session_state.matches:
        ranking()
    record = st.session_state.matches.get(key)
    return deepcopy(record) if record else None


def select_creator(creator_id: str) -> None:
    if creator_id not in set(creators()["creator_id"]):
        raise ValueError(f"Unknown creator: {creator_id}")
    st.session_state.selected_creator_id = creator_id
    persist_state()


def selected_creator() -> dict[str, Any]:
    ranked = ranking()
    if ranked.empty:
        return creators().iloc[0].to_dict()
    selected_id = st.session_state.get("selected_creator_id")
    matches = ranked[ranked["creator_id"] == selected_id]
    if matches.empty:
        return ranked.iloc[0].to_dict()
    return matches.iloc[0].to_dict()


def _ensure_workflow_record(creator_id: str | None, initial_state: str = "qualified") -> dict[str, Any]:
    if not creator_id:
        raise ValueError("creator_id is required")
    if creator_id not in set(creators()["creator_id"]):
        raise ValueError(f"Unknown creator: {creator_id}")
    entry_type, entry_id = _current_root()
    key = _scope_key(entry_type, entry_id, creator_id)
    if key not in st.session_state.creator_workflows:
        state = initial_state if initial_state in WORKFLOW_STATES else "discovered"
        st.session_state.creator_workflows[key] = {
            "creator_id": creator_id,
            "entry_type": entry_type,
            "entry_id": entry_id,
            "state": state,
            "events": [],
        }
    return st.session_state.creator_workflows[key]


def creator_state(creator_id: str) -> str:
    return str(_ensure_workflow_record(creator_id)["state"])


def allowed_next_creator_states(creator_id: str) -> list[str]:
    current = creator_state(creator_id)
    return [state for state in WORKFLOW_STATES if can_transition(current, state)]


def _tracking_assets(creator_id: str, entry_id: str) -> dict[str, str]:
    """Stable unique coupon + UTM deeplink for one creator in one root context."""

    campaign = re.sub(r"[^a-z0-9]+", "-", str(entry_id).lower()).strip("-")[:32] or "launch"
    content = re.sub(r"[^a-z0-9]+", "-", str(creator_id).lower()).strip("-") or "creator"
    digest = hashlib.sha256(f"{entry_id}:{creator_id}".encode()).hexdigest()[:6].upper()
    coupon = f"X5-{creator_id}-{digest}"
    deeplink = (
        "https://store.insta360.com/"
        f"?utm_source=instaspark&utm_medium=creator"
        f"&utm_campaign={campaign}&utm_content={content}&coupon={coupon}"
    )
    return {
        "coupon": coupon,
        "deeplink": deeplink,
        "utm_source": "instaspark",
        "utm_medium": "creator",
        "utm_campaign": campaign,
        "utm_content": content,
    }


def _attach_tracking(case: dict[str, Any], creator_id: str, entry_id: str) -> dict[str, Any]:
    if case.get("coupon") and case.get("deeplink"):
        if not case.get("market"):
            case["market"] = _creator_market(creator_id)
        return case
    case.update(_tracking_assets(creator_id, entry_id))
    if not case.get("market"):
        case["market"] = _creator_market(creator_id)
    return case


CONTACT_PACK_STATES = frozenset(
    {
        "approved",
        "contacted",
        "negotiating",
        "contracted",
        "content_in_review",
    }
)
DEFAULT_OUTREACH_TONE = "Professional"


def _creator_record(creator_id: str) -> dict[str, Any]:
    matches = creators()[creators()["creator_id"] == creator_id]
    if matches.empty:
        return {"creator_id": creator_id, "creator_name": creator_id}
    return matches.iloc[0].to_dict()


def _session_outreach_tone() -> str:
    tone = str(st.session_state.get("studio_brand_tone") or "").strip()
    return tone or DEFAULT_OUTREACH_TONE


def _latest_brief_excerpt(creator_id: str) -> str:
    assets = [
        item
        for item in content_assets()
        if item.get("creator_id") == creator_id and (item.get("excerpt") or item.get("body"))
    ]
    if not assets:
        return ""
    latest = max(assets, key=lambda item: str(item.get("created_at") or ""))
    return str(latest.get("excerpt") or latest.get("body") or "").strip()


def _live_case_for(creator_id: str) -> dict[str, Any] | None:
    entry_type, entry_id = _current_root()
    return next(
        (
            case
            for case in st.session_state.outreach_cases
            if case["creator_id"] == creator_id
            and case["entry_type"] == entry_type
            and case["entry_id"] == entry_id
            and case.get("status") != "closed_lost"
        ),
        None,
    )


def _fill_outreach_message(case: dict[str, Any], creator_id: str, *, force: bool = False) -> None:
    if case.get("outreach_message") and not force:
        return
    from services.llm_service import generate_outreach_message, generation_mode_label

    tone = _session_outreach_tone()
    case["outreach_message"] = generate_outreach_message(
        active_mission(),
        _creator_record(creator_id),
        coupon=case.get("coupon"),
        deeplink=case.get("deeplink"),
        brief_excerpt=_latest_brief_excerpt(creator_id),
        tone=tone,
    )
    case["outreach_tone"] = tone
    case["outreach_source"] = generation_mode_label()


def ensure_outreach_case(creator_id: str, owner: str | None = None) -> dict[str, Any]:
    """Create at most one active case for a creator and root context."""

    require_write()
    context = active_context()
    entry_type, entry_id = _current_root()
    current_state = creator_state(creator_id)
    outreach_states = {
        "approved",
        "contacted",
        "negotiating",
        "contracted",
        "content_in_review",
        "published",
        "measured",
    }
    if current_state not in outreach_states:
        raise ValueError("An OutreachCase requires an approved creator collaboration")
    existing = next(
        (
            case
            for case in st.session_state.outreach_cases
            if case["creator_id"] == creator_id
            and case["entry_type"] == entry_type
            and case["entry_id"] == entry_id
            and case.get("status") != "closed_lost"
        ),
        None,
    )
    if existing is not None:
        _attach_tracking(existing, creator_id, entry_id)
        _fill_outreach_message(existing, creator_id)
        persist_state()
        return deepcopy(existing)
    case = {
        "outreach_case_id": f"outreach_{entry_id}_{creator_id}",
        "creator_id": creator_id,
        "entry_type": entry_type,
        "entry_id": entry_id,
        "mission_id": context.get("mission_id"),
        "opportunity_id": context.get("opportunity_id"),
        "owner": owner or context.get("owner", "Operator"),
        "channel": "Not selected",
        "next_action": "Prepare personalized outreach",
        "status": current_state,
        "market": _creator_market(creator_id) or context.get("market"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _attach_tracking(case, creator_id, entry_id)
    _fill_outreach_message(case, creator_id)
    st.session_state.outreach_cases.append(case)
    persist_state()
    return deepcopy(case)


def transition_creator_state(
    creator_id: str,
    to_state: str,
    *,
    actor: str,
    reason: str,
    evidence: list[str] | tuple[str, ...] | str,
) -> dict[str, Any]:
    require_write()
    record = _ensure_workflow_record(creator_id)
    entry_type, entry_id = _current_root()
    context = active_context()
    audit_evidence = evidence or ["operator://manual-review"]
    event = transition_event(
        entity_id=creator_id,
        from_state=record["state"],
        to_state=to_state,
        actor=actor,
        reason=reason,
        evidence=audit_evidence,
        entry_type=entry_type,
        entry_id=entry_id,
    ).to_dict()
    event["creator_id"] = creator_id
    event["occurred_at"] = event["timestamp"]
    event["mission_id"] = context.get("mission_id")
    event["opportunity_id"] = context.get("opportunity_id")
    record["state"] = to_state
    record["events"].append(event)
    if entry_type == EntryType.CREATOR_OPPORTUNITY.value:
        opportunity = _opportunity_by_id(entry_id)
        if opportunity is not None and opportunity.get("creator_id") == creator_id:
            opportunity["status"] = to_state
    if to_state == "shortlisted" and creator_id not in st.session_state.shortlist_ids:
        st.session_state.shortlist_ids.append(creator_id)
    if to_state == "approved":
        ensure_outreach_case(creator_id, owner=actor)
    for case in st.session_state.outreach_cases:
        if case["creator_id"] == creator_id and case["entry_type"] == entry_type and case["entry_id"] == entry_id:
            case["status"] = to_state
            case["updated_at"] = event["occurred_at"]
            next_states = [state for state in WORKFLOW_STATES if can_transition(to_state, state)]
            case["next_action"] = (
                f'Advance to {next_states[0].replace("_", " ")}' if next_states else "Workflow complete"
            )
    repository.append_creator_event(
        creator_id,
        "State change",
        f'{event["from_state"]} → {to_state}',
        reason,
        actor,
    )
    persist_state()
    return deepcopy(record)


def save_decision(
    creator_id: str,
    decision: str,
    reason: str,
    *,
    reason_code: str | None = None,
    note: str | None = None,
    evidence: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    require_write()
    context = active_context()
    if not str(reason).strip():
        raise ValueError("decision reason is required")
    match = match_for_creator(creator_id)
    if match is None and context["entry_type"] == EntryType.MISSION.value:
        raise ValueError("A human decision requires a Match record in the active context")
    default_codes = {
        "Approved": "strong_fit",
        "Review": "needs_review",
        "Rejected": "risk_or_cost",
    }
    stable_reason_code = (reason_code or default_codes.get(decision, "operator_decision")).strip()
    if not stable_reason_code:
        raise ValueError("reason_code is required")
    existing = next(
        (
            item
            for item in reversed(st.session_state.decision_log)
            if item["creator_id"] == creator_id
            and item["entry_type"] == context["entry_type"]
            and item["entry_id"] == context["entry_id"]
            and item["decision"] == decision
        ),
        None,
    )
    current_state = creator_state(creator_id)
    if decision == "Approved" and existing and current_state in {
        "approved",
        "contacted",
        "negotiating",
        "contracted",
        "content_in_review",
        "published",
        "measured",
    }:
        case = ensure_outreach_case(creator_id, owner=existing["actor"])
        if case.get("coupon") and not existing.get("coupon"):
            existing["coupon"] = case["coupon"]
            existing["deeplink"] = case.get("deeplink")
            existing["utm_campaign"] = case.get("utm_campaign")
            existing["utm_content"] = case.get("utm_content")
            persist_state()
        return deepcopy(existing)
    record = {
        "decision_id": f'decision_{len(st.session_state.decision_log) + 1:04d}',
        "creator_id": creator_id,
        "match_id": match["match_id"] if match else None,
        "decision": decision,
        "reason_code": stable_reason_code,
        "reason": reason,
        "note": note if note is not None else reason,
        "evidence": list(evidence or []),
        "actor": context.get("owner", "Operator"),
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "entry_type": context["entry_type"],
        "entry_id": context["entry_id"],
        "mission_id": context.get("mission_id"),
        "opportunity_id": context.get("opportunity_id"),
    }
    if decision == "Approved":
        transition_creator_state(
            creator_id,
            "approved",
            actor=record["actor"],
            reason=reason,
            evidence=evidence or ["decision://human-approval"],
        )
        case = next(
            (
                item
                for item in st.session_state.outreach_cases
                if item["creator_id"] == creator_id
                and item["entry_type"] == context["entry_type"]
                and item["entry_id"] == context["entry_id"]
            ),
            None,
        )
        if case:
            record["coupon"] = case.get("coupon")
            record["deeplink"] = case.get("deeplink")
            record["utm_campaign"] = case.get("utm_campaign")
            record["utm_content"] = case.get("utm_content")
    elif decision == "Rejected":
        transition_creator_state(
            creator_id,
            "closed_lost",
            actor=record["actor"],
            reason=reason,
            evidence=evidence or ["decision://human-rejection"],
        )
    st.session_state.decision_log.append(record)
    repository.append_decision(creator_id, decision, reason)
    persist_state()
    return deepcopy(record)


def workflow_board() -> dict[str, list[dict[str, Any]]]:
    entry_type, entry_id = _current_root()
    creator_rows = {row["creator_id"]: row.to_dict() for _, row in creators().iterrows()}
    visible_states = WORKFLOW_STATES[2:]
    board: dict[str, list[dict[str, Any]]] = {state: [] for state in visible_states}
    for record in st.session_state.creator_workflows.values():
        if record["entry_type"] != entry_type or record["entry_id"] != entry_id:
            continue
        if record["state"] not in board:
            continue
        creator = creator_rows.get(record["creator_id"], {"creator_id": record["creator_id"], "creator_name": record["creator_id"]})
        outreach_case = next(
            (
                case
                for case in st.session_state.outreach_cases
                if case["creator_id"] == record["creator_id"]
                and case["entry_type"] == entry_type
                and case["entry_id"] == entry_id
            ),
            {},
        )
        board[record["state"]].append(
            {
                **creator,
                **deepcopy(record),
                **deepcopy(outreach_case),
                "next_states": allowed_next_creator_states(record["creator_id"]),
            }
        )
    return {stage: people for stage, people in board.items() if people}


def workflow_events() -> list[dict[str, Any]]:
    entry_type, entry_id = _current_root()
    events = []
    for record in st.session_state.creator_workflows.values():
        if record["entry_type"] == entry_type and record["entry_id"] == entry_id:
            events.extend(deepcopy(record.get("events", [])))
    return sorted(events, key=lambda event: event["occurred_at"])


def workflow_summary() -> dict[str, int]:
    entry_type, entry_id = _current_root()
    summary = {state: 0 for state in WORKFLOW_STATES}
    for record in st.session_state.creator_workflows.values():
        if record["entry_type"] == entry_type and record["entry_id"] == entry_id:
            summary[record["state"]] += 1
    return summary


def mission_health_snapshot() -> dict[str, Any]:
    """Compute Launch health at render time. Does not persist or seed a score."""

    counts = pipeline_counts(workflow_summary())
    return mission_health(
        shortlisted=counts["shortlisted"],
        approved=counts["approved"],
        outreach=counts["outreach"],
        measured=counts["measured"],
        tracking_assets=len(tracking_assets()),
        performance_events=len(performance_events()),
    )


def performance_events() -> list[dict[str, Any]]:
    context = active_context()
    return deepcopy(
        [
            event
            for event in st.session_state.performance_events
            if event.get("entry_type") == context["entry_type"]
            and event.get("entry_id") == context["entry_id"]
        ]
    )


def record_performance_event(
    creator_id: str,
    orders: int,
    revenue_usd: float,
    spend_usd: float,
    *,
    coupon: str | None = None,
    utm: str | None = None,
    content_asset_id: str | None = None,
    note: str | None = None,
    market: str | None = None,
    recorded_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Append one operator-recorded conversion for the active root. Never inferred."""

    require_write()
    if creator_id not in set(creators()["creator_id"]):
        raise ValueError(f"Unknown creator: {creator_id}")
    orders_n = int(orders)
    revenue_n = float(revenue_usd)
    spend_n = float(spend_usd)
    if orders_n < 0 or revenue_n < 0 or spend_n < 0:
        raise ValueError("orders, revenue_usd and spend_usd must be non-negative")
    context = active_context()
    stamped_market = (str(market).strip() if market else "") or _creator_market(creator_id) or context.get("market")
    record = {
        "event_id": f"perf_{len(st.session_state.performance_events) + 1:04d}",
        "creator_id": creator_id,
        "orders": orders_n,
        "revenue_usd": revenue_n,
        "spend_usd": spend_n,
        "coupon": coupon or None,
        "utm": utm or None,
        "content_asset_id": content_asset_id or None,
        "note": note or None,
        "market": stamped_market,
        "entry_type": context["entry_type"],
        "entry_id": context["entry_id"],
        "mission_id": context.get("mission_id"),
        "opportunity_id": context.get("opportunity_id"),
        "recorded_at": _as_recorded_at(recorded_at),
    }
    st.session_state.performance_events.append(record)
    persist_state()
    return deepcopy(record)


def tracking_assets() -> list[dict[str, Any]]:
    """Issued coupon / UTM records for the active root — not conversion events."""
    entry_type, entry_id = _current_root()
    return deepcopy(
        [
            case
            for case in st.session_state.outreach_cases
            if case.get("entry_type") == entry_type
            and case.get("entry_id") == entry_id
            and case.get("coupon")
        ]
    )


def format_contact_pack(pack: dict[str, Any]) -> str:
    """Plain-text pack for Streamlit copy. Empty optional sections are omitted."""

    message = str(pack.get("outreach_message") or "").strip()
    coupon = str(pack.get("coupon") or "").strip()
    deeplink = str(pack.get("deeplink") or "").strip()
    excerpt = str(pack.get("brief_excerpt") or "").strip()
    urls = [str(url).strip() for url in pack.get("live_evidence_urls") or [] if str(url).strip()]
    blocks: list[str] = []
    if message:
        blocks.append(message)
    if coupon:
        blocks.append(f"Coupon: {coupon}")
    if deeplink:
        blocks.append(f"UTM: {deeplink}")
    if excerpt:
        blocks.append(f"Brief excerpt: {excerpt}")
    if urls:
        blocks.append("Live evidence:\n" + "\n".join(urls))
    return "\n\n".join(blocks).strip() + ("\n" if blocks else "")


def contact_pack_for(creator_id: str) -> dict[str, Any]:
    """Read-only contact pack for an outreach-stage creator. Does not send."""

    current_state = creator_state(creator_id)
    case = _live_case_for(creator_id)
    if case is None:
        raise ValueError("An OutreachCase requires an approved creator collaboration")
    message = str(case.get("outreach_message") or "").strip()
    if not message:
        from services.llm_service import generate_outreach_message, generation_mode_label

        tone = str(case.get("outreach_tone") or "").strip() or _session_outreach_tone()
        message = generate_outreach_message(
            active_mission(),
            _creator_record(creator_id),
            coupon=case.get("coupon"),
            deeplink=case.get("deeplink"),
            brief_excerpt=_latest_brief_excerpt(creator_id),
            tone=tone,
        )
        source = generation_mode_label()
    else:
        tone = str(case.get("outreach_tone") or "").strip()
        source = str(case.get("outreach_source") or "")
    creator = _creator_record(creator_id)
    return {
        "creator_id": creator_id,
        "creator_name": creator.get("creator_name", creator_id),
        "outreach_case_id": case.get("outreach_case_id"),
        "state": current_state,
        "outreach_message": message,
        "coupon": case.get("coupon") or "",
        "deeplink": case.get("deeplink") or "",
        "utm_campaign": case.get("utm_campaign") or "",
        "utm_content": case.get("utm_content") or "",
        "brief_excerpt": _latest_brief_excerpt(creator_id),
        "live_evidence_urls": [
            str(item.get("url")).strip()
            for item in live_evidence_for(creator_id)
            if str(item.get("url") or "").strip()
        ],
        "tone": tone,
        "source": source,
    }


def refresh_outreach_message(creator_id: str, *, tone: str | None = None) -> dict[str, Any]:
    """Regenerate and persist the outreach note. Writers only; does not send."""

    require_write()
    if tone:
        st.session_state.studio_brand_tone = str(tone).strip()
    ensure_outreach_case(creator_id)
    live = _live_case_for(creator_id)
    if live is None:
        raise ValueError("An OutreachCase requires an approved creator collaboration")
    _fill_outreach_message(live, creator_id, force=True)
    live["updated_at"] = datetime.now(timezone.utc).isoformat()
    persist_state()
    return contact_pack_for(creator_id)


def attach_live_evidence(creator_id: str, channel: dict[str, Any]) -> dict[str, Any]:
    """Attach a labeled live-platform channel as evidence on the selected creator."""
    require_write()
    if creator_id not in set(creators()["creator_id"]):
        raise ValueError(f"Unknown creator: {creator_id}")
    channel_id = str(channel.get("channel_id") or "").strip()
    url = str(channel.get("url") or "").strip()
    if not channel_id or not url:
        raise ValueError("A live channel requires channel_id and url")
    context = active_context()
    existing = next(
        (
            item
            for item in st.session_state.live_evidence
            if item["creator_id"] == creator_id
            and item["channel_id"] == channel_id
            and item["entry_type"] == context["entry_type"]
            and item["entry_id"] == context["entry_id"]
        ),
        None,
    )
    if existing is not None:
        return deepcopy(existing)
    record = {
        "creator_id": creator_id,
        "channel_id": channel_id,
        "title": channel.get("title") or channel_id,
        "url": url,
        "source": channel.get("source") or "youtube_data_api",
        "country": channel.get("country"),
        "subscriber_count": channel.get("subscriber_count"),
        "attached_at": datetime.now(timezone.utc).isoformat(),
        "entry_type": context["entry_type"],
        "entry_id": context["entry_id"],
    }
    st.session_state.live_evidence.append(record)
    persist_state()
    return deepcopy(record)


def live_evidence_for(creator_id: str) -> list[dict[str, Any]]:
    entry_type, entry_id = _current_root()
    return deepcopy(
        [
            item
            for item in st.session_state.get("live_evidence", [])
            if item.get("creator_id") == creator_id
            and item.get("entry_type") == entry_type
            and item.get("entry_id") == entry_id
        ]
    )


_OUTREACH_BRIEF_STATES = frozenset(
    {
        "approved",
        "contacted",
        "negotiating",
        "contracted",
    }
)
_PAST_CONTENT_REVIEW = frozenset(
    {
        "content_in_review",
        "published",
        "measured",
    }
)
_BRIEF_STUDIO_REASON = "Brief generated in Content Studio"


def _advance_toward_content_in_review(creator_id: str) -> None:
    """Walk legal linear hops to content_in_review. No-op if not eligible.

    There is no ``in_outreach`` state. Outreach-eligible names are
    ``approved`` / ``contacted`` / ``negotiating`` / ``contracted``.
    Shortlisted, closed_lost, and states already at or past content
    review are left unchanged. Illegal jumps are never requested.
    """

    current = creator_state(creator_id)
    if current in _PAST_CONTENT_REVIEW or current not in _OUTREACH_BRIEF_STATES:
        return
    context = active_context()
    user = st.session_state.get("auth_user") or {}
    actor = str(user.get("display_name") or context.get("owner") or "Operator")
    evidence = [f"content-studio://brief/{creator_id}"]
    hops = 0
    while creator_state(creator_id) != "content_in_review":
        current = creator_state(creator_id)
        nxt = next(
            (
                state
                for state in WORKFLOW_STATES
                if can_transition(current, state) and state != "closed_lost"
            ),
            None,
        )
        if nxt is None or nxt in {"published", "measured"}:
            return
        transition_creator_state(
            creator_id,
            nxt,
            actor=actor,
            reason=_BRIEF_STUDIO_REASON,
            evidence=evidence,
        )
        hops += 1
        if hops > 8:
            return


def save_content_asset(
    creator_id: str,
    title: str,
    body: str,
    *,
    status: str = "in_review",
) -> dict[str, Any]:
    """Append a Content Studio brief for the active creator + root context."""

    require_write()
    if creator_id not in set(creators()["creator_id"]):
        raise ValueError(f"Unknown creator: {creator_id}")
    title_text = str(title or "").strip()
    body_text = str(body or "").strip()
    if not title_text or not body_text:
        raise ValueError("content asset title and body are required")
    context = active_context()
    excerpt = " ".join(body_text.split())[:280]
    record = {
        "asset_id": f"asset_{len(st.session_state.content_assets) + 1:04d}",
        "creator_id": creator_id,
        "title": title_text,
        "body": body_text,
        "excerpt": excerpt,
        "status": str(status or "in_review").strip() or "in_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entry_type": context["entry_type"],
        "entry_id": context["entry_id"],
        "mission_id": context.get("mission_id"),
        "opportunity_id": context.get("opportunity_id"),
    }
    st.session_state.content_assets.append(record)
    _advance_toward_content_in_review(creator_id)
    persist_state()
    return deepcopy(record)


def content_assets(*, status: str | None = None) -> list[dict[str, Any]]:
    """Saved content assets for the active root. Empty is honest."""

    context = active_context()
    wanted = str(status).strip() if status else None
    return deepcopy(
        [
            item
            for item in st.session_state.get("content_assets", [])
            if item.get("entry_type") == context["entry_type"]
            and item.get("entry_id") == context["entry_id"]
            and (wanted is None or item.get("status") == wanted)
        ]
    )


def content_assets_in_review_count() -> int:
    return len(content_assets(status="in_review"))
