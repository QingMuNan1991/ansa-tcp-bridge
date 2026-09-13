"""Bridge client wrapping ANSA's IAPConnection (TCP).

This client connects to ANSA running in listener mode (`-listenport 9999`),
handshakes via the IAP protocol, and executes Python scripts on the live
ANSA session. It reuses a single connection across calls and reconnects
automatically if dropped.

The actual IAP protocol implementation is imported from the user's ANSA
installation at ``$ANSA_SCRIPTS_PATH/RemoteControl/ansa/AnsaProcessModule.py``
so we always stay compatible with the user's ANSA version.
"""
from __future__ import annotations

import importlib
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

# ---- Lazy import of ANSA's IAPConnection ----
_IAP_MOD = None
_IAP_IMPORT_ERROR: Exception | None = None


def _load_iap_module():
    """Import AnsaProcessModule from the ANSA install (ANSA_SCRIPTS_PATH)."""
    global _IAP_MOD, _IAP_IMPORT_ERROR
    if _IAP_MOD is not None:
        return _IAP_MOD
    if _IAP_IMPORT_ERROR is not None:
        raise _IAP_IMPORT_ERROR

    scripts_path = os.environ.get("ANSA_SCRIPTS_PATH", "").strip()
    if not scripts_path:
        raise RuntimeError(
            "ANSA_SCRIPTS_PATH environment variable is not set. "
            "Point it to your <ANSA_INSTALL>/scripts directory."
        )
    rc_path = str(Path(scripts_path) / "RemoteControl")
    if rc_path not in sys.path:
        sys.path.insert(0, rc_path)
    try:
        _IAP_MOD = importlib.import_module("ansa.AnsaProcessModule")
    except Exception as exc:  # pragma: no cover
        _IAP_IMPORT_ERROR = exc
        raise RuntimeError(
            f"Failed to import AnsaProcessModule from {rc_path!r}: {exc}"
        ) from exc
    return _IAP_MOD


class AnsaBridge:
    """Reusable TCP bridge to ANSA in listener mode.

    Parameters
    ----------
    host : str
        Hostname where ANSA is listening. Default ``localhost``.
    port : int
        Port ANSA is listening on. Default ``9999``.
    connect_timeout : float
        Maximum seconds to wait for initial connection. Default ``30``.
    call_timeout : float
        Per-call timeout in seconds. Default ``300``.
    """

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 9999

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        connect_timeout: float = 30.0,
        call_timeout: float = 300.0,
    ) -> None:
        self.host = host or os.environ.get("ANSA_HOST", self.DEFAULT_HOST)
        self.port = int(port or os.environ.get("ANSA_PORT", self.DEFAULT_PORT))
        self.connect_timeout = float(connect_timeout)
        self.call_timeout = float(call_timeout)

        self._lock = threading.Lock()
        self._conn = None  # IAPConnection instance
        self._transaction_id = 0

    # ----- low-level connection management -----
    def _ensure_connected(self) -> None:
        if self._conn is not None:
            return
        iap = _load_iap_module()
        # IAPConnection(port) auto-connects with retry; but we want a deadline
        deadline = time.time() + self.connect_timeout
        last_err: Exception | None = None
        # Patch IAPConnection to honour deadline by passing our own loop
        # simplest: just call IAPConnection(port) and trust its internal retry
        try:
            self._conn = iap.IAPConnection(self.port)
            # IAPConnection leaves the socket with NO timeout, so any recv()
            # (e.g. hello()) blocks forever if ANSA stops answering. Apply the
            # call timeout so every read is bounded.
            self._conn.ansa_control.settimeout(self.call_timeout)
        except Exception as exc:
            last_err = exc
            if time.time() > deadline:
                raise ConnectionError(
                    f"Cannot connect to ANSA at {self.host}:{self.port}: {exc}"
                ) from exc
            # retry
            while time.time() < deadline:
                time.sleep(1.0)
                try:
                    self._conn = iap.IAPConnection(self.port)
                    self._conn.ansa_control.settimeout(self.call_timeout)
                    last_err = None
                    break
                except Exception as exc2:
                    last_err = exc2
            if self._conn is None:
                raise ConnectionError(
                    f"Cannot connect to ANSA at {self.host}:{self.port}: {last_err}"
                ) from last_err
        # handshake
        try:
            self._conn.hello()
        except Exception as exc:
            self._safe_close()
            raise ConnectionError(f"IAP handshake failed: {exc}") from exc

    def _safe_close(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is None:
            return
        try:
            try:
                conn.goodbye(post_connection_action=0x01)  # keep_listening
            except Exception:
                pass
            conn.close()
        except Exception:
            pass

    def close(self) -> None:
        with self._lock:
            self._safe_close()

    def is_connected(self) -> bool:
        return self._conn is not None

    # ----- public API -----
    def ping(self) -> dict[str, Any]:
        """Handshake-only ping; no script execution.

        NOTE: _ensure_connected() already performs the IAP handshake. ANSA's
        IAP listener does NOT tolerate a second HelloRequest on the same
        connection (it simply stops answering -> recv hangs). So do not call
        hello() again here.
        """
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
        return {
            "ok": True,
            "host": self.host,
            "port": self.port,
            "connected": True,
        }

    def run_script(
        self,
        script: str,
        function_name: str = "main",
        pre_execution_database_action: str = "keep",
        muted: bool = False,
        reconnect_on_error: bool = True,
    ) -> dict[str, Any]:
        """Execute a Python script on ANSA and return the result.

        The script must define a function whose name is ``function_name``
        (default ``main``) returning a ``dict[str, str]`` (values must be
        strings; non-string values will be coerced via ``str()``).

        Parameters
        ----------
        script : str
            Python source to execute inside ANSA.
        function_name : str
            Name of the entry-point function defined in ``script``.
        pre_execution_database_action : str
            ``"reset"`` to clear the ANSA database first (default ``"keep"``).
        muted : bool
            If True, suppress GUI interactions in ANSA.
        reconnect_on_error : bool
            If the call fails, drop the connection and try once more.
        """
        iap = _load_iap_module()
        pre = (
            iap.PreExecutionDatabaseAction.reset_database
            if pre_execution_database_action == "reset"
            else iap.PreExecutionDatabaseAction.keep_database
        )
        muted_flag = iap.MutedExecution.on if muted else iap.MutedExecution.off

        with self._lock:
            try:
                return self._do_run(
                    iap, script, function_name, pre, muted_flag
                )
            except Exception as exc:
                if reconnect_on_error and self._conn is not None:
                    self._safe_close()
                    return self._do_run(
                        iap, script, function_name, pre, muted_flag
                    )
                raise

    def _do_run(self, iap, script, function_name, pre, muted_flag):
        self._ensure_connected()
        assert self._conn is not None
        resp = self._conn.run_script_text(
            script_text=script,
            function_name=function_name,
            pre_execution_database_action=pre,
            muted_execution=muted_flag,
        )
        if not resp.success():
            details = resp.get_script_execution_details()
            return {
                "ok": False,
                "error": "ANSA script execution failed",
                "script_execution_details": details,
            }
        result = resp.get_response_dict()
        if result is None:
            return {
                "ok": True,
                "result": None,
                "return_type": resp.get_script_return_type(),
            }
        return {"ok": True, "result": _coerce_dict(result)}

    def run_file(
        self,
        filepath: str,
        function_name: str = "main",
        pre_execution_database_action: str = "keep",
        muted: bool = False,
    ) -> dict[str, Any]:
        """Execute a Python file inside ANSA and return the result."""
        iap = _load_iap_module()
        pre = (
            iap.PreExecutionDatabaseAction.reset_database
            if pre_execution_database_action == "reset"
            else iap.PreExecutionDatabaseAction.keep_database
        )
        muted_flag = iap.MutedExecution.on if muted else iap.MutedExecution.off
        with self._lock:
            self._ensure_connected()
            assert self._conn is not None
            resp = self._conn.run_script_file(
                filepath=filepath,
                function_name=function_name,
                pre_execution_database_action=pre,
                muted_execution=muted_flag,
            )
        if not resp.success():
            return {
                "ok": False,
                "error": "ANSA script execution failed",
                "script_execution_details": resp.get_script_execution_details(),
            }
        result = resp.get_response_dict()
        if result is None:
            return {"ok": True, "result": None}
        return {"ok": True, "result": _coerce_dict(result)}


def _coerce_dict(d: dict) -> dict:
    """Coerce dict values to JSON-friendly types."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, bytes):
            try:
                v = v.decode("utf-8")
            except UnicodeDecodeError:
                v = v.hex()
        if not isinstance(v, str):
            v = str(v)
        out[str(k)] = v
    return out


# module-level singleton (lazy)
_default_bridge: AnsaBridge | None = None


def get_default_bridge() -> AnsaBridge:
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = AnsaBridge()
    return _default_bridge
