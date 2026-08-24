"""Versionable Product DNA. Claims are the visual-proof graph for this SKU.

This is a file-backed object with a stable dna_id and version, not a copy of
Launch Mission form fields. It does not read a live PIM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DNA_PATH = ROOT / "data" / "product_dna.json"


def load_product_dna(path: str | Path = DEFAULT_DNA_PATH) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Product DNA must be a JSON object.")
    dna_id = str(raw.get("dna_id") or "").strip()
    sku = str(raw.get("sku") or "").strip()
    version = raw.get("version")
    claims = raw.get("claims")
    if not dna_id or not sku:
        raise ValueError("Product DNA requires dna_id and sku.")
    if not isinstance(version, int) or version < 1:
        raise ValueError("Product DNA version must be a positive integer.")
    if not isinstance(claims, list) or not claims:
        raise ValueError("Product DNA requires at least one claim.")
    for claim in claims:
        if not str(claim.get("claim_id") or "").strip() or not str(claim.get("claim") or "").strip():
            raise ValueError("Every DNA claim needs claim_id and claim text.")
    return raw


def dna_document(dna: Mapping[str, Any] | None) -> str:
    """Flatten DNA into retrieval text. Empty DNA returns empty string."""

    if not dna:
        return ""
    parts = [str(dna.get("sku") or ""), str(dna.get("audience") or "")]
    for claim in dna.get("claims") or []:
        parts.append(str(claim.get("claim") or ""))
        parts.extend(str(item) for item in (claim.get("scenes") or []))
        parts.extend(str(item) for item in (claim.get("visual_proof") or []))
    return " ".join(part for part in parts if str(part).strip())


def claim_ids(dna: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not dna:
        return ()
    return tuple(str(claim.get("claim_id")) for claim in dna.get("claims") or [] if claim.get("claim_id"))
