"""Connections tools (3 tools) - bolts, spot welds, rivets, seams."""
from __future__ import annotations
import json
from mcp_server.ansi_scripts import wrap_main, to_json
from mcp_server.bridge_client import AnsaBridge


def _apply_connectors(deck: int) -> str:
    # NOTE: base.GetEntityCount does not exist in ANSA 25 and
    # constants.CONNECTION does not exist either - count via CollectEntities.
    return (
        "import ansa\nfrom ansa import connections, base\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        "    def _n():\n"
        "        return len(base.CollectEntities(deck, None, 'CONNECTION', False) or [])\n"
        "    try:\n"
        "        before = _n()\n"
        "        rc = connections.ApplyConnectors(deck) if hasattr(connections, 'ApplyConnectors') else connections.RealizeConnectors(deck)\n"
        "        after = _n()\n"
        "        return {'ok': 'true', 'deck': str(deck),\n"
        "                'connections_before': str(before), 'connections_after': str(after),\n"
        "                'realized': str(max(0, after - before))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _check_connections(deck: int) -> str:
    return (
        "import ansa\nfrom ansa import connections, base, constants\nimport json\n\n"
        "def main():\n"
        f"    deck = {deck}\n"
        "    try:\n"
        "        fn = getattr(connections, 'CheckConnectors', None) or getattr(connections, 'ValidateConnectors', None)\n"
        "        if fn is None:\n"
        "            return {'ok': 'false', 'error': 'no check API on connections module'}\n"
        "        res = fn(deck)\n"
        "        return {'ok': 'true', 'deck': str(deck), 'result': json.dumps(res, default=str)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _list_connectors(deck: int) -> str:
    # CollectEntities takes only (deck, container, type, bool); read fields
    # per entity with GetEntityCardValues(deck, entity, fields).
    return (
        "import ansa\nfrom ansa import connections, base\nimport json\n\n"
        "def main():\n"
        "    deck = base.CurrentDeck() if " + str(deck) + " < 0 else " + str(deck) + "\n"
        "    try:\n"
        "        conns = base.CollectEntities(deck, None, 'CONNECTION', False) or []\n"
        "        rows = {}\n"
        "        for i, e in enumerate(conns[:200]):\n"
        "            row = {'_id': str(getattr(e, '_id', i))}\n"
        "            try:\n"
        "                v = base.GetEntityCardValues(deck, e, ['Name', 'Type'])\n"
        "                if isinstance(v, dict):\n"
        "                    row.update({k: str(x) for k, x in v.items()})\n"
        "            except Exception:\n"
        "                pass\n"
        "            rows[str(i)] = row\n"
        "        return {'ok': 'true', 'deck': str(deck), 'count': str(len(conns)),\n"
        "                'connectors': json.dumps(rows)}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def register(mcp, bridge: AnsaBridge) -> None:
    @mcp.tool()
    def apply_connectors(deck: int) -> str:
        """Realize all CONNECTION entities (spot welds, bolts, ...)."""
        return to_json(bridge.run_script(
            _apply_connectors(deck), function_name="main"))

    @mcp.tool()
    def check_connections(deck: int) -> str:
        """Validate realized connections."""
        return to_json(bridge.run_script(
            _check_connections(deck), function_name="main"))

    @mcp.tool()
    def list_connectors(deck: int) -> str:
        """List all CONNECTION entities (id, name, type)."""
        return to_json(bridge.run_script(
            _list_connectors(deck), function_name="main"))
