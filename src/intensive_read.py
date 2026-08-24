"""Top-20 intensive-read pack. Authored timestamps, not ASR.

The PDF intensive-read step lists subtitles, keyframes and comments. This demo
does not collect those. The operator surface is a clip list with timestamps
mapped to Product DNA claim ids and an explicit asr_status=not_collected.
"""

from __future__ import annotations

import html
from typing import Any, Iterable, Mapping

import pandas as pd

from src.content_evidence import clips_for, load_creator_content


INTENSIVE_N = 20


def intensive_read_pack(
    ranked: pd.DataFrame,
    posts: Iterable[Mapping[str, Any]] | None = None,
    *,
    n: int = INTENSIVE_N,
) -> list[dict[str, Any]]:
    """Return one inspectable row per Top-N ranked creator. Empty ranking is []."""

    if ranked is None or ranked.empty:
        return []
    clip_source = list(posts) if posts is not None else load_creator_content()
    rows: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(ranked.head(n).iterrows(), start=1):
        creator_id = str(row.get("creator_id") or "")
        clips = []
        for clip in clips_for(creator_id, clip_source):
            stamps = [
                {
                    "t": str(stamp.get("t") or ""),
                    "label": str(stamp.get("label") or ""),
                    "claim_id": str(stamp.get("claim_id") or ""),
                }
                for stamp in clip.get("timestamps") or []
                if str(stamp.get("t") or "").strip() and str(stamp.get("label") or "").strip()
            ]
            clips.append(
                {
                    "post_id": str(clip.get("post_id") or ""),
                    "url": str(clip.get("url") or ""),
                    "title": str(clip.get("title") or clip.get("post_id") or ""),
                    "timestamps": stamps,
                    "asr_status": str(clip.get("asr_status") or "not_collected"),
                    "asr": clip.get("asr"),
                }
            )
        rows.append(
            {
                "rank": rank,
                "creator_id": creator_id,
                "creator_name": str(row.get("creator_name") or creator_id),
                "clips": clips,
            }
        )
    return rows


def intensive_read_html(pack: Iterable[Mapping[str, Any]]) -> str:
    rows = list(pack or [])
    if not rows:
        return (
            '<div class="is-card" id="intensive-read-board"><div class="is-panel-body">'
            "<small>No gated creators to intensive-read.</small></div></div>"
        )
    esc = html.escape
    cards = []
    for item in rows:
        clip_blocks = []
        for clip in item.get("clips") or []:
            stamps = "".join(
                f'<li><b>{esc(stamp.get("t", ""))}</b> {esc(stamp.get("label", ""))}'
                f' · claim {esc(stamp.get("claim_id", "") or "unmapped")}</li>'
                for stamp in clip.get("timestamps") or []
            ) or "<li>No labeled timestamps</li>"
            clip_blocks.append(
                "<div style=\"margin:6px 0 0 8px\">"
                f'<b>{esc(clip.get("title") or clip.get("post_id") or "Clip")}</b> '
                f'<small>{esc(clip.get("url", ""))} · ASR {esc(str(clip.get("asr_status") or "not_collected"))}</small>'
                f"<ul style=\"margin:2px 0 0 16px\">{stamps}</ul></div>"
            )
        cards.append(
            f'<div class="is-intensive-row" data-creator-id="{esc(str(item.get("creator_id", "")))}">'
            f'<b>{int(item.get("rank") or 0):02d}. {esc(str(item.get("creator_name", "")))}</b> '
            f'<small>{esc(str(item.get("creator_id", "")))} · {len(item.get("clips") or [])} clips</small>'
            f'{"".join(clip_blocks)}</div>'
        )
    return (
        '<div class="is-card" id="intensive-read-board">'
        '<div class="is-panel-head"><span class="is-panel-title">Top 20 intensive-read clips</span>'
        '<span class="is-panel-link">Authored timestamps · not ASR</span></div>'
        '<div class="is-panel-body">'
        "<small>Mapped to Product DNA claim_id. Subtitles, keyframes and comments are not_collected. "
        "This is not multimodal ASR.</small>"
        f'{"".join(cards)}</div></div>'
    )
