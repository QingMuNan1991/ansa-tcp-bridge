# -*- coding: utf-8 -*-
"""Middle-surface (cast) task on casting.ansa — user specification:

  1. remove LOGOS before casting
  2. minimum solid thickness for the middle surface = 1.0 mm
  3. target element length                          = 3.0 mm
  4. model: casting.ansa

API notes (checked against the ANSA 25 API docs, not guessed):
  * base.RemoveLogosAutomatic(height, size, source_faces)
      height = max logo height, size = max logo size (mm).
      The official doc example is RemoveLogosAutomatic(1, 5).
      It returns 1 on success - it does NOT report how many logos it removed,
      so we measure the effect via the FACE count.
  * base.MidSurfAuto(...) takes KEYWORD ARGUMENTS ONLY.
      Its first positional parameter is `thick` (a float), NOT the face list -
      which is exactly why passing faces positionally raised
      "TypeError: must be real number, not list".
      thick  = minimum thickness of the solid(s)      -> 1.0 mm (req. 2)
      length = target element length, MUST be > thick -> 3.0 mm (req. 3)

Run with --dry-run to print + compile-check the generated ANSA script without
touching ANSA (protects against the details=3 / script_not_loaded trap).
"""
import os
import socket
import subprocess
import sys
import time

os.environ.setdefault(
    "ANSA_SCRIPTS_PATH",
    r"D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\scripts",
)
sys.path.insert(0, r"D:\ansa-tcp-bridge")
from mcp_server.bridge_client import AnsaBridge   # noqa: E402

PORT = 9999
WORK = r"D:\ansa-tcp-bridge"
BAT = r"D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\ansa64.bat"

MODEL = (r"J:\1_CAE_guide\1. ANSA\ANSA_META_ V24_Documentation_CN"
         r"\ANSA_Documentation_v24.0.0_CN\tutorials\meshing"
         r"\middle_surface_extraction\tutorial_files\casting.ansa")
OUT_MODEL = os.path.join(WORK, "output", "casting_midsurface.ansa")

THICK_MIN = 1.0        # requirement 2: minimum solid thickness (mm)
ELEM_SIZE = 3.0        # requirement 3: target element length (mm)
LOGO_HEIGHT = 5.0      # requirement 1: max logo height recognised (mm)
LOGO_SIZE = 20.0       # requirement 1: max logo size   recognised (mm)
# Measured on casting.ansa by probe_logo_steps.py (FACE sweep, start = 632):
#   (0.5,  2) -> 632   nothing
#   (1.0,  5) -> 632   nothing  <-- the ANSA doc example value: too tight here
#   (2.0, 10) -> 609   removes 23 faces
#   (5.0, 20) -> 576   removes the remaining 33  <- use this
#   (10 , 50) -> 576   nothing left
# i.e. all logos in this model are <= 5 mm high and <= 20 mm in size.


def say(*a):
    print(" ".join(str(x) for x in a), flush=True)


def port_up():
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("localhost", PORT)) == 0


SCRIPT_TEMPLATE = r'''
def main():
    import os
    from ansa import base
    out = {}

    ok = base.Open(r"__MODEL__")
    out['model_opened'] = str(ok)
    deck = base.CurrentDeck()

    faces_before = base.CollectEntities(deck, None, 'FACE', False) or []
    out['faces_before'] = str(len(faces_before))

    # ---- requirement 1: remove logos BEFORE casting ------------------------
    out['has_RemoveLogosAutomatic'] = str(hasattr(base, 'RemoveLogosAutomatic'))
    if hasattr(base, 'RemoveLogosAutomatic'):
        try:
            rc = base.RemoveLogosAutomatic(__LOGO_HEIGHT__, __LOGO_SIZE__,
                                           source_faces=faces_before)
            out['remove_logos'] = 'rc=%s (returns 1 on success)' % rc
        except Exception as exc:
            out['remove_logos'] = 'FAILED: %s' % repr(exc)[:200]
            try:
                rc = base.RemoveLogosAutomatic(__LOGO_HEIGHT__, __LOGO_SIZE__)
                out['remove_logos_retry'] = 'rc=%s' % rc
            except Exception as exc2:
                out['remove_logos_retry'] = 'FAILED: %s' % repr(exc2)[:200]

    faces_after = base.CollectEntities(deck, None, 'FACE', False) or []
    out['faces_after_logo_removal'] = str(len(faces_after))

    # ---- requirements 2+3: cast with thick=1mm, length=3mm -----------------
    kwargs = dict(
        thick=__THICK__,
        length=__ELEM__,
        elem_type=3,
        exact_middle=True,
        connect_weldings=True,
        collapse_ribs_height=100,
        collapse_ribs_height_as_percentage=True,
        part='auto_create',
        property='use_existing',
        get_result_type=True,
        ret_ents=True,
    )
    try:
        res = base.MidSurfAuto(faces=faces_after, **kwargs)
        out['casting_mode'] = 'faces=explicit list (%d)' % len(faces_after)
    except Exception as exc:
        out['casting_err_with_faces'] = repr(exc)[:200]
        res = base.MidSurfAuto(**kwargs)
        out['casting_mode'] = 'faces omitted -> whole database'

    shells = base.CollectEntities(deck, None, 'SHELL', False) or []
    out['shells_out'] = str(len(shells))
    try:
        out['result_type'] = str(getattr(res, 'type', None))[:500]
    except Exception:
        pass

    # ---- save the resulting database --------------------------------------
    out_path = r"__OUT__"
    try:
        d = os.path.dirname(out_path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
    except Exception:
        pass
    for fn_name in ('SaveAs', 'Save'):
        fn = getattr(base, fn_name, None)
        if fn is None:
            continue
        try:
            fn(out_path)
            out['saved_to'] = '%s (%s)' % (out_path, fn_name)
            break
        except Exception as exc:
            out['save_err_' + fn_name] = repr(exc)[:150]
    return out
'''


def build_script() -> str:
    return (SCRIPT_TEMPLATE
            .replace("__MODEL__", MODEL)
            .replace("__OUT__", OUT_MODEL)
            .replace("__LOGO_HEIGHT__", repr(float(LOGO_HEIGHT)))
            .replace("__LOGO_SIZE__", repr(float(LOGO_SIZE)))
            .replace("__THICK__", repr(float(THICK_MIN)))
            .replace("__ELEM__", repr(float(ELEM_SIZE))))


if "--dry-run" in sys.argv:
    _s = build_script()
    say(_s)
    try:
        compile(_s, "<gen>", "exec")
        say(">>> COMPILE OK")
    except SyntaxError as exc:
        say(">>> COMPILE FAIL:", exc.lineno, exc.msg)
    sys.exit(0)


say("=" * 72)
say("MIDDLE SURFACE TASK on casting.ansa")
say("  remove logos   : yes (height<=%gmm, size<=%gmm)"
    % (LOGO_HEIGHT, LOGO_SIZE))
say("  min thickness  : %g mm" % THICK_MIN)
say("  element length : %g mm" % ELEM_SIZE)
say("  output         : %s" % OUT_MODEL)
say("=" * 72)

# --- 1. clean slate ---------------------------------------------------------
subprocess.run(["taskkill", "/F", "/T", "/IM", "ansa_win64.exe"],
               capture_output=True, timeout=25)
for _ in range(30):
    if not port_up():
        break
    time.sleep(1)
say("[1] port free:", not port_up())

# --- 2. launch listener (same path as ansa_listener.bat) --------------------
os.makedirs(os.path.join(WORK, "diag_out"), exist_ok=True)
os.environ["PWD"] = WORK
start_cmd = ('start "ANSA listener :%d" /min "%s" '
             '-nolauncher -listenport %d -foregr -b' % (PORT, BAT, PORT))
subprocess.Popen("cmd /c " + start_cmd, shell=True, cwd=WORK,
                 stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for i in range(60):
    if port_up():
        say("[2] listener UP after %ds" % i)
        break
    time.sleep(1)
else:
    say("[2] FAILED: port never opened")
    sys.exit(1)

# --- 3. run the task --------------------------------------------------------
b = AnsaBridge(host="localhost", port=PORT, connect_timeout=60, call_timeout=900)
t0 = time.time()
say("[3] ping ->", b.ping(), "(%.1fs)" % (time.time() - t0))

say("[4] open -> remove logos -> MidSurfAuto(thick=%g, length=%g) -> save ..."
    % (THICK_MIN, ELEM_SIZE))
t0 = time.time()
try:
    resp = b.run_script(build_script(), "main",
                        pre_execution_database_action="keep")
    say("    finished in %.1fs" % (time.time() - t0))
    result = (resp or {}).get("result", resp)
    if isinstance(result, dict):
        for k in sorted(result):
            say("    %-28s = %s" % (k, result[k]))
    else:
        say("    raw:", result)
except Exception as exc:
    say("[4] FAILED after %.1fs:" % (time.time() - t0), repr(exc))

try:
    b.close()
except Exception:
    pass
say("\nDONE")
