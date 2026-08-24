"""Top-20 intensive-read pack. Labeled demo evidence, not ASR.

The PDF intensive-read step lists subtitles, keyframes and comments. This demo
does not run ASR, OCR, or comment scraping. The operator surface is a clip list
with timestamps mapped to Product DNA claim ids plus an explicit labeled-demo
caption / keyframe-note / comment-theme layer. Platform ASR stays not_collected.
"""

from __future__ import annotations

import html
from typing import Any, Iterable, Mapping

import pandas as pd

from src.content_evidence import clips_for, load_creator_content


INTENSIVE_N = 20
LEGEND = "Labeled demo evidence — not ASR, not scraped comments."


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
                    "caption": str(stamp.get("caption") or ""),
                    "keyframe_note": str(stamp.get("keyframe_note") or ""),
                    "caption_source": str(stamp.get("caption_source") or clip.get("caption_source") or ""),
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
                    "caption_source": str(clip.get("caption_source") or ""),
                    "keyframe_status": str(clip.get("keyframe_status") or ""),
                    "comment_status": str(clip.get("comment_status") or ""),
                    "comment_themes": [str(item) for item in (clip.get("comment_themes") or []) if str(item).strip()],
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


def _youtube_block_html(block: Mapping[str, Any] | None, esc) -> str:
    if not block:
        return ""
    source = esc(str(block.get("source") or "youtube_data_api"))
    if block.get("items"):
        tracks = "".join(
            f"<li>{esc(item.get('language') or 'und')} · {esc(item.get('name') or item.get('id') or 'track')} "
            f"· {esc(item.get('track_kind') or '')}</li>"
            for item in block.get("items") or []
        )
        return (
            f'<div class="is-youtube-captions"><small><b>YouTube caption tracks</b> · source: {source}. '
            "Listed only, not downloaded, not ranked, not ASR.</small>"
            f"<ul style=\"margin:2px 0 0 16px\">{tracks}</ul></div>"
        )
    error = esc(str(block.get("error") or "No caption tracks listed."))
    return (
        f'<div class="is-youtube-captions"><small><b>YouTube captions</b> · source: {source}. '
        f"{error} Labeled demo layer stays below.</small></div>"
    )


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
            themes = ", ".join(esc(theme) for theme in clip.get("comment_themes") or []) or "none"
            stamps = "".join(
                "<li>"
                f'<b>{esc(stamp.get("t", ""))}</b> · claim {esc(stamp.get("claim_id", "") or "unmapped")}'
                f"<br/><small>Caption ({esc(stamp.get('caption_source') or clip.get('caption_source') or 'labeled_demo')}): "
                f"{esc(stamp.get('caption', ''))}</small>"
                f"<br/><small>Keyframe ({esc(clip.get('keyframe_status') or 'labeled_demo_note')}): "
                f"{esc(stamp.get('keyframe_note', ''))}</small>"
                "</li>"
                for stamp in clip.get("timestamps") or []
            ) or "<li>No labeled timestamps</li>"
            clip_blocks.append(
                "<div style=\"margin:6px 0 0 8px\">"
                f'<b>{esc(clip.get("title") or clip.get("post_id") or "Clip")}</b> '
                f'<small>{esc(clip.get("url", ""))} · ASR {esc(str(clip.get("asr_status") or "not_collected"))}</small>'
                f"<ul style=\"margin:2px 0 0 16px\">{stamps}</ul>"
                f"<small>Comment themes ({esc(str(clip.get('comment_status') or 'labeled_demo_themes'))}): {themes}</small>"
                "</div>"
            )
        cards.append(
            f'<div class="is-intensive-row" data-creator-id="{esc(str(item.get("creator_id", "")))}">'
            f'<b>{int(item.get("rank") or 0):02d}. {esc(str(item.get("creator_name", "")))}</b> '
            f'<small>{esc(str(item.get("creator_id", "")))} · {len(item.get("clips") or [])} clips</small>'
            f"{_youtube_block_html(item.get('youtube_captions'), esc)}"
            f'{"".join(clip_blocks)}</div>'
        )
    return (
        '<div class="is-card" id="intensive-read-board">'
        '<div class="is-panel-head"><span class="is-panel-title">Top 20 intensive-read clips</span>'
        '<span class="is-panel-link">Labeled demo · not ASR</span></div>'
        '<div class="is-panel-body">'
        f"<small>{html.escape(LEGEND)} Platform ASR stays not_collected. "
        "This is not multimodal ASR, not Whisper, not OCR.</small>"
        f'{"".join(cards)}</div></div>'
    )
