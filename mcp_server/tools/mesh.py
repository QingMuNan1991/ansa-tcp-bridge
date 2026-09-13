"""Mesh tools (5 tools)."""
from __future__ import annotations
import json
from mcp_server.ansi_scripts import wrap_main, to_json
from mcp_server.bridge_client import AnsaBridge


def _mesh_shells(deck: int, entity_ids: list[int], length: float) -> str:
    return (
        "import ansa\nfrom ansa import mesh\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    entity_ids = {list(entity_ids)}\n"
        f"    length = float({length})\n"
        "    try:\n"
        "        before = mesh.CountShellElements(deck) if hasattr(mesh, 'CountShellElements') else 0\n"
        "        rc = mesh.MeshShell(deck, entity_ids, length) if hasattr(mesh, 'MeshShell') else mesh.GenerateShellMesh(deck, entity_ids, length)\n"
        "        after = mesh.CountShellElements(deck) if hasattr(mesh, 'CountShellElements') else 0\n"
        "        return {'ok': 'true', 'deck': str(deck), 'length': str(length), "
        "'shells_before': str(before), 'shells_after': str(after), 'added': str(max(0, after - before))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _mesh_volume(deck: int, entity_ids: list[int]) -> str:
    return (
        "import ansa\nfrom ansa import mesh\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    entity_ids = {list(entity_ids)}\n"
        "    try:\n"
        "        before = mesh.CountSolidElements(deck) if hasattr(mesh, 'CountSolidElements') else 0\n"
        "        rc = mesh.MeshVolume(deck, entity_ids) if hasattr(mesh, 'MeshVolume') else mesh.GenerateVolumeMesh(deck, entity_ids)\n"
        "        after = mesh.CountSolidElements(deck) if hasattr(mesh, 'CountSolidElements') else 0\n"
        "        return {'ok': 'true', 'deck': str(deck), 'solids_before': str(before), "
        "'solids_after': str(after), 'added': str(max(0, after - before))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _set_shell_mesh_params(deck: int, length: float) -> str:
    return (
        "import ansa\nfrom ansa import mesh, base\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    length = float({length})\n"
        "    try:\n"
        "        rc = mesh.SetShellMeshParams(deck, length) if hasattr(mesh, 'SetShellMeshParams') else mesh.SetMeshSize(deck, length)\n"
        "        return {'ok': 'true', 'deck': str(deck), 'length': str(length)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _delete_mesh(deck: int, entity_ids: list[int]) -> str:
    return (
        "import ansa\nfrom ansa import mesh\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    entity_ids = {list(entity_ids)}\n"
        "    try:\n"
        "        rc = mesh.DeleteMesh(deck, entity_ids) if hasattr(mesh, 'DeleteMesh') else mesh.EraseMesh(deck, entity_ids)\n"
        "        return {'ok': 'true', 'deck': str(deck), 'deleted': str(len(entity_ids))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _run_batch_mesh(script_path: str) -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\nimport os\n\n"
        "def main():\n"
        f"    script_path = r'''{script_path}'''\n"
        "    if not os.path.isfile(script_path):\n"
        "        return {'ok': 'false', 'error': 'script not found: ' + script_path}\n"
        "    try:\n"
        "        with open(script_path, 'r', encoding='utf-8') as f:\n"
        "            src = f.read()\n"
        "        g = {'__name__': '__batch__', 'base': base, 'mesh': __import__('ansa.mesh', fromlist=['mesh'])}\n"
        "        exec(compile(src, script_path, 'exec'), g)\n"
        "        if 'main' in g and callable(g['main']):\n"
        "            ret = g['main']()\n"
        "            if isinstance(ret, dict):\n"
        "                ret = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in ret.items()}\n"
        "                return ret\n"
        "        return {'ok': 'true', 'script': script_path}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def register(mcp, bridge: AnsaBridge) -> None:
    @mcp.tool()
    def mesh_shells(deck: int, entity_ids: list[int], length: float) -> str:
        """Generate shell mesh on selected faces."""
        return to_json(bridge.run_script(
            _mesh_shells(deck, entity_ids, length), function_name="main"))

    @mcp.tool()
    def mesh_volume(deck: int, entity_ids: list[int]) -> str:
        """Generate volume mesh."""
        return to_json(bridge.run_script(
            _mesh_volume(deck, entity_ids), function_name="main"))

    @mcp.tool()
    def set_shell_mesh_params(deck: int, length: float) -> str:
        """Configure global shell mesh parameters."""
        return to_json(bridge.run_script(
            _set_shell_mesh_params(deck, length), function_name="main"))

    @mcp.tool()
    def delete_mesh(deck: int, entity_ids: list[int]) -> str:
        """Delete mesh from selected faces."""
        return to_json(bridge.run_script(
            _delete_mesh(deck, entity_ids), function_name="main"))

    @mcp.tool()
    def run_batch_mesh(script_path: str) -> str:
        """Run a batch mesh script (Python file)."""
        return to_json(bridge.run_script(
            _run_batch_mesh(script_path), function_name="main"))
