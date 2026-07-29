"""DaVinci Resolve MCP server entry point (stdio transport)."""

import logging

from mcp.server.fastmcp import FastMCP

from resolve.config import load_config
from resolve.errors import ResolveError
from tools.context import Services, register

logging.basicConfig(
    level=load_config().log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("davinci-mcp")


def create_server(services: Services | None = None) -> FastMCP:
    """Build the MCP server; dependency injection keeps it testable without Resolve."""
    mcp = FastMCP(
        "DaVinci Resolve",
        instructions=(
            "Inspect and control DaVinci Resolve Studio using only Blackmagic's official "
            "scripting API. Timeline clips use 1-based track_index and item_index addresses. "
            "Call connect_to_resolve first and inspect before mutating."
        ),
    )
    register(mcp, services or Services.build())
    return mcp


def main() -> None:
    try:
        create_server().run(transport="stdio")
    except ResolveError as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
