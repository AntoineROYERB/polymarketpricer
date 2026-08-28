"""Rate limiting that survives FastAPI's router-inclusion internals.

slowapi's own ``SlowAPIMiddleware`` discovers the matching route by walking
``app.routes`` and reading ``route.endpoint``. Since FastAPI 0.13x, routes added
through ``include_router`` are represented by a single ``_IncludedRouter`` object
that exposes no ``endpoint`` attribute, so the lookup returns ``None`` — and
slowapi treats "no handler" as "exempt". The result is silent: ``/health`` and
``/docs`` stay limited while every ``/api/v1/*`` route is waved through.

The limiter keys its buckets on the request path by default (``key_style="url"``),
so the handler is not actually needed to enforce a global default limit. This
middleware therefore performs the check with the path alone.
"""

from collections.abc import Awaitable, Callable

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

EXEMPT_PATHS = frozenset({"/health"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        limiter: Limiter = request.app.state.limiter
        if not limiter.enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        try:
            limiter._check_request_limit(request, None, True)
        except RateLimitExceeded as exc:
            return _rate_limit_exceeded_handler(request, exc)

        response = await call_next(request)
        view_limit = getattr(request.state, "view_rate_limit", None)
        if view_limit is not None:
            response = limiter._inject_headers(response, view_limit)
        return response
