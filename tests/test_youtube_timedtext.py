from __future__ import annotations

import io
import urllib.error

from services import youtube_timedtext


XML_BODY = """<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="3">
<body>
<p t="1000" d="2000">All-day battery on the trail</p>
<p t="21000" d="1500">POV ride with the X5</p>
</body>
</timedtext>
"""

JSON3_BODY = """{
  "events": [
    {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "All-day battery on the trail"}]},
    {"tStartMs": 21000, "segs": [{"utf8": "POV ride with the X5"}]}
  ]
}
"""

PLAYER_TRACKS = {
    "captions": {
        "playerCaptionsTracklistRenderer": {
            "captionTracks": [
                {
                    "languageCode": "en",
                    "kind": "asr",
                    "baseUrl": "https://www.youtube.com/api/timedtext?v=abc123&kind=asr&lang=en",
                },
                {
                    "languageCode": "en",
                    "baseUrl": "https://www.youtube.com/api/timedtext?v=abc123&lang=en",
                },
            ]
        }
    }
}


def test_parse_timedtext_xml_and_json3():
    xml_lines = youtube_timedtext.parse_timedtext(XML_BODY.encode())
    json_lines = youtube_timedtext.parse_timedtext(JSON3_BODY)
    assert xml_lines[0] == {"t": "00:01", "text": "All-day battery on the trail"}
    assert json_lines[1]["t"] == "00:21"
    assert json_lines[1]["text"] == "POV ride with the X5"
    assert youtube_timedtext.parse_timedtext(b"") == []
    assert youtube_timedtext.parse_timedtext(b"   ") == []


def test_pick_prefers_standard_over_asr():
    chosen = youtube_timedtext.pick_caption_track(
        PLAYER_TRACKS["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"],
        [{"language": "en", "track_kind": "standard"}],
    )
    assert chosen is not None
    assert chosen.get("kind") != "asr"
    assert "kind=asr" not in chosen["baseUrl"]


def test_fetch_public_timedtext_xml_success(monkeypatch):
    monkeypatch.setattr(youtube_timedtext, "_http_post_json", lambda *args, **kwargs: PLAYER_TRACKS)

    def fake_get(url: str, *, timeout: int = 20) -> bytes:
        assert "kind=asr" not in url
        assert url.startswith("https://www.youtube.com/api/timedtext")
        return XML_BODY.encode()

    monkeypatch.setattr(youtube_timedtext, "_http_get", fake_get)
    result = youtube_timedtext.fetch_public_timedtext("abc123", [{"language": "en"}])
    assert result["caption_body_status"] == "downloaded_public_timedtext"
    assert result["source"] == "youtube_public_timedtext"
    assert result["track_kind"] == "standard"
    assert result["caption_lines"][0]["text"] == "All-day battery on the trail"


def test_fetch_public_timedtext_json3_success(monkeypatch):
    monkeypatch.setattr(youtube_timedtext, "_http_post_json", lambda *args, **kwargs: PLAYER_TRACKS)
    monkeypatch.setattr(youtube_timedtext, "_http_get", lambda *args, **kwargs: JSON3_BODY.encode())
    result = youtube_timedtext.fetch_public_timedtext("abc123")
    assert result["caption_body_status"] == "downloaded_public_timedtext"
    assert [line["t"] for line in result["caption_lines"]] == ["00:01", "00:21"]


def test_fetch_public_timedtext_404_stays_not_downloaded(monkeypatch):
    monkeypatch.setattr(youtube_timedtext, "_http_post_json", lambda *args, **kwargs: PLAYER_TRACKS)

    def boom(url: str, *, timeout: int = 20) -> bytes:
        raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b""))

    monkeypatch.setattr(youtube_timedtext, "_http_get", boom)
    result = youtube_timedtext.fetch_public_timedtext("abc123")
    assert result["caption_body_status"] == "not_downloaded"
    assert result["caption_lines"] == []
    assert result["error"] == "http_404"


def test_fetch_never_claims_download_when_mock_empty(monkeypatch):
    monkeypatch.setattr(youtube_timedtext, "_http_post_json", lambda *args, **kwargs: PLAYER_TRACKS)
    monkeypatch.setattr(youtube_timedtext, "_http_get", lambda *args, **kwargs: b"")
    result = youtube_timedtext.fetch_public_timedtext("abc123")
    assert result["caption_body_status"] == "not_downloaded"
    assert result["caption_lines"] == []
    assert result["source"] == "youtube_public_timedtext"
    assert result["error"] == "empty_timedtext"


def test_fetch_no_player_tracks_stays_not_downloaded(monkeypatch):
    monkeypatch.setattr(youtube_timedtext, "_http_post_json", lambda *args, **kwargs: {})
    result = youtube_timedtext.fetch_public_timedtext("abc123", [{"language": "en"}])
    assert result["caption_body_status"] == "not_downloaded"
    assert result["caption_lines"] == []
    assert result["error"] == "public_timedtext_unavailable"
