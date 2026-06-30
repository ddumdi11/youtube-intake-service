"""Status-/Fehlerkonstanten und einheitliche Fehlerstruktur (Core, server-frei)."""

# JSON-Status-Werte fuer Konsumenten (Extension, Somas, WordPress)
STATUS_COMPLETE = "complete"            # Metadaten + Transkript vorhanden
STATUS_METADATA_ONLY = "metadata_only"  # Metadaten vorhanden, kein Transkript
STATUS_ERROR = "error"                  # harte Fehler (ungueltige URL, Video nicht verfuegbar)

# Fehlercodes fuer die error_payload-Struktur
ERROR_INVALID_URL = "invalid_url"
ERROR_VIDEO_UNAVAILABLE = "video_unavailable"
ERROR_PROCESSING_FAILED = "processing_failed"


def error_payload(error_code: str, detail: str) -> dict:
    """Einheitliche Fehlerstruktur, auch bei 4xx/5xx im Body lesbar."""
    return {
        "status": STATUS_ERROR,
        "error_code": error_code,
        "detail": detail,
        "errors": [detail],
    }
