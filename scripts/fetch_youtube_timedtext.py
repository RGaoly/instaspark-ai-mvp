"""Backfill public timedtext bodies into the intensive-read YouTube cache.

Retries every not_downloaded clip, including those without captions.list tracks.
Empty/404 stays not_downloaded. Does not print secrets. Does not enter ranking.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.youtube_service import caption_tracks_for_video, is_youtube_available
from services.youtube_timedtext import fetch_public_timedtext
from src.youtube_clips import DEFAULT_YOUTUBE_CLIPS_PATH

CAPTIONS_LIST_RETRY_CAP = 40


def _apply(clip: dict, result: dict) -> bool:
    lines = list(result.get("caption_lines") or [])
    if result.get("caption_body_status") == "downloaded_public_timedtext" and lines:
        clip["caption_body_status"] = "downloaded_public_timedtext"
        clip["caption_body_source"] = result.get("source") or "youtube_public_timedtext"
        clip["caption_lines"] = lines
        clip["caption_language"] = result.get("language")
        clip["caption_track_kind"] = result.get("track_kind")
        clip["caption_body_error"] = None
        return True
    clip["caption_body_status"] = "not_downloaded"
    clip["caption_body_source"] = None
    clip["caption_lines"] = []
    clip["caption_body_error"] = result.get("error") or "public_timedtext_unavailable"
    return False


def main() -> None:
    path = DEFAULT_YOUTUBE_CLIPS_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    clips = list(raw.get("clips") or [])
    downloaded = 0
    still_missing = 0
    captions_list_used = 0
    for index, clip in enumerate(clips, start=1):
        clip["transcript"] = None
        clip["asr"] = None
        clip["asr_status"] = "not_collected"
        if clip.get("caption_body_status") == "downloaded_public_timedtext" and clip.get("caption_lines"):
            downloaded += 1
            continue
        video_id = str(clip.get("video_id") or "")
        tracks = list(clip.get("caption_tracks") or [])
        result = fetch_public_timedtext(video_id, tracks)
        if not _apply(clip, result) and not tracks and captions_list_used < CAPTIONS_LIST_RETRY_CAP and is_youtube_available():
            listed = caption_tracks_for_video(video_id)
            tracks = list(listed.get("items") or [])
            captions_list_used += 1
            if tracks:
                clip["caption_tracks"] = tracks
                result = fetch_public_timedtext(video_id, tracks)
                _apply(clip, result)
        if clip.get("caption_body_status") == "downloaded_public_timedtext" and clip.get("caption_lines"):
            downloaded += 1
        else:
            still_missing += 1
        if index % 15 == 0:
            print(
                f"probed {index}/{len(clips)} downloaded={downloaded} "
                f"not_downloaded={still_missing} captions.list={captions_list_used}",
                flush=True,
            )
        time.sleep(0.12)

    raw["clips"] = clips
    raw["timedtext_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw["timedtext_downloaded"] = downloaded
    raw["timedtext_not_downloaded"] = still_missing
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote timedtext: {downloaded} downloaded_public_timedtext / "
        f"{still_missing} not_downloaded / {len(clips)} clips "
        f"(captions.list retries={captions_list_used})"
    )


if __name__ == "__main__":
    main()
