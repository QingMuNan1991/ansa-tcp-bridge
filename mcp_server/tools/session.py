"""Session & File I/O tools (9 tools)."""
from __future__ import annotations
import json
from mcp_server.ansi_scripts import (
    snippet_open_model, snippet_new_model, snippet_save_model,
    snippet_export_solver, snippet_run_python, to_json,
)
from mcp_server.bridge_client import AnsaBridge


def register(mcp, bridge: AnsaBridge) -> None:
    @mcp.tool()
    def ping_ansa() -> str:
        """Check that ANSA is reachable; returns connection info."""
        try:
            payload = bridge.ping()
            payload["server_version"] = "0.1.0"
            return to_json({"ok": True, "data": payload})
        except Exception as exc:
            return to_json({"ok": False, "error": repr(exc),
                            "error_type": type(exc).__name__})

    @mcp.tool()
    def open_model(filepath: str) -> str:
        """Open a model file (.ansa, .bdf, .key, .inp, ...)."""
        script = snippet_open_model(filepath)
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def new_model() -> str:
        """Clear the current model."""
        script = snippet_new_model()
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def save_model() -> str:
        """Save the current model in place."""
        script = snippet_save_model(None, None, silent=True)
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def save_model_as(filepath: str) -> str:
        """Save the current model to a new .ansa file."""
        script = snippet_save_model(filepath, None, silent=True)
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def export_nastran(filepath: str) -> str:
        """Export as Nastran .bdf file."""
        script = snippet_export_solver("NASTRAN", filepath, "all", {})
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def export_lsdyna(filepath: str) -> str:
        """Export as LS-DYNA .key file."""
        script = snippet_export_solver("LSDYNA", filepath, "all", {})
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def export_step(filepath: str) -> str:
        """Export geometry as .stp file."""
        script = snippet_export_solver("STEP", filepath, "all", {})
        return to_json(bridge.run_script(script, function_name="main"))

    @mcp.tool()
    def run_python_script_in_ansa(script: str, function_name: str = "main") -> str:
        """Run an arbitrary Python script inside the live ANSA session.

        The script must define a function with the given name (default
        ``main``) returning a dict. Available globals: ansa, base, mesh,
        connections, constants, guitk.
        """
        runnable = snippet_run_python(script, function_name)
        return to_json(bridge.run_script(runnable, function_name="main"))
