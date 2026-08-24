from pathlib import Path
import html as html_lib

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.intensive_read import YT_LEGEND, intensive_read_html, intensive_read_pack, nearest_timedtext_line
from src.scoring import rank_creators

ROOT = Path(__file__).resolve().parents[1]
CLAIM_IDS = {"all_day", "pov", "rugged", "360"}


def test_intensive_read_pack_exposes_twenty_creators_clips_and_timestamps():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    assert len(ranked) >= 20

    pack = intensive_read_pack(ranked, posts, n=20)
    assert len(pack) == 20
    html = intensive_read_html(pack)
    assert 'id="intensive-read-board"' in html
    assert "Top 20 intensive-read clips" in html
    assert "This is not multimodal ASR" in html
    assert "not_collected" in html
    assert "Instagram Reels" not in html
    assert "TikTok For Business" not in html

    clip_n = 0
    stamp_n = 0
    for item in pack:
        assert item["creator_id"]
        assert item["clips"]
        assert f'data-creator-id="{item["creator_id"]}"' in html
        assert item["creator_id"] in html
        for clip in item["clips"]:
            assert clip["asr_status"] == "not_collected"
            assert clip["asr"] in (None, "")
            assert clip["caption_source"] == "labeled_demo"
            assert clip["keyframe_status"] == "labeled_demo_note"
            assert clip["comment_status"] == "labeled_demo_themes"
            assert clip["comment_themes"]
            catalog_url = str(clip.get("catalog_url") or clip.get("url") or "")
            assert catalog_url.startswith("https://example.com/demo/") or str(clip.get("url") or "").startswith("https://example.com/demo/")
            if clip.get("video_id"):
                assert str(clip["url"]).startswith("https://www.youtube.com/watch")
                assert clip.get("keyframe_source") == "youtube_thumbnail"
                assert clip.get("comment_source") == "youtube_data_api"
                assert clip.get("caption_body_status") in {"not_downloaded", "downloaded_public_timedtext"}
                assert clip.get("youtube_source") == "youtube_data_api"
                assert clip.get("ownership") in {
                    "public_search_hit",
                    "channel_search_match",
                    "attached_channel",
                }
                if clip.get("ownership") in {"channel_search_match", "attached_channel"}:
                    assert clip.get("channel_id")
                if clip.get("caption_body_status") == "downloaded_public_timedtext":
                    assert clip.get("caption_body_source") == "youtube_public_timedtext"
                    assert clip.get("caption_lines")
                    assert html_lib.escape(clip["caption_lines"][0]["text"]) in html
                    assert "youtube_public_timedtext" in html
                else:
                    assert not clip.get("caption_lines")
            assert clip["timestamps"]
            assert all(stamp["t"] and stamp["label"] for stamp in clip["timestamps"])
            assert all(stamp["claim_id"] in CLAIM_IDS for stamp in clip["timestamps"])
            assert all(stamp["caption"] and stamp["keyframe_note"] for stamp in clip["timestamps"])
            clip_n += 1
            stamp_n += len(clip["timestamps"])
            assert clip["url"] in html or clip.get("catalog_url", "") in html
            assert clip["timestamps"][0]["t"] in html
            assert clip["timestamps"][0]["claim_id"] in html
            assert clip["timestamps"][0]["caption"] in html
            assert clip["timestamps"][0]["keyframe_note"] in html
            assert clip["comment_themes"][0] in html
    html_youtube = intensive_read_html(
        [
            {
                **pack[0],
                "youtube_captions": {
                    "source": "youtube_data_api",
                    "items": [{"language": "en", "name": "English", "track_kind": "standard"}],
                },
            }
        ]
    )
    assert "source: youtube_data_api" in html_youtube
    assert "not ranked" in html_youtube
    assert clip_n == 60
    assert stamp_n >= 60
    youtube_n = sum(1 for item in pack for clip in item["clips"] if clip.get("video_id"))
    assert 40 <= youtube_n <= 60
    assert "ASR not_collected" in html
    assert "Labeled demo evidence — not ASR, not scraped comments." in html or "youtube_data_api" in html
    assert "labeled_demo" in html
    assert "asr_collected" not in html.lower()
    assert "whisper output" not in html.lower()
    assert "Whisper" not in YT_LEGEND
    assert "ASR" not in YT_LEGEND
    assert "youtube_public_timedtext" in YT_LEGEND
    assert "attached_channel" in YT_LEGEND
    assert "channel_search_match" in YT_LEGEND
    assert "public_search_hit" in YT_LEGEND


def test_intensive_read_html_empty_ranking():
    import pandas as pd

    assert intensive_read_pack(pd.DataFrame()) == []
    html = intensive_read_html([])
    assert 'id="intensive-read-board"' in html
    assert "No gated creators" in html


def test_nearest_timedtext_line_stays_within_window():
    lines = [{"t": "00:01", "text": "Hello trail"}, {"t": "01:00", "text": "Later"}]
    near = nearest_timedtext_line("00:08", lines, window_seconds=20)
    assert near == {"t": "00:01", "text": "Hello trail"}
    assert nearest_timedtext_line("03:00", lines, window_seconds=20) is None
    assert nearest_timedtext_line("00:08", [], window_seconds=20) is None


def test_attached_channel_overlays_replace_topic_search_cache():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    creator_id = str(ranked.iloc[0]["creator_id"])
    creator_posts = [post for post in posts if post["creator_id"] == creator_id]
    attached = [
        {
            "post_id": creator_posts[0]["post_id"],
            "creator_id": creator_id,
            "video_id": "attachedVid1",
            "url": "https://www.youtube.com/watch?v=attachedVid1",
            "title": "Creator-owned public upload",
            "thumbnail_url": "https://i.ytimg.com/vi/attachedVid1/hqdefault.jpg",
            "channel_id": "UCattached",
            "channel_title": str(ranked.iloc[0]["creator_name"]),
            "comment_snippets": ["from the attached channel"],
            "comment_themes": ["Public comment theme: camera"],
            "caption_tracks": [{"language": "en", "track_kind": "standard", "source": "youtube_data_api"}],
            "caption_body_status": "downloaded_public_timedtext",
            "caption_body_source": "youtube_public_timedtext",
            "caption_lines": [{"t": "00:03", "text": "This is my Insta360 on the trail today"}],
            "ownership": "attached_channel",
            "keyframe_source": "youtube_thumbnail",
            "comment_source": "youtube_data_api",
            "asr_status": "not_collected",
        }
    ]
    pack = intensive_read_pack(
        ranked,
        posts,
        n=20,
        attached_by_creator={creator_id: attached},
    )
    row = next(item for item in pack if item["creator_id"] == creator_id)
    first = row["clips"][0]
    assert first["ownership"] == "attached_channel"
    assert first["video_id"] == "attachedVid1"
    assert first["channel_id"] == "UCattached"
    html = intensive_read_html(pack)
    assert "ownership: attached_channel" in html
    assert html_lib.escape("This is my Insta360 on the trail today") in html
    for clip in row["clips"]:
        if clip["post_id"] == creator_posts[0]["post_id"]:
            continue
        assert not clip.get("video_id")
