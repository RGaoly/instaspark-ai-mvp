"""Top-20 intensive-read pack. YouTube public overlay + labeled-demo timestamps.

Public YouTube hits never enter ranking. Public timedtext lines are a separate
layer from labeled_demo DNA timestamps. Bodies are never invented from demo text.
"""

from __future__ import annotations

import html
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.content_evidence import clips_for, load_creator_content
from src.verified_channels import (
    LEFTOVER_SEARCH_NOTE,
    binds_by_creator_id,
    cache_clips_by_video_id,
    overlay_for_verified_bind,
    verified_row_label,
)
from src.youtube_clips import attach_youtube_overlay, bind_uploads_to_posts, youtube_clips_by_post_id


INTENSIVE_N = 20
LEGEND = "Labeled demo evidence — not ASR, not scraped comments."
YT_LEGEND = (
    "youtube_data_api: public video link, thumbnail keyframe proxy, comment snippets. "
    "youtube_public_timedtext: caption lines when YouTube exposes them. "
    "ownership attached_channel = operator-attached channel uploads; "
    "catalog_channel = this catalog row is that public YouTube channel, not KYC; "
    "channel_search_match = leftover name match on an unbound synthetic row; "
    "public_search_hit = topic search, not the catalog creator. "
    "labeled_demo: DNA claim timestamps (separate layer). Not ranked."
)


def intensive_read_pack(
    ranked: pd.DataFrame,
    posts: Iterable[Mapping[str, Any]] | None = None,
    *,
    n: int = INTENSIVE_N,
    youtube_clips: Mapping[str, Mapping[str, Any]] | None = None,
    attached_by_creator: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Return one inspectable row per Top-N ranked creator. Empty ranking is [].

    attached_by_creator wins over a verified public-channel bind and the topic-search cache.
    """

    if ranked is None or ranked.empty:
        return []
    clip_source = list(posts) if posts is not None else load_creator_content()
    overlay = dict(youtube_clips if youtube_clips is not None else youtube_clips_by_post_id())
    attached_by_creator = attached_by_creator or {}
    verified_binds = binds_by_creator_id()
    cache_by_video = cache_clips_by_video_id(overlay.values())
    rows: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(ranked.head(n).iterrows(), start=1):
        creator_id = str(row.get("creator_id") or "")
        creator_posts = clips_for(creator_id, clip_source)
        verified_bind = None
        if creator_id in attached_by_creator:
            attached_rows = [dict(item) for item in attached_by_creator.get(creator_id) or []]
            if attached_rows and all(str(item.get("post_id") or "").strip() for item in attached_rows):
                bound = {
                    str(item["post_id"]): {**item, "ownership": "attached_channel"}
                    for item in attached_rows
                    if item.get("video_id")
                }
            else:
                bound = bind_uploads_to_posts(creator_posts, attached_rows, ownership="attached_channel")
            for post in creator_posts:
                post_id = str(post.get("post_id") or "")
                if post_id in bound:
                    overlay[post_id] = bound[post_id]
                else:
                    overlay.pop(post_id, None)
        elif creator_id in verified_binds:
            verified_bind = verified_binds[creator_id]
            bound = overlay_for_verified_bind(
                verified_bind,
                creator_posts,
                cache_by_video=cache_by_video,
            )
            for post in creator_posts:
                post_id = str(post.get("post_id") or "")
                if post_id in bound:
                    overlay[post_id] = bound[post_id]
                    video_id = str(bound[post_id].get("video_id") or "")
                    if video_id:
                        cache_by_video[video_id] = bound[post_id]
                else:
                    overlay.pop(post_id, None)
        clips = []
        for clip in creator_posts:
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
            base = {
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
            clips.append(attach_youtube_overlay(base, overlay.get(base["post_id"])))
        rows.append(
            {
                "rank": rank,
                "creator_id": creator_id,
                "creator_name": str(row.get("creator_name") or creator_id),
                "clips": clips,
                "verified_bind": {
                    "channel_id": verified_bind.get("channel_id"),
                    "channel_title": verified_bind.get("channel_title"),
                    "bind_reason": verified_bind.get("bind_reason"),
                }
                if verified_bind
                else None,
            }
        )
    return rows


def _stamp_seconds(value: str) -> int | None:
    parts = str(value or "").strip().split(":")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    nums = [int(part) for part in parts]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def nearest_timedtext_line(
    stamp_t: str,
    lines: Iterable[Mapping[str, Any]] | None,
    *,
    window_seconds: int = 20,
) -> dict[str, str] | None:
    target = _stamp_seconds(stamp_t)
    rows = [dict(item) for item in lines or [] if str(item.get("t") or "").strip() and str(item.get("text") or "").strip()]
    if target is None or not rows:
        return None

    def distance(item: Mapping[str, Any]) -> int:
        seconds = _stamp_seconds(str(item.get("t") or ""))
        if seconds is None:
            return 10**9
        return abs(seconds - target)

    chosen = min(rows, key=distance)
    if distance(chosen) > window_seconds:
        return None
    return {"t": str(chosen.get("t") or ""), "text": str(chosen.get("text") or "")}


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
            "Listed only, not ranked.</small>"
            f"<ul style=\"margin:2px 0 0 16px\">{tracks}</ul></div>"
        )
    error = esc(str(block.get("error") or "No caption tracks listed."))
    return (
        f'<div class="is-youtube-captions"><small><b>YouTube captions</b> · source: {source}. '
        f"{error} Labeled demo layer stays below.</small></div>"
    )


def _clip_timedtext_html(clip: Mapping[str, Any], esc) -> str:
    lines = [item for item in clip.get("caption_lines") or [] if item.get("t") and item.get("text")]
    if clip.get("caption_body_status") != "downloaded_public_timedtext" or not lines:
        return ""
    preview = "".join(
        f"<li><small>{esc(item.get('t'))} · {esc(item.get('text'))}</small></li>" for item in lines[:8]
    )
    more = f" · showing 8 of {len(lines)}" if len(lines) > 8 else f" · {len(lines)} lines"
    return (
        f'<div class="is-public-timedtext"><small><b>Public timedtext</b> · source: youtube_public_timedtext{more}. '
        "Separate from labeled_demo.</small>"
        f"<ul style=\"margin:2px 0 0 16px\">{preview}</ul></div>"
    )


def _clip_youtube_html(clip: Mapping[str, Any], esc) -> str:
    if not clip.get("video_id"):
        return ""
    thumb = str(clip.get("thumbnail_url") or "")
    img = (
        f'<img src="{esc(thumb)}" alt="YouTube thumbnail keyframe proxy" width="160" '
        'style="display:block;margin:4px 0;border-radius:4px"/>'
        if thumb
        else ""
    )
    snippets = "".join(
        f"<li><small>{esc(text)}</small></li>" for text in clip.get("comment_snippets") or []
    ) or "<li><small>No public comment snippets returned.</small></li>"
    tracks = clip.get("caption_tracks") or []
    body_status = str(clip.get("caption_body_status") or "not_downloaded")
    if body_status == "downloaded_public_timedtext" and clip.get("caption_lines"):
        track_line = (
            f"{len(tracks)} caption track(s) listed, public timedtext downloaded "
            f"({len(clip.get('caption_lines') or [])} lines, source: youtube_public_timedtext)"
        )
    elif tracks:
        track_line = f"{len(tracks)} caption track(s) listed, body not_downloaded"
    else:
        track_line = "No caption tracks listed; body not_downloaded"
    yt_themes = ", ".join(esc(theme) for theme in clip.get("youtube_comment_themes") or []) or "none"
    return (
        "<div style=\"margin:4px 0 0 8px\">"
        f'<a href="{esc(str(clip.get("url") or ""))}">{esc(str(clip.get("youtube_title") or clip.get("url") or "YouTube"))}</a> '
        f'<small>source: youtube_data_api · ownership: {esc(str(clip.get("ownership") or "public_search_hit"))}'
        + (
            f' · channel_id: {esc(str(clip.get("channel_id")))}'
            if clip.get("channel_id")
            else ""
        )
        + f" · keyframe_source: youtube_thumbnail · {esc(track_line)}</small>"
        f"{img}"
        f"<small>Public comments (comment_source: youtube_data_api): {yt_themes}</small>"
        f"<ul style=\"margin:2px 0 0 16px\">{snippets}</ul>"
        f"{_clip_timedtext_html(clip, esc)}"
        "</div>"
    )


def intensive_read_html(pack: Iterable[Mapping[str, Any]]) -> str:
    rows = list(pack or [])
    if not rows:
        return (
            '<div class="is-card" id="intensive-read-board"><div class="is-panel-body">'
            "<small>No gated creators to intensive-read.</small></div></div>"
        )
    esc = html.escape
    has_youtube = any(clip.get("video_id") for item in rows for clip in item.get("clips") or [])
    legend = YT_LEGEND if has_youtube else LEGEND
    cards = []
    for item in rows:
        clip_blocks = []
        for clip in item.get("clips") or []:
            themes = ", ".join(esc(theme) for theme in clip.get("comment_themes") or []) or "none"
            public_lines = list(clip.get("caption_lines") or [])
            stamps = "".join(
                "<li>"
                f'<b>{esc(stamp.get("t", ""))}</b> · claim {esc(stamp.get("claim_id", "") or "unmapped")}'
                f"<br/><small>Caption ({esc(stamp.get('caption_source') or clip.get('caption_source') or 'labeled_demo')}): "
                f"{esc(stamp.get('caption', ''))}</small>"
                + (
                    (
                        "<br/><small>Public timedtext near DNA "
                        f"({esc(near.get('t'))}, source: youtube_public_timedtext): "
                        f"{esc(near.get('text'))}</small>"
                    )
                    if (near := nearest_timedtext_line(str(stamp.get("t") or ""), public_lines))
                    else ""
                )
                + f"<br/><small>Keyframe note ({esc(clip.get('keyframe_status') or 'labeled_demo_note')}): "
                f"{esc(stamp.get('keyframe_note', ''))}</small>"
                "</li>"
                for stamp in clip.get("timestamps") or []
            ) or "<li>No labeled timestamps</li>"
            clip_blocks.append(
                "<div style=\"margin:6px 0 0 8px\">"
                f'<b>{esc(clip.get("title") or clip.get("post_id") or "Clip")}</b> '
                f'<small>{esc(clip.get("catalog_url") or clip.get("url", ""))} · ASR {esc(str(clip.get("asr_status") or "not_collected"))}</small>'
                f"{_clip_youtube_html(clip, esc)}"
                f"<ul style=\"margin:2px 0 0 16px\">{stamps}</ul>"
                f"<small>Labeled demo comment themes ({esc(str(clip.get('comment_status') or 'labeled_demo_themes'))}): {themes}</small>"
                "</div>"
            )
        bind = item.get("verified_bind") if isinstance(item.get("verified_bind"), Mapping) else None
        if bind:
            row_note = (
                f"<br/><small>{esc(verified_row_label(bind))}. "
                "Clips are this channel's public uploads. Not KYC.</small>"
            )
        elif any(str(clip.get("ownership") or "") == "public_search_hit" for clip in item.get("clips") or []):
            row_note = f"<br/><small>{esc(LEFTOVER_SEARCH_NOTE)}</small>"
        else:
            row_note = ""
        cards.append(
            f'<div class="is-intensive-row" data-creator-id="{esc(str(item.get("creator_id", "")))}">'
            f'<b>{int(item.get("rank") or 0):02d}. {esc(str(item.get("creator_name", "")))}</b> '
            f'<small>{esc(str(item.get("creator_id", "")))} · {len(item.get("clips") or [])} clips</small>'
            f"{row_note}"
            f"{_youtube_block_html(item.get('youtube_captions'), esc)}"
            f'{"".join(clip_blocks)}</div>'
        )
    return (
        '<div class="is-card" id="intensive-read-board">'
        '<div class="is-panel-head"><span class="is-panel-title">Top 20 intensive-read clips</span>'
        f'<span class="is-panel-link">{"youtube_data_api + labeled_demo" if has_youtube else "Labeled demo · not ASR"}</span></div>'
        '<div class="is-panel-body">'
        f"<small>{html.escape(legend)} Platform ASR stays not_collected. "
        "This is not multimodal ASR, not Whisper, not OCR.</small>"
        f'{"".join(cards)}</div></div>'
    )
