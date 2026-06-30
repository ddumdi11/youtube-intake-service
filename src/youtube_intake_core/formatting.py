"""Formatierungs-Helfer fuer den Core."""


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
