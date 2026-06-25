# YouTube Intake Service

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-unterst%C3%BCtzen-FFDD00?logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/ddumdi11)

*In anderer Sprache lesen: [English](README.md) (vollständige Dokumentation)*

Ein kleiner lokaler **FastAPI-Dienst** (Sidecar), der aus einer YouTube-URL saubere,
direkt weiterverwendbare Daten macht — Titel, Kanal, Dauer, Thumbnail und Transkript —
und sie anderen Anwendungen über eine schlanke HTTP-API bereitstellt.

Er läuft unauffällig im Hintergrund: sucht sich selbst einen freien Port, schreibt seine
Verbindungsdaten in eine Datei, damit Client-Apps ihn finden, und beendet sich nach
Inaktivität automatisch.

> Diese deutsche Fassung ist bewusst kurz gehalten. Details (alle API-Felder,
> Fehlercodes, Build) stehen in der [englischen README](README.md).

## Voraussetzungen

- Python 3.11 oder neuer
- Internetzugriff (für `yt-dlp` und `youtube-transcript-api`)

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Start

```powershell
python main.py
```

Optional mit eigenem Auto-Shutdown-Timeout (Minuten, 1–1440):

```powershell
python main.py --timeout 90
```

Der Dienst bindet sich an `127.0.0.1`, sucht einen freien Port (`51283`–`51300`),
schreibt die Verbindungsdaten nach `~/.youtube_intake/service.info` und beendet sich nach
Inaktivität. Eine Oberfläche unter `/` gibt es nicht — der Dienst ist zum Aufruf durch
andere Apps gedacht, der Wurzelpfad liefert daher bewusst `404`.

## API in Kürze

- `GET /health` – Lebenszeichen, setzt zugleich den Idle-Timer zurück.
- `GET /process?url=<youtube_url>&language=de` – liefert JSON mit `status`
  (`complete` / `metadata_only`), `transcript_available`, `title`, `channel`,
  `duration` (rohe Sekunden), `duration_formatted` (`MM:SS`), `thumbnail_url_maxres`,
  `transcript`, `markdown`, `warnings`, `errors`.

Fehler liefern einen einheitlichen JSON-Body mit `error_code`:
`400 invalid_url`, `404 video_unavailable`, `500 processing_failed`.

## Tests

```powershell
pip install pytest httpx
python -m pytest tests/
```

Die Tests laufen vollständig offline (`yt-dlp` und Transcript-API werden gemockt).

## Build als .exe

```powershell
python build.py
```

Erzeugt per PyInstaller einen One-File-Build im Ordner `dist/`.

## Unterstützen

Wenn dir dieses Projekt Zeit gespart hat, kannst du mir gern
[einen Kaffee ausgeben](https://www.buymeacoffee.com/ddumdi11). Danke!

## Lizenz

Siehe [`LICENSE`](LICENSE).
