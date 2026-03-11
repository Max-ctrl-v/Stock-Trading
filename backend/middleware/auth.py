"""JWT auth middleware — protects all /api/ routes except /api/auth/login."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.services.auth import decode_token

# Routes that don't require auth
PUBLIC_PATHS = {"/api/auth/login", "/", "/api/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths, static assets, and non-API routes
        if path in PUBLIC_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid authorization header"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        payload = decode_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # Attach user info to request state
        request.state.user = payload.get("sub", "")
        return await call_next(request)
