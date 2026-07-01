"""Daemon-Mechanik: Portwahl, service.info, Idle-Shutdown, Server-Runner + CLI.

Importiert den Core, niemals umgekehrt.
"""

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

logger = logging.getLogger(__name__)

PORT_RANGE_START = 51283
PORT_RANGE_END = 51300
MIN_PORT = 1024
MAX_PORT = 65535
DEFAULT_TIMEOUT_MINUTES = 60
MIN_TIMEOUT_MINUTES = 1
MAX_TIMEOUT_MINUTES = 1440
SERVICE_INFO_PATH = Path.home() / ".youtube_intake" / "service.info"


class PortConflictError(RuntimeError):
    """Kein nutzbarer Port verfuegbar (Bereich belegt oder --port belegt/ungueltig)."""


def _try_bind(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def find_free_port(start: int = PORT_RANGE_START, end: int = PORT_RANGE_END) -> int:
    for port in range(start, end + 1):
        if _try_bind(port):
            return port
    raise PortConflictError(f"Kein freier Port im Bereich {start}-{end} gefunden.")


def resolve_port(requested: object) -> int:
    """Liefert einen nutzbaren Port oder wirft PortConflictError mit klarer Meldung."""
    if requested is not None:
        if not (MIN_PORT <= requested <= MAX_PORT):
            raise PortConflictError(
                f"--port muss zwischen {MIN_PORT} und {MAX_PORT} liegen (angegeben: {requested})."
            )
        if _try_bind(requested):
            return requested
        raise PortConflictError(f"Der angeforderte Port {requested} ist bereits belegt.")
    return find_free_port()


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


async def run_server(timeout_minutes: int, port: int) -> None:
    timeout_seconds = timeout_minutes * 60
    controller = IdleShutdownController(timeout_seconds)

    from .app import create_app

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the YouTube Intake Service.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_MINUTES,
        help=f"Auto-shutdown timeout in Minuten ({MIN_TIMEOUT_MINUTES}-{MAX_TIMEOUT_MINUTES}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            f"Konkreten Port erzwingen ({MIN_PORT}-{MAX_PORT}); "
            f"ueberschreibt den Standardbereich {PORT_RANGE_START}-{PORT_RANGE_END}."
        ),
    )
    return parser.parse_args()


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
        port = resolve_port(args.port)
    except PortConflictError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        print(
            f"Hinweis: Standard-Portbereich ist {PORT_RANGE_START}-{PORT_RANGE_END}. "
            f"Mit --port <n> einen freien Port ({MIN_PORT}-{MAX_PORT}) erzwingen.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        asyncio.run(run_server(timeout_minutes, port))
    except KeyboardInterrupt:
        logger.info("Beendet durch Benutzer (Strg+C).")
