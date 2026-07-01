"""YouTube Intake Server — FastAPI-App und Daemon-Mechanik.

Importiert den Core (youtube_intake_core); der Core importiert niemals den Server.
"""

from .app import create_app
from .daemon import (
    DEFAULT_TIMEOUT_MINUTES,
    PORT_RANGE_END,
    PORT_RANGE_START,
    IdleShutdownController,
    PortConflictError,
    find_free_port,
    main,
    remove_service_info,
    resolve_port,
    run_server,
    validate_timeout,
    write_service_info,
)

__all__ = [
    "create_app",
    "main",
    "run_server",
    "find_free_port",
    "resolve_port",
    "validate_timeout",
    "write_service_info",
    "remove_service_info",
    "IdleShutdownController",
    "PortConflictError",
    "PORT_RANGE_START",
    "PORT_RANGE_END",
    "DEFAULT_TIMEOUT_MINUTES",
]
