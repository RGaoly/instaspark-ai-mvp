from __future__ import annotations

from services import youtube_service


def test_youtube_unavailable_without_key(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "")
    assert youtube_service.is_youtube_available() is False
    assert youtube_service.youtube_status_label() == "YouTube lookup off"


def test_search_channels_does_not_invent_rows_without_key(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "")
    result = youtube_service.search_channels("action camera")
    assert result["available"] is False
    assert result["items"] == []
    assert result["error"]
    assert result["query"] == "action camera"


def test_search_channels_requires_query():
    result = youtube_service.search_channels("   ")
    assert result["items"] == []
    assert result["error"]


def test_search_channels_maps_live_payload(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str]) -> dict:
        if path == "search":
            return {
                "items": [
                    {"id": {"channelId": "UC123"}, "snippet": {"channelId": "UC123", "title": "Trail Cam"}},
                ]
            }
        assert path == "channels"
        return {
            "items": [
                {
                    "id": "UC123",
                    "snippet": {
                        "title": "Trail Cam",
                        "description": "POV outdoor",
                        "country": "US",
                    },
                    "statistics": {
                        "subscriberCount": "12000",
                        "videoCount": "80",
                        "hiddenSubscriberCount": False,
                    },
                }
            ]
        }

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    result = youtube_service.search_channels("outdoor pov")
    assert result["available"] is True
    assert result["error"] is None
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["channel_id"] == "UC123"
    assert item["title"] == "Trail Cam"
    assert item["subscriber_count"] == 12000
    assert item["url"] == "https://www.youtube.com/channel/UC123"
    assert item["source"] == "youtube_data_api"


def test_captions_for_channel_do_not_invent_tracks_without_key(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "")
    result = youtube_service.captions_for_channel("UC123")
    assert result["source"] == "youtube_data_api"
    assert result["available"] is False
    assert result["items"] == []
    assert result["transcript"] is None
    assert "YOUTUBE_API_KEY" in result["error"]


def test_captions_for_channel_lists_tracks_without_downloading(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str]) -> dict:
        if path == "search":
            return {"items": [{"id": {"videoId": "vid1"}}]}
        assert path == "captions"
        return {
            "items": [
                {"id": "cap1", "snippet": {"language": "en", "name": "English", "trackKind": "standard"}}
            ]
        }

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    result = youtube_service.captions_for_channel("UC123")
    assert result["source"] == "youtube_data_api"
    assert result["video_id"] == "vid1"
    assert result["transcript"] is None
    assert result["items"][0]["language"] == "en"
    assert result["items"][0]["source"] == "youtube_data_api"


def test_search_videos_does_not_invent_rows_without_key(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "")
    result = youtube_service.search_videos("insta360 cycling")
    assert result["source"] == "youtube_data_api"
    assert result["available"] is False
    assert result["items"] == []
    assert "YOUTUBE_API_KEY" in result["error"]


def test_videos_list_maps_public_thumbnails(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str], *, timeout=None) -> dict:
        assert path == "videos"
        return {
            "items": [
                {
                    "id": "abc123",
                    "snippet": {
                        "title": "Trail POV",
                        "channelTitle": "Public Cam",
                        "channelId": "UCpub",
                        "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg"}},
                    },
                    "contentDetails": {"duration": "PT2M10S"},
                    "status": {"privacyStatus": "public"},
                }
            ]
        }

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    result = youtube_service.videos_list(["abc123"])
    assert result["items"][0]["url"] == "https://www.youtube.com/watch?v=abc123"
    assert result["items"][0]["keyframe_source"] == "youtube_thumbnail"
    assert result["items"][0]["privacy"] == "public"


def test_videos_list_drops_non_public(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str], *, timeout=None) -> dict:
        return {
            "items": [
                {
                    "id": "priv1",
                    "snippet": {"title": "Hidden", "thumbnails": {}},
                    "contentDetails": {},
                    "status": {"privacyStatus": "private"},
                }
            ]
        }

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    result = youtube_service.videos_list(["priv1"])
    assert result["items"] == []


def test_comment_threads_and_captions_stay_not_asr(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str], *, timeout=None) -> dict:
        if path == "commentThreads":
            return {
                "items": [
                    {
                        "snippet": {
                            "topLevelComment": {
                                "snippet": {"textDisplay": "Love this insta360 POV on the trail"}
                            }
                        }
                    }
                ]
            }
        assert path == "captions"
        return {"items": [{"id": "cap1", "snippet": {"language": "en", "name": "English", "trackKind": "asr"}}]}

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    comments = youtube_service.comment_threads_for_video("abc123")
    tracks = youtube_service.caption_tracks_for_video("abc123")
    assert comments["snippets"]
    assert any("insta360" in theme.lower() or "pov" in theme.lower() for theme in comments["themes"])
    assert tracks["transcript"] is None
    assert tracks["caption_body_status"] == "not_downloaded"
    assert "asr" not in {key.lower() for key in comments}


def test_search_channels_surfaces_api_errors(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def boom(path: str, params: dict[str, str]) -> dict:
        raise RuntimeError("YouTube API HTTP 403")

    monkeypatch.setattr(youtube_service, "_request", boom)
    result = youtube_service.search_channels("x5")
    assert result["items"] == []
    assert "403" in result["error"]


def test_videos_for_channel_lists_public_uploads(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str], *, timeout=None) -> dict:
        if path == "search":
            assert params["channelId"] == "UCpub"
            assert params["type"] == "video"
            return {"items": [{"id": {"videoId": "upl1"}}, {"id": {"videoId": "upl2"}}]}
        assert path == "videos"
        return {
            "items": [
                {
                    "id": "upl1",
                    "snippet": {
                        "title": "Own upload one",
                        "channelTitle": "Alex Rides",
                        "channelId": "UCpub",
                        "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/upl1/hqdefault.jpg"}},
                    },
                    "contentDetails": {"duration": "PT1M"},
                    "status": {"privacyStatus": "public"},
                },
                {
                    "id": "upl2",
                    "snippet": {
                        "title": "Own upload two",
                        "channelTitle": "Alex Rides",
                        "channelId": "UCpub",
                        "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/upl2/hqdefault.jpg"}},
                    },
                    "contentDetails": {"duration": "PT2M"},
                    "status": {"privacyStatus": "public"},
                },
            ]
        }

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    result = youtube_service.videos_for_channel("UCpub", max_results=3)
    assert result["error"] is None
    assert [item["video_id"] for item in result["items"]] == ["upl1", "upl2"]
    assert all(item["url"].startswith("https://www.youtube.com/watch") for item in result["items"])


def test_videos_for_channel_does_not_invent_without_key(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "")
    result = youtube_service.videos_for_channel("UCpub")
    assert result["items"] == []
    assert "YOUTUBE_API_KEY" in result["error"]


def test_uploads_via_playlist_does_not_invent_without_key(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "")
    result = youtube_service.uploads_via_playlist("UCpub")
    assert result["items"] == []
    assert "YOUTUBE_API_KEY" in result["error"]
    listed = youtube_service.channels_list(["UCpub"])
    assert listed["items"] == []
    assert "YOUTUBE_API_KEY" in listed["error"]


def test_uploads_via_playlist_maps_public_uploads(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def fake_request(path: str, params: dict[str, str], *, timeout=None) -> dict:
        if path == "channels":
            return {
                "items": [
                    {
                        "id": "UCpub",
                        "snippet": {"title": "Public Cam"},
                        "contentDetails": {"relatedPlaylists": {"uploads": "UUpub"}},
                    }
                ]
            }
        if path == "playlistItems":
            assert params["playlistId"] == "UUpub"
            return {
                "items": [
                    {"contentDetails": {"videoId": "upl1"}},
                    {"contentDetails": {"videoId": "upl2"}},
                ]
            }
        assert path == "videos"
        return {
            "items": [
                {
                    "id": "upl1",
                    "snippet": {
                        "title": "Own upload one",
                        "channelTitle": "Public Cam",
                        "channelId": "UCpub",
                        "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/upl1/hqdefault.jpg"}},
                    },
                    "contentDetails": {"duration": "PT1M"},
                    "status": {"privacyStatus": "public"},
                },
                {
                    "id": "upl2",
                    "snippet": {
                        "title": "Own upload two",
                        "channelTitle": "Public Cam",
                        "channelId": "UCpub",
                        "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/upl2/hqdefault.jpg"}},
                    },
                    "contentDetails": {"duration": "PT2M"},
                    "status": {"privacyStatus": "public"},
                },
            ]
        }

    monkeypatch.setattr(youtube_service, "_request", fake_request)
    result = youtube_service.uploads_via_playlist("UCpub", max_results=3)
    assert result["error"] is None
    assert result["via"] == "playlistItems"
    assert [item["video_id"] for item in result["items"]] == ["upl1", "upl2"]
    assert all(item["channel_id"] == "UCpub" for item in result["items"])
