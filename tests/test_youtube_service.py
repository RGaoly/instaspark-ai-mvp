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


def test_search_channels_surfaces_api_errors(monkeypatch):
    monkeypatch.setattr(youtube_service, "YOUTUBE_API_KEY", "test-key")

    def boom(path: str, params: dict[str, str]) -> dict:
        raise RuntimeError("YouTube API HTTP 403")

    monkeypatch.setattr(youtube_service, "_request", boom)
    result = youtube_service.search_channels("x5")
    assert result["items"] == []
    assert "403" in result["error"]
