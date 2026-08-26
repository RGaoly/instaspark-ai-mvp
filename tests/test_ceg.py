from __future__ import annotations

from src.ceg import (
    CONTRACT,
    ENGINE_HUMAN,
    ENGINE_MODEL,
    ENGINE_RULE,
    RANKING_MODEL_VERSION,
    REASON_GATE_BLOCKED,
    REASON_HUMAN_OVERRIDE,
    REASON_NO_MODEL,
    ROLE_BRIEF_WRITER,
    ROLE_CALIBRATOR,
    ROLE_COMPLIANCE_GUARD,
    ROLE_EVIDENCE_READER,
    ROLE_MATCH_ARBITER,
    ROLE_SCOUT,
    ROLES,
    STATUS_BLOCKED,
    STATUS_DEGRADED,
    STATUS_OK,
    WORKFLOW_ID,
    brief_writer_step,
    compliance_guard_step,
    degraded_matrix,
    evidence_reader_step,
    match_arbiter_step,
    run,
    scout_step,
)
from src.product_dna import load_product_dna
from views.creator_compare import ceg_trace_panel_html


def _gate(*, grounded: bool = False, model: bool = True, override: dict | None = None) -> dict:
    claims = (
        [
            {
                "claim_id": "pov",
                "quote": "using POV with the mouth mount for this",
                "timestamp": "00:33",
                "post_id": "POST-C012-01",
                "source_label": "evidence_reader",
            }
        ]
        if grounded
        else []
    )
    if grounded:
        status = "grounded"
    elif override:
        status = "overridden"
    elif not model:
        status = "blocked_no_model"
    else:
        status = "blocked_no_grounded_evidence"
    return {
        "blocked": not grounded and not override,
        "grounded": grounded,
        "status": status,
        "claims": claims,
        "model_available": model,
        "override": override,
        "prompt_version": "evidence_reader_v1",
        "model": "deepseek-chat" if model else "",
        "pack_id": "evidence_reader_x5_v1",
    }


def test_contract_names_six_roles_and_only_the_reader_mints_claims():
    assert WORKFLOW_ID == "ceg"
    assert ROLES == (
        ROLE_SCOUT,
        ROLE_EVIDENCE_READER,
        ROLE_MATCH_ARBITER,
        ROLE_BRIEF_WRITER,
        ROLE_COMPLIANCE_GUARD,
        ROLE_CALIBRATOR,
    )
    advancing = [item.role for item in CONTRACT if item.advances_claims]
    assert advancing[0] == ROLE_EVIDENCE_READER
    scout = next(item for item in CONTRACT if item.role == ROLE_SCOUT)
    assert scout.engine == ENGINE_RULE
    assert scout.advances_claims is False
    reader = next(item for item in CONTRACT if item.role == ROLE_EVIDENCE_READER)
    assert reader.engine == ENGINE_MODEL
    assert reader.degraded_engine is None


def test_scout_never_advances_a_claim():
    step = scout_step(
        "ceg_test",
        creator_id="C012",
        scout={"source": "catalog_momentum", "score": 71},
        target_claim_ids=["all_day", "pov", "rugged", "360"],
    )
    assert step.role == ROLE_SCOUT
    assert step.engine == ENGINE_RULE
    assert step.status == STATUS_OK
    assert step.claim_ids == ()
    assert step.degraded_reason is None


def test_evidence_reader_blocks_with_zero_claims_when_no_model():
    step = evidence_reader_step(
        "ceg_test",
        creator_id="C001",
        gate=_gate(grounded=False, model=False),
        model_available=False,
    )
    assert step.engine == ENGINE_MODEL
    assert step.status == STATUS_BLOCKED
    assert step.claim_ids == ()
    assert step.degraded_reason == REASON_NO_MODEL


def test_evidence_reader_is_the_only_step_that_puts_claim_ids_on_a_fresh_run():
    step = evidence_reader_step(
        "ceg_test",
        creator_id="C012",
        gate=_gate(grounded=True),
        model_available=True,
    )
    assert step.status == STATUS_OK
    assert step.claim_ids == ("pov",)
    assert step.outputs["quotes"][0]["timestamp"] == "00:33"


def test_match_arbiter_blocks_when_no_claim_is_grounded():
    step = match_arbiter_step(
        "ceg_test",
        creator_id="C001",
        match={"score": 80, "model_version": RANKING_MODEL_VERSION, "match_id": "m1"},
        gate=_gate(grounded=False),
        grounded_claim_ids=(),
        target_claim_ids=["pov"],
    )
    assert step.engine == ENGINE_RULE
    assert step.status == STATUS_BLOCKED
    assert step.claim_ids == ()
    assert step.degraded_reason == REASON_GATE_BLOCKED
    assert step.outputs["ranking_model_version"] == RANKING_MODEL_VERSION


def test_match_arbiter_human_override_advances_zero_claims():
    step = match_arbiter_step(
        "ceg_test",
        creator_id="C001",
        match={"score": 80, "model_version": RANKING_MODEL_VERSION},
        gate=_gate(grounded=False, override={"override_id": "gate_override_0001", "actor": "Olivia"}),
        grounded_claim_ids=(),
        target_claim_ids=["pov"],
    )
    assert step.engine == ENGINE_HUMAN
    assert step.status == STATUS_DEGRADED
    assert step.claim_ids == ()
    assert step.degraded_reason == REASON_HUMAN_OVERRIDE


def test_brief_writer_records_template_fallback_when_no_model():
    step = brief_writer_step(
        "ceg_test",
        creator_id="C012",
        artifact={"kind": "brief", "text": "Shoot POV on the handlebar.", "artifact_id": "CA-1", "source_label": "template"},
        grounded_claim_ids=("pov",),
        gate_open=True,
        model_available=False,
    )
    assert step.engine == ENGINE_RULE
    assert step.status == STATUS_DEGRADED
    assert step.degraded_reason == REASON_NO_MODEL
    assert step.claim_ids == ("pov",)


def test_compliance_guard_flags_an_invented_ip_rating():
    step = compliance_guard_step(
        "ceg_test",
        creator_id="C012",
        artifact={"kind": "brief", "text": "The X5 is IP68 and waterproof to 10 meters."},
        dna=load_product_dna(),
        signed_off_by=None,
    )
    codes = {item["rule"] for item in step.outputs["findings"]}
    assert "invented_ip_rating" in codes or "invented_depth_rating" in codes
    assert step.role == ROLE_COMPLIANCE_GUARD
    assert step.engine == ENGINE_RULE


def test_run_returns_six_typed_steps_and_blocks_without_evidence():
    trace = run(
        creator_id="C001",
        entry_type="mission",
        entry_id="launch_x5_us_001",
        dna=load_product_dna(),
        gate=_gate(grounded=False, model=False),
        match={"score": 70, "model_version": RANKING_MODEL_VERSION},
        model_available=False,
    )
    assert [step.role for step in trace.steps] == list(ROLES)
    assert trace.status == STATUS_BLOCKED
    assert trace.claim_ids == ()
    reader = trace.step(ROLE_EVIDENCE_READER)
    assert reader is not None
    assert reader.degraded_reason == REASON_NO_MODEL


def test_run_advances_grounded_claims_when_the_reader_succeeds():
    trace = run(
        creator_id="C012",
        entry_type="mission",
        entry_id="launch_x5_us_001",
        dna=load_product_dna(),
        gate=_gate(grounded=True),
        match={"score": 82, "model_version": RANKING_MODEL_VERSION, "match_id": "m12"},
        artifact={"kind": "brief", "text": "Use the mouth mount for POV.", "artifact_id": "CA-12"},
        model_available=True,
    )
    assert "pov" in trace.claim_ids
    assert trace.step(ROLE_EVIDENCE_READER).status == STATUS_OK
    assert trace.step(ROLE_MATCH_ARBITER).outputs["ranking_model_version"] == RANKING_MODEL_VERSION
    payload = trace.to_dict()
    assert payload["status"] == trace.status
    assert payload["claim_ids"] == list(trace.claim_ids)


def test_calibrator_never_advances_a_claim():
    from src.ceg import calibrator_step

    skipped = calibrator_step("ceg_test", decisions=[], current_weights=None)
    assert skipped.role == ROLE_CALIBRATOR
    assert skipped.claim_ids == ()
    assert skipped.engine == ENGINE_RULE
    moved = calibrator_step(
        "ceg_test",
        decisions=[{"reason_code": "risk_or_cost"}],
        current_weights=None,
    )
    assert moved.claim_ids == ()
    assert moved.outputs["auto_applied"] is False
    matrix = degraded_matrix()
    assert [row["role"] for row in matrix] == list(ROLES)
    reader = next(row for row in matrix if row["role"] == ROLE_EVIDENCE_READER)
    assert "no keyword fallback" in reader["degraded_behaviour"].lower() or "cannot mint" in reader["degraded_behaviour"].lower()
    assert reader["degraded_engine"] == "none"


def test_compare_panel_renders_the_trace_and_the_empty_state():
    empty = ceg_trace_panel_html(None)
    assert 'id="ceg-run-trace"' in empty
    assert "No run recorded yet" in empty
    filled = ceg_trace_panel_html(
        {
            "run_id": "ceg_demo_001",
            "status": "ok",
            "steps": [
                {
                    "role": ROLE_EVIDENCE_READER,
                    "engine": ENGINE_MODEL,
                    "status": STATUS_OK,
                    "claim_ids": ["pov"],
                    "degraded_reason": None,
                }
            ],
        }
    )
    assert "ceg_demo_001" in filled
    assert ROLE_EVIDENCE_READER in filled
    assert "pov" in filled
