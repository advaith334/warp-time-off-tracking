"""Logging and request correlation.

The system had one logger, two `logger.exception` calls and no configuration at
all, which meant those two calls emitted under uvicorn's default root handler
and nothing else was ever recorded. A scheduled accrual run that skipped an
employee left a `PARTIAL` row in the database and no line anywhere else.

Deliberately stdlib `dictConfig` rather than a structured-logging dependency:
what was missing here is configuration, not a formatter library. The request id
is carried in a `ContextVar` so it reaches log records emitted deep inside a
service without threading an argument through every call.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from logging.config import dictConfig

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

REQUEST_ID_HEADER = "X-Request-Id"
request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attaches the current request id to every record, including library ones."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adopts an inbound request id or mints one, and echoes it back.

    Adopting `X-Request-Id` rather than always minting means a trace started at
    a load balancer or by the frontend survives into these logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        token = request_id.set(incoming or uuid.uuid4().hex[:12])
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id.get()
            return response
        finally:
            request_id.reset(token)


def configure() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "filters": ["request_id"],
                }
            },
            # uvicorn configures its own loggers; leaving them to propagate here
            # would print every access line twice.
            "loggers": {"uvicorn.access": {"propagate": False}},
            "root": {"handlers": ["console"], "level": settings.log_level},
        }
    )
