from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.intensive_read import intensive_read_html
from src.scoring import rank_creators
from src.youtube_clips import attach_youtube_overlay, load_youtube_intensive_clips

ROOT = Path(__file__).resolve().parents[1]


def test_ranking_ids_do_not_change_when_youtube_cache_is_read():
    scoring = (ROOT / "src/scoring.py").read_text(encoding="utf-8")
    assert "youtube_clips" not in scoring
    assert "youtube_intensive" not in scoring
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    before = list(rank_creators(catalog, mission)["creator_id"])
    load_youtube_intensive_clips()
    after = list(rank_creators(catalog, mission)["creator_id"])
    assert before == after
    assert set(catalog["creator_id"]) == {f"C{i:03d}" for i in range(1, 61)}


def test_committed_cache_covers_sixty_creators_when_present():
    pack = load_youtube_intensive_clips()
    if not pack.get("available"):
        return
    clips = pack["clips"]
    assert len(clips) >= 60
    assert len({item["creator_id"] for item in clips}) == 60
    assert all(item["asr_status"] == "not_collected" for item in clips)
    assert all(item["caption_body_status"] == "not_downloaded" for item in clips)
    assert all(str(item["url"]).startswith("https://www.youtube.com/watch") for item in clips)


def test_catalog_clip_urls_stay_example_dot_com():
    for post in load_creator_content():
        assert post["url"].startswith("https://example.com/demo/")
        assert post["asr_status"] == "not_collected"


def test_attach_overlay_keeps_asr_not_collected():
    clip = {
        "post_id": "POST-C001-01",
        "url": "https://example.com/demo/c001/clip-01",
        "asr_status": "not_collected",
        "asr": None,
    }
    merged = attach_youtube_overlay(
        clip,
        {
            "video_id": "abc123",
            "url": "https://www.youtube.com/watch?v=abc123",
            "title": "Trail POV",
            "thumbnail_url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
            "comment_snippets": ["Great insta360 shot"],
            "comment_themes": ["Public comment theme: insta360"],
            "caption_tracks": [{"language": "en"}],
            "ownership": "public_search_hit",
        },
    )
    assert merged["catalog_url"].startswith("https://example.com/demo/")
    assert merged["url"].startswith("https://www.youtube.com/watch")
    assert merged["asr_status"] == "not_collected"
    assert merged["asr"] is None
    html = intensive_read_html(
        [
            {
                "rank": 1,
                "creator_id": "C001",
                "creator_name": "Alex Rides",
                "clips": [merged | {"title": "clip", "timestamps": [{"t": "00:01", "claim_id": "pov", "caption": "x", "keyframe_note": "y", "caption_source": "labeled_demo"}], "caption_source": "labeled_demo", "keyframe_status": "labeled_demo_note", "comment_status": "labeled_demo_themes", "comment_themes": ["demo"]}],
            }
        ]
    )
    assert "youtube_data_api" in html
    assert "labeled_demo" in html
    assert "i.ytimg.com" in html
    assert "Great insta360 shot" in html


def test_loader_rejects_invented_asr(tmp_path):
    path = tmp_path / "yt.json"
    path.write_text(
        json.dumps(
            {
                "pack_id": "t",
                "version": 1,
                "source": "youtube_data_api",
                "clips": [
                    {
                        "post_id": "POST-X",
                        "video_id": "abc",
                        "url": "https://www.youtube.com/watch?v=abc",
                        "asr_status": "asr_collected",
                        "privacy": "public",
                        "keyframe_source": "youtube_thumbnail",
                        "comment_source": "youtube_data_api",
                        "caption_body_status": "not_downloaded",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not_collected"):
        load_youtube_intensive_clips(path)
