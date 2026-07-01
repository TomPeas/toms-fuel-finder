"""Application logging setup.

Control verbosity with the LOG_LEVEL env var (DEBUG | INFO | WARNING | ERROR);
defaults to INFO. At DEBUG you also see every outbound HTTP request, via the
httpx event hooks below.

Usage in code — log under the app namespace so LOG_LEVEL applies:

    from logging_config import get_logger
    logger = get_logger(__name__)
    logger.debug(...) / logger.info(...) / logger.warning(...) / logger.error(...)
"""

import logging
import os
from collections.abc import Callable
from typing import Any

from httpx import Request, Response

logger = logging.getLogger("fuel_finder")


def get_logger(name: str) -> logging.Logger:
    """Return a child of the app logger so it honours LOG_LEVEL."""
    return logger.getChild(name)


class _HealthCheckFilter(logging.Filter):
    """Drop uvicorn access-log lines for health-check probes (Fly pings /readyz
    every interval, which otherwise floods the logs)."""

    _PATHS = ("/readyz", "/livez", "/health")

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(path in message for path in self._PATHS)


def configure_logging() -> None:
    """Configure logging. Call once at application startup.

    Third-party libraries stay at WARNING (so the HTTP/2 stack — httpx, h2,
    hpack — doesn't flood DEBUG). Only our own ``fuel_finder`` logger honours
    LOG_LEVEL, so DEBUG shows just our requests and batching info.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=logging.WARNING,  # baseline for third-party libraries
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        force=True,  # take effect even if uvicorn already configured logging
    )
    logger.setLevel(level)  # our app logger only
    # quieten the access log for health-check probes
    logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())


def _log_response_line(response: Response) -> None:
    """Log a response: errors (>=400) at WARNING so they're always visible,
    successful responses at DEBUG."""
    request = response.request
    if response.status_code >= 400:
        logger.warning(
            "HTTP %s on %s %s", response.status_code, request.method, request.url
        )
    else:
        logger.debug("← %s %s %s", response.status_code, request.method, request.url)


async def _log_request(request: Request) -> None:
    logger.debug("→ %s %s", request.method, request.url)


async def _log_response(response: Response) -> None:
    _log_response_line(response)


def _sync_log_request(request: Request) -> None:
    logger.debug("→ %s %s", request.method, request.url)


def _sync_log_response(response: Response) -> None:
    _log_response_line(response)


# For AsyncClient(event_hooks=HTTPX_EVENT_HOOKS) — logs every request at DEBUG and
# every error response at WARNING.
HTTPX_EVENT_HOOKS: dict[str, list[Callable[..., Any]]] = {
    "request": [_log_request],
    "response": [_log_response],
}

# Same, for the synchronous httpx.Client (e.g. the postcode lookup).
SYNC_HTTPX_EVENT_HOOKS: dict[str, list[Callable[..., Any]]] = {
    "request": [_sync_log_request],
    "response": [_sync_log_response],
}
