"""Viewport visibility tools (5 tools)."""
from __future__ import annotations
import json
from mcp_server.ansi_scripts import wrap_main, to_json
from mcp_server.bridge_client import AnsaBridge


def _show_only(deck: int, entity_type: str, entity_ids: list[int]) -> str:
    return (
        "import ansa\nfrom ansa import base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    type_value = constants.{entity_type.upper()} if hasattr(constants, '{entity_type.upper()}') else None\n"
        f"    entity_ids = {list(entity_ids)}\n"
        "    try:\n"
        "        rc = base.SetVisibility(deck, type_value, entity_ids, mode='only') if hasattr(base, 'SetVisibility') else None\n"
        "        if rc is None:\n"
        "            # fallback: hide all then show requested\n"
        "            base.HideAll(deck)\n"
        "            base.Show(deck, type_value, entity_ids)\n"
        "        return {'ok': 'true', 'deck': str(deck), 'type': '" + entity_type + "', 'shown': str(len(entity_ids))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _show_also(deck: int, entity_type: str, entity_ids: list[int]) -> str:
    return (
        "import ansa\nfrom ansa import base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    type_value = constants.{entity_type.upper()} if hasattr(constants, '{entity_type.upper()}') else None\n"
        f"    entity_ids = {list(entity_ids)}\n"
        "    try:\n"
        "        base.Show(deck, type_value, entity_ids) if hasattr(base, 'Show') else None\n"
        "        return {'ok': 'true', 'deck': str(deck), 'type': '" + entity_type + "', 'shown': str(len(entity_ids))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _hide(deck: int, entity_type: str, entity_ids: list[int]) -> str:
    return (
        "import ansa\nfrom ansa import base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    type_value = constants.{entity_type.upper()} if hasattr(constants, '{entity_type.upper()}') else None\n"
        f"    entity_ids = {list(entity_ids)}\n"
        "    try:\n"
        "        base.Hide(deck, type_value, entity_ids) if hasattr(base, 'Hide') else None\n"
        "        return {'ok': 'true', 'deck': str(deck), 'type': '" + entity_type + "', 'hidden': str(len(entity_ids))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _near(radius: float, deck: int, entity_type: str, entity_ids: list[int]) -> str:
    return (
        "import ansa\nfrom ansa import base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        f"    radius = float({radius})\n"
        f"    type_value = constants.{entity_type.upper()} if hasattr(constants, '{entity_type.upper()}') else None\n"
        f"    seed_ids = {list(entity_ids)}\n"
        "    try:\n"
        "        fn = getattr(base, 'SelectNear', None) or getattr(base, 'SelectEntitiesNear', None)\n"
        "        if fn is None:\n"
        "            return {'ok': 'false', 'error': 'no SelectNear API'}\n"
        "        ids = fn(deck, type_value, seed_ids, radius)\n"
        "        if not isinstance(ids, (list, tuple)):\n"
        "            ids = list(ids) if ids else []\n"
        "        return {'ok': 'true', 'deck': str(deck), 'radius': str(radius),\n"
        "                'seed_count': str(len(seed_ids)), 'found_count': str(len(ids)),\n"
        "                'found_ids': json.dumps(ids[:200])}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _neighb(steps: int) -> str:
    return (
        "import ansa\nfrom ansa import base\nimport json\n\n"
        "def main():\n"
        f"    steps = int({steps})\n"
        "    try:\n"
        "        fn = getattr(base, 'SelectNeighb', None) or getattr(base, 'ExpandSelectionByConnectivity', None)\n"
        "        if fn is None:\n"
        "            return {'ok': 'false', 'error': 'no SelectNeighb API'}\n"
        "        ids = fn(steps)\n"
        "        if not isinstance(ids, (list, tuple)):\n"
        "            ids = list(ids) if ids else []\n"
        "        return {'ok': 'true', 'steps': str(steps), 'count': str(len(ids)),\n"
        "                'ids': json.dumps(ids[:500])}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def register(mcp, bridge: AnsaBridge) -> None:
    @mcp.tool()
    def show_only(deck: int, entity_type: str, entity_ids: list[int]) -> str:
        """Isolate - show ONLY these entities (hide everything else)."""
        return to_json(bridge.run_script(
            _show_only(deck, entity_type, entity_ids), function_name="main"))

    @mcp.tool()
    def show_also(deck: int, entity_type: str, entity_ids: list[int]) -> str:
        """Add to visible set without hiding others."""
        return to_json(bridge.run_script(
            _show_also(deck, entity_type, entity_ids), function_name="main"))

    @mcp.tool()
    def hide(deck: int, entity_type: str, entity_ids: list[int]) -> str:
        """Hide specific entities."""
        return to_json(bridge.run_script(
            _hide(deck, entity_type, entity_ids), function_name="main"))

    @mcp.tool()
    def near(radius: float, deck: int, entity_type: str,
             entity_ids: list[int]) -> str:
        """Expand visible set to all within radius (mm)."""
        return to_json(bridge.run_script(
            _near(radius, deck, entity_type, entity_ids), function_name="main"))

    @mcp.tool()
    def neighb(steps: int) -> str:
        """Expand visible set by N connected-neighbour hops."""
        return to_json(bridge.run_script(
            _neighb(steps), function_name="main"))
