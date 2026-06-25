"""Netzwerkfreie Unit-Tests fuer den YouTube Intake Service.

yt-dlp und die Transcript-API werden gemockt, damit die Tests offline und
deterministisch laufen. Getestet werden Dauer-Formatierung (Schritt 1) sowie
Status-/Fehlerfelder (Schritt 2).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from main import (  # noqa: E402
    VideoUnavailableError,
    error_payload,
    extract_video_id,
    format_duration,
    get_video_info_and_transcript,
)
from yt_dlp.utils import DownloadError  # noqa: E402
from youtube_transcript_api import NoTranscriptFound  # noqa: E402


# --- Schritt 1: Dauer-Formatierung -----------------------------------------

@pytest.mark.parametrize(
    "seconds,expected",
    [
        (1155, "19:15"),   # Beispiel-JSON: 1155 s -> 19:15 (Somas-Stil)
        (0, "0:00"),
        (59, "0:59"),
        (60, "1:00"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (None, "0:00"),
        (-5, "0:00"),
        ("123", "2:03"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=GILJNcoJ7O0") == "GILJNcoJ7O0"
    assert extract_video_id("https://youtu.be/GILJNcoJ7O0") == "GILJNcoJ7O0"
    assert extract_video_id("https://example.com/not-youtube") is None


# --- Hilfs-Mocks ------------------------------------------------------------

class _FakeYDL:
    info = {"title": "Test Title", "uploader": "Test Channel", "duration": 1155}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        return self.info


class _FakeTranscriptObj:
    def fetch(self):
        return [{"text": "Hallo"}, {"text": "Welt"}]


class _FakeTranscriptList:
    def find_transcript(self, langs):
        return _FakeTranscriptObj()


class _FakeTranscriptApi:
    def list(self, video_id):
        return _FakeTranscriptList()


def _patch_ydl(monkeypatch, ydl_cls=_FakeYDL):
    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", lambda *a, **k: ydl_cls())


# --- Schritt 2: Status-/Fehlerfelder ---------------------------------------

def test_invalid_url_raises_value_error():
    with pytest.raises(ValueError):
        get_video_info_and_transcript("https://example.com/no-id")


def test_complete_status_with_transcript(monkeypatch):
    _patch_ydl(monkeypatch)
    monkeypatch.setattr(main, "YouTubeTranscriptApi", _FakeTranscriptApi)

    result = get_video_info_and_transcript("https://youtu.be/GILJNcoJ7O0", "de")

    assert result["status"] == "complete"
    assert result["transcript_available"] is True
    assert result["transcript"] == "Hallo Welt"
    assert result["duration"] == 1155           # roh in Sekunden bleibt erhalten
    assert result["duration_formatted"] == "19:15"
    assert result["errors"] == []
    assert result["warnings"] == []
    # Markdown: formatierte Dauer, kein "Sekunden"-Rohwert, beschreibender Alt-Text
    assert "**Dauer:** 19:15" in result["markdown"]
    assert "Sekunden" not in result["markdown"]
    assert "Thumbnail zum Video" in result["markdown"]


def test_metadata_only_when_no_transcript(monkeypatch):
    _patch_ydl(monkeypatch)

    class _NoTranscriptApi:
        def list(self, video_id):
            raise NoTranscriptFound(video_id, ["de"], [])

    monkeypatch.setattr(main, "YouTubeTranscriptApi", _NoTranscriptApi)

    result = get_video_info_and_transcript("https://youtu.be/GILJNcoJ7O0", "de")

    assert result["status"] == "metadata_only"
    assert result["transcript_available"] is False
    assert result["transcript"] == ""
    assert result["warnings"]                       # mindestens ein Hinweis
    assert "_Kein Transkript verfuegbar._" in result["markdown"]


def test_video_unavailable_raises(monkeypatch):
    class _FailingYDL(_FakeYDL):
        def extract_info(self, url, download=False):
            raise DownloadError("Video unavailable")

    _patch_ydl(monkeypatch, _FailingYDL)

    with pytest.raises(VideoUnavailableError):
        get_video_info_and_transcript("https://youtu.be/GILJNcoJ7O0", "de")


def test_error_payload_shape():
    payload = error_payload("invalid_url", "Ungueltige URL")
    assert payload == {
        "status": "error",
        "error_code": "invalid_url",
        "detail": "Ungueltige URL",
        "errors": ["Ungueltige URL"],
    }


# --- Endpoint-Tests ---------------------------------------------------------

def _make_client():
    from fastapi.testclient import TestClient

    controller = main.IdleShutdownController(60)
    return TestClient(main.create_app(controller))


def test_health_endpoint():
    client = _make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_process_invalid_url_returns_400():
    client = _make_client()
    resp = client.get("/process", params={"url": "https://example.com/no-id"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "invalid_url"


def test_process_video_unavailable_returns_404(monkeypatch):
    class _FailingYDL(_FakeYDL):
        def extract_info(self, url, download=False):
            raise DownloadError("Video unavailable")

    _patch_ydl(monkeypatch, _FailingYDL)

    client = _make_client()
    resp = client.get("/process", params={"url": "https://youtu.be/GILJNcoJ7O0"})
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "video_unavailable"
