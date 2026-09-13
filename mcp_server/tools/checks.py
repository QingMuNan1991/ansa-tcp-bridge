"""Quality & geometry checks (9 tools)."""
from __future__ import annotations
import textwrap
from mcp_server.ansi_scripts import wrap_main, to_json
from mcp_server.bridge_client import AnsaBridge


def _check_intersections(fast: bool) -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\n\n"
        "def main():\n"
        "    try:\n"
        f"        fn = base.CheckIntersections if not {fast} else getattr(base, 'CheckIntersectionsFast', base.CheckIntersections)\n"
        "        res = fn()\n"
        "        if isinstance(res, dict):\n"
        "            data = res\n"
        "        else:\n"
        "            data = {'count': int(res) if res is not None else 0}\n"
        "        return {'ok': 'true', 'fast': '" + ("true" if fast else "false") + "', 'result': json.dumps(data)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _check_penetrations(auto_fix: bool) -> str:
    body = f"""
    res = None
    try:
        res = base.CheckPenetrations(auto_fix={auto_fix})
    except Exception:
        try:
            res = base.CheckPenetrations()
        except Exception as exc:
            result['error'] = repr(exc)
            result['ok'] = 'false'
            res = None
    if isinstance(res, dict):
        result['result'] = json.dumps(res)
    elif res is not None:
        result['count'] = int(res)
    result['auto_fix'] = '{str(auto_fix).lower()}'
    """
    return wrap_main(body)


def _check_free_nodes() -> str:
    body = """
    try:
        res = base.CheckFreeNodes() if hasattr(base, 'CheckFreeNodes') else None
    except Exception as exc:
        result['error'] = repr(exc)
        result['ok'] = 'false'
        res = None
    if isinstance(res, dict):
        result['result'] = json.dumps(res)
    elif res is not None:
        result['free_count'] = len(res) if hasattr(res, '__len__') else int(res)
        try:
            result['ids'] = json.dumps(list(res)[:200])
        except Exception:
            pass
    """
    return wrap_main(body)


def _run_quality_check(name: str, deck: int) -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    name = '{name}'\n"
        "    try:\n"
        "        fn = getattr(base, 'RunQualityCheck', None)\n"
        "        if fn is None:\n"
        "            fn = getattr(base, 'QualityCheck', None)\n"
        "        if fn is None:\n"
        "            return {'ok': 'false', 'error': 'no quality check API available'}\n"
        "        res = fn(deck, name)\n"
        "        return {'ok': 'true', 'check': name, 'deck': str(deck), 'result': json.dumps(res, default=str)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _count_failed_elements(deck: int, entity_type: str) -> str:
    return (
        "import ansa\nfrom ansa import base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    type_value = constants.{entity_type.upper()} if hasattr(constants, '{entity_type.upper()}') else None\n"
        "    if type_value is None:\n"
        "        return {'ok': 'false', 'error': 'unknown entity type: " + entity_type + "'}\n"
        "    try:\n"
        "        failed = base.GetFailedEntitiesCount(deck, type_value) if hasattr(base, 'GetFailedEntitiesCount') else 0\n"
        "        return {'ok': 'true', 'deck': str(deck), 'type': '" + entity_type + "', 'failed_count': int(failed)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _check_geometry(deck: int) -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        "    try:\n"
        "        res = base.CheckGeometry(deck) if hasattr(base, 'CheckGeometry') else None\n"
        "        return {'ok': 'true', 'deck': str(deck), 'result': json.dumps(res, default=str)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _check_sharp_edges(angle: float, deck: int) -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    angle = float({angle})\n"
        "    try:\n"
        "        fn = getattr(base, 'CheckSharpEdges', None)\n"
        "        if fn is None:\n"
        "            return {'ok': 'false', 'error': 'CheckSharpEdges not available'}\n"
        "        res = fn(deck, angle)\n"
        "        return {'ok': 'true', 'deck': str(deck), 'angle': str(angle), 'result': json.dumps(res, default=str)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _check_rigid_dependencies() -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\n\n"
        "def main():\n"
        "    try:\n"
        "        res = base.CheckRigidDependencies() if hasattr(base, 'CheckRigidDependencies') else None\n"
        "        return {'ok': 'true', 'result': json.dumps(res, default=str)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _calc_mesh_quality(deck: int, entity_type: str) -> str:
    return (
        "import ansa\nfrom ansa import base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    type_value = constants.{entity_type.upper()} if hasattr(constants, '{entity_type.upper()}') else None\n"
        "    if type_value is None:\n"
        "        return {'ok': 'false', 'error': 'unknown entity type: " + entity_type + "'}\n"
        "    out = {}\n"
        "    for metric in ['Skewness', 'Warping', 'AspectRatio', 'MinAngle', 'MaxAngle', 'Jacobian', 'Taper']:\n"
        "        fn = getattr(base, f'Calc{metric}', None)\n"
        "        if fn is None: continue\n"
        "        try:\n"
        "            v = fn(deck, type_value)\n"
        "            if v is not None:\n"
        "                out[metric] = v\n"
        "        except Exception:\n"
        "            pass\n"
        "    return {'ok': 'true', 'deck': str(deck), 'type': '" + entity_type + "', 'metrics': json.dumps(out, default=str)}\n"
    )


def register(mcp, bridge: AnsaBridge) -> None:
    @mcp.tool()
    def check_intersections(fast: bool = False) -> str:
        """Detect intersecting shell surfaces."""
        return to_json(bridge.run_script(
            _check_intersections(fast), function_name="main"))

    @mcp.tool()
    def check_penetrations(auto_fix: bool = False) -> str:
        """Detect (and optionally fix) shell penetrations."""
        return to_json(bridge.run_script(
            _check_penetrations(auto_fix), function_name="main"))

    @mcp.tool()
    def check_free_nodes() -> str:
        """Find free nodes and free edges."""
        return to_json(bridge.run_script(
            _check_free_nodes(), function_name="main"))

    @mcp.tool()
    def run_quality_check(check_name: str, deck: int) -> str:
        """Run a named quality check (e.g. 'Warping')."""
        return to_json(bridge.run_script(
            _run_quality_check(check_name, deck), function_name="main"))

    @mcp.tool()
    def count_failed_elements(deck: int, entity_type: str) -> str:
        """Count elements failing quality criteria."""
        return to_json(bridge.run_script(
            _count_failed_elements(deck, entity_type), function_name="main"))

    @mcp.tool()
    def check_geometry(deck: int) -> str:
        """Check CAD face geometry."""
        return to_json(bridge.run_script(
            _check_geometry(deck), function_name="main"))

    @mcp.tool()
    def check_sharp_edges(angle: float, deck: int) -> str:
        """Detect sharp edges above the given angle (degrees)."""
        return to_json(bridge.run_script(
            _check_sharp_edges(angle, deck), function_name="main"))

    @mcp.tool()
    def check_rigid_dependencies() -> str:
        """Check RBE rigid body dependency issues."""
        return to_json(bridge.run_script(
            _check_rigid_dependencies(), function_name="main"))

    @mcp.tool()
    def calc_mesh_quality(deck: int, entity_type: str) -> str:
        """Aggregate skewness/warping/aspect-ratio/etc. for the type."""
        return to_json(bridge.run_script(
            _calc_mesh_quality(deck, entity_type), function_name="main"))
