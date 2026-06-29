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


async def _log_request(request: Request) -> None:
    logger.debug("→ %s %s", request.method, request.url)


async def _log_response(response: Response) -> None:
    request = response.request
    logger.debug("← %s %s %s", response.status_code, request.method, request.url)


# Pass to AsyncClient(event_hooks=HTTPX_EVENT_HOOKS) to log requests at DEBUG.
HTTPX_EVENT_HOOKS: dict[str, list[Callable[..., Any]]] = {
    "request": [_log_request],
    "response": [_log_response],
}
