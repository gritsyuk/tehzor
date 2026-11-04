"""Запуск MCP-сервера: `tehzor-mcp` (stdio) или `tehzor-mcp --transport http`.

HTTP (streamable-http) требует токен: TEHZOR_MCP_HTTP_TOKEN — клиент передаёт `Authorization: Bearer <токен>`.
Без токена HTTP запускается только с явным --insecure-no-auth и только на 127.0.0.1.
"""

from __future__ import annotations

import argparse
import hmac
import logging
import os
import sys
from typing import Any

from .config import Settings
from .server import create_server


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tehzor-mcp", description="MCP-сервер Tehzor для LLM-агентов")
    p.add_argument("--transport", choices=["stdio", "http"], default=os.environ.get("TEHZOR_MCP_TRANSPORT", "stdio"))
    p.add_argument("--host", default=os.environ.get("TEHZOR_MCP_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("TEHZOR_MCP_PORT", "8000")))
    p.add_argument("--path", default=os.environ.get("TEHZOR_MCP_PATH", "/mcp"))
    p.add_argument(
        "--insecure-no-auth", action="store_true", help="HTTP без токена (только для локальной отладки на 127.0.0.1)"
    )
    p.add_argument("--log-level", default=os.environ.get("TEHZOR_MCP_LOG_LEVEL", "WARNING"))
    return p


class BearerAuth:
    """ASGI-проверка `Authorization: Bearer <токен>` для HTTP-транспорта."""

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.token = token.encode()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"")
            if not (auth.startswith(b"Bearer ") and hmac.compare_digest(auth[7:], self.token)):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")],
                    }
                )
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    # stdout занят протоколом stdio — логи только в stderr
    logging.basicConfig(
        level=args.log_level.upper(), stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings.from_env()
    if args.transport == "stdio":
        create_server(settings).run("stdio")
        return

    token = os.environ.get("TEHZOR_MCP_HTTP_TOKEN")
    if not token:
        if not args.insecure_no_auth or args.host not in ("127.0.0.1", "localhost", "::1"):
            sys.exit(
                "tehzor-mcp: для HTTP задайте TEHZOR_MCP_HTTP_TOKEN "
                "(без токена — только --insecure-no-auth на 127.0.0.1)"
            )
    import uvicorn

    server = create_server(settings, host=args.host, port=args.port, streamable_http_path=args.path)
    app: Any = server.streamable_http_app()
    if token:
        app = BearerAuth(app, token)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
