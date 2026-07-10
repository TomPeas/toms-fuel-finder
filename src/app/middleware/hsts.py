from collections.abc import Awaitable, Callable

from fastapi import Request, Response


async def hsts_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add HSTS so browsers stick to HTTPS. Registered in main.py."""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains"
    )
    return response
