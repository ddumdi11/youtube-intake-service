"""Status-/Fehlerkonstanten und einheitliche Fehlerstruktur (Core, server-frei)."""

# JSON-Status-Werte fuer Konsumenten (Extension, Somas, WordPress)
STATUS_COMPLETE = "complete"            # Metadaten + Transkript vorhanden
STATUS_METADATA_ONLY = "metadata_only"  # Metadaten vorhanden, kein Transkript
STATUS_ERROR = "error"                  # harte Fehler (ungueltige URL, Video nicht verfuegbar)

# Fehlercodes fuer die error_payload-Struktur
ERROR_INVALID_URL = "invalid_url"
ERROR_VIDEO_UNAVAILABLE = "video_unavailable"
ERROR_PROCESSING_FAILED = "processing_failed"


class IntakeError(Exception):
    """Basis fuer fachliche Core-Fehler. Traegt error_code + message.

    Unerwartetes Internes -> IntakeError(error_code="processing_failed").
    """

    error_code = ERROR_PROCESSING_FAILED

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code


class InvalidURLError(IntakeError):
    """Keine YouTube-Video-ID aus der URL parsebar (ohne Netz erkennbar)."""

    error_code = ERROR_INVALID_URL


class VideoUnavailableError(IntakeError):
    """yt-dlp meldet das Video als nicht verfuegbar (privat, entfernt, gesperrt)."""

    error_code = ERROR_VIDEO_UNAVAILABLE


def error_payload(error_code: str, detail: str) -> dict:
    """Einheitliche Fehlerstruktur, auch bei 4xx/5xx im Body lesbar."""
    return {
        "status": STATUS_ERROR,
        "error_code": error_code,
        "detail": detail,
        "errors": [detail],
    }
