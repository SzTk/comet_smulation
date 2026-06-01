from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.core.config import settings


class EmailAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.auth_enabled:
            return await call_next(request)

        email = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "")
        if not email or email not in settings.allowed_emails:
            return Response("Forbidden", status_code=403)

        return await call_next(request)
