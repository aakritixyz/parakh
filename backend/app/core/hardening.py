"""Bounded, process-local rate limits and request/security-header enforcement."""
from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from starlette.responses import JSONResponse

from app.core.config import get_settings


class RequestHardening:
    def __init__(self, app):
        self.app = app
        self.windows = OrderedDict()
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = get_settings()
        headers = dict(scope.get("headers", []))
        limit = settings.max_upload_bytes + 1024 * 1024
        raw_length = headers.get(b"content-length", b"0")
        try:
            length = int(raw_length)
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
        if length < 0 or length > limit:
            return await JSONResponse({"detail": "Request exceeds upload limit"}, 413)(scope, receive, send)
        path = scope["path"]
        if path.startswith("/api/"):
            now = monotonic()
            client = scope.get("client") or ("unknown", 0)
            key = (client[0], "auth" if "/auth/login" in path else "api")
            capacity = 20 if key[1] == "auth" else 600
            with self.lock:
                window = self.windows.setdefault(key, deque())
                while window and window[0] <= now - 60:
                    window.popleft()
                blocked = len(window) >= capacity
                if not blocked:
                    window.append(now)
                self.windows.move_to_end(key)
                while len(self.windows) > 10000:
                    self.windows.popitem(last=False)
            if blocked:
                return await JSONResponse({"detail": "Rate limit reached; retry in 60 seconds"}, 429, headers={"Retry-After": "60"})(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    from starlette.exceptions import HTTPException
                    raise HTTPException(413, "Request exceeds upload limit")
            return message

        async def secure_send(message):
            if message["type"] == "http.response.start":
                extra = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                         (b"referrer-policy", b"no-referrer"), (b"cache-control", b"no-store"),
                         (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                         (b"content-security-policy", b"default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'")]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)
        await self.app(scope, bounded_receive, secure_send)
