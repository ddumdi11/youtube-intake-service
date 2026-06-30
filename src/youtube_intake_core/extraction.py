"""Reine Extraktionslogik: Metadaten via yt-dlp + Transkript via youtube-transcript-api.

Dieses Modul importiert NIEMALS fastapi/uvicorn. Es ist der server-freie Kern.
"""

import logging
import re
from typing import Optional

import yt_dlp
from yt_dlp.utils import DownloadError
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from .errors import STATUS_COMPLETE, STATUS_METADATA_ONLY
from .formatting import format_duration
from .markdown import build_markdown

logger = logging.getLogger(__name__)


class VideoUnavailableError(Exception):
    """Raised when yt-dlp cannot retrieve the video (private, removed, geo-blocked)."""


def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def build_thumbnail_urls(video_id: str) -> dict:
    base = f"https://i.ytimg.com/vi/{video_id}"
    return {
        "maxres": f"{base}/maxresdefault.jpg",
        "sd": f"{base}/sddefault.jpg",
        "hq": f"{base}/hqdefault.jpg",
    }


def _snippet_text(snippet: object) -> str:
    if isinstance(snippet, dict):
        return str(snippet.get("text", ""))
    text = getattr(snippet, "text", "")
    return str(text)


def get_video_info_and_transcript(url: str, language: str = "de") -> dict:
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Ungültige YouTube-URL: {url}")

    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": False}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise VideoUnavailableError(
            f"Video nicht verfuegbar (privat, entfernt oder gesperrt): {url}"
        ) from exc

    transcript_text = ""
    warnings: list[str] = []
    try:
        try:
            transcript_list = YouTubeTranscriptApi().list(video_id)
        except AttributeError:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript_obj = transcript_list.find_transcript([language])
        except NoTranscriptFound:
            try:
                transcript_obj = transcript_list.find_transcript(["en"])
            except NoTranscriptFound:
                transcript_obj = next(iter(transcript_list))

        entries = transcript_obj.fetch()
        transcript_text = " ".join(
            _snippet_text(snippet).strip() for snippet in entries if _snippet_text(snippet).strip()
        )
    except (TranscriptsDisabled, NoTranscriptFound, StopIteration) as exc:
        message = f"Kein passendes Transkript gefunden: {exc}"
        logger.warning(message)
        warnings.append(message)
    except Exception as exc:
        message = f"Fehler beim Laden des Transkripts: {exc}"
        logger.warning(message)
        warnings.append(message)

    thumbnails = build_thumbnail_urls(video_id)

    title = info.get("title", "Unbekannter Titel")
    channel = info.get("uploader", "Unbekannter Kanal")
    duration_seconds = info.get("duration", 0) or 0
    duration_formatted = format_duration(duration_seconds)
    transcript_available = bool(transcript_text)
    status = STATUS_COMPLETE if transcript_available else STATUS_METADATA_ONLY

    markdown_body = build_markdown(
        title=title,
        channel=channel,
        duration_formatted=duration_formatted,
        url=url,
        thumbnails=thumbnails,
        transcript_text=transcript_text,
    )

    return {
        "status": status,
        "transcript_available": transcript_available,
        "title": title,
        "channel": channel,
        "duration": duration_seconds,
        "duration_formatted": duration_formatted,
        "url": url,
        "thumbnail_url_maxres": thumbnails["maxres"],
        "transcript": transcript_text,
        "markdown": markdown_body,
        "warnings": warnings,
        "errors": [],
    }
