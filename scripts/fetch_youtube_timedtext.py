"""Backfill public timedtext bodies into the intensive-read YouTube cache.

Only clips that already list caption tracks are probed. Empty/404 stays
not_downloaded. Does not print secrets. Does not enter ranking.
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

from services.youtube_timedtext import fetch_public_timedtext
from src.youtube_clips import DEFAULT_YOUTUBE_CLIPS_PATH


def main() -> None:
    path = DEFAULT_YOUTUBE_CLIPS_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    clips = list(raw.get("clips") or [])
    listed = [item for item in clips if item.get("caption_tracks")]
    downloaded = 0
    still_missing = 0
    for index, clip in enumerate(clips, start=1):
        if not clip.get("caption_tracks"):
            clip["caption_body_status"] = clip.get("caption_body_status") or "not_downloaded"
            clip["caption_lines"] = []
            clip["caption_body_source"] = None
            clip["transcript"] = None
            clip["asr"] = None
            clip["asr_status"] = "not_collected"
            continue
        result = fetch_public_timedtext(str(clip.get("video_id") or ""), list(clip.get("caption_tracks") or []))
        status = result.get("caption_body_status") or "not_downloaded"
        lines = list(result.get("caption_lines") or [])
        if status == "downloaded_public_timedtext" and lines:
            clip["caption_body_status"] = "downloaded_public_timedtext"
            clip["caption_body_source"] = result.get("source") or "youtube_public_timedtext"
            clip["caption_lines"] = lines
            clip["caption_language"] = result.get("language")
            clip["caption_track_kind"] = result.get("track_kind")
            clip["caption_body_error"] = None
            downloaded += 1
        else:
            clip["caption_body_status"] = "not_downloaded"
            clip["caption_body_source"] = None
            clip["caption_lines"] = []
            clip["caption_body_error"] = result.get("error") or "public_timedtext_unavailable"
            still_missing += 1
        clip["transcript"] = None
        clip["asr"] = None
        clip["asr_status"] = "not_collected"
        if index % 10 == 0:
            print(
                f"probed {index}/{len(clips)} listed={len(listed)} "
                f"downloaded={downloaded} not_downloaded={still_missing}",
                flush=True,
            )
        time.sleep(0.15)

    raw["clips"] = clips
    raw["timedtext_fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw["timedtext_downloaded"] = downloaded
    raw["timedtext_not_downloaded"] = sum(
        1 for item in clips if item.get("caption_body_status") != "downloaded_public_timedtext"
    )
    raw["note"] = (
        "Public YouTube search hits for intensive read. Not claimed as catalog-creator uploads. "
        "Never enters ranking. Public timedtext bodies stored when YouTube exposes them "
        "(source youtube_public_timedtext). Empty timedtext stays not_downloaded. "
        "Not Whisper. ASR not collected."
    )
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote timedtext: {downloaded} downloaded_public_timedtext / "
        f"{len(listed)} listed tracks / {len(clips)} clips"
    )


if __name__ == "__main__":
    main()
