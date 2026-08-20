"""HTTP 401 OAuth challenges for protected MCP tool calls."""

from __future__ import annotations

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.mcp_auth_middleware import AUTH_OPTIONAL_TOOLS
from src.core.oauth_service import get_mcp_oauth_issuer


class MCPOAuthChallengeMiddleware:
    """Return MCP OAuth discovery challenges before FastMCP handles missing auth."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        body, replay_receive = await _buffer_request_body(receive)
        if _is_unauthenticated_protected_tool_call(scope, body):
            await _send_oauth_challenge(send)
            return

        await self.app(scope, replay_receive, send)


async def _buffer_request_body(receive: Receive) -> tuple[bytes, Receive]:
    messages: list[Message] = []
    body_parts: list[bytes] = []

    while True:
        message = await receive()
        messages.append(message)
        if message["type"] == "http.request":
            body_parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        else:
            break

    async def replay_receive() -> Message:
        if messages:
            return messages.pop(0)
        return await receive()

    return b"".join(body_parts), replay_receive


def _is_unauthenticated_protected_tool_call(scope: Scope, body: bytes) -> bool:
    if _has_auth_header(scope):
        return False

    tool_name = _extract_tool_name(body)
    return tool_name is not None and tool_name not in AUTH_OPTIONAL_TOOLS


def _has_auth_header(scope: Scope) -> bool:
    headers = {name.decode("latin-1").lower(): value.decode("latin-1") for name, value in scope.get("headers", [])}
    if headers.get("x-adcp-auth"):
        return True
    authorization = headers.get("authorization") or ""
    return authorization.lower().startswith("bearer ") and bool(authorization[7:].strip())


def _extract_tool_name(body: bytes) -> str | None:
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict) or payload.get("method") != "tools/call":
        return None
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    return name if isinstance(name, str) else None


async def _send_oauth_challenge(send: Send) -> None:
    metadata_url = f"{get_mcp_oauth_issuer()}/.well-known/oauth-protected-resource"
    body = json.dumps({"error": "authorization_required"}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"www-authenticate", f'Bearer resource_metadata="{metadata_url}"'.encode("latin-1")),
    ]
    await send({"type": "http.response.start", "status": 401, "headers": headers})
    await send({"type": "http.response.body", "body": body})