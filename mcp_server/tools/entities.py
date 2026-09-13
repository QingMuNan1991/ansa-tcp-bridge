"""Entity queries & edits tools (19 tools).

All tools operate on a (deck, entity_type, entity_ids) triple and call
the corresponding ANSA API inside the live session.
"""
from __future__ import annotations
import json
import textwrap
from mcp_server.ansi_scripts import (
    wrap_main, _resolve_entity_type, to_json,
)
from mcp_server.bridge_client import AnsaBridge


VALID_OPS = {
    "count", "list", "get", "set", "create", "delete", "search",
    "bbox", "get_node_coords", "change_type", "create_part",
    "create_set", "add_to_set", "summary", "includes",
    "calc_mass", "calc_shell_area", "calc_solid_volume",
}


def _op_snippet(op: str, **kwargs) -> str:
    """Dispatch to the right ANSA-side snippet builder."""
    if op == "count":
        return _snippet_count(kwargs["deck"], kwargs["entity_type"])
    if op == "list":
        return _snippet_list(kwargs["deck"], kwargs["entity_type"],
                             kwargs.get("fields"), kwargs.get("limit", 100))
    if op == "get":
        return _snippet_get(kwargs["deck"], kwargs["entity_type"],
                            kwargs["entity_id"], kwargs.get("fields"))
    if op == "set":
        return _snippet_set(kwargs["deck"], kwargs["entity_type"],
                            kwargs["entity_id"], kwargs["fields"])
    if op == "create":
        return _snippet_create(kwargs["deck"], kwargs["entity_type"],
                               kwargs["fields"])
    if op == "delete":
        return _snippet_delete(kwargs["deck"], kwargs["entity_type"],
                               kwargs["entity_ids"])
    if op == "search":
        return _snippet_search(kwargs["deck"], kwargs["pattern"])
    if op == "bbox":
        return _snippet_bbox(kwargs["deck"], kwargs["entity_type"])
    if op == "get_node_coords":
        return _snippet_node_coords(kwargs["node_ids"])
    if op == "change_type":
        return _snippet_change_type(kwargs["deck"], kwargs["entity_type"],
                                    kwargs["entity_ids"], kwargs["new_type"])
    if op == "create_part":
        return _snippet_create_part(kwargs["name"])
    if op == "create_set":
        return _snippet_create_set(kwargs["deck"], kwargs["name"])
    if op == "add_to_set":
        return _snippet_add_to_set(kwargs["deck"], kwargs["set_id"],
                                   kwargs["entity_type"], kwargs["entity_ids"])
    if op == "summary":
        return _snippet_summary(kwargs["deck"])
    if op == "includes":
        return _snippet_includes(kwargs["deck"])
    if op == "calc_mass":
        return _snippet_calc_mass(kwargs["deck"], kwargs["entity_type"],
                                  kwargs.get("entity_ids"))
    if op == "calc_shell_area":
        return _snippet_calc_shell_area(kwargs["deck"], kwargs["element_id"])
    if op == "calc_solid_volume":
        return _snippet_calc_solid_volume(kwargs["deck"], kwargs["element_id"])
    raise ValueError(f"unknown op {op!r}")


# ---------------------------------------------------------------------------
# Snippet builders
# ---------------------------------------------------------------------------
def _snippet_count(deck, entity_type):
    # base.GetEntityCount does not exist in ANSA 25 - count the collect list.
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    deck = base.CurrentDeck() if {deck} < 0 else {deck}
    result['deck'] = str(deck)
    result['type'] = '{entity_type}'
    result['count'] = _count(deck, type_value)
    """
    return wrap_main(body)


def _snippet_list(deck, entity_type, fields, limit):
    # CollectEntities() takes only (deck, container, type, flag) - there is no
    # `fields` argument. Field values must be read per-entity afterwards via
    # GetEntityCardValues(deck, entity, fields).
    fields_repr = repr(list(fields)) if fields else "None"
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    deck = base.CurrentDeck() if {deck} < 0 else {deck}
    ents = base.CollectEntities(deck, None, type_value, False) or []
    result['deck'] = str(deck)
    result['type'] = '{entity_type}'
    result['count'] = len(ents)
    wanted = {fields_repr}
    rows = {{}}
    for _i, _e in enumerate(ents[:{limit}]):
        _row = {{'_id': str(getattr(_e, '_id', _i))}}
        if wanted:
            try:
                _vals = base.GetEntityCardValues(deck, _e, wanted)
                if isinstance(_vals, dict):
                    _row.update({{k: str(v) for k, v in _vals.items()}})
            except Exception as _exc:
                _row['_error'] = repr(_exc)
        rows[str(_i)] = _row
    result['returned'] = len(rows)
    result['entities'] = json.dumps(rows)
    """
    return wrap_main(body)


def _snippet_get(deck, entity_type, entity_id, fields):
    # GetEntity() has no `fields` kwarg in ANSA 25 - fetch the entity, then
    # read its field values explicitly.
    fields_repr = repr(list(fields)) if fields else "None"
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    deck = base.CurrentDeck() if {deck} < 0 else {deck}
    ent = base.GetEntity(deck, type_value, {entity_id})
    result['deck'] = str(deck)
    result['type'] = '{entity_type}'
    result['entity_id'] = '{entity_id}'
    if ent is None:
        result['found'] = False
    else:
        result['found'] = True
        wanted = {fields_repr}
        row = {{}}
        if wanted:
            try:
                vals = base.GetEntityCardValues(deck, ent, wanted)
                if isinstance(vals, dict):
                    row.update({{k: str(v) for k, v in vals.items()}})
            except Exception as exc:
                row['_error'] = repr(exc)
        result['entity'] = json.dumps(row)
    """
    return wrap_main(body)


def _snippet_set(deck, entity_type, entity_id, fields):
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    if type_value is None:
        result['error'] = 'unknown entity_type: {entity_type}'
        result['ok'] = 'false'
    else:
        ok = base.SetEntityFields({deck}, type_value, {entity_id}, {repr(fields)})
        result['deck'] = '{deck}'
        result['type'] = '{entity_type}'
        result['entity_id'] = {entity_id}
        result['updated'] = bool(ok)
    """
    return wrap_main(body)


def _snippet_create(deck, entity_type, fields):
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    if type_value is None:
        result['error'] = 'unknown entity_type: {entity_type}'
        result['ok'] = 'false'
    else:
        new_id = base.CreateEntity({deck}, type_value, {repr(fields)})
        result['deck'] = '{deck}'
        result['type'] = '{entity_type}'
        result['entity_id'] = new_id
        result['created'] = (new_id is not None and new_id > 0)
    """
    return wrap_main(body)


def _snippet_delete(deck, entity_type, entity_ids):
    ids_repr = list(entity_ids)
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    if type_value is None:
        result['error'] = 'unknown entity_type: {entity_type}'
        result['ok'] = 'false'
    else:
        deleted = 0
        for eid in {ids_repr}:
            try:
                if base.DeleteEntity({deck}, type_value, eid):
                    deleted += 1
            except Exception:
                pass
        result['deck'] = '{deck}'
        result['type'] = '{entity_type}'
        result['requested'] = len({ids_repr})
        result['deleted'] = deleted
    """
    return wrap_main(body)


def _snippet_search(deck, pattern):
    body = f"""
    # ANSA search_entities_by_name (deck, pattern, entity_type) returns list
    try:
        ents = base.SearchEntityByName({deck}, r'''{pattern}''', None)
        if not isinstance(ents, list):
            ents = list(ents) if ents else []
        result['deck'] = '{deck}'
        result['pattern'] = r'''{pattern}'''
        result['count'] = len(ents)
        result['matches'] = json.dumps(ents[:200])
    except Exception as exc:
        result['error'] = repr(exc)
        result['ok'] = 'false'
    """
    return wrap_main(body)


def _snippet_bbox(deck, entity_type):
    # ANSA 25 has no GetEntityBox/CalcBoundingBox, so derive the box from GRID
    # coordinates. IMPORTANT: only GRID entities may be queried for X/Y/Z -
    # calling GetEntityCardValues with unknown fields on hundreds of FACE
    # entities crashed ANSA outright, so never fall back to arbitrary types.
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    deck = base.CurrentDeck() if {deck} < 0 else {deck}
    ents = base.CollectEntities(deck, None, type_value, False) or []
    result['deck'] = str(deck)
    result['type'] = '{entity_type}'
    result['count'] = len(ents)
    nodes = base.CollectEntities(deck, None, 'GRID', False) or []
    if not nodes:
        nodes = base.CollectEntities(deck, None, 'NODE', False) or []
    result['nodes'] = len(nodes)
    xs = []
    ys = []
    zs = []
    for _n in nodes[:20000]:
        try:
            v = base.GetEntityCardValues(deck, _n, ['X', 'Y', 'Z'])
        except Exception:
            continue
        if isinstance(v, dict) and 'X' in v and 'Y' in v and 'Z' in v:
            try:
                xs.append(float(v['X']))
                ys.append(float(v['Y']))
                zs.append(float(v['Z']))
            except Exception:
                continue
    if xs:
        result['min'] = json.dumps([min(xs), min(ys), min(zs)])
        result['max'] = json.dumps([max(xs), max(ys), max(zs)])
        result['nodes_used'] = len(xs)
    else:
        result['ok'] = 'false'
        result['error'] = ('no GRID nodes with coordinates in this model; '
                           'the bounding box needs a mesh')
    """
    return wrap_main(body)


def _snippet_node_coords(node_ids):
    body = f"""
    coords = []
    deck = base.CurrentDeck()
    grid_const = 'GRID'
    for nid in {list(node_ids)}:
        try:
            ent = base.GetEntity(deck, grid_const, nid, ['X','Y','Z'])
            if isinstance(ent, dict):
                coords.append([float(ent.get('X', 0.0)),
                               float(ent.get('Y', 0.0)),
                               float(ent.get('Z', 0.0))])
            else:
                coords.append(None)
        except Exception:
            coords.append(None)
    result['nodes'] = json.dumps(coords)
    """
    return wrap_main(body)


def _snippet_change_type(deck, entity_type, entity_ids, new_type):
    body = f"""
    src = {_resolve_entity_type(entity_type)}
    dst = {_resolve_entity_type(new_type)}
    if src is None or dst is None:
        result['error'] = 'unknown entity type'
        result['ok'] = 'false'
    else:
        changed = 0
        for eid in {list(entity_ids)}:
            try:
                if base.ChangeElementType({deck}, src, dst, eid):
                    changed += 1
            except Exception:
                pass
        result['changed'] = changed
        result['requested'] = len({list(entity_ids)})
    """
    return wrap_main(body)


def _snippet_create_part(name):
    body = f"""
    try:
        pid = base.CreatePart(r'''{name}''')
        result['part_id'] = pid
        result['name'] = r'''{name}'''
        result['created'] = (pid is not None and pid > 0)
    except Exception as exc:
        result['error'] = repr(exc)
        result['ok'] = 'false'
    """
    return wrap_main(body)


def _snippet_create_set(deck, name):
    body = f"""
    try:
        sid = base.SetCreate({deck}, r'''{name}''')
        result['set_id'] = sid
        result['name'] = r'''{name}'''
        result['created'] = (sid is not None and sid > 0)
    except Exception as exc:
        result['error'] = repr(exc)
        result['ok'] = 'false'
    """
    return wrap_main(body)


def _snippet_add_to_set(deck, set_id, entity_type, entity_ids):
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    if type_value is None:
        result['error'] = 'unknown entity_type: {entity_type}'
        result['ok'] = 'false'
    else:
        added = 0
        for eid in {list(entity_ids)}:
            try:
                if base.SetAddEntity({deck}, {set_id}, type_value, eid):
                    added += 1
            except Exception:
                pass
        result['set_id'] = {set_id}
        result['added'] = added
        result['requested'] = len({list(entity_ids)})
    """
    return wrap_main(body)


def _snippet_summary(deck):
    # NOTE: the original version resolved entity types via
    # getattr(constants, t), but ANSA 25's `constants` module does not expose
    # SHELL/SOLID/... as attributes, so every type hit `continue` and the
    # tool always reported an empty model. CollectEntities() accepts the type
    # as a plain string, which is verified to work on 25.1.4.
    types = ['SHELL', 'SOLID', 'GRID', 'NODE', 'CBAR', 'CQUAD', 'CTRIA',
             'CTETRA', 'CHEXA', 'CPENTA', 'RBE2', 'RBE3', 'SET', 'PART',
             'MATERIAL', 'PROPERTY', 'INCLUDE', 'FACE', 'CONNECTION',
             'BOLT', 'GROUP']
    return (
        "import ansa\n"
        "from ansa import base\n"
        "import json\n\n"
        "def main():\n"
        "    deck = base.CurrentDeck() if " + str(deck) + " < 0 else " + str(deck) + "\n"
        "    types = " + repr(types) + "\n"
        "    out = {}\n"
        "    for t in types:\n"
        "        try:\n"
        "            ents = base.CollectEntities(deck, None, t, False) or []\n"
        "            out[t] = len(ents)\n"
        "        except Exception:\n"
        "            out[t] = -1\n"
        "    total = sum(v for v in out.values() if isinstance(v, int) and v > 0)\n"
        "    return {'ok': 'true', 'deck': str(deck), 'counts': json.dumps(out),"
        " 'total_entities': str(total)}\n"
    )


def _snippet_includes(deck):
    # ANSA 25 has no constants.INCLUDE (types are plain strings), and
    # CollectEntities takes only (deck, container, type, bool) - no fields.
    return (
        "import ansa\n"
        "from ansa import base\n"
        "import json\n\n"
        "def main():\n"
        "    deck = base.CurrentDeck() if " + str(deck) + " < 0 else " + str(deck) + "\n"
        "    try:\n"
        "        incs = base.CollectEntities(deck, None, 'INCLUDE', False) or []\n"
        "        rows = {}\n"
        "        for i, e in enumerate(incs):\n"
        "            row = {'_id': str(getattr(e, '_id', i))}\n"
        "            try:\n"
        "                v = base.GetEntityCardValues(deck, e, ['Name'])\n"
        "                if isinstance(v, dict) and 'Name' in v:\n"
        "                    row['Name'] = str(v['Name'])\n"
        "            except Exception:\n"
        "                pass\n"
        "            rows[str(i)] = row\n"
        "        return {'ok': 'true', 'deck': str(deck), 'includes': json.dumps(rows), 'count': str(len(rows))}\n"
        "    except Exception as exc:\n"
        "        return {'ok': 'false', 'error': repr(exc)}\n"
    )


def _snippet_calc_mass(deck, entity_type, entity_ids):
    ids_clause = (
        f"entity_ids = {list(entity_ids)}" if entity_ids else "entity_ids = None"
    )
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    if type_value is None:
        result['error'] = 'unknown entity_type: {entity_type}'
        result['ok'] = 'false'
    else:
        try:
            {ids_clause}
            per = []
            total = 0.0
            if entity_ids is not None:
                for eid in entity_ids:
                    m = base.CalcElementMass({deck}, type_value, eid) if hasattr(base, 'CalcElementMass') else 0.0
                    per.append({{'id': eid, 'mass': m}})
                    total += float(m)
            else:
                total = base.CalcMass({deck}, type_value) if hasattr(base, 'CalcMass') else 0.0
            result['total_mass'] = total
            if per:
                result['per_element'] = json.dumps(per)
        except Exception as exc:
            result['error'] = repr(exc)
            result['ok'] = 'false'
    """
    return wrap_main(body)


def _snippet_calc_shell_area(deck, element_id):
    body = f"""
    try:
        area = base.CalcShellArea({deck}, {element_id}) if hasattr(base, 'CalcShellArea') else 0.0
        result['element_id'] = {element_id}
        result['area'] = float(area)
    except Exception as exc:
        result['error'] = repr(exc)
        result['ok'] = 'false'
    """
    return wrap_main(body)


def _snippet_calc_solid_volume(deck, element_id):
    body = f"""
    try:
        vol = base.CalcSolidVolume({deck}, {element_id}) if hasattr(base, 'CalcSolidVolume') else 0.0
        result['element_id'] = {element_id}
        result['volume'] = float(vol)
    except Exception as exc:
        result['error'] = repr(exc)
        result['ok'] = 'false'
    """
    return wrap_main(body)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
def register(mcp, bridge: AnsaBridge) -> None:
    @mcp.tool()
    def count_entities(deck: int, entity_type: str) -> str:
        """Count entities of a given type on a deck."""
        return to_json(bridge.run_script(
            _op_snippet("count", deck=deck, entity_type=entity_type),
            function_name="main"))

    @mcp.tool()
    def list_entities(deck: int, entity_type: str, fields: list[str] | None = None,
                      limit: int = 100) -> str:
        """List entities with card field values."""
        return to_json(bridge.run_script(
            _op_snippet("list", deck=deck, entity_type=entity_type,
                        fields=fields, limit=limit),
            function_name="main"))

    @mcp.tool()
    def get_entity(deck: int, entity_type: str, entity_id: int,
                   fields: list[str] | None = None) -> str:
        """Fetch a single entity."""
        return to_json(bridge.run_script(
            _op_snippet("get", deck=deck, entity_type=entity_type,
                        entity_id=entity_id, fields=fields),
            function_name="main"))

    @mcp.tool()
    def set_entity_fields(deck: int, entity_type: str, entity_id: int,
                          fields: dict) -> str:
        """Write card field values on an existing entity."""
        return to_json(bridge.run_script(
            _op_snippet("set", deck=deck, entity_type=entity_type,
                        entity_id=entity_id, fields=fields),
            function_name="main"))

    @mcp.tool()
    def create_entity(deck: int, entity_type: str, fields: dict) -> str:
        """Create a new entity with the given fields."""
        return to_json(bridge.run_script(
            _op_snippet("create", deck=deck, entity_type=entity_type, fields=fields),
            function_name="main"))

    @mcp.tool()
    def delete_entities(deck: int, entity_type: str, entity_ids: list[int]) -> str:
        """Delete multiple entities."""
        return to_json(bridge.run_script(
            _op_snippet("delete", deck=deck, entity_type=entity_type,
                        entity_ids=entity_ids),
            function_name="main"))

    @mcp.tool()
    def search_entities_by_name(deck: int, pattern: str) -> str:
        """Search entities by name (wildcards + regex)."""
        return to_json(bridge.run_script(
            _op_snippet("search", deck=deck, pattern=pattern),
            function_name="main"))

    @mcp.tool()
    def get_bounding_box(deck: int, entity_type: str) -> str:
        """Get the axis-aligned bounding box of all entities of a type."""
        return to_json(bridge.run_script(
            _op_snippet("bbox", deck=deck, entity_type=entity_type),
            function_name="main"))

    @mcp.tool()
    def get_node_coordinates(node_ids: list[int]) -> str:
        """Return X/Y/Z for a list of GRID IDs."""
        return to_json(bridge.run_script(
            _op_snippet("get_node_coords", node_ids=node_ids),
            function_name="main"))

    @mcp.tool()
    def change_element_type(deck: int, entity_type: str, entity_ids: list[int],
                            new_type: str) -> str:
        """Convert elements from one type to another."""
        return to_json(bridge.run_script(
            _op_snippet("change_type", deck=deck, entity_type=entity_type,
                        entity_ids=entity_ids, new_type=new_type),
            function_name="main"))

    @mcp.tool()
    def create_part(name: str) -> str:
        """Create a Model Browser part."""
        return to_json(bridge.run_script(
            _op_snippet("create_part", name=name),
            function_name="main"))

    @mcp.tool()
    def create_set(deck: int, name: str) -> str:
        """Create a named SET."""
        return to_json(bridge.run_script(
            _op_snippet("create_set", deck=deck, name=name),
            function_name="main"))

    @mcp.tool()
    def add_to_set(deck: int, set_id: int, entity_type: str,
                   entity_ids: list[int]) -> str:
        """Add entities to a SET."""
        return to_json(bridge.run_script(
            _op_snippet("add_to_set", deck=deck, set_id=set_id,
                        entity_type=entity_type, entity_ids=entity_ids),
            function_name="main"))

    @mcp.tool()
    def get_model_summary(deck: int = -1) -> str:
        """Return non-zero entity counts across ~50 common types."""
        return to_json(bridge.run_script(
            _op_snippet("summary", deck=deck),
            function_name="main"))

    @mcp.tool()
    def list_model_includes(deck: int) -> str:
        """List all INCLUDE files with IDs, names, child counts."""
        return to_json(bridge.run_script(
            _op_snippet("includes", deck=deck),
            function_name="main"))

    @mcp.tool()
    def calc_element_mass(deck: int, entity_type: str,
                          entity_ids: list[int] | None = None) -> str:
        """Total + per-element mass."""
        return to_json(bridge.run_script(
            _op_snippet("calc_mass", deck=deck, entity_type=entity_type,
                        entity_ids=entity_ids),
            function_name="main"))

    @mcp.tool()
    def calc_shell_area(deck: int, element_id: int) -> str:
        """Surface area of a shell element."""
        return to_json(bridge.run_script(
            _op_snippet("calc_shell_area", deck=deck, element_id=element_id),
            function_name="main"))

    @mcp.tool()
    def calc_solid_volume(deck: int, element_id: int) -> str:
        """Volume of a solid element."""
        return to_json(bridge.run_script(
            _op_snippet("calc_solid_volume", deck=deck, element_id=element_id),
            function_name="main"))
