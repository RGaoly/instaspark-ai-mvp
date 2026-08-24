from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.content_evidence import load_creator_content, load_deep_read_pack


def _valid_clip(post_id: str = "POST-X-01") -> dict:
    return {
        "post_id": post_id,
        "creator_id": "C001",
        "url": "https://example.com/demo/x/clip-01",
        "timestamps": [{"t": "00:08", "label": "Handlebar POV", "claim_id": "pov"}],
        "asr": None,
        "asr_status": "not_collected",
    }


def _valid_layer(post_id: str = "POST-X-01") -> dict:
    return {
        "post_id": post_id,
        "caption_source": "labeled_demo",
        "keyframe_status": "labeled_demo_note",
        "comment_status": "labeled_demo_themes",
        "comment_themes": ["Catalog label (not scraped): outdoor setup questions"],
        "stamps": [
            {
                "t": "00:08",
                "claim_id": "pov",
                "caption": "On-screen label: handlebar POV, trail filling the frame.",
                "keyframe_note": "Would show: POV handle or rider eye-line; trail filling the frame.",
            }
        ],
    }


def _write_pair(tmp_path: Path, posts: list, clips: list) -> tuple[Path, Path]:
    content = tmp_path / "content.json"
    deep = tmp_path / "deep.json"
    content.write_text(json.dumps(posts), encoding="utf-8")
    deep.write_text(
        json.dumps(
            {
                "pack_id": "deep_read_test_v1",
                "version": 1,
                "layer": "labeled_demo",
                "clips": clips,
            }
        ),
        encoding="utf-8",
    )
    return content, deep


def test_demo_pack_is_versioned_labeled_demo_not_asr():
    pack = load_deep_read_pack()
    posts = load_creator_content()
    assert pack["pack_id"] == "deep_read_x5_v1"
    assert pack["version"] == 1
    assert pack["layer"] == "labeled_demo"
    assert len(pack["clips"]) == 180
    assert len(posts) == 180
    assert {item["post_id"] for item in pack["clips"]} == {item["post_id"] for item in posts}


def test_loader_rejects_asr_collected_status(tmp_path):
    post = _valid_clip()
    post["asr_status"] = "asr_collected"
    content, deep = _write_pair(tmp_path, [post], [_valid_layer()])
    with pytest.raises(ValueError, match="not_collected"):
        load_creator_content(content, deep_read_path=deep)


def test_loader_rejects_whisper_caption_source(tmp_path):
    layer = _valid_layer()
    layer["caption_source"] = "whisper"
    content, deep = _write_pair(tmp_path, [_valid_clip()], [layer])
    with pytest.raises(ValueError, match="whisper"):
        load_creator_content(content, deep_read_path=deep)


def test_loader_rejects_youtube_captions_without_fetch_path(tmp_path):
    layer = _valid_layer()
    layer["caption_source"] = "youtube_captions"
    content, deep = _write_pair(tmp_path, [_valid_clip()], [layer])
    with pytest.raises(ValueError, match="youtube_captions"):
        load_creator_content(content, deep_read_path=deep)


def test_loader_rejects_non_null_asr_body(tmp_path):
    post = _valid_clip()
    post["asr"] = "pretend transcript"
    content, deep = _write_pair(tmp_path, [post], [_valid_layer()])
    with pytest.raises(ValueError, match="must not claim ASR"):
        load_creator_content(content, deep_read_path=deep)
