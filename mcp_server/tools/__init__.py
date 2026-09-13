"""Tools package: registers all tool modules on the FastMCP instance."""
from mcp_server.tools import (
    session, entities, checks, mesh, connections, visibility,
)


def register_all(mcp, bridge) -> None:
    session.register(mcp, bridge)
    entities.register(mcp, bridge)
    checks.register(mcp, bridge)
    mesh.register(mcp, bridge)
    connections.register(mcp, bridge)
    visibility.register(mcp, bridge)
