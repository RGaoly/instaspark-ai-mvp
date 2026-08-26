"""Claim-Evidence-Guardrail (CEG): the named agent workflow behind a launch decision.

The original idea in this product is not "an LLM writes a brief". It is that the
**atomic unit of work is a single Product DNA claim**. A creator is not approved
because a score is high; a creator is approved because named roles advanced
specific ``claim_id`` values, on a named engine, with a recorded degraded reason
whenever the model was absent. A launch decision is therefore traceable
claim-by-claim.

Six named roles, in order, each with a typed step contract:

1. ``Scout``           - rule  - proposes the candidate from catalog momentum / inbound routing.
2. ``EvidenceReader``  - model - reads real public caption lines into grounded claim evidence.
3. ``MatchArbiter``    - rule  - claim-underwrite score plus the claim-evidence approval gate.
4. ``BriefWriter``     - model - writes the operator artifact, degrading to the rule template.
5. ``ComplianceGuard`` - rule  - checks the artifact against per-claim DNA guardrails.
6. ``Calibrator``      - rule  - reason codes become a weight proposal; never auto-applies.

Two invariants hold everywhere in this module:

* **No claim without evidence.** Only ``EvidenceReader`` can put a ``claim_id``
  into a step's ``claim_ids``. Rules never mint claim evidence, so a rule-only
  run advances zero claims and the ``MatchArbiter`` blocks.
* **Degradation is recorded, never hidden.** When a step cannot run on its
  primary engine it keeps its ``role``, switches ``engine``, and states
  ``degraded_reason``. It never silently substitutes a weaker method.

This module is pure: it takes already-loaded inputs and returns a ``CegRun``.
``components/state.py`` supplies the session/SQLite wiring and persists the trace.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

WORKFLOW_ID = "ceg"
WORKFLOW_NAME = "Claim-Evidence-Guardrail"
WORKFLOW_VERSION = "ceg_v2"

ROLE_SCOUT = "Scout"
ROLE_EVIDENCE_READER = "EvidenceReader"
ROLE_MATCH_ARBITER = "MatchArbiter"
ROLE_BRIEF_WRITER = "BriefWriter"
ROLE_COMPLIANCE_GUARD = "ComplianceGuard"
ROLE_CALIBRATOR = "Calibrator"

ENGINE_MODEL = "model"
ENGINE_RULE = "rule"
ENGINE_HUMAN = "human"
ENGINES = (ENGINE_MODEL, ENGINE_RULE, ENGINE_HUMAN)

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_BLOCKED = "blocked"
STATUS_SKIPPED = "skipped"
STATUSES = (STATUS_OK, STATUS_DEGRADED, STATUS_BLOCKED, STATUS_SKIPPED)

ARTIFACT_BRIEF = "brief"
ARTIFACT_OUTREACH_MESSAGE = "outreach_message"

RANKING_MODEL_VERSION = "claim_underwrite_v1"
RULE_MIX_VERSION = "rule_mix_tfidf_v1"

# Degraded reasons. Stable strings so docs, UI and tests agree.
REASON_NO_MODEL = "no_model_configured"
REASON_NO_EXTRACTION = "no_grounded_extraction_for_creator"
REASON_HUMAN_OVERRIDE = "human_override_without_grounded_claim"
REASON_GATE_BLOCKED = "evidence_gate_blocked"
REASON_NO_ARTIFACT = "artifact_not_produced_in_this_run"
REASON_UNGROUNDED_ARTIFACT = "artifact_written_before_a_claim_was_grounded"
REASON_GUARDRAIL_FINDINGS = "guardrail_findings_require_human_fix"
REASON_NO_MATCH = "no_match_record_in_active_root"
REASON_NO_DECISIONS = "no_reason_codes_to_calibrate"


# ── Step contracts ───────────────────────────────────────────────


@dataclass(frozen=True)
class StepContract:
    """The declared contract of one CEG role. Code, docs and tests read this."""

    role: str
    engine: str
    degraded_engine: str | None
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    advances_claims: bool
    purpose: str
    degraded_behaviour: str


CONTRACT: tuple[StepContract, ...] = (
    StepContract(
        role=ROLE_SCOUT,
        engine=ENGINE_RULE,
        degraded_engine=None,
        inputs=("creator_id", "scout_source", "scout_score", "target_claim_ids"),
        outputs=("source", "score", "windows", "target_claim_ids"),
        advances_claims=False,
        purpose="Propose the candidate from catalog momentum proxies or inbound routing.",
        degraded_behaviour="Never degrades: it is a rule step and needs no model.",
    ),
    StepContract(
        role=ROLE_EVIDENCE_READER,
        engine=ENGINE_MODEL,
        degraded_engine=None,
        inputs=("creator_id", "caption_lines", "product_dna_claims"),
        outputs=("claims", "quotes", "timestamps", "prompt_version", "model"),
        advances_claims=True,
        purpose="Read real public caption lines and ground DNA claims in verbatim quotes.",
        degraded_behaviour=(
            "Blocks with no_model_configured. There is no keyword fallback: a rule "
            "cannot mint claim evidence, so zero claims are advanced."
        ),
    ),
    StepContract(
        role=ROLE_MATCH_ARBITER,
        engine=ENGINE_RULE,
        degraded_engine=ENGINE_HUMAN,
        inputs=("match_score", "hard_gates", "evidence_gate", "grounded_claim_ids"),
        outputs=("score", "ranking_model_version", "gate_status", "unevidenced_claim_ids"),
        advances_claims=True,
        purpose="Combine claim-underwrite coverage with the claim-evidence approval gate. Rule mix is the Scout constraint, not the product.",
        degraded_behaviour=(
            "Blocks when no claim is grounded. An audited human override switches the "
            "engine to human and advances zero claims."
        ),
    ),
    StepContract(
        role=ROLE_BRIEF_WRITER,
        engine=ENGINE_MODEL,
        degraded_engine=ENGINE_RULE,
        inputs=("mission", "creator", "grounded_claim_ids", "artifact_kind"),
        outputs=("artifact_kind", "artifact_id", "chars", "source_label"),
        advances_claims=True,
        purpose="Write the operator artifact grounded in the claims the reader advanced.",
        degraded_behaviour=(
            "Falls back to the deterministic template in services/llm_service.py and "
            "records no_model_configured. Writing before the gate opens is marked degraded."
        ),
    ),
    StepContract(
        role=ROLE_COMPLIANCE_GUARD,
        engine=ENGINE_RULE,
        degraded_engine=ENGINE_HUMAN,
        inputs=("artifact_text", "product_dna_guardrails"),
        outputs=("findings", "checked_claim_ids", "severity"),
        advances_claims=False,
        purpose="Check the artifact against the per-claim DNA guardrails before a human sends it.",
        degraded_behaviour="Never degrades. A hard finding blocks; a soft finding needs a human fix.",
    ),
    StepContract(
        role=ROLE_CALIBRATOR,
        engine=ENGINE_RULE,
        degraded_engine=None,
        inputs=("decision_reason_codes", "current_weights"),
        outputs=("proposed_weights", "deltas", "reason_counts"),
        advances_claims=False,
        purpose="Turn recorded reason codes into a mix-weight proposal for the next book. Never auto-applies.",
        degraded_behaviour="Skips with no_reason_codes_to_calibrate when the decision log is empty. Never invents a proposal.",
    ),
)

CONTRACT_BY_ROLE: dict[str, StepContract] = {item.role: item for item in CONTRACT}
ROLES: tuple[str, ...] = tuple(item.role for item in CONTRACT)


# ── Guardrail checks, keyed by the DNA claim they protect ─────────

SEVERITY_HARD = "hard"
SEVERITY_SOFT = "soft"

CLAIM_GUARDRAIL_PATTERNS: dict[str, tuple[tuple[str, str], ...]] = {
    "all_day": (
        (r"\b\d+(?:\.\d+)?\s*(?:mah|amp[-\s]?hours?)\b", "invented_battery_capacity"),
        (r"\bbatter(?:y|ies)\s+(?:life\s+)?(?:of\s+|up\s+to\s+)?\d+", "invented_battery_runtime"),
        (
            r"\b\d+(?:\.\d+)?\s*(?:minutes?|mins?|hours?|hrs?)\s+of\s+(?:battery|runtime|recording|shooting)\b",
            "invented_battery_runtime",
        ),
    ),
    "pov": (
        (r"\b(?:only|exclusive|exclusively)\s+on\s+(?:tiktok|instagram|reels|shorts)\b", "platform_exclusive_format"),
        (r"\bplatform[-\s]exclusive\b", "platform_exclusive_format"),
    ),
    "rugged": (
        (r"\bip\s?[5-6]\d\b", "invented_ip_rating"),
        (r"\bwaterproof\s+(?:to|up\s+to)\s+\d+", "invented_depth_rating"),
    ),
    "360": (
        (r"\b\d+(?:\.\d+)?\s?k\b(?!\w)", "invented_resolution"),
        (r"\b\d{2,4}\s?fps\b", "invented_frame_rate"),
    ),
}

# Workflow-level guardrails that are not owned by a single claim.
GLOBAL_GUARDRAIL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:tiktok\s+shop|instagram\s+shop|tiktok\s+inventory)\b", "invented_platform_inventory"),
    (r"\b(?:guaranteed|guarantee)\s+(?:\d|views|sales|roi)", "guaranteed_outcome"),
)

PRICE_COMMITMENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\$\s?\d", "price_commitment"),
    (r"\b\d[\d,\.]*\s?(?:usd|eur|mxn)\b", "price_commitment"),
    (r"\bwe (?:will|can) pay\b", "price_commitment"),
)

DISCLOSURE_TOKENS: tuple[str, ...] = (
    "paid partnership",
    "paid-usage",
    "paid usage",
    "#ad",
    "disclosure",
    "disclose",
    "colaboracion pagada",
)


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _claim_guardrail_text(dna: Mapping[str, Any] | None, claim_id: str) -> str:
    for claim in (dna or {}).get("claims") or []:
        if _as_text(claim.get("claim_id")) == claim_id:
            return _as_text(claim.get("guardrail"))
    return ""


def guardrail_findings(
    text: Any,
    dna: Mapping[str, Any] | None,
    *,
    kind: str = ARTIFACT_BRIEF,
) -> list[dict[str, Any]]:
    """Real pattern findings on the artifact text, each tagged with the claim it protects.

    An empty list is an honest pass, not a guarantee of compliance: the checks are
    the DNA guardrails written down as patterns, not a legal review.
    """

    body = str(text or "")
    lowered = body.lower()
    findings: list[dict[str, Any]] = []
    for claim_id, patterns in CLAIM_GUARDRAIL_PATTERNS.items():
        if claim_id not in {_as_text(claim.get("claim_id")) for claim in (dna or {}).get("claims") or []}:
            continue
        for pattern, rule in patterns:
            match = re.search(pattern, lowered, re.I)
            if match is None:
                continue
            findings.append(
                {
                    "claim_id": claim_id,
                    "rule": rule,
                    "severity": SEVERITY_HARD,
                    "match": match.group(0).strip()[:80],
                    "guardrail": _claim_guardrail_text(dna, claim_id),
                }
            )
    for pattern, rule in GLOBAL_GUARDRAIL_PATTERNS:
        match = re.search(pattern, lowered, re.I)
        if match is not None:
            findings.append(
                {
                    "claim_id": None,
                    "rule": rule,
                    "severity": SEVERITY_HARD,
                    "match": match.group(0).strip()[:80],
                    "guardrail": "Do not invent inventory or guarantee an outcome.",
                }
            )
    if kind == ARTIFACT_OUTREACH_MESSAGE:
        for pattern, rule in PRICE_COMMITMENT_PATTERNS:
            match = re.search(pattern, lowered, re.I)
            if match is not None:
                findings.append(
                    {
                        "claim_id": None,
                        "rule": rule,
                        "severity": SEVERITY_HARD,
                        "match": match.group(0).strip()[:80],
                        "guardrail": "An outreach note must not commit a price.",
                    }
                )
    if kind == ARTIFACT_BRIEF and body and not any(token in lowered for token in DISCLOSURE_TOKENS):
        findings.append(
            {
                "claim_id": None,
                "rule": "missing_paid_partnership_disclosure",
                "severity": SEVERITY_SOFT,
                "match": "",
                "guardrail": "Paid partnership disclosure is required on generated briefs.",
            }
        )
    return findings


def has_hard_finding(findings: Iterable[Mapping[str, Any]]) -> bool:
    return any(_as_text(item.get("severity")) == SEVERITY_HARD for item in findings or [])


# ── Step / run records ───────────────────────────────────────────


def digest(payload: Any) -> str:
    """Stable 12-hex digest of a step's inputs. Never carries a secret value."""

    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


@dataclass
class CegStep:
    """One executed role. ``claim_ids`` is which DNA claims this step advanced."""

    step_id: str
    role: str
    engine: str
    inputs_digest: str
    outputs: dict[str, Any]
    status: str
    claim_ids: tuple[str, ...] = ()
    degraded_reason: str | None = None
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if self.role not in CONTRACT_BY_ROLE:
            raise ValueError(f"Unknown CEG role: {self.role}")
        if self.engine not in ENGINES:
            raise ValueError(f"Unknown CEG engine: {self.engine}")
        if self.status not in STATUSES:
            raise ValueError(f"Unknown CEG status: {self.status}")
        contract = CONTRACT_BY_ROLE[self.role]
        if self.claim_ids and not contract.advances_claims:
            raise ValueError(f"{self.role} must not advance DNA claims")
        self.claim_ids = tuple(_as_text(item) for item in self.claim_ids if _as_text(item))
        self.recorded_at = self.recorded_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "role": self.role,
            "engine": self.engine,
            "inputs_digest": self.inputs_digest,
            "outputs": dict(self.outputs),
            "status": self.status,
            "claim_ids": list(self.claim_ids),
            "degraded_reason": self.degraded_reason,
            "recorded_at": self.recorded_at,
        }


@dataclass
class CegRun:
    """One traced pass of the workflow for one creator in one root context."""

    run_id: str
    creator_id: str
    entry_type: str
    entry_id: str
    dna_id: str
    dna_version: Any
    steps: list[CegStep] = field(default_factory=list)
    started_at: str = ""

    def __post_init__(self) -> None:
        self.started_at = self.started_at or datetime.now(timezone.utc).isoformat()

    def step(self, role: str) -> CegStep | None:
        return next((item for item in self.steps if item.role == role), None)

    @property
    def status(self) -> str:
        statuses = {item.status for item in self.steps}
        if STATUS_BLOCKED in statuses:
            return STATUS_BLOCKED
        if STATUS_DEGRADED in statuses:
            return STATUS_DEGRADED
        return STATUS_OK

    @property
    def claim_ids(self) -> tuple[str, ...]:
        seen: list[str] = []
        for item in self.steps:
            for claim_id in item.claim_ids:
                if claim_id not in seen:
                    seen.append(claim_id)
        return tuple(seen)

    @property
    def blocked_roles(self) -> tuple[str, ...]:
        return tuple(item.role for item in self.steps if item.status == STATUS_BLOCKED)

    @property
    def degraded_engines(self) -> dict[str, str]:
        return {
            item.role: item.engine
            for item in self.steps
            if item.engine != CONTRACT_BY_ROLE[item.role].engine
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": WORKFLOW_ID,
            "workflow_version": WORKFLOW_VERSION,
            "creator_id": self.creator_id,
            "entry_type": self.entry_type,
            "entry_id": self.entry_id,
            "dna_id": self.dna_id,
            "dna_version": self.dna_version,
            "status": self.status,
            "claim_ids": list(self.claim_ids),
            "blocked_roles": list(self.blocked_roles),
            "started_at": self.started_at,
            "steps": [item.to_dict() for item in self.steps],
        }


def _step_id(run_id: str, index: int, role: str) -> str:
    return f"{run_id}:{index}:{role}"


# ── Roles ────────────────────────────────────────────────────────


def scout_step(
    run_id: str,
    *,
    creator_id: str,
    scout: Mapping[str, Any] | None,
    target_claim_ids: Sequence[str],
) -> CegStep:
    """Rule step. Proposes the candidate. Advances no claim: rules cannot ground one."""

    payload = dict(scout or {})
    source = _as_text(payload.get("source")) or "catalog_momentum"
    outputs = {
        "source": source,
        "score": payload.get("score"),
        "windows": {
            key: payload.get(key)
            for key in ("window_7d", "window_30d", "window_90d")
            if payload.get(key) is not None
        },
        "target_claim_ids": list(target_claim_ids),
        "note": "Catalog / inbound proxies propose the candidate. A claim is never advanced here.",
    }
    return CegStep(
        step_id=_step_id(run_id, 1, ROLE_SCOUT),
        role=ROLE_SCOUT,
        engine=ENGINE_RULE,
        inputs_digest=digest({"creator_id": creator_id, "scout": payload, "claims": list(target_claim_ids)}),
        outputs=outputs,
        status=STATUS_OK,
        claim_ids=(),
    )


def evidence_reader_step(
    run_id: str,
    *,
    creator_id: str,
    gate: Mapping[str, Any],
    model_available: bool,
) -> CegStep:
    """Model step. The only role allowed to put a claim_id into the trace."""

    claims = list(gate.get("claims") or [])
    claim_ids = tuple(dict.fromkeys(_as_text(item.get("claim_id")) for item in claims if _as_text(item.get("claim_id"))))
    outputs = {
        "grounded_claims": len(claims),
        "quotes": [
            {
                "claim_id": _as_text(item.get("claim_id")),
                "post_id": _as_text(item.get("post_id")),
                "timestamp": _as_text(item.get("timestamp")),
                "quote": _as_text(item.get("quote"))[:160],
            }
            for item in claims[:6]
        ],
        "prompt_version": _as_text(gate.get("prompt_version")),
        "model": _as_text(gate.get("model")),
        "pack_id": _as_text(gate.get("pack_id")),
        "caption_source": "youtube_public_timedtext",
    }
    if claim_ids:
        return CegStep(
            step_id=_step_id(run_id, 2, ROLE_EVIDENCE_READER),
            role=ROLE_EVIDENCE_READER,
            engine=ENGINE_MODEL,
            inputs_digest=digest({"creator_id": creator_id, "pack_id": outputs["pack_id"]}),
            outputs=outputs,
            status=STATUS_OK,
            claim_ids=claim_ids,
        )
    return CegStep(
        step_id=_step_id(run_id, 2, ROLE_EVIDENCE_READER),
        role=ROLE_EVIDENCE_READER,
        engine=ENGINE_MODEL,
        inputs_digest=digest({"creator_id": creator_id, "pack_id": outputs["pack_id"]}),
        outputs=outputs,
        status=STATUS_BLOCKED,
        claim_ids=(),
        degraded_reason=REASON_NO_MODEL if not model_available else REASON_NO_EXTRACTION,
    )


def match_arbiter_step(
    run_id: str,
    *,
    creator_id: str,
    match: Mapping[str, Any] | None,
    gate: Mapping[str, Any],
    grounded_claim_ids: Sequence[str],
    target_claim_ids: Sequence[str],
) -> CegStep:
    """Rule step. Claim-underwrite coverage plus the claim-evidence gate verdict."""

    record = dict(match or {})
    override = gate.get("override")
    grounded = tuple(dict.fromkeys(_as_text(item) for item in grounded_claim_ids if _as_text(item)))
    outputs = {
        "score": record.get("score"),
        "ranking_model_version": _as_text(record.get("model_version")) or RANKING_MODEL_VERSION,
        "match_id": _as_text(record.get("match_id")) or None,
        "gate_status": _as_text(gate.get("status")),
        "evidenced_claim_ids": list(grounded),
        "unevidenced_claim_ids": [item for item in target_claim_ids if item not in grounded],
        "note": "Claim coverage is the underwriting book. Rule mix is the Scout constraint. YouTube overlay never enters the catalog.",
    }
    inputs_digest = digest(
        {
            "creator_id": creator_id,
            "match_id": outputs["match_id"],
            "score": outputs["score"],
            "gate_status": outputs["gate_status"],
            "grounded": list(grounded),
        }
    )
    if grounded:
        status, engine, reason = STATUS_OK, ENGINE_RULE, None
        claim_ids: tuple[str, ...] = grounded
        if not record:
            status, reason = STATUS_DEGRADED, REASON_NO_MATCH
    elif override:
        status, engine, reason = STATUS_DEGRADED, ENGINE_HUMAN, REASON_HUMAN_OVERRIDE
        claim_ids = ()
        outputs["override_id"] = _as_text(override.get("override_id")) or None
        outputs["override_actor"] = _as_text(override.get("actor")) or None
    else:
        status, engine, reason = STATUS_BLOCKED, ENGINE_RULE, REASON_GATE_BLOCKED
        claim_ids = ()
    return CegStep(
        step_id=_step_id(run_id, 3, ROLE_MATCH_ARBITER),
        role=ROLE_MATCH_ARBITER,
        engine=engine,
        inputs_digest=inputs_digest,
        outputs=outputs,
        status=status,
        claim_ids=claim_ids,
        degraded_reason=reason,
    )


def brief_writer_step(
    run_id: str,
    *,
    creator_id: str,
    artifact: Mapping[str, Any] | None,
    grounded_claim_ids: Sequence[str],
    gate_open: bool,
    model_available: bool,
) -> CegStep:
    """Model step, degrading to the deterministic template when no key is configured."""

    record = dict(artifact or {})
    kind = _as_text(record.get("kind")) or ARTIFACT_BRIEF
    text = str(record.get("text") or "")
    grounded = tuple(dict.fromkeys(_as_text(item) for item in grounded_claim_ids if _as_text(item)))
    outputs = {
        "artifact_kind": kind,
        "artifact_id": _as_text(record.get("artifact_id")) or None,
        "title": _as_text(record.get("title"))[:120] or None,
        "chars": len(text),
        "source_label": _as_text(record.get("source_label")) or None,
    }
    inputs_digest = digest(
        {
            "creator_id": creator_id,
            "kind": kind,
            "artifact_id": outputs["artifact_id"],
            "chars": outputs["chars"],
            "grounded": list(grounded),
        }
    )
    engine = ENGINE_MODEL if model_available else ENGINE_RULE
    if not record:
        status = STATUS_BLOCKED if not gate_open else STATUS_SKIPPED
        reason = REASON_GATE_BLOCKED if not gate_open else REASON_NO_ARTIFACT
        return CegStep(
            step_id=_step_id(run_id, 4, ROLE_BRIEF_WRITER),
            role=ROLE_BRIEF_WRITER,
            engine=engine,
            inputs_digest=inputs_digest,
            outputs=outputs,
            status=status,
            claim_ids=(),
            degraded_reason=reason,
        )
    if not gate_open:
        status, reason = STATUS_DEGRADED, REASON_UNGROUNDED_ARTIFACT
    elif not model_available:
        status, reason = STATUS_DEGRADED, REASON_NO_MODEL
    else:
        status, reason = STATUS_OK, None
    return CegStep(
        step_id=_step_id(run_id, 4, ROLE_BRIEF_WRITER),
        role=ROLE_BRIEF_WRITER,
        engine=engine,
        inputs_digest=inputs_digest,
        outputs=outputs,
        status=status,
        claim_ids=grounded if gate_open else (),
        degraded_reason=reason,
    )


def compliance_guard_step(
    run_id: str,
    *,
    creator_id: str,
    artifact: Mapping[str, Any] | None,
    dna: Mapping[str, Any] | None,
    signed_off_by: str | None = None,
) -> CegStep:
    """Rule step. Runs the per-claim DNA guardrails over the produced artifact."""

    record = dict(artifact or {})
    kind = _as_text(record.get("kind")) or ARTIFACT_BRIEF
    text = str(record.get("text") or "")
    checked = [
        _as_text(claim.get("claim_id"))
        for claim in (dna or {}).get("claims") or []
        if _as_text(claim.get("claim_id")) in CLAIM_GUARDRAIL_PATTERNS
    ]
    if not record:
        return CegStep(
            step_id=_step_id(run_id, 5, ROLE_COMPLIANCE_GUARD),
            role=ROLE_COMPLIANCE_GUARD,
            engine=ENGINE_RULE,
            inputs_digest=digest({"creator_id": creator_id, "kind": kind, "chars": 0}),
            outputs={"artifact_kind": kind, "findings": [], "checked_claim_ids": checked},
            status=STATUS_SKIPPED,
            degraded_reason=REASON_NO_ARTIFACT,
        )
    findings = guardrail_findings(text, dna, kind=kind)
    outputs = {
        "artifact_kind": kind,
        "findings": findings,
        "checked_claim_ids": checked,
        "severity": SEVERITY_HARD if has_hard_finding(findings) else (SEVERITY_SOFT if findings else None),
        "signed_off_by": _as_text(signed_off_by) or None,
        "note": "Pattern checks derived from the DNA guardrails. Not a legal review.",
    }
    if has_hard_finding(findings):
        status, engine, reason = STATUS_BLOCKED, ENGINE_RULE, REASON_GUARDRAIL_FINDINGS
    elif findings:
        status, engine, reason = STATUS_DEGRADED, ENGINE_RULE, REASON_GUARDRAIL_FINDINGS
    elif _as_text(signed_off_by):
        status, engine, reason = STATUS_OK, ENGINE_HUMAN, None
    else:
        status, engine, reason = STATUS_OK, ENGINE_RULE, None
    return CegStep(
        step_id=_step_id(run_id, 5, ROLE_COMPLIANCE_GUARD),
        role=ROLE_COMPLIANCE_GUARD,
        engine=engine,
        inputs_digest=digest({"creator_id": creator_id, "kind": kind, "chars": len(text)}),
        outputs=outputs,
        status=status,
        degraded_reason=reason,
    )


def calibrator_step(
    run_id: str,
    *,
    decisions: Sequence[Mapping[str, Any]] | None = None,
    current_weights: Mapping[str, float] | None = None,
) -> CegStep:
    """Rule step. Reason codes become a weight proposal. Never mints a claim."""

    from src.calibrator import propose

    proposal = propose(decisions, current_weights)
    outputs = {
        "status": proposal["status"],
        "reason_counts": proposal["reason_counts"],
        "proposed_weights": proposal["proposed_weights"],
        "deltas": proposal["deltas"],
        "auto_applied": False,
        "note": proposal["note"],
    }
    skipped = proposal["status"] == "skipped"
    return CegStep(
        step_id=_step_id(run_id, 6, ROLE_CALIBRATOR),
        role=ROLE_CALIBRATOR,
        engine=ENGINE_RULE,
        inputs_digest=digest({"reason_counts": proposal["reason_counts"]}),
        outputs=outputs,
        status=STATUS_SKIPPED if skipped else STATUS_OK,
        claim_ids=(),
        degraded_reason=REASON_NO_DECISIONS if skipped else None,
    )


# ── Orchestrator ─────────────────────────────────────────────────


def run_id_for(entry_type: str, entry_id: str, creator_id: str, *, seq: int = 1) -> str:
    scope = digest({"entry_type": entry_type, "entry_id": entry_id, "creator_id": creator_id})
    return f"ceg_{scope}_{int(seq):03d}"


def run(
    *,
    creator_id: str,
    entry_type: str,
    entry_id: str,
    dna: Mapping[str, Any] | None,
    gate: Mapping[str, Any],
    match: Mapping[str, Any] | None = None,
    scout: Mapping[str, Any] | None = None,
    artifact: Mapping[str, Any] | None = None,
    model_available: bool | None = None,
    signed_off_by: str | None = None,
    run_id: str | None = None,
    seq: int = 1,
    decisions: Sequence[Mapping[str, Any]] | None = None,
    current_weights: Mapping[str, float] | None = None,
) -> CegRun:
    """Execute the five typed steps over already-loaded inputs and return the trace.

    ``gate`` is the Evidence Reader approval verdict from
    ``src.evidence_reader.gate_state``. It is the single source of truth for
    which claims are grounded: this orchestrator never re-derives evidence.
    """

    from src.product_dna import claim_ids as dna_claim_ids

    target_claim_ids = list(dna_claim_ids(dna))
    available = bool(gate.get("model_available")) if model_available is None else bool(model_available)
    resolved_run_id = run_id or run_id_for(entry_type, entry_id, creator_id, seq=seq)

    reader = evidence_reader_step(
        resolved_run_id,
        creator_id=creator_id,
        gate=gate,
        model_available=available,
    )
    arbiter = match_arbiter_step(
        resolved_run_id,
        creator_id=creator_id,
        match=match,
        gate=gate,
        grounded_claim_ids=reader.claim_ids,
        target_claim_ids=target_claim_ids,
    )
    gate_open = arbiter.status != STATUS_BLOCKED and bool(reader.claim_ids)
    steps = [
        scout_step(
            resolved_run_id,
            creator_id=creator_id,
            scout=scout,
            target_claim_ids=target_claim_ids,
        ),
        reader,
        arbiter,
        brief_writer_step(
            resolved_run_id,
            creator_id=creator_id,
            artifact=artifact,
            grounded_claim_ids=reader.claim_ids,
            gate_open=gate_open,
            model_available=available,
        ),
        compliance_guard_step(
            resolved_run_id,
            creator_id=creator_id,
            artifact=artifact,
            dna=dna,
            signed_off_by=signed_off_by,
        ),
        calibrator_step(
            resolved_run_id,
            decisions=decisions,
            current_weights=current_weights,
        ),
    ]
    return CegRun(
        run_id=resolved_run_id,
        creator_id=_as_text(creator_id),
        entry_type=_as_text(entry_type),
        entry_id=_as_text(entry_id),
        dna_id=_as_text((dna or {}).get("dna_id")),
        dna_version=(dna or {}).get("version"),
        steps=steps,
    )


def degraded_matrix() -> list[dict[str, str]]:
    """What every role does when the model is absent. Docs and UI read this."""

    return [
        {
            "role": item.role,
            "engine": item.engine,
            "degraded_engine": item.degraded_engine or "none",
            "advances_claims": "yes" if item.advances_claims else "no",
            "purpose": item.purpose,
            "degraded_behaviour": item.degraded_behaviour,
        }
        for item in CONTRACT
    ]
