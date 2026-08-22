"""Shared domain contracts and creator-collaboration workflow rules.

This module deliberately has no UI, persistence, or third-party dependencies.  It
is the common vocabulary used by both product entry points: a launch mission and
a creator opportunity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union


class EntryType(str, Enum):
    """The two supported ways to start creator collaboration work."""

    MISSION = "mission"
    OPPORTUNITY = "opportunity"

    # Product-language aliases make call sites self-documenting while keeping
    # the persisted values consistent with the active-context contract.
    LAUNCH_MISSION = "mission"
    CREATOR_OPPORTUNITY = "opportunity"


class CollaborationStatus(str, Enum):
    """Canonical creator-collaboration states shared by every feature."""

    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    SHORTLISTED = "shortlisted"
    APPROVED = "approved"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    CONTRACTED = "contracted"
    CONTENT_IN_REVIEW = "content_in_review"
    PUBLISHED = "published"
    MEASURED = "measured"
    CLOSED_LOST = "closed_lost"


# String values are exported for straightforward UI controls and persistence.
WORKFLOW_STATES: Tuple[str, ...] = tuple(status.value for status in CollaborationStatus)

_LINEAR_WORKFLOW: Tuple[CollaborationStatus, ...] = (
    CollaborationStatus.DISCOVERED,
    CollaborationStatus.QUALIFIED,
    CollaborationStatus.SHORTLISTED,
    CollaborationStatus.APPROVED,
    CollaborationStatus.CONTACTED,
    CollaborationStatus.NEGOTIATING,
    CollaborationStatus.CONTRACTED,
    CollaborationStatus.CONTENT_IN_REVIEW,
    CollaborationStatus.PUBLISHED,
    CollaborationStatus.MEASURED,
)

# A collaboration may be abandoned while it is still being evaluated or
# negotiated.  Once contracted, downstream exceptions are audit events rather
# than a silent rewrite to a sales-style ``closed_lost`` outcome.
_ALLOWED_TRANSITIONS = {
    state: {next_state}
    for state, next_state in zip(_LINEAR_WORKFLOW, _LINEAR_WORKFLOW[1:])
}
_ALLOWED_TRANSITIONS[CollaborationStatus.MEASURED] = set()
_ALLOWED_TRANSITIONS[CollaborationStatus.CLOSED_LOST] = set()
for state in _LINEAR_WORKFLOW[:6]:
    _ALLOWED_TRANSITIONS[state].add(CollaborationStatus.CLOSED_LOST)


StatusLike = Union[CollaborationStatus, str]
EntryTypeLike = Union[EntryType, str]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_text(value: str, field_name: str) -> str:
    if value is None:
        raise ValueError("{} is required".format(field_name))
    text = str(value).strip()
    if not text:
        raise ValueError("{} is required".format(field_name))
    return text


def _status(value: StatusLike) -> CollaborationStatus:
    if isinstance(value, CollaborationStatus):
        return value
    return CollaborationStatus(str(value).strip().lower())


def _entry_type(value: EntryTypeLike) -> EntryType:
    if isinstance(value, EntryType):
        return value
    normalized = str(value).strip().lower()
    normalized = {
        "launch_mission": EntryType.MISSION.value,
        "creator_opportunity": EntryType.OPPORTUNITY.value,
    }.get(normalized, normalized)
    return EntryType(normalized)


def _evidence_items(evidence: Union[str, Iterable[str]]) -> Tuple[str, ...]:
    if evidence is None:
        raise ValueError("evidence must contain at least one item")
    if isinstance(evidence, str):
        items = (evidence.strip(),)
    else:
        items = tuple(str(item).strip() for item in evidence if item is not None)
    items = tuple(item for item in items if item)
    if not items:
        raise ValueError("evidence must contain at least one item")
    return items


def can_transition(from_state: StatusLike, to_state: StatusLike) -> bool:
    """Return whether a direct workflow transition is legal.

    Unknown values are treated as invalid instead of leaking an enum conversion
    error into UI code.
    """

    try:
        source = _status(from_state)
        target = _status(to_state)
    except (TypeError, ValueError):
        return False
    return target in _ALLOWED_TRANSITIONS[source]


def next_linear_state(from_state: StatusLike) -> Optional[str]:
    """Return the next linear hop. ``closed_lost`` is never the primary advance.

    Unknown or terminal states return ``None`` instead of inventing a label
    such as ``in_outreach``.
    """

    try:
        source = _status(from_state)
    except (TypeError, ValueError):
        return None
    for candidate in _LINEAR_WORKFLOW:
        if can_transition(source, candidate):
            return candidate.value
    return None


def allowed_next_states(from_state: StatusLike) -> Tuple[str, ...]:
    """Legal hops from ``from_state`` in canonical ``WORKFLOW_STATES`` order."""

    try:
        source = _status(from_state)
    except (TypeError, ValueError):
        return ()
    return tuple(state for state in WORKFLOW_STATES if can_transition(source, state))


@dataclass(frozen=True)
class TransitionEvent:
    """Immutable audit record emitted for every accepted state change."""

    entity_id: str
    from_state: CollaborationStatus
    to_state: CollaborationStatus
    actor: str
    timestamp: datetime
    reason: str
    evidence: Tuple[str, ...]
    entry_type: EntryType
    entry_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-ready representation suitable for persistence."""

        record = asdict(self)
        record["from_state"] = self.from_state.value
        record["to_state"] = self.to_state.value
        record["entry_type"] = self.entry_type.value
        record["timestamp"] = self.timestamp.isoformat()
        record["evidence"] = list(self.evidence)
        return record


def transition_event(
    entity_id: str,
    from_state: StatusLike,
    to_state: StatusLike,
    actor: str,
    reason: str,
    evidence: Union[str, Iterable[str]],
    entry_type: EntryTypeLike,
    entry_id: str,
    timestamp: Optional[datetime] = None,
) -> TransitionEvent:
    """Validate a state change and create its immutable audit event.

    Raises ``ValueError`` for illegal transitions or incomplete audit data.
    ``timestamp`` is injectable for deterministic imports/tests and defaults to
    the current UTC time.
    """

    source = _status(from_state)
    target = _status(to_state)
    if not can_transition(source, target):
        raise ValueError(
            "illegal collaboration transition: {} -> {}".format(
                source.value, target.value
            )
        )

    occurred_at = timestamp or _utc_now()
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")

    return TransitionEvent(
        entity_id=_require_text(entity_id, "entity_id"),
        from_state=source,
        to_state=target,
        actor=_require_text(actor, "actor"),
        timestamp=occurred_at,
        reason=_require_text(reason, "reason"),
        evidence=_evidence_items(evidence),
        entry_type=_entry_type(entry_type),
        entry_id=_require_text(entry_id, "entry_id"),
    )


@dataclass
class Mission:
    mission_id: str
    name: str
    product: str
    markets: Tuple[str, ...] = ()
    languages: Tuple[str, ...] = ()
    objective: str = ""
    campaign_dates: Optional[str] = None
    budget_usd: Optional[float] = None
    owner: str = ""
    status: str = "draft"
    created_at: datetime = field(default_factory=_utc_now)
    entry_type: EntryType = field(default=EntryType.LAUNCH_MISSION, init=False)


@dataclass
class Opportunity:
    opportunity_id: str
    creator_id: str
    title: str
    opportunity_type: str = "creator_signal"
    source: str = ""
    source_url: Optional[str] = None
    market: Optional[str] = None
    language: str = ""
    hypothesis: str = ""
    status: CollaborationStatus = CollaborationStatus.DISCOVERED
    observed_at: datetime = field(default_factory=_utc_now)
    evidence: Tuple[str, ...] = ()
    suggested_action: str = ""
    linked_mission_id: Optional[str] = None
    owner: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    entry_type: EntryType = field(default=EntryType.CREATOR_OPPORTUNITY, init=False)


@dataclass
class Creator:
    creator_id: str
    display_name: str
    platforms: Tuple[str, ...] = ()
    markets: Tuple[str, ...] = ()
    languages: Tuple[str, ...] = ()
    profile_urls: Mapping[str, str] = field(default_factory=dict)


@dataclass
class Match:
    match_id: str
    creator_id: str
    mission_id: str
    entry_type: EntryType
    entry_id: str
    score: float
    gate_passed: bool = True
    rationale: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()
    opportunity_id: Optional[str] = None
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Decision:
    decision_id: str
    match_id: Optional[str]
    outcome: str
    actor: str
    reason_code: str
    reason: str
    note: str
    evidence: Tuple[str, ...]
    creator_id: Optional[str] = None
    mission_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    decided_at: datetime = field(default_factory=_utc_now)


@dataclass
class OutreachCase:
    outreach_case_id: str
    creator_id: str
    entry_type: EntryType
    entry_id: str
    owner: str
    status: CollaborationStatus = CollaborationStatus.DISCOVERED
    channel: Optional[str] = None
    next_action: Optional[str] = None
    mission_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    transitions: List[TransitionEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.mission_id and not self.opportunity_id:
            raise ValueError("OutreachCase requires a mission_id or opportunity_id")

    def transition(
        self,
        to_state: StatusLike,
        actor: str,
        reason: str,
        evidence: Union[str, Iterable[str]],
        timestamp: Optional[datetime] = None,
    ) -> TransitionEvent:
        """Move this case once and append the corresponding audit record."""

        event = transition_event(
            entity_id=self.outreach_case_id,
            from_state=self.status,
            to_state=to_state,
            actor=actor,
            reason=reason,
            evidence=evidence,
            entry_type=self.entry_type,
            entry_id=self.entry_id,
            timestamp=timestamp,
        )
        self.status = event.to_state
        self.updated_at = event.timestamp
        self.transitions.append(event)
        return event


@dataclass
class ContentAsset:
    content_asset_id: str
    outreach_case_id: str
    creator_id: str
    asset_type: str
    version: int
    review_status: str
    locale: Optional[str] = None
    mission_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    source_urls: Tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)


# Display-only match labels. Thresholds are inclusive lower bounds.
MATCH_TIER_THRESHOLDS: Tuple[Tuple[float, str], ...] = (
    (80.0, "Excellent"),
    (70.0, "Strong"),
    (55.0, "Moderate"),
    (0.0, "Weak"),
)

# Pipeline buckets used by Launch Mission health. Later states count as
# earlier ones so approving a shortlist does not look like "Needs shortlist".
HEALTH_SHORTLISTED_STATES: Tuple[str, ...] = (
    CollaborationStatus.SHORTLISTED.value,
    CollaborationStatus.APPROVED.value,
    CollaborationStatus.CONTACTED.value,
    CollaborationStatus.NEGOTIATING.value,
    CollaborationStatus.CONTRACTED.value,
    CollaborationStatus.CONTENT_IN_REVIEW.value,
    CollaborationStatus.PUBLISHED.value,
    CollaborationStatus.MEASURED.value,
)
HEALTH_APPROVED_STATES: Tuple[str, ...] = HEALTH_SHORTLISTED_STATES[1:]
HEALTH_OUTREACH_STATES: Tuple[str, ...] = HEALTH_APPROVED_STATES[1:]


def match_tier(total_score: float) -> str:
    """Return Excellent / Strong / Moderate / Weak from a 0–100 total_score."""

    score = float(total_score)
    for threshold, label in MATCH_TIER_THRESHOLDS:
        if score >= threshold:
            return label
    return "Weak"


def match_label(total_score: float) -> str:
    return "{} Match".format(match_tier(total_score))


def match_fit_label(total_score: float) -> str:
    return "{} Fit".format(match_tier(total_score))


def _split_catalog_tokens(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [item.strip() for item in value.replace("|", ",").split(",") if item.strip()]
        return tuple(parts)
    try:
        return tuple(str(item).strip() for item in list(value) if str(item).strip())
    except TypeError:
        text = str(value).strip()
        return (text,) if text else ()


def declared_platforms(
    creator: Mapping[str, Any],
    live_evidence: Iterable[Mapping[str, Any]] | None = None,
) -> Tuple[str, ...]:
    """Platforms we can actually name: catalog field, then attached live evidence.

    The demo CSV has no platforms column. Do not invent Instagram or TikTok.
    """

    seen: list[str] = []
    for item in _split_catalog_tokens(creator.get("platforms")):
        if item not in seen:
            seen.append(item)
    for row in live_evidence or ():
        blob = " ".join(
            str(row.get(key) or "") for key in ("source", "url", "title")
        ).lower()
        if "youtube" in blob and "YouTube" not in seen:
            seen.append("YouTube")
    return tuple(seen)


def pipeline_counts(summary: Mapping[str, int]) -> Dict[str, int]:
    """Sum workflow states into shortlisted / approved / outreach / measured."""

    def _sum(states: Tuple[str, ...]) -> int:
        return sum(int(summary.get(state, 0) or 0) for state in states)

    return {
        "shortlisted": _sum(HEALTH_SHORTLISTED_STATES),
        "approved": _sum(HEALTH_APPROVED_STATES),
        "outreach": _sum(HEALTH_OUTREACH_STATES),
        "measured": int(summary.get(CollaborationStatus.MEASURED.value, 0) or 0),
    }


def mission_health(
    *,
    shortlisted: int,
    approved: int,
    outreach: int,
    measured: int,
    tracking_assets: int,
    performance_events: int,
) -> Dict[str, Any]:
    """Render-time health from the active creator pipeline. Not persisted.

    Bands (first match wins):

    ============  =====  ================================
    Condition     Score  Label
    0 shortlisted 28     Needs shortlist
    shortlisted,
    none approved 54     Matching in progress
    approved with
    tracking, no
    events        72     Outreach live, no conversions yet
    ≥1 performance
    event         88     Measured
    ============  =====  ================================
    """

    counts = {
        "shortlisted": int(shortlisted),
        "approved": int(approved),
        "outreach": int(outreach),
        "measured": int(measured),
        "tracking_assets": int(tracking_assets),
        "performance_events": int(performance_events),
    }
    if counts["performance_events"] >= 1:
        band = {
            "score": 88,
            "band": "measured",
            "label": "Measured",
            "note": "Sourced performance events",
        }
    elif counts["approved"] >= 1 and counts["tracking_assets"] >= 1:
        band = {
            "score": 72,
            "band": "outreach_live",
            "label": "Outreach live",
            "note": "No conversions yet",
        }
    elif counts["shortlisted"] >= 1:
        band = {
            "score": 54,
            "band": "matching",
            "label": "Matching in progress",
            "note": "Shortlisted, none approved",
        }
    else:
        band = {
            "score": 28,
            "band": "needs_shortlist",
            "label": "Needs shortlist",
            "note": "No creators shortlisted",
        }
    return {**band, "counts": counts}


# Launch Mission process strip. Later pipeline states count as earlier ones,
# matching pipeline_counts / mission_health, so an approval is not "Needs shortlist".
LAUNCH_PROGRESS_STEPS: Tuple[str, ...] = ("shortlist", "approve", "measure")

PERIOD_WINDOW_DAYS: Dict[str, Optional[int]] = {
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
    "All recorded events": None,
}


def launch_progress(
    *,
    shortlisted: int,
    approved: int,
    tracking_assets: int,
    performance_events: int,
) -> Dict[str, Any]:
    """Map live pipeline counts to process steps and the next real task.

    Status is ``done`` / ``current`` / ``pending``. Exactly one step is
    ``current`` until every step is ``done``.
    """

    shortlisted_n = int(shortlisted)
    approved_n = int(approved)
    tracking_n = int(tracking_assets)
    events_n = int(performance_events)
    shortlist_done = shortlisted_n >= 1
    approve_done = approved_n >= 1 and tracking_n >= 1
    measure_done = events_n >= 1

    if not shortlist_done:
        statuses = ("current", "pending", "pending")
    elif not approve_done:
        statuses = ("done", "current", "pending")
    elif not measure_done:
        statuses = ("done", "done", "current")
    else:
        statuses = ("done", "done", "done")

    steps = [
        {
            "id": "shortlist",
            "title": "Shortlist",
            "note": "{} shortlisted+".format(shortlisted_n),
            "status": statuses[0],
            "count": shortlisted_n,
        },
        {
            "id": "approve",
            "title": "Approve / outreach",
            "note": "{} approved · {} tracking assets".format(approved_n, tracking_n),
            "status": statuses[1],
            "count": approved_n,
        },
        {
            "id": "measure",
            "title": "Measure",
            "note": "{} performance events".format(events_n),
            "status": statuses[2],
            "count": events_n,
        },
    ]
    next_task = {
        "shortlist": {
            "id": "shortlist",
            "title": "Shortlist creators",
            "note": "Add at least one creator to the shortlist.",
        },
        "approve": {
            "id": "approve",
            "title": "Approve one creator",
            "note": "Approval mints a coupon and UTM tracking asset.",
        },
        "measure": {
            "id": "measure",
            "title": "Record a conversion on Growth Review",
            "note": "ROI stays 0x until an operator records an event.",
        },
    }
    current = next((step for step in steps if step["status"] == "current"), None)
    if current is None:
        upcoming = [
            {
                "id": "complete",
                "title": "Review recorded outcomes",
                "note": "Sourced events are on Growth Review.",
            }
        ]
    else:
        upcoming = [next_task[current["id"]]]
    return {"steps": steps, "upcoming": upcoming, "current_id": None if current is None else current["id"]}


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse a timezone-aware ISO timestamp. Naive values are treated as UTC."""

    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_dated_records(
    records: Iterable[Mapping[str, Any]],
    *,
    period_days: Optional[int] = None,
    market: Optional[str] = None,
    now: Optional[datetime] = None,
    timestamp_field: str = "recorded_at",
    market_field: str = "market",
) -> List[Dict[str, Any]]:
    """Filter events or tracking rows by a real time window and market.

    Missing timestamps are excluded from a bounded period (they cannot prove
    they fall inside the window) and included when the period is all records.
    Missing markets are excluded from a specific-market filter.
    ``market`` values ``All``, ``All markets``, empty, or ``None`` disable
    the market predicate.
    """

    clock = now or _utc_now()
    if clock.tzinfo is None or clock.utcoffset() is None:
        clock = clock.replace(tzinfo=timezone.utc)
    clock = clock.astimezone(timezone.utc)
    market_key = str(market).strip() if market is not None else ""
    apply_market = bool(market_key) and market_key not in {"All", "All markets"}
    cutoff = None if period_days is None else clock - timedelta(days=int(period_days))

    matched: List[Dict[str, Any]] = []
    for record in records:
        row = dict(record)
        if apply_market and str(row.get(market_field) or "").strip() != market_key:
            continue
        if cutoff is not None:
            stamp = parse_iso_datetime(row.get(timestamp_field))
            if stamp is None or stamp < cutoff:
                continue
        matched.append(row)
    return matched


def filter_performance_events(
    events: Iterable[Mapping[str, Any]],
    *,
    period_days: Optional[int] = None,
    market: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Keep performance events inside the selected period and market."""

    return filter_dated_records(
        events,
        period_days=period_days,
        market=market,
        now=now,
        timestamp_field="recorded_at",
        market_field="market",
    )


def attributed_roi(events: Iterable[Mapping[str, Any]]) -> float:
    """Revenue / spend from recorded events. Empty or zero spend is 0x."""

    revenue = sum(float(event.get("revenue_usd", 0) or 0) for event in events)
    spend = sum(float(event.get("spend_usd", 0) or 0) for event in events)
    return revenue / spend if spend else 0.0


@dataclass
class PerformanceEvent:
    performance_event_id: str
    outreach_case_id: str
    creator_id: str
    metric_name: str
    value: float
    occurred_at: datetime
    source: str
    mission_id: Optional[str] = None
    content_asset_id: Optional[str] = None
    time_window: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


__all__ = [
    "CollaborationStatus",
    "ContentAsset",
    "Creator",
    "Decision",
    "EntryType",
    "HEALTH_APPROVED_STATES",
    "HEALTH_OUTREACH_STATES",
    "HEALTH_SHORTLISTED_STATES",
    "LAUNCH_PROGRESS_STEPS",
    "MATCH_TIER_THRESHOLDS",
    "PERIOD_WINDOW_DAYS",
    "Match",
    "Mission",
    "Opportunity",
    "OutreachCase",
    "PerformanceEvent",
    "TransitionEvent",
    "WORKFLOW_STATES",
    "allowed_next_states",
    "attributed_roi",
    "can_transition",
    "declared_platforms",
    "filter_dated_records",
    "filter_performance_events",
    "launch_progress",
    "match_fit_label",
    "match_label",
    "match_tier",
    "mission_health",
    "next_linear_state",
    "parse_iso_datetime",
    "pipeline_counts",
    "transition_event",
]
