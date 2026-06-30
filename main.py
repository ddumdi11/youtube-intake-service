import argparse
import asyncio
import json
import logging
import os
import re
import socket
import threading
import time
from pathlib import Path
from typing import Optional

import uvicorn
import yt_dlp
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from yt_dlp.utils import DownloadError
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

logger = logging.getLogger(__name__)


class VideoUnavailableError(Exception):
    """Raised when yt-dlp cannot retrieve the video (private, removed, geo-blocked)."""


# JSON-Status-Werte fuer Konsumenten (Extension, Somas, WordPress)
STATUS_COMPLETE = "complete"          # Metadaten + Transkript vorhanden
STATUS_METADATA_ONLY = "metadata_only"  # Metadaten vorhanden, kein Transkript
STATUS_ERROR = "error"                # harte Fehler (ungueltige URL, Video nicht verfuegbar)

PORT_RANGE_START = 51283
PORT_RANGE_END = 51300
DEFAULT_TIMEOUT_MINUTES = 60
MIN_TIMEOUT_MINUTES = 1
MAX_TIMEOUT_MINUTES = 1440
SERVICE_INFO_PATH = Path.home() / ".youtube_intake" / "service.info"


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


def format_duration(seconds: object) -> str:
    """Render Sekunden als human-friendly MM:SS bzw. H:MM:SS (Somas-Stil)."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "0:00"
    if total < 0:
        total = 0
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def error_payload(error_code: str, detail: str) -> dict:
    """Einheitliche Fehlerstruktur, auch bei 4xx/5xx im Body lesbar."""
    return {
        "status": STATUS_ERROR,
        "error_code": error_code,
        "detail": detail,
        "errors": [detail],
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
    duration_seconds = info.get("duration", 0) or 0
    duration_formatted = format_duration(duration_seconds)
    transcript_available = bool(transcript_text)
    status = STATUS_COMPLETE if transcript_available else STATUS_METADATA_ONLY

    transcript_markdown = transcript_text if transcript_available else "_Kein Transkript verfuegbar._"
    alt_text = f'Thumbnail zum Video „{title}“'

    markdown_body = f"""# {title}

![{alt_text}]({thumbnails['maxres']})

**Kanal:** {info.get('uploader', 'Unbekannter Kanal')}
**Dauer:** {duration_formatted}
**URL:** [{url}]({url})

> Falls das Bild nicht angezeigt wird, diese Varianten testen:
> - [MaxRes]({thumbnails['maxres']})
> - [SD]({thumbnails['sd']})
> - [HQ]({thumbnails['hq']})

## Transkript

{transcript_markdown}
"""

    return {
        "status": status,
        "transcript_available": transcript_available,
        "title": title,
        "channel": info.get("uploader", "Unbekannter Kanal"),
        "duration": duration_seconds,
        "duration_formatted": duration_formatted,
        "url": url,
        "thumbnail_url_maxres": thumbnails["maxres"],
        "transcript": transcript_text,
        "markdown": markdown_body,
        "warnings": warnings,
        "errors": [],
    }


def find_free_port(start: int = PORT_RANGE_START, end: int = PORT_RANGE_END) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Kein freier Port im Bereich {start}-{end} gefunden.")


def write_service_info(port: int, timeout_minutes: int) -> None:
    SERVICE_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "host": "127.0.0.1",
        "port": port,
        "pid": os.getpid(),
        "timeout_minutes": timeout_minutes,
        "base_url": f"http://127.0.0.1:{port}",
    }
    SERVICE_INFO_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def remove_service_info() -> None:
    try:
        SERVICE_INFO_PATH.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Konnte service.info nicht entfernen: %s", exc)


class IdleShutdownController:
    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._deadline = time.monotonic() + timeout_seconds
        self._stop_event = threading.Event()

    def reset(self) -> None:
        with self._lock:
            self._deadline = time.monotonic() + self.timeout_seconds

    def remaining_seconds(self) -> int:
        with self._lock:
            remaining = self._deadline - time.monotonic()
        return max(0, int(remaining))

    def stop(self) -> None:
        self._stop_event.set()

    def monitor(self, on_timeout) -> None:
        while not self._stop_event.wait(1.0):
            if self.remaining_seconds() <= 0:
                logger.info("Idle timeout erreicht, Server wird beendet.")
                on_timeout()
                return


def create_app(controller: IdleShutdownController) -> FastAPI:
    app = FastAPI(title="YouTube Intake Service", version="0.1.0")

    @app.middleware("http")
    async def reset_timeout_middleware(request: Request, call_next):
        controller.reset()
        response = await call_next(request)
        response.headers["X-Timeout-Remaining"] = str(controller.remaining_seconds())
        return response

    @app.get("/health")
    async def health():
        return {"status": "ok", "timeout_in_seconds": controller.remaining_seconds()}

    @app.get("/process")
    async def process(
        url: str = Query(..., description="YouTube URL"),
        language: str = Query("de", min_length=2, max_length=10),
    ):
        try:
            _t0 = time.monotonic()
            result = await asyncio.to_thread(get_video_info_and_transcript, url, language)
            logger.debug("process %.2fs %s", time.monotonic() - _t0, url)
        except ValueError as exc:
            return JSONResponse(status_code=400, content=error_payload("invalid_url", str(exc)))
        except VideoUnavailableError as exc:
            return JSONResponse(
                status_code=404, content=error_payload("video_unavailable", str(exc))
            )
        except Exception as exc:
            logger.exception("Verarbeitung fehlgeschlagen")
            return JSONResponse(
                status_code=500,
                content=error_payload("processing_failed", f"Verarbeitung fehlgeschlagen: {exc}"),
            )
        return result

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the YouTube Intake Service.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_MINUTES,
        help=f"Auto-shutdown timeout in Minuten ({MIN_TIMEOUT_MINUTES}-{MAX_TIMEOUT_MINUTES}).",
    )
    return parser.parse_args()


async def run_server(timeout_minutes: int) -> None:
    port = find_free_port()
    timeout_seconds = timeout_minutes * 60
    controller = IdleShutdownController(timeout_seconds)
    app = create_app(controller)

    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)

    def trigger_shutdown() -> None:
        server.should_exit = True

    monitor_thread = threading.Thread(
        target=controller.monitor,
        args=(trigger_shutdown,),
        name="idle-shutdown-monitor",
        daemon=True,
    )

    write_service_info(port, timeout_minutes)
    logger.info("Service-Info geschrieben nach %s", SERVICE_INFO_PATH)
    monitor_thread.start()
    try:
        await server.serve()
    finally:
        controller.stop()
        remove_service_info()


def validate_timeout(timeout_minutes: int) -> int:
    if timeout_minutes < MIN_TIMEOUT_MINUTES or timeout_minutes > MAX_TIMEOUT_MINUTES:
        raise ValueError(
            f"--timeout muss zwischen {MIN_TIMEOUT_MINUTES} und {MAX_TIMEOUT_MINUTES} Minuten liegen."
        )
    return timeout_minutes


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    try:
        timeout_minutes = validate_timeout(args.timeout)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        asyncio.run(run_server(timeout_minutes))
    except KeyboardInterrupt:
        logger.info("Beendet durch Benutzer (Strg+C).")


if __name__ == "__main__":
    main()
