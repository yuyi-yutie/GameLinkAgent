"""Local-only access guards for the web server.

Binding to 127.0.0.1 is necessary but not sufficient: any page in any browser can
reach a loopback server, and a hostile DNS name can be pointed at 127.0.0.1. So we
also pin the ``Host`` header (blocks DNS rebinding) and reject mutating requests
whose browser-supplied ``Origin``/``Referer`` is not loopback (blocks CSRF).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "testserver"})
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

READABLE_SUFFIXES = frozenset(
    {".yaml", ".yml", ".md", ".json", ".gd", ".tscn", ".tres", ".txt", ".cfg"}
)


def hostname(value: str) -> str:
    """Strip the port (and IPv6 brackets) from a host or netloc string."""
    text = value.strip().lower()
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end != -1 else text
    return text.rsplit(":", 1)[0] if ":" in text else text


def is_loopback(value: str) -> bool:
    if not value:
        return False
    return hostname(urlsplit(value).netloc or value) in ALLOWED_HOSTS


class LocalOnlyMiddleware:
    """Pure-ASGI guard, so streamed responses are never buffered."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        host = hostname(headers.get("host", ""))
        if host and host not in ALLOWED_HOSTS:
            await JSONResponse(
                {"error": f"host not allowed: {host}"}, status_code=403
            )(scope, receive, send)
            return

        if scope["method"] in MUTATING_METHODS:
            for name in ("origin", "referer"):
                value = headers.get(name)
                if value and not is_loopback(value):
                    await JSONResponse(
                        {"error": "cross-origin request rejected"}, status_code=403
                    )(scope, receive, send)
                    return

        await self.app(scope, receive, send)


def resolve_in_workspace(workspace: Path, raw: str) -> Path:
    """Resolve ``raw`` against ``workspace`` and refuse anything that escapes it."""
    target = Path(raw)
    if not target.is_absolute():
        target = workspace / target
    resolved = target.resolve()
    root = workspace.resolve()
    if resolved != root and root not in resolved.parents:
        raise PermissionError(f"path outside the workspace: {resolved}")
    return resolved


def check_readable(path: Path) -> None:
    if path.suffix.lower() not in READABLE_SUFFIXES:
        raise PermissionError(f"refusing to read {path.suffix or 'extensionless'} file")
