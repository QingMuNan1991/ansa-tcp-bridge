"""Generators for the Python snippets that are executed inside ANSA.

Every tool in :mod:`mcp_server.tools` builds a small Python script here and
sends it to the live ANSA session over IAP.

Three ANSA 25.1.4 facts that this module is built around (all verified by
probing a live session - see ``probe_constants.py``):

1. ``from ansa import ansa_class`` does **not** exist. Importing it makes ANSA
   reject the whole script with ``script_execution_details == 0x03``.
2. ``ansa.constants`` exposes **no entity-type attributes** - there is no
   ``constants.FACE``/``constants.SHELL``/... (it only has solver names and
   PART field keys). Entity types must be passed as plain **strings**
   (``base.CollectEntities(deck, None, "FACE", False)``).
3. ``base.GetEntityCount`` and ``base.New`` do **not** exist. Count via
   ``len(base.CollectEntities(...))`` and clear the DB via ``base.Clear()``.
"""
from __future__ import annotations

import json
import textwrap

# Entity-type name -> ANSA entity-type string. ANSA 25 resolves types by name,
# so the mapping is essentially identity but is kept for the few aliases.
ENTITY_TYPE_MAP = {
    "SHELL": "SHELL",
    "SOLID": "SOLID",
    "GRID": "GRID",
    "CBAR": "CBAR",
    "CQUAD": "CQUAD",
    "CTRIA": "CTRIA",
    "CTETRA": "CTETRA",
    "CHEXA": "CHEXA",
    "CPENTA": "CPENTA",
    "RBE2": "RBE2",
    "RBE3": "RBE3",
    "SET": "SET",
    "PART": "PART",
    "MATERIAL": "MATERIAL",
    "PROPERTY": "PROPERTY",
    "INCLUDE": "INCLUDE",
    "FACE": "FACE",
    "SOLID_ENTITY": "SOLID_ENTITY",
    "CONNECTION": "CONNECTION",
    "BOLT": "BOLT",
    "SPOTWELD": "SPOTWELD",
    "RIVET": "RIVET",
    "SEAM": "SEAM",
    "NODE": "NODE",
    "ELEMENT": "ELEMENT",
    "MASS": "MASS",
    "CMASS": "CMASS",
    "PLOT": "PLOT",
}

# Solver name -> the ANSA output function that writes it. ANSA has no generic
# "OutputSolver"; each deck has its own ``base.Output<Deck>`` function.
SOLVER_OUTPUT_FN = {
    "NASTRAN": "OutputNastran",
    "LSDYNA": "OutputLSDyna",
    "DYNA": "OutputLSDyna",
    "ANSYS": "OutputAnsys",
    "ABAQUS": "OutputAbaqus",
    "RADIOSS": "OutputRadioss",
    "PAMCRASH": "OutputPamCrash",
    "OPTISTRUCT": "OutputOptistruct",
    "PERMAS": "OutputPermas",
    "MARC": "OutputMarc",
    "CGNS": "OutputCGNS",
    "FLUENT": "OutputFluent",
    "OPENFOAM": "OutputOpenFoam",
    "STARCCM": "OutputStarCCM",
    # geometry / neutral formats
    "STEP": "SaveFileAsStep",
    "IGES": "SaveFileAsIges",
    "JT": "SaveFileAsJT",
    "VDA": "SaveFileAsVda",
    "STL": "OutputStereoLithography",
    "VRML": "OutputVrml",
    "UNIVERSAL": "OutputUniversal",
    "GEOM": "OutputGEOM",
}


def to_json(obj) -> str:
    """JSON-encode a tool result (never raises on exotic objects)."""
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _resolve_entity_type(name: str) -> str:
    """Return the ANSA-side *expression* for an entity-type name.

    Returns a quoted string literal (e.g. ``"'FACE'"``) because ANSA 25
    accepts entity types as strings and has no ``constants.FACE``.
    """
    if not name:
        return "None"
    if name.startswith(("'", '"')):
        return name  # already a literal expression
    key = name.upper().replace(" ", "_")
    return repr(ENTITY_TYPE_MAP.get(key, key))


def wrap_main(body: str, imports: list[str] | None = None) -> str:
    """Wrap a snippet body in a ``def main():`` returning a string dict.

    The body should populate a local ``result`` dict.

    Indentation is normalised here: the body is dedented to column 0 and then
    re-indented by 16 spaces so that it lands *inside* the ``try:`` block.
    Getting this wrong produces an IndentationError, which ANSA reports as
    ``script_execution_details == 0x03`` (script_not_loaded) - a very
    misleading error, so this function is covered by ``check_snippets.py``.
    """
    prelude_lines = [
        "import ansa",
        "from ansa import base",
        "from ansa import mesh",
        "from ansa import connections",
        "from ansa import constants",
        "from ansa import guitk",
        "import json",
        "import traceback",
        # helpers available to every generated snippet
        "def _count(deck, type_name):",
        "    try:",
        "        return len(base.CollectEntities(deck, None, type_name, False) or [])",
        "    except Exception:",
        "        return 0",
        "def _collect(deck, type_name, fields=None):",
        "    try:",
        "        return base.CollectEntities(deck, None, type_name, fields, False) or []",
        "    except Exception:",
        "        try:",
        "            return base.CollectEntities(deck, None, type_name, False) or []",
        "        except Exception:",
        "            return []",
    ]
    if imports:
        prelude_lines.extend(imports)
    # The prelude must be indented as a WHOLE block: if only its first line
    # carries the template's leading spaces, textwrap.dedent sees a common
    # prefix of "" and strips nothing, leaving the whole template indented.
    prelude = textwrap.indent("\n".join(prelude_lines), " " * 8)
    body = textwrap.indent(textwrap.dedent(body), " " * 16)
    return textwrap.dedent(
        f"""
{prelude}


        def main():
            result = {{}}
            try:
{body}
                if 'ok' not in result:
                    result['ok'] = 'true'
            except Exception as exc:
                import traceback
                result = {{
                    'ok': 'false',
                    'error': repr(exc),
                    'traceback': traceback.format_exc(),
                }}
            # Coerce all values to strings (IAP string_dict requirement)
            return {{k: (v if isinstance(v, str) else str(v)) for k, v in result.items()}}
        """
    ).strip() + "\n"


# ---------------------------------------------------------------------------
# Session / file I/O snippets
# ---------------------------------------------------------------------------
def snippet_open_model(filepath: str) -> str:
    body = f"""
    rc = base.Open(r'''{filepath}''')
    result['opened'] = (rc == 0)
    result['return_code'] = rc
    result['path'] = r'''{filepath}'''
    if rc != 0:
        result['ok'] = 'false'
    """
    return wrap_main(body)


def snippet_new_model() -> str:
    # base.New() does not exist in ANSA 25; base.Clear() empties the DB.
    body = """
    cleared = False
    err = ''
    for _fn_name in ('Clear', 'New'):
        _fn = getattr(base, _fn_name, None)
        if _fn is None:
            continue
        try:
            _rc = _fn()
            cleared = (_rc is None or _rc == 0)
            if cleared:
                break
        except Exception as exc:
            err = repr(exc)
    result['cleared'] = cleared
    if err:
        result['error'] = err
    if not cleared:
        result['ok'] = 'false'
    """
    return wrap_main(body)


def snippet_save_model(path: str | None, version: str | None,
                       silent: bool) -> str:
    body_lines = ["result['saved'] = False"]
    if path:
        body_lines.append(f"rc = base.SaveAs(r'''{path}''')")
        body_lines.append("result['saved'] = (rc == 0)")
        body_lines.append("result['return_code'] = rc")
        body_lines.append(f"result['path'] = r'''{path}'''")
    else:
        body_lines.append("rc = base.Save()")
        body_lines.append("result['saved'] = (rc == 0)")
        body_lines.append("result['return_code'] = rc")
    if version:
        body_lines.append(f"result['version'] = '{version}'")
    body_lines.append("if not result['saved']:")
    body_lines.append("    result['ok'] = 'false'")
    # Every line needs the SAME indentation or dedent's common-prefix calc
    # breaks and the generated code ends up with mixed indentation.
    body = "\n".join("    " + line for line in body_lines)
    return wrap_main(body)


def snippet_export_solver(solver: str, path: str, scope: str = "all",
                          options: dict | None = None) -> str:
    key = str(solver).upper().replace(" ", "")
    fn_name = SOLVER_OUTPUT_FN.get(key, "Output" + str(solver).capitalize())
    body = f"""
    fn = getattr(base, '{fn_name}', None)
    if fn is None:
        result['ok'] = 'false'
        result['error'] = 'no ANSA output function for solver {solver}'
        result['tried'] = 'base.{fn_name}'
    else:
        rc = None
        last_err = ''
        # Signature varies between ANSA builds; try the common shapes.
        for args in ((r'''{path}''',), (base.CurrentDeck(), r'''{path}''')):
            try:
                rc = fn(*args)
                break
            except Exception as exc:
                last_err = repr(exc)
                continue
        result['solver'] = '{solver}'
        result['function'] = 'base.{fn_name}'
        result['path'] = r'''{path}'''
        result['return_code'] = rc
        result['exported'] = (rc == 0 or rc is None)
        if rc is None and last_err:
            result['ok'] = 'false'
            result['error'] = last_err
    """
    return wrap_main(body)


def snippet_run_python(script: str, function_name: str | None) -> str:
    """Execute an arbitrary user-supplied Python function inside ANSA.

    The user script is ``exec``-ed in its own namespace and the named function
    is then called; its dict return value is forwarded as the result.
    """
    fn = function_name or "main"
    body = f"""
    user_src = {json.dumps(script)}
    exec_globals = {{'ansa': ansa, 'base': base, 'mesh': mesh,
                     'connections': connections, 'constants': constants,
                     'guitk': guitk, '__name__': '__user__'}}
    try:
        exec(compile(user_src, '<user_script>', 'exec'), exec_globals)
        fn_name = '{fn}'
        if fn_name in exec_globals and callable(exec_globals[fn_name]):
            ret = exec_globals[fn_name]()
            if isinstance(ret, dict):
                for k, v in ret.items():
                    if isinstance(v, str):
                        result[str(k)] = v
                    else:
                        try:
                            result[str(k)] = json.dumps(v)
                        except Exception:
                            result[str(k)] = str(v)
            elif ret is not None:
                result['return'] = json.dumps(ret) if not isinstance(ret, str) else ret
        else:
            result['error'] = 'function ' + fn_name + ' not defined in user script'
            result['ok'] = 'false'
    except Exception as exc:
        result['error'] = repr(exc)
        result['traceback'] = traceback.format_exc()
        result['ok'] = 'false'
    """
    return wrap_main(body)


# ---------------------------------------------------------------------------
# Query snippets
# ---------------------------------------------------------------------------
def snippet_count_entities(deck: int, entity_type: str) -> str:
    body = f"""
    type_value = {_resolve_entity_type(entity_type)}
    result['deck'] = '{deck}'
    result['type'] = '{entity_type}'
    result['count'] = _count({deck} if {deck} >= 0 else base.CurrentDeck(), type_value)
    """
    return wrap_main(body)


def snippet_get_model_summary(deck: int = -1) -> str:
    types = list(ENTITY_TYPE_MAP.keys())
    body = f"""
    deck = base.CurrentDeck() if {deck} < 0 else {deck}
    counts = {{}}
    for _t in {types!r}:
        counts[_t] = _count(deck, _t)
    result['deck'] = deck
    result['counts'] = json.dumps(counts)
    result['nonzero'] = json.dumps({{k: v for k, v in counts.items() if v > 0}})
    result['total_entities'] = sum(v for v in counts.values() if v > 0)
    """
    return wrap_main(body)
