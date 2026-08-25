"""Versionable Creator Genome pack. One object per catalog creator.

This is a file-backed asset with a pack version and per-creator genome_id,
not a restatement of Search table cells. Uncollected live signals stay
explicit. It does not run ASR, comment mining, or a platform crawl.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GENOME_PATH = ROOT / "data" / "creator_genome.json"
UNCOLLECTED = "not_collected"
REQUIRED_UNCOLLECTED = (
    "asr_status",
    "comment_status",
    "keyframe_status",
)


def load_genome_pack(path: str | Path = DEFAULT_GENOME_PATH) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Creator Genome pack must be a JSON object.")
    pack_id = str(raw.get("genome_pack_id") or "").strip()
    version = raw.get("version")
    genomes = raw.get("genomes")
    if not pack_id:
        raise ValueError("Creator Genome pack requires genome_pack_id.")
    if not isinstance(version, int) or version < 1:
        raise ValueError("Creator Genome pack version must be a positive integer.")
    if not isinstance(genomes, list) or not genomes:
        raise ValueError("Creator Genome pack requires at least one genome.")
    ids: list[str] = []
    creators: list[str] = []
    for item in genomes:
        genome_id = str(item.get("genome_id") or "").strip()
        creator_id = str(item.get("creator_id") or "").strip()
        genome_version = item.get("version")
        clip_ids = item.get("clip_ids")
        if not genome_id or not creator_id:
            raise ValueError("Every genome needs genome_id and creator_id.")
        if not isinstance(genome_version, int) or genome_version < 1:
            raise ValueError(f"{genome_id} version must be a positive integer.")
        if not isinstance(clip_ids, list) or not clip_ids:
            raise ValueError(f"{genome_id} needs at least one clip_id.")
        for field in REQUIRED_UNCOLLECTED:
            if item.get(field) != UNCOLLECTED:
                raise ValueError(f"{genome_id} must mark {field} as {UNCOLLECTED}.")
        if item.get("commerce", {}).get("status") != UNCOLLECTED:
            raise ValueError(f"{genome_id} commerce must stay {UNCOLLECTED} until PerformanceEvents exist.")
        ids.append(genome_id)
        creators.append(creator_id)
    if len(ids) != len(set(ids)):
        raise ValueError("genome_id values must be unique.")
    if len(creators) != len(set(creators)):
        raise ValueError("Each creator_id may appear once in the genome pack.")
    return raw


def genomes_by_id(pack: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    data = pack if pack is not None else load_genome_pack()
    return {str(item["creator_id"]): dict(item) for item in data.get("genomes") or []}


def genome_for(creator_id: str, pack: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    genome = genomes_by_id(pack).get(str(creator_id))
    return dict(genome) if genome else None


def genome_document(genome: Mapping[str, Any] | None) -> str:
    """Flatten collected genome fields for sparse retrieval. Skips uncollected."""

    if not genome:
        return ""
    topic_scene = genome.get("topic_scene") or {}
    audience = genome.get("audience") or {}
    parts = [
        str(genome.get("creator_name") or ""),
        " ".join(str(item) for item in (topic_scene.get("topics") or [])),
        " ".join(str(item) for item in (topic_scene.get("scenes") or [])),
        " ".join(str(item) for item in (genome.get("visual_style") or [])),
        str(audience.get("country") or ""),
        str(audience.get("language") or ""),
    ]
    return " ".join(part for part in parts if str(part).strip())


def clip_ids_for(creator_id: str, pack: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    genome = genome_for(creator_id, pack)
    if not genome:
        return ()
    return tuple(str(item) for item in genome.get("clip_ids") or [] if str(item).strip())


def genome_panel_html(creator_id: str, pack: Mapping[str, Any] | None = None) -> str:
    """Operator-facing genome card. Uncollected fields stay explicit."""

    genome = genome_for(creator_id, pack)
    if not genome:
        return (
            '<div class="is-card"><div class="is-panel-body">'
            "<small>No Creator Genome for this catalog row.</small></div></div>"
        )
    esc = html.escape
    momentum = genome.get("momentum") or {}
    audience = genome.get("audience") or {}
    cost = genome.get("cost") or {}
    commerce = genome.get("commerce") or {}
    topics = ", ".join(str(item) for item in ((genome.get("topic_scene") or {}).get("topics") or []) if str(item).strip())
    styles = ", ".join(str(item) for item in (genome.get("visual_style") or []) if str(item).strip())
    return f"""
    <div class="is-card">
      <div class="is-panel-head">
        <span class="is-panel-title">Creator Genome</span>
        <span class="is-panel-link">{esc(str(genome.get("genome_id", "")))} · v{esc(str(genome.get("version", "")))}</span>
      </div>
      <div class="is-panel-body">
        <p><b>{esc(str(genome.get("creator_name") or creator_id))}</b>
        <small> · {esc(str(audience.get("country") or ""))} · {esc(str(audience.get("language") or ""))}</small>
        {f"<br/><small>Public YouTube channel {esc(str(genome.get('youtube_channel_id')))}. Not KYC.</small>" if str(genome.get("youtube_channel_id") or "").startswith("UC") else ""}</p>
        <p><b>Topics / style</b><br/>{esc(topics or "—")} · {esc(styles or "—")}</p>
        <p><b>Momentum proxies</b><br/>
        7d {esc(str(momentum.get("window_7d", "—")))}
        · 30d {esc(str(momentum.get("window_30d", "—")))}
        · 90d {esc(str(momentum.get("window_90d", "—")))}</p>
        <p><b>Clip index</b><br/>{len(genome.get("clip_ids") or [])} authored clips · {esc(str(genome.get("vector_ref") or "sparse_tfidf_catalog_document"))}</p>
        <p><b>Quote</b><br/>USD {esc(str(cost.get("quote_usd", "—")))} · sample {esc(str(cost.get("sample_status", "not_collected")))}</p>
        <small>{esc(str(momentum.get("note") or ""))}
        Age {esc(str(audience.get("age_status", "not_collected")))}.
        Commerce {esc(str(commerce.get("status", "not_collected")))}.
        ASR {esc(str(genome.get("asr_status", "not_collected")))},
        comments {esc(str(genome.get("comment_status", "not_collected")))},
        keyframes {esc(str(genome.get("keyframe_status", "not_collected")))}.
        Not live platform analytics.</small>
      </div>
    </div>
    """
