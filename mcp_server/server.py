"""Main FastMCP server entry point for ansa-tcp-bridge."""
from __future__ import annotations

import argparse
import logging
import os
import sys

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]

from mcp_server import __version__
from mcp_server.bridge_client import AnsaBridge, get_default_bridge
from mcp_server.tools import register_all


def _build_mcp(bridge: AnsaBridge):
    if FastMCP is None:
        raise SystemExit(
            "The 'mcp' package is not installed. Run: pip install mcp[cli]"
        )
    mcp = FastMCP("ansa-tcp-bridge")
    register_all(mcp, bridge)
    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ansa-tcp-bridge",
        description="MCP server for BETA CAE Systems ANSA via IAPConnection (TCP)",
    )
    parser.add_argument(
        "--ansa-scripts",
        default=os.environ.get("ANSA_SCRIPTS_PATH"),
        help="Path to <ANSA_INSTALL>/scripts (env: ANSA_SCRIPTS_PATH)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("ANSA_HOST", "localhost"),
        help="Hostname where ANSA is listening (env: ANSA_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ANSA_PORT", "9999")),
        help="ANSA listener port (env: ANSA_PORT)",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse"),
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="MCP transport (env: MCP_TRANSPORT)",
    )
    parser.add_argument(
        "--sse-port",
        type=int,
        default=int(os.environ.get("MCP_SSE_PORT", "8000")),
        help="HTTP port for SSE transport (env: MCP_SSE_PORT)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (env: LOG_LEVEL)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("ansa-tcp-bridge")

    if not args.ansa_scripts:
        log.error(
            "ANSA_SCRIPTS_PATH is not set. Use --ansa-scripts or the "
            "ANSA_SCRIPTS_PATH env var (e.g. C:\\Program Files (x86)\\"
            "BETA_CAE_Systems\\ansa_v25.1.4\\scripts)."
        )
        return 2

    os.environ["ANSA_SCRIPTS_PATH"] = args.ansa_scripts
    os.environ["ANSA_HOST"] = args.host
    os.environ["ANSA_PORT"] = str(args.port)

    bridge = AnsaBridge(
        host=args.host,
        port=args.port,
    )
    mcp = _build_mcp(bridge)

    log.info(
        "ansa-tcp-bridge v%s starting (transport=%s, ANSA=%s:%d, scripts=%s)",
        __version__, args.transport, args.host, args.port, args.ansa_scripts,
    )

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.sse_port)
    else:
        mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
