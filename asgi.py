"""Combined ASGI app: FastAPI + MCP Streamable HTTP on a single port.

Routes:
  /mcp/  -> MCP server (Streamable HTTP, API key auth)
  /      -> FastAPI app
"""

import contextlib
import logging
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labs_mcp.server import mcp as mcp_server

logger = logging.getLogger(__name__)

session_manager = StreamableHTTPSessionManager(
    app=mcp_server._mcp_server,
    json_response=False,
    stateless=True,
)

_allowed_keys: set[str] | None = None


def _get_allowed_keys() -> set[str]:
    global _allowed_keys
    if _allowed_keys is None:
        raw = os.environ.get("LABS_MCP_API_KEYS", "")
        _allowed_keys = {k.strip() for k in raw.split(",") if k.strip()}
    return _allowed_keys


class MCPWithAuth:
    """ASGI middleware that validates API key before delegating to MCP."""

    async def __call__(
        self, scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        if scope["type"] != "http":
            return

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        api_key = (
            auth.removeprefix("Bearer ").strip()
            if auth.startswith("Bearer ")
            else ""
        )

        allowed = _get_allowed_keys()

        if not allowed:
            logger.warning("LABS_MCP_API_KEYS not set — MCP is open")
        elif not api_key or api_key not in allowed:
            response = JSONResponse(
                {"error": "Invalid or missing API key"}, status_code=401
            )
            await response(scope, receive, send)
            return

        await session_manager.handle_request(scope, receive, send)


mcp_app = MCPWithAuth()


def create_asgi_app() -> Starlette:
    from app.main import app as fastapi_app

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    routes = [
        Mount("/mcp", app=mcp_app),
        Mount("/", app=fastapi_app),
    ]

    return Starlette(routes=routes, lifespan=lifespan)


app = create_asgi_app()
