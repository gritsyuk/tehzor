"""MCP-сервер Tehzor: `pip install "tehzor[mcp]"`, запуск `tehzor-mcp`."""

from .config import Settings
from .server import create_server

__all__ = ["Settings", "create_server"]
