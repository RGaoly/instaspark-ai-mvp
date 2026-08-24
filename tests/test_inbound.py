"""Inbound golden-path tests: corpus, parse, identity, score, route, no send."""

from __future__ import annotations

from pathlib import Path

from src.data_loader import load_creators
from src.inbound import (
    DEMO_MISSIONS,
    EXTRACTOR_VERSION,
    LANGUAGES,
    OWNERS,
    PERSONAS,
    ROUTING_RULE_VERSION,
    draft_reply,
    extract_fields,
    load_inbound_messages,
    materialize_corpus,
    materialize_opportunity,
    recommend_owner,
    resolve_identity,
    reverse_match_mission,
)


ROOT = Path(__file__).resolve().parents[1]


def _catalog() -> list[dict]:
    return load_creators(ROOT / "data" / "creators.csv").to_dict("records")


def test_inbound_corpus_matches_pilot_scope():
    messages = load_inbound_messages()
    assert len(messages) == 30
    languages = {item["language"] for item in messages}
    assert languages == set(LANGUAGES)
    personas = {item["gold"]["persona"] for item in messages}
    assert set(PERSONAS) <= personas
    ids = [item["message_id"] for item in messages]
    assert len(ids) == len(set(ids))
    assert all(item["raw_content"] for item in messages)
    assert all(item["translated_content"] for item in messages)
    assert all(item.get("gold") for item in messages)


def test_extractor_recovers_labeled_footer_not_gold_key():
    messages = load_inbound_messages()
    recovered = 0
    for message in messages:
        gold = message["gold"]
        extracted = extract_fields(message["raw_content"])
        assert "gold" not in extracted
        assert extracted["intent"] == gold["intent"]
        assert extracted["market"] == gold["market"]
        assert extracted["language"] == gold["language"]
        assert extracted["product"] == gold["product"]
        assert extracted["persona"] == gold["persona"]
        assert float(extracted["price_usd"]) == float(gold["price_usd"])
        recovered += 1
    assert recovered == 30


def test_identity_matches_catalog_and_flags_impersonation():
    catalog = _catalog()
    diego = resolve_identity("Diego Trail", catalog, persona="kol")
    assert diego["identity_status"] == "matched"
    assert diego["creator_id"] == "C003"

    lucia = resolve_identity("Lucía García", catalog, persona="kol")
    assert lucia["identity_status"] == "new"
    assert lucia["creator_id"] is None

    fake = resolve_identity("Diego Trail Official", catalog, persona="impersonation")
    assert fake["identity_status"] == "impersonation"
    assert fake["creator_id"] is None
    assert fake["suspected_creator_id"] == "C003"


def test_germany_has_no_demo_mission_link():
    match = reverse_match_mission(
        {"product": "Insta360 X5", "market": "Germany", "persona": "kol"}
    )
    assert match["mission_id"] is None
    assert "No launch mission" in match["match_reason"]

    mx = reverse_match_mission(
        {"product": "Insta360 X5", "market": "Mexico", "persona": "kol"}
    )
    assert mx["mission_id"] == "launch_x5_mx_001"


def test_six_owners_cover_routing_and_brand_safety():
    assert len(OWNERS) == 6
    catalog = _catalog()
    packed = materialize_corpus(catalog=catalog, missions=DEMO_MISSIONS)
    owners_used = {item["owner"] for item in packed["opportunities"]}
    assert "Brand Safety Review" in owners_used
    assert "LATAM Creator Marketing" in owners_used
    assert "US Creator Marketing" in owners_used
    assert "Affiliate Partnerships" in owners_used
    assert owners_used <= set(OWNERS)
    spam = next(item for item in packed["opportunities"] if item["persona"] == "spam")
    assert spam["inbound_status"] == "held"
    assert spam["recommended_owner"] == "Brand Safety Review"
    assert spam["linked_mission_id"] is None


def test_high_potential_kol_is_mission_matched_not_auto_sent():
    catalog = _catalog()
    maya = next(item for item in load_inbound_messages() if item["sender_name"] == "Maya Outdoors")
    packed = materialize_opportunity(maya, catalog)
    opportunity = packed["opportunity"]
    assert opportunity["identity_status"] == "matched"
    assert opportunity["creator_id"] == "C004"
    assert opportunity["recommended_mission_id"] == "launch_x5_mx_001"
    assert opportunity["inbound_status"] == "mission_matched"
    assert opportunity["high_potential"] is True
    assert "does not confirm a rate" in opportunity["reply_draft"].lower() or "no confirma tarifa" in opportunity["reply_draft"].lower()
    assert packed["routing_decision"]["rule_version"] == ROUTING_RULE_VERSION
    assert opportunity["extractor_version"] == EXTRACTOR_VERSION
    assert opportunity["raw_content"] == maya["raw_content"]


def test_reply_drafts_do_not_commit_price():
    english = draft_reply(language="English", sender_name="Zoe", product="Insta360 X5", availability="2026-09")
    spanish = draft_reply(language="Spanish", sender_name="Lucía", product="Insta360 X5", availability="2026-09")
    german = draft_reply(language="German", sender_name="Sven", product="Insta360 X5", availability="2026-09")
    for text in (english, spanish, german):
        assert "4500" not in text
        assert "$" not in text
        assert "USD" not in text


def test_recommend_owner_rejects_unknown_roster_drift():
    identity = {"identity_status": "matched"}
    routed = recommend_owner({"persona": "kol", "market": "United States"}, identity)
    assert routed["owner"] == "US Creator Marketing"
