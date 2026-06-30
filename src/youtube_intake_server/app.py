"""FastAPI-App: Routen /health und /process. Importiert den Core fuer die Logik."""

import asyncio
import logging
import time

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from youtube_intake_core import (
    ERROR_INVALID_URL,
    ERROR_PROCESSING_FAILED,
    ERROR_VIDEO_UNAVAILABLE,
    IntakeError,
    error_payload,
    process,
)

from .daemon import IdleShutdownController

logger = logging.getLogger(__name__)

# error_code -> HTTP-Status (heutiges Mapping, Wire-Form unveraendert).
HTTP_STATUS_BY_ERROR_CODE = {
    ERROR_INVALID_URL: 400,
    ERROR_VIDEO_UNAVAILABLE: 404,
    ERROR_PROCESSING_FAILED: 500,
}


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
    async def process_endpoint(
        url: str = Query(..., description="YouTube URL"),
        language: str = Query("de", min_length=2, max_length=10),
    ):
        try:
            _t0 = time.monotonic()
            result = await asyncio.to_thread(process, url, language)
            logger.debug("process %.2fs %s", time.monotonic() - _t0, url)
        except IntakeError as exc:
            status_code = HTTP_STATUS_BY_ERROR_CODE.get(exc.error_code, 500)
            if status_code >= 500:
                logger.exception("Verarbeitung fehlgeschlagen")
            return JSONResponse(
                status_code=status_code,
                content=error_payload(exc.error_code, exc.message),
            )
        except Exception as exc:
            logger.exception("Verarbeitung fehlgeschlagen")
            return JSONResponse(
                status_code=500,
                content=error_payload(ERROR_PROCESSING_FAILED, f"Verarbeitung fehlgeschlagen: {exc}"),
            )
        return result

    return app
