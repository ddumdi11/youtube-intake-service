# YouTube Intake Service

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/ddumdi11)

*Read this in another language: [Deutsch](README.de.md)*

A small local **FastAPI sidecar** that turns any YouTube URL into clean, ready-to-use
data — title, channel, duration, thumbnail and transcript — and serves it to your other
applications over a tiny HTTP API.

It runs quietly in the background: it finds its own free port, writes its connection
details to a file so client apps can locate it, and shuts itself down automatically after
a period of inactivity.

## Features

- One endpoint, clean output: metadata + transcript + ready-made Markdown
- Automatic free-port discovery (range `51283`–`51300`)
- Writes connection info to `~/.youtube_intake/service.info`
- Idle auto-shutdown (configurable timeout)
- Builds into a single standalone `.exe` (PyInstaller)
- Clear `status`/`errors` fields so consumers can tell *fully processed*,
  *metadata only* and hard errors apart

## Requirements

- Python 3.11 or newer
- Internet access (for `yt-dlp` and `youtube-transcript-api`)

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running

```powershell
python main.py
```

Optional custom idle-shutdown timeout (minutes, 1–1440):

```powershell
python main.py --timeout 90
```

On start the service binds to `127.0.0.1`, picks a free port, writes the connection
details to `~/.youtube_intake/service.info` (see [`service.info.example`](service.info.example)),
and exits automatically after inactivity. There is no UI at `/` — the service is meant to
be called by other apps, so opening the root URL returns `404` by design.

## API

### `GET /health`

Liveness check; also resets the idle timer.

```json
{ "status": "ok", "timeout_in_seconds": 3599 }
```

### `GET /process?url=<youtube_url>&language=de`

Response fields (HTTP 200):

| Field | Description |
| --- | --- |
| `status` | `complete` (metadata + transcript) or `metadata_only` (no transcript) |
| `transcript_available` | `true` / `false` |
| `title` | Video title |
| `channel` | Uploader / channel name |
| `duration` | Duration in **raw seconds** (for machine processing) |
| `duration_formatted` | Duration as `MM:SS` / `H:MM:SS` |
| `url` | The requested URL |
| `thumbnail_url_maxres` | Max-res thumbnail URL |
| `transcript` | Plain-text transcript (empty if none) |
| `markdown` | Ready-made Markdown (human-friendly duration, descriptive thumbnail alt text) |
| `warnings` | Non-fatal notes (e.g. missing transcript) |
| `errors` | Empty on success |

#### Error responses

Hard failures return the matching HTTP status with a uniform JSON body:

```json
{
  "status": "error",
  "error_code": "invalid_url",
  "detail": "...",
  "errors": ["..."]
}
```

| Status | `error_code` | Meaning |
| --- | --- | --- |
| `400` | `invalid_url` | Not a valid YouTube URL |
| `404` | `video_unavailable` | Video private, removed or geo-blocked |
| `500` | `processing_failed` | Unexpected error |

## Tests

```powershell
pip install pytest httpx
python -m pytest tests/
```

The tests run fully offline — `yt-dlp` and the transcript API are mocked.

## Build a standalone .exe

```powershell
python build.py
```

The script runs PyInstaller for a one-file build; the result lands in `dist/`.

## Support

If this project saved you time, you can
[buy me a coffee](https://www.buymeacoffee.com/ddumdi11). Thank you!

## License

See [`LICENSE`](LICENSE).
