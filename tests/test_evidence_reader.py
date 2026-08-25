from __future__ import annotations

import json
from pathlib import Path

import pytest

from components import state
from infra import repository
from src import evidence_reader
from src.data_loader import load_creators, load_mission
from src.intensive_read import attach_evidence_reader, intensive_read_html, intensive_read_pack
from src.product_dna import load_product_dna
from src.scoring import rank_creators
from src.youtube_clips import load_youtube_intensive_clips

ROOT = Path(__file__).resolve().parents[1]
FAKE_MODEL = "fake-eval-model"


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def session(monkeypatch):
    fake = SessionState()
    monkeypatch.setattr(state.st, "session_state", fake)
    state.bootstrap_state()
    return fake


def _dna():
    return load_product_dna()


def _clip_with_body(creator_id: str | None = None) -> dict:
    clips = evidence_reader.eligible_clips(load_youtube_intensive_clips().get("clips") or [])
    assert clips
    if creator_id is None:
        return clips[0]
    match = [clip for clip in clips if clip["creator_id"] == creator_id]
    return match[0] if match else {}


def _grounded_pack(clip: dict, *, claim_id: str = "pov", supported: bool = True) -> dict:
    line = evidence_reader.caption_lines_of(clip)[0]
    return {
        "pack_id": evidence_reader.PACK_ID,
        "version": 1,
        "prompt_version": evidence_reader.PROMPT_VERSION,
        "extractor": evidence_reader.EXTRACTOR,
        "model": FAKE_MODEL,
        "caption_source": evidence_reader.CAPTION_SOURCE,
        "coverage": {"eligible_clips": 1, "attempted_clips": 1, "extracted": 1, "supported_claims": 1},
        "clips": [
            {
                "clip_id": clip["post_id"],
                "post_id": clip["post_id"],
                "creator_id": clip["creator_id"],
                "channel_id": clip.get("channel_id"),
                "video_id": clip.get("video_id"),
                "url": clip.get("url"),
                "caption_source": evidence_reader.CAPTION_SOURCE,
                "extractor": evidence_reader.EXTRACTOR,
                "model": FAKE_MODEL,
                "prompt_version": evidence_reader.PROMPT_VERSION,
                "claims": [
                    {
                        "claim_id": claim_id,
                        "supported": supported,
                        "confidence": 0.8,
                        "quote": line["text"],
                        "timestamp": line["t"],
                        "note": "Model cited this caption line.",
                    }
                ],
                "contradictions": [],
                "brand_safety_flags": [],
                "grounding": {"kept": 1},
                "status": evidence_reader.STATUS_EXTRACTED,
                "error": None,
            }
        ],
    }


# ── Grounding validator ──────────────────────────────────────────


def test_grounding_validator_drops_hallucinated_quote_from_the_model():
    clip = _clip_with_body()
    lines = evidence_reader.caption_lines_of(clip)
    real = lines[0]

    def hallucinating_call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "pov",
                        "supported": True,
                        "confidence": 0.95,
                        "quote": "The Insta360 X5 filmed all day in the rain and never stopped",
                        "timestamp": real["t"],
                        "note": "invented sentence that is in no caption line",
                    },
                    {
                        "claim_id": "360",
                        "supported": True,
                        "confidence": 0.7,
                        "quote": real["text"],
                        "timestamp": real["t"],
                        "note": "real verbatim caption line",
                    },
                ],
                "contradictions": [
                    {"quote": "this quote was never spoken", "timestamp": real["t"], "why": "invented"}
                ],
                "brand_safety_flags": [],
            }
        )

    result = evidence_reader.extract_clip(
        clip, _dna(), call=hallucinating_call, model=FAKE_MODEL, available=True
    )
    assert result["status"] == "extracted"
    assert [item["claim_id"] for item in result["claims"]] == ["360"]
    assert result["claims"][0]["quote"] == real["text"]
    assert result["claims"][0]["timestamp"] == real["t"]
    assert result["contradictions"] == []
    assert result["grounding"]["rejected_hallucinated_quotes"] == 2
    assert result["grounding"]["declared_unsupported"] == 0
    assert result["model"] == FAKE_MODEL
    assert result["prompt_version"] == evidence_reader.PROMPT_VERSION


def test_honest_unsupported_claim_is_not_counted_as_a_hallucination():
    clip = _clip_with_body()

    def honest_call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "pov",
                        "supported": False,
                        "confidence": 0.1,
                        "quote": "",
                        "timestamp": "",
                        "note": "the clip does not support this claim",
                    }
                ],
                "contradictions": [],
                "brand_safety_flags": [],
            }
        )

    result = evidence_reader.extract_clip(clip, _dna(), call=honest_call, model=FAKE_MODEL, available=True)
    assert result["status"] == "extracted"
    assert result["claims"] == []
    assert result["grounding"]["declared_unsupported"] == 1
    assert result["grounding"]["rejected_hallucinated_quotes"] == 0
    assert result["grounding"]["rejected_missing_quote"] == 0


def test_adjacent_caption_lines_are_kept_as_verbatim_transcript():
    clip = _clip_with_body()
    lines = evidence_reader.caption_lines_of(clip)
    assert len(lines) >= 2
    joined = f"{lines[0]['text']} {lines[1]['text']}"

    def call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "pov",
                        "supported": True,
                        "confidence": 0.8,
                        "quote": joined,
                        "timestamp": lines[0]["t"],
                        "note": "YouTube split this sentence across two chunks",
                    }
                ]
            }
        )

    result = evidence_reader.extract_clip(clip, _dna(), call=call, model=FAKE_MODEL, available=True)
    assert [item["claim_id"] for item in result["claims"]] == ["pov"]
    assert result["claims"][0]["quote"] == joined
    assert result["claims"][0]["timestamp"] == lines[0]["t"]
    assert result["grounding"]["joined_adjacent_lines"] == 1
    assert result["grounding"]["rejected_cross_line_quotes"] == 0
    assert result["grounding"]["rejected_hallucinated_quotes"] == 0


def test_three_line_stitches_are_still_rejected():
    clip = _clip_with_body()
    lines = evidence_reader.caption_lines_of(clip)
    if len(lines) < 3:
        pytest.skip("need a clip with at least three caption lines")
    stitched = f"{lines[0]['text']} {lines[1]['text']} {lines[2]['text']}"
    pair = f"{lines[0]['text']} {lines[1]['text']}"
    assert stitched != pair
    assert stitched not in pair

    def call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "pov",
                        "supported": True,
                        "confidence": 0.8,
                        "quote": stitched,
                        "timestamp": lines[0]["t"],
                        "note": "joined three caption chunks",
                    }
                ]
            }
        )

    result = evidence_reader.extract_clip(clip, _dna(), call=call, model=FAKE_MODEL, available=True)
    assert result["claims"] == []
    assert result["grounding"]["rejected_cross_line_quotes"] == 1
    assert result["grounding"]["joined_adjacent_lines"] == 0


def test_grounding_validator_drops_timestamps_and_claim_ids_not_in_the_input():
    clip = _clip_with_body()
    lines = evidence_reader.caption_lines_of(clip)
    real = lines[0]
    stamps = {item["t"] for item in lines}
    invented_stamp = "99:59"
    assert invented_stamp not in stamps

    def call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "pov",
                        "supported": True,
                        "confidence": 1.4,
                        "quote": real["text"],
                        "timestamp": invented_stamp,
                        "note": "timestamp is not in the supplied lines",
                    },
                    {
                        "claim_id": "battery_life_pro_max",
                        "supported": True,
                        "confidence": 0.5,
                        "quote": real["text"],
                        "timestamp": real["t"],
                        "note": "claim id is not in the Product DNA",
                    },
                ]
            }
        )

    result = evidence_reader.extract_clip(clip, _dna(), call=call, model=FAKE_MODEL, available=True)
    assert result["claims"] == []
    assert result["grounding"]["rejected_unknown_timestamps"] == 1
    assert result["grounding"]["rejected_unknown_claim_ids"] == 1


def test_confidence_is_clamped_and_quote_is_retimed_to_the_matching_line():
    clip = _clip_with_body()
    lines = evidence_reader.caption_lines_of(clip)
    first, second = lines[0], lines[1]
    assert first["text"] != second["text"]

    def call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "rugged",
                        "supported": True,
                        "confidence": 12,
                        "quote": second["text"],
                        "timestamp": first["t"],
                        "note": "cited the wrong line timestamp",
                    }
                ]
            }
        )

    result = evidence_reader.extract_clip(clip, _dna(), call=call, model=FAKE_MODEL, available=True)
    assert result["claims"][0]["confidence"] == 1.0
    assert result["claims"][0]["timestamp"] == second["t"]
    assert result["grounding"]["retimed_quotes"] == 1


def test_invalid_model_json_is_an_error_not_an_invented_claim():
    clip = _clip_with_body()
    result = evidence_reader.extract_clip(
        clip, _dna(), call=lambda system, user: "sure! here is my answer", model=FAKE_MODEL, available=True
    )
    assert result["status"] == "error"
    assert result["error"] == "invalid_json"
    assert result["claims"] == []


# ── No model ─────────────────────────────────────────────────────


def test_without_a_model_the_agent_returns_unavailable_no_model_and_never_keyword_matches():
    clip = _clip_with_body()

    def forbidden_call(system_prompt: str, user_prompt: str) -> str:  # pragma: no cover
        raise AssertionError("The agent must not call a model when none is configured")

    result = evidence_reader.extract_clip(clip, _dna(), call=forbidden_call, available=False)
    assert result["status"] == "unavailable_no_model"
    assert result["claims"] == []
    assert result["contradictions"] == []
    assert result["brand_safety_flags"] == []
    assert result["model"] == ""

    pack = evidence_reader.extract_pack([clip], _dna(), call=forbidden_call, available=False)
    assert pack["coverage"]["unavailable_no_model"] == 1
    assert pack["coverage"]["supported_claims"] == 0
    assert pack["model"] == ""
    assert evidence_reader.grounded_claims_for_creator(clip["creator_id"], pack) == []


def test_agent_refuses_labeled_demo_captions():
    labeled = {
        "post_id": "POST-C004-01",
        "creator_id": "C004",
        "caption_source": "labeled_demo",
        "caption_body_status": "not_downloaded",
        "caption_lines": [],
        "timestamps": [{"t": "00:04", "claim_id": "pov", "caption": "labeled demo caption"}],
    }
    assert evidence_reader.caption_lines_of(labeled) == []
    assert evidence_reader.eligible_clips([labeled]) == []
    with pytest.raises(ValueError, match="downloaded_public_timedtext"):
        evidence_reader.extract_clip(labeled, _dna(), call=lambda s, u: "{}", available=True)


# ── Cache ────────────────────────────────────────────────────────


def test_cache_round_trip_and_missing_file_is_an_honest_empty_pack(tmp_path):
    clip = _clip_with_body()
    line = evidence_reader.caption_lines_of(clip)[0]

    def call(system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "all_day",
                        "supported": True,
                        "confidence": 0.6,
                        "quote": line["text"],
                        "timestamp": line["t"],
                        "note": "grounded",
                    }
                ]
            }
        )

    pack = evidence_reader.extract_pack([clip], _dna(), call=call, model=FAKE_MODEL, available=True)
    target = tmp_path / "evidence_extractions.json"
    evidence_reader.save_pack(pack, target)
    loaded = evidence_reader.load_pack(target)

    assert loaded["pack_id"] == evidence_reader.PACK_ID
    assert loaded["prompt_version"] == evidence_reader.PROMPT_VERSION
    assert loaded["available"] is True
    assert loaded["clips"][0]["claims"] == pack["clips"][0]["claims"]
    rows = evidence_reader.supported_claim_rows(loaded)
    assert len(rows) == 1
    assert rows[0]["source_label"].startswith("youtube_public_timedtext + evidence_reader(")
    assert evidence_reader.load_pack(tmp_path / "missing.json")["clips"] == []
    assert evidence_reader.load_pack(tmp_path / "missing.json")["available"] is False

    blob = json.loads(target.read_text(encoding="utf-8"))
    assert "api_key" not in json.dumps(blob).lower()
    assert "sk-" not in json.dumps(blob)
    with pytest.raises(ValueError):
        evidence_reader.save_pack({**pack, "api_key": "nope"}, tmp_path / "rejected.json")


def test_cached_pack_rejects_unavailable_rows_that_carry_claims(tmp_path):
    clip = _clip_with_body()
    line = evidence_reader.caption_lines_of(clip)[0]
    tampered = {
        "pack_id": evidence_reader.PACK_ID,
        "version": 1,
        "prompt_version": evidence_reader.PROMPT_VERSION,
        "extractor": evidence_reader.EXTRACTOR,
        "caption_source": evidence_reader.CAPTION_SOURCE,
        "model": "",
        "clips": [
            {
                "post_id": clip["post_id"],
                "creator_id": clip["creator_id"],
                "status": evidence_reader.STATUS_NO_MODEL,
                "claims": [
                    {"claim_id": "pov", "supported": True, "quote": line["text"], "timestamp": line["t"]}
                ],
            }
        ],
    }
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="unavailable_no_model"):
        evidence_reader.load_pack(path)


def test_committed_cache_covers_the_public_caption_bodies_and_stays_grounded():
    clips = load_youtube_intensive_clips().get("clips") or []
    eligible = evidence_reader.eligible_clips(clips)
    pack = evidence_reader.load_pack()
    lines_by_post = {clip["post_id"]: evidence_reader.caption_lines_of(clip) for clip in eligible}

    assert pack["coverage"]["eligible_clips"] == len(eligible)
    assert pack["coverage"]["attempted_clips"] == len(pack["clips"])
    assert set(row["post_id"] for row in pack["clips"]) <= set(lines_by_post)
    for row in pack["clips"]:
        lines = lines_by_post[row["post_id"]]
        texts = {item["text"] for item in lines}
        stamps = {item["t"] for item in lines}
        assert row["caption_source"] == evidence_reader.CAPTION_SOURCE
        assert row["prompt_version"] == evidence_reader.PROMPT_VERSION
        for claim in row["claims"]:
            assert claim["timestamp"] in stamps
            texts_list = [item["text"] for item in lines]
            in_one = any(claim["quote"] in text for text in texts_list)
            in_adjacent = any(
                claim["quote"] in f"{left} {right}"
                for left, right in zip(texts_list, texts_list[1:])
            )
            assert in_one or in_adjacent
    blob = json.dumps(pack).lower()
    for token in ("api_key", "authorization", "bearer ", "sk-"):
        assert token not in blob


# ── Ranking is untouched ─────────────────────────────────────────


def test_extractions_never_change_ranking_ids_or_model_version():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    baseline = rank_creators(catalog, mission)
    baseline_ids = [str(item) for item in baseline["creator_id"].tolist()]

    clip = _clip_with_body()
    pack = _grounded_pack(clip)
    after = rank_creators(catalog, mission)
    assert [str(item) for item in after["creator_id"].tolist()] == baseline_ids
    assert (after["ranking_model_version"] == "rule_mix_tfidf_v1").all()

    read_pack = intensive_read_pack(
        baseline,
        n=20,
        evidence_by_post_id=evidence_reader.extractions_by_post_id(pack),
    )
    assert [row["creator_id"] for row in read_pack] == baseline_ids[:20]
    assert "total_score" not in json.dumps(pack)


def test_intensive_read_board_shows_the_grounded_quote_timestamp_and_source_label():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(catalog, mission)
    creator_id = next(
        str(item)
        for item in ranked["creator_id"].tolist()
        if _clip_with_body(str(item))
    )
    clip = _clip_with_body(creator_id)
    pack = _grounded_pack(clip)
    line = evidence_reader.caption_lines_of(clip)[0]

    read_pack = intensive_read_pack(
        ranked,
        n=20,
        evidence_by_post_id=evidence_reader.extractions_by_post_id(pack),
    )
    html = intensive_read_html(read_pack)
    assert "Evidence Reader" in html
    assert f"evidence_reader({FAKE_MODEL})" in html
    assert "youtube_public_timedtext + evidence_reader" in html
    assert line["t"] in html
    assert "labeled_demo" in html
    assert "asr_collected" not in html.lower()

    row = next(item for item in read_pack if item["creator_id"] == creator_id)
    target = next(item for item in row["clips"] if item["post_id"] == clip["post_id"])
    assert target["evidence_reader"]["claims"][0]["quote"] == line["text"]
    assert target["evidence_reader"]["status"] == "extracted"
    other = next(
        (item for item in row["clips"] if item["post_id"] != clip["post_id"] and item.get("evidence_reader")),
        None,
    )
    if other is not None:
        assert other["evidence_reader"]["status"] in {"not_run", "unavailable_no_model"}


def test_stale_cached_quotes_are_dropped_before_display():
    clip = _clip_with_body()
    stale = _grounded_pack(clip)
    stale["clips"][0]["claims"][0]["quote"] = "a quote this clip never contained"
    block = evidence_reader.extractions_by_post_id(stale)[clip["post_id"]]
    attached = attach_evidence_reader(clip, block)
    assert attached["claims"] == []
    assert attached["dropped_stale_claims"] == 1


# ── Approval gate ────────────────────────────────────────────────


def test_approval_gate_blocks_without_grounded_evidence_and_records_an_audited_override(session):
    ranked = state.ranking()
    creator_id = next(
        str(row["creator_id"])
        for _, row in ranked.iterrows()
        if state.evidence_gate_state(str(row["creator_id"]))["blocked"]
    )
    gate = state.evidence_gate_state(creator_id)
    assert gate["blocked"] is True
    assert gate["grounded"] is False
    assert gate["status"] in {"blocked_no_model", "blocked_no_grounded_evidence"}

    with pytest.raises(state.EvidenceGateBlocked, match="Claim-grounded|Evidence Reader"):
        state.save_decision(creator_id, "Approved", "Approve without claim-grounded evidence")
    assert state.creator_state(creator_id) != "approved"
    assert session.decision_log == []

    with pytest.raises(ValueError, match="operator reason"):
        state.record_evidence_gate_override(creator_id, reason="")

    override = state.record_evidence_gate_override(
        creator_id,
        reason="Operator accepts the risk: no public caption body for this creator.",
        actor="Olivia Chen",
    )
    assert override["gate_status"] in {"blocked_no_model", "blocked_no_grounded_evidence"}
    audit = repository.load_approval_audit()
    assert any(
        row["action"] == "evidence_gate_override"
        and creator_id in row["approval_id"]
        and row["actor"] == "Olivia Chen"
        and row["reason"].startswith("Operator accepts the risk")
        for row in audit
    )
    assert any(
        row["type"] == "Evidence gate" and row["creator_id"] == creator_id
        for row in repository.load_creator_events()
    )

    after = state.evidence_gate_state(creator_id)
    assert after["blocked"] is False
    assert after["status"] == "overridden"

    decision = state.save_decision(creator_id, "Approved", "Approve on an audited override")
    assert decision["evidence_gate"]["status"] == "overridden"
    assert decision["evidence_gate"]["grounded"] is False
    assert decision["evidence_gate"]["override"]["reason"].startswith("Operator accepts the risk")
    assert state.creator_state(creator_id) == "approved"
    assert any(str(item).startswith("evidence_gate_override://") for item in decision["evidence"])


def test_grounded_extraction_satisfies_the_gate_and_lands_on_the_decision(session, monkeypatch):
    ranked = state.ranking()
    creator_id = next(
        str(item) for item in ranked["creator_id"].tolist() if _clip_with_body(str(item))
    )
    clip = _clip_with_body(creator_id)
    pack = _grounded_pack(clip)
    monkeypatch.setattr(state, "evidence_extraction_pack", lambda: pack)

    gate = state.evidence_gate_state(creator_id)
    assert gate["blocked"] is False
    assert gate["grounded"] is True
    assert gate["status"] == "grounded"
    assert gate["claims"][0]["timestamp"]
    assert gate["claims"][0]["model"] == FAKE_MODEL

    if state.creator_state(creator_id) == "qualified":
        state.transition_creator_state(
            creator_id,
            "shortlisted",
            actor="Olivia Chen",
            reason="Shortlisted before approval",
            evidence=["catalog://evidence"],
        )

    decision = state.save_decision(creator_id, "Approved", "Approve on model-grounded claim evidence")
    assert decision["evidence_gate"]["status"] == "grounded"
    assert decision["evidence_gate"]["claims"][0]["claim_id"] == "pov"
    assert decision["evidence_gate"]["model"] == FAKE_MODEL
    assert decision["evidence_gate"]["override"] is None
    assert any(str(item).startswith("evidence_reader://") for item in decision["evidence"])
    assert state.creator_state(creator_id) == "approved"
    assert state.evidence_gate_overrides() == []
    trace = state.latest_ceg_run(creator_id)
    assert trace is not None
    assert [step["role"] for step in trace["steps"]] == [
        "Scout",
        "EvidenceReader",
        "MatchArbiter",
        "BriefWriter",
        "ComplianceGuard",
    ]
    assert "pov" in trace["claim_ids"]


def test_override_is_refused_when_grounded_evidence_already_exists(session, monkeypatch):
    ranked = state.ranking()
    creator_id = next(
        str(item) for item in ranked["creator_id"].tolist() if _clip_with_body(str(item))
    )
    monkeypatch.setattr(state, "evidence_extraction_pack", lambda: _grounded_pack(_clip_with_body(creator_id)))
    with pytest.raises(ValueError, match="already satisfies"):
        state.record_evidence_gate_override(creator_id, reason="Not needed, evidence already grounded")


def test_viewer_cannot_override_the_gate_or_approve(session):
    session.auth_user = {"username": "demo", "role": "viewer", "display_name": "Demo Viewer"}
    creator_id = str(state.ranking().iloc[0]["creator_id"])
    with pytest.raises(PermissionError, match="read-only"):
        state.record_evidence_gate_override(creator_id, reason="Viewer should never override the gate")
    with pytest.raises(PermissionError, match="read-only"):
        state.save_decision(creator_id, "Approved", "Viewer should never approve")
    assert session.get("evidence_gate_overrides") == []
    assert repository.load_approval_audit() == []


def test_override_is_scoped_to_the_active_root_entry(session):
    creator_id = str(state.ranking().iloc[0]["creator_id"])
    state.record_evidence_gate_override(creator_id, reason="Mission-scoped audited override")
    assert state.evidence_gate_state(creator_id)["blocked"] is False

    state.set_active_context("opportunity", "OPP-001")
    assert state.evidence_gate_overrides() == []
    assert state.evidence_gate_state(creator_id)["blocked"] is True
