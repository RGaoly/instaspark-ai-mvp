"""Deterministic inbound-mail pipeline for the dual-entry Creator Opportunity path.

This is not a live mailbox, not an LLM extractor, and not a price commitment.
Synthetic messages carry a labeled footer so field recovery is auditable. Translation
is pre-authored in the corpus. External send stays out of this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOUND_PATH = ROOT / "data" / "inbound_messages.json"

EXTRACTOR_VERSION = "labeled-footer-v1"
ROUTING_RULE_VERSION = "inbound-route-v1"

OWNERS: tuple[str, ...] = (
    "Global Creator Team",
    "US Creator Marketing",
    "LATAM Creator Marketing",
    "Mexico Marketing",
    "Affiliate Partnerships",
    "Brand Safety Review",
)

PERSONAS: tuple[str, ...] = (
    "kol",
    "mcn",
    "affiliate",
    "channel_partner",
    "spam",
    "impersonation",
)

INBOUND_STATUSES: tuple[str, ...] = (
    "received",
    "parsed",
    "qualified",
    "routed",
    "mission_matched",
    "reply_ready",
    "held",
    "rejected",
)

LANGUAGES: tuple[str, ...] = ("English", "Spanish", "German")

US_MISSION = {
    "mission_id": "launch_x5_us_001",
    "name": "Insta360 X5 United States Launch",
    "product": "Insta360 X5",
    "market": "United States",
    "language": "English",
    "max_cost_usd": 12000,
    "target_topics": ("cycling", "travel", "outdoor"),
}

MX_MISSION = {
    "mission_id": "launch_x5_mx_001",
    "name": "Insta360 X5 Mexico Launch",
    "product": "Insta360 X5",
    "market": "Mexico",
    "language": "Spanish",
    "max_cost_usd": 12000,
    "target_topics": ("cycling", "travel", "outdoor"),
}

DEMO_MISSIONS: tuple[dict[str, Any], ...] = (US_MISSION, MX_MISSION)

_FIELD_PATTERNS = {
    "intent": re.compile(r"^intent:\s*(.+)$", re.I | re.M),
    "market": re.compile(r"^market:\s*(.+)$", re.I | re.M),
    "language": re.compile(r"^language:\s*(.+)$", re.I | re.M),
    "price_usd": re.compile(r"^price_usd:\s*([0-9]+(?:\.[0-9]+)?)$", re.I | re.M),
    "availability": re.compile(r"^availability:\s*(.+)$", re.I | re.M),
    "product": re.compile(r"^product:\s*(.+)$", re.I | re.M),
    "channel": re.compile(r"^channel:\s*(.+)$", re.I | re.M),
    "persona": re.compile(r"^persona:\s*(.+)$", re.I | re.M),
}

_INTENT_STRENGTH = {
    "review+affiliate": 90.0,
    "review": 80.0,
    "affiliate": 78.0,
    "product seeding": 72.0,
    "paid review": 75.0,
    "mcn pitch": 48.0,
    "channel partnership": 70.0,
    "generic pitch": 38.0,
    "spam": 8.0,
    "impersonation": 18.0,
}

_TOPIC_WORDS = (
    "cycling",
    "ciclis",
    "outdoor",
    "travel",
    "viaje",
    "ski",
    "surf",
    "pov",
    "motorcycle",
    "moto",
    "adventure",
    "aventura",
)


def _strip(value: object) -> str:
    return str(value or "").strip()


def load_inbound_messages(path: str | Path = DEFAULT_INBOUND_PATH) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Inbound corpus must be a JSON array.")
    messages = [dict(item) for item in raw]
    ids = [_strip(item.get("message_id")) for item in messages]
    if any(not identifier for identifier in ids):
        raise ValueError("Every inbound message must have a message_id.")
    if len(ids) != len(set(ids)):
        raise ValueError("Inbound message IDs must be unique.")
    return messages


def extract_fields(raw_content: str) -> dict[str, Any]:
    """Recover labeled-footer fields. Does not read a parallel gold key."""

    text = str(raw_content or "")
    extracted: dict[str, Any] = {
        "intent": None,
        "market": None,
        "language": None,
        "price_usd": None,
        "availability": None,
        "product": None,
        "channel": None,
        "persona": None,
    }
    for key, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip()
        if key == "price_usd":
            extracted[key] = float(value)
        elif key == "persona":
            extracted[key] = value.strip().lower()
        else:
            extracted[key] = value
    return extracted


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def resolve_identity(
    sender_name: str,
    catalog: Iterable[Mapping[str, Any]],
    *,
    persona: str | None = None,
) -> dict[str, Any]:
    """Match a claimed name to the demo catalog. Impersonation is never auto-linked."""

    claimed = _strip(sender_name)
    normalized = _normalize_name(claimed)
    records = list(catalog)
    exact = next(
        (
            row
            for row in records
            if _normalize_name(str(row.get("creator_name") or "")) == normalized
        ),
        None,
    )
    extra_tokens = bool(re.search(r"\b(official|team|staff|admin|support)\b", normalized))
    if persona == "impersonation" or extra_tokens:
        suspected = exact
        if suspected is None:
            for row in records:
                catalog_name = _normalize_name(str(row.get("creator_name") or ""))
                if catalog_name and catalog_name in normalized:
                    suspected = row
                    break
        return {
            "identity_status": "impersonation",
            "creator_id": None,
            "matched_name": str((suspected or {}).get("creator_name") or "") or None,
            "suspected_creator_id": str((suspected or {}).get("creator_id") or "") or None,
            "confidence": 0.4 if suspected is not None else 0.2,
        }
    if exact is not None:
        return {
            "identity_status": "matched",
            "creator_id": str(exact.get("creator_id")),
            "matched_name": str(exact.get("creator_name")),
            "suspected_creator_id": None,
            "confidence": 0.95,
        }
    return {
        "identity_status": "new",
        "creator_id": None,
        "matched_name": None,
        "suspected_creator_id": None,
        "confidence": 0.55,
    }


def _intent_strength(intent: str | None, persona: str | None) -> float:
    if persona in {"spam", "impersonation"}:
        return _INTENT_STRENGTH[persona]
    key = _strip(intent).lower()
    return _INTENT_STRENGTH.get(key, 50.0)


def _content_fit(raw_content: str, topics: Sequence[str]) -> float:
    blob = (raw_content or "").lower()
    hits = sum(1 for word in _TOPIC_WORDS if word in blob)
    mission_hits = sum(1 for topic in topics if str(topic).lower() in blob)
    return min(100.0, 20.0 * hits + 15.0 * mission_hits)


def _commercial_fit(price_usd: float | None, max_cost_usd: float) -> float:
    if price_usd is None:
        return 50.0
    if price_usd <= 0:
        return 40.0
    if price_usd > max_cost_usd:
        return 28.0
    return max(40.0, 100.0 - (price_usd / max_cost_usd) * 40.0)


def _brand_safety(persona: str | None) -> float:
    if persona == "spam":
        return 8.0
    if persona == "impersonation":
        return 12.0
    if persona == "mcn":
        return 62.0
    return 86.0


def score_inbound(
    extracted: Mapping[str, Any],
    raw_content: str,
    *,
    mission: Mapping[str, Any] | None = None,
    translated_content: str = "",
) -> dict[str, Any]:
    persona = extracted.get("persona")
    topics = tuple((mission or US_MISSION).get("target_topics") or ())
    budget = float((mission or US_MISSION).get("max_cost_usd") or 12000)
    intent = _intent_strength(extracted.get("intent"), persona)
    content = _content_fit(f"{raw_content}\n{translated_content}", topics)
    commercial = _commercial_fit(extracted.get("price_usd"), budget)
    safety = _brand_safety(persona)
    total = round(intent * 0.30 + content * 0.30 + commercial * 0.20 + safety * 0.20, 1)
    return {
        "opportunity_score": total,
        "score_breakdown": {
            "intent_strength": round(intent, 1),
            "content_fit": round(content, 1),
            "commercial_fit": round(commercial, 1),
            "brand_safety": round(safety, 1),
        },
        "high_potential": total >= 75 and persona not in {"spam", "impersonation"},
    }


def reverse_match_mission(
    extracted: Mapping[str, Any],
    missions: Sequence[Mapping[str, Any]] = DEMO_MISSIONS,
) -> dict[str, Any]:
    product = _strip(extracted.get("product")).lower()
    market = _strip(extracted.get("market"))
    if extracted.get("persona") in {"spam", "impersonation"}:
        return {
            "mission_id": None,
            "match_reason": "Held: identity or spam risk before any mission link.",
            "confidence": 0.1,
        }
    if product and "x5" not in product and "insta360" not in product:
        return {
            "mission_id": None,
            "match_reason": "Product interest is not the X5 launch SKU.",
            "confidence": 0.2,
        }
    for mission in missions:
        if _strip(mission.get("market")) == market:
            return {
                "mission_id": str(mission["mission_id"]),
                "match_reason": f"Market {market} reverse-matched to {mission.get('name')}.",
                "confidence": 0.86,
            }
    return {
        "mission_id": None,
        "match_reason": f"No launch mission in this demo for market {market or 'unknown'}.",
        "confidence": 0.35,
    }


def recommend_owner(extracted: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    persona = extracted.get("persona")
    market = _strip(extracted.get("market"))
    if persona in {"spam", "impersonation"} or identity.get("identity_status") == "impersonation":
        owner = "Brand Safety Review"
        reason = "Identity or spam risk routes to brand safety, not a market owner."
    elif persona == "affiliate":
        owner = "Affiliate Partnerships"
        reason = "Affiliate intent uses the affiliate desk."
    elif persona == "channel_partner":
        owner = "Mexico Marketing" if market == "Mexico" else "Global Creator Team"
        reason = "Channel-partner pitch uses the regional marketing owner."
    elif persona == "mcn":
        owner = "Global Creator Team"
        reason = "Agency/MCN batches stay with the global creator desk."
    elif market == "United States":
        owner = "US Creator Marketing"
        reason = "US English KOL inbound uses US Creator Marketing."
    elif market == "Mexico":
        owner = "LATAM Creator Marketing"
        reason = "Mexico Spanish KOL inbound uses LATAM Creator Marketing."
    else:
        owner = "Global Creator Team"
        reason = "No regional owner for this market in the six-person demo roster."
    if owner not in OWNERS:
        raise ValueError(f"Owner {owner} is not in the demo roster")
    return {
        "owner": owner,
        "reason": reason,
        "rule_version": ROUTING_RULE_VERSION,
        "confidence": 0.3 if owner == "Brand Safety Review" else 0.82,
    }


def inbound_status_for(
    extracted: Mapping[str, Any],
    identity: Mapping[str, Any],
    mission_match: Mapping[str, Any],
    owner: Mapping[str, Any],
) -> str:
    if extracted.get("persona") in {"spam", "impersonation"}:
        return "held"
    if identity.get("identity_status") == "impersonation":
        return "held"
    if mission_match.get("mission_id") and owner.get("owner"):
        return "mission_matched"
    if owner.get("owner"):
        return "routed"
    if extracted.get("intent"):
        return "qualified"
    return "parsed"


def draft_reply(
    *,
    language: str,
    sender_name: str,
    product: str | None,
    availability: str | None,
) -> str:
    """Local-language draft. Never commits a price and never sends."""

    name = sender_name or "there"
    sku = product or "Insta360 X5"
    window = availability or "your stated window"
    if str(language).lower().startswith("span"):
        return (
            f"Hola {name},\n\n"
            f"Gracias por escribir sobre {sku}. Este borrador no confirma tarifa ni envía producto. "
            f"Si el equipo aprueba, el siguiente paso es un media kit y una fecha en {window}. "
            "Nada se envía fuera de InstaSpark hasta una aprobación humana.\n\n"
            "Equipo de creadores InstaSpark"
        )
    if str(language).lower().startswith("germ") or language == "German":
        return (
            f"Hallo {name},\n\n"
            f"danke für die Nachricht zu {sku}. Dieser Entwurf bestätigt keinen Preis und versendet nichts. "
            f"Nach menschlicher Freigabe wären Media Kit und ein Termin in {window} der nächste Schritt. "
            "Es geht keine externe Mail raus, bevor jemand freigibt.\n\n"
            "InstaSpark Creator Team"
        )
    return (
        f"Hi {name},\n\n"
        f"Thanks for reaching out about {sku}. This draft does not confirm a rate and does not ship a unit. "
        f"If the owner approves, the next step is a media kit and a date in {window}. "
        "Nothing is sent outside InstaSpark until a human approves.\n\n"
        "InstaSpark creator team"
    )


def sla_risk(received_at: str, status: str) -> bool:
    """Heuristic for the demo corpus: timestamps ending in older hours are at risk if still open."""

    if status in {"mission_matched", "reply_ready", "rejected"}:
        return False
    return bool(re.search(r"T0[0-6]:", received_at or ""))


def materialize_opportunity(
    message: Mapping[str, Any],
    catalog: Iterable[Mapping[str, Any]],
    missions: Sequence[Mapping[str, Any]] = DEMO_MISSIONS,
) -> dict[str, Any]:
    """Parse one synthetic message into an opportunity plus routing decision."""

    raw = str(message.get("raw_content") or "")
    extracted = extract_fields(raw)
    identity = resolve_identity(
        str(message.get("sender_name") or ""),
        catalog,
        persona=extracted.get("persona"),
    )
    mission_match = reverse_match_mission(extracted, missions)
    matched_mission = next(
        (item for item in missions if item.get("mission_id") == mission_match.get("mission_id")),
        None,
    )
    scored = score_inbound(
        extracted,
        raw,
        mission=matched_mission,
        translated_content=str(message.get("translated_content") or ""),
    )
    owner = recommend_owner(extracted, identity)
    status = inbound_status_for(extracted, identity, mission_match, owner)
    creator_id = identity.get("creator_id") or ""
    reply = draft_reply(
        language=str(extracted.get("language") or message.get("language") or "English"),
        sender_name=str(message.get("sender_name") or ""),
        product=extracted.get("product"),
        availability=extracted.get("availability"),
    )
    opportunity_id = str(message.get("opportunity_id") or "").strip() or (
        str(message.get("message_id") or "").replace("MSG", "OPP-INB")
    )
    routing = {
        "recommended_owner": owner["owner"],
        "team": owner["owner"],
        "rule_version": ROUTING_RULE_VERSION,
        "model_version": EXTRACTOR_VERSION,
        "confidence": owner["confidence"],
        "reason": owner["reason"],
        "human_override": None,
        "opportunity_id": opportunity_id,
        "message_id": message.get("message_id"),
    }
    link = {
        "opportunity_id": opportunity_id,
        "mission_id": mission_match.get("mission_id"),
        "creator_id": creator_id or None,
        "match_score": scored["opportunity_score"],
        "match_reason": mission_match["match_reason"],
        "status": "suggested" if mission_match.get("mission_id") else "unlinked",
        "linked_by": "rule",
        "rule_version": ROUTING_RULE_VERSION,
    }
    title = _strip(message.get("title")) or (
        f"{extracted.get('intent') or 'Inbound'} · {message.get('sender_name') or message.get('message_id')}"
    )
    return {
        "opportunity": {
            "opportunity_id": opportunity_id,
            "opportunity_type": "inbound",
            "creator_id": creator_id,
            "title": title,
            "source": str(message.get("source_channel") or extracted.get("channel") or "email"),
            "source_channel": str(message.get("source_channel") or extracted.get("channel") or "email"),
            "market": extracted.get("market") or message.get("market") or "",
            "language": extracted.get("language") or message.get("language") or "",
            "hypothesis": str(message.get("summary") or message.get("translated_content") or "")[:280],
            "evidence": [
                f"inbound://{message.get('message_id')}",
                f"extractor:{EXTRACTOR_VERSION}",
                str(message.get("summary") or "").strip() or "Original message retained.",
            ],
            "status": "discovered" if status in {"held", "parsed", "received"} else "qualified",
            "inbound_status": status,
            "owner": owner["owner"],
            "observed_at": message.get("received_at") or "",
            "created_at": message.get("received_at") or "",
            "suggested_action": (
                "Hold for brand-safety review; do not reply or commit a price."
                if status == "held"
                else "Confirm owner, mission link and reply draft before any external send."
            ),
            "linked_mission_id": None,
            "message_id": message.get("message_id"),
            "thread_id": message.get("thread_id"),
            "asking_price_usd": extracted.get("price_usd"),
            "availability": extracted.get("availability"),
            "collaboration_type": extracted.get("intent"),
            "product_interest": extracted.get("product"),
            "opportunity_score": scored["opportunity_score"],
            "score_breakdown": scored["score_breakdown"],
            "high_potential": scored["high_potential"],
            "recommended_mission_id": mission_match.get("mission_id"),
            "recommended_owner": owner["owner"],
            "identity_status": identity["identity_status"],
            "persona": extracted.get("persona"),
            "raw_content": raw,
            "translated_content": message.get("translated_content") or "",
            "summary": message.get("summary") or "",
            "reply_draft": reply,
            "sender": message.get("sender") or "",
            "sender_name": message.get("sender_name") or "",
            "received_at": message.get("received_at") or "",
            "sla_risk": sla_risk(str(message.get("received_at") or ""), status),
            "routing_rule_version": ROUTING_RULE_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "attachments": list(message.get("attachments") or []),
        },
        "routing_decision": routing,
        "mission_link": link,
        "extracted": extracted,
        "identity": identity,
    }


def materialize_corpus(
    messages: Sequence[Mapping[str, Any]] | None = None,
    catalog: Iterable[Mapping[str, Any]] | None = None,
    missions: Sequence[Mapping[str, Any]] = DEMO_MISSIONS,
    path: str | Path = DEFAULT_INBOUND_PATH,
) -> dict[str, list[dict[str, Any]]]:
    rows = list(messages if messages is not None else load_inbound_messages(path))
    creators = list(catalog or ())
    opportunities: list[dict[str, Any]] = []
    routing_decisions: list[dict[str, Any]] = []
    mission_links: list[dict[str, Any]] = []
    for message in rows:
        packed = materialize_opportunity(message, creators, missions)
        opportunities.append(packed["opportunity"])
        routing_decisions.append(packed["routing_decision"])
        mission_links.append(packed["mission_link"])
    return {
        "opportunities": opportunities,
        "routing_decisions": routing_decisions,
        "mission_links": mission_links,
        "messages": [dict(item) for item in rows],
    }
