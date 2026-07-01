"""YouTube Intake Core — reine Extraktionslogik, frei von Server-Abhaengigkeiten.

Public API:
    process(url, language="de") -> dict   # identische Wire-Form wie bisher
    __version__
"""

from .errors import (
    ERROR_INVALID_URL,
    ERROR_PROCESSING_FAILED,
    ERROR_VIDEO_UNAVAILABLE,
    STATUS_COMPLETE,
    STATUS_ERROR,
    STATUS_METADATA_ONLY,
    IntakeError,
    InvalidURLError,
    VideoUnavailableError,
    error_payload,
)
from .extraction import (
    build_thumbnail_urls,
    extract_video_id,
)
from .extraction import get_video_info_and_transcript as process
from .formatting import format_duration
from .markdown import build_markdown

__version__ = "1.0.0"

__all__ = [
    "process",
    "__version__",
    "IntakeError",
    "InvalidURLError",
    "VideoUnavailableError",
    "extract_video_id",
    "build_thumbnail_urls",
    "format_duration",
    "build_markdown",
    "error_payload",
    "STATUS_COMPLETE",
    "STATUS_METADATA_ONLY",
    "STATUS_ERROR",
    "ERROR_INVALID_URL",
    "ERROR_VIDEO_UNAVAILABLE",
    "ERROR_PROCESSING_FAILED",
]
