"""Subprocess timeout guard so pathological circuits cannot wedge a web worker."""

from __future__ import annotations

import multiprocessing as mp
from typing import Any, Callable


class TranspileTimeoutError(TimeoutError):
    """Raised when a transpilation job exceeds the configured wall-clock limit."""


def _runner(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], conn: Any) -> None:
    try:
        conn.send(("ok", fn(*args, **kwargs)))
    except Exception as exc:  # pragma: no cover - forwarded across process boundary
        conn.send(("err", (type(exc).__name__, str(exc), getattr(exc, "line", None))))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_with_timeout(
    fn: Callable[..., Any],
    *args: Any,
    timeout_seconds: float = 15.0,
    **kwargs: Any,
) -> Any:
    ctx = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_runner, args=(fn, args, kwargs, child_conn))
    proc.start()
    child_conn.close()  # close in parent so EOF is detectable

    if not parent_conn.poll(timeout=timeout_seconds):
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
        parent_conn.close()
        raise TranspileTimeoutError(f"Transpilation exceeded {timeout_seconds:.1f}s limit")

    try:
        status, payload = parent_conn.recv()
    except EOFError:
        proc.join(timeout=1.0)
        parent_conn.close()
        raise RuntimeError("Worker exited without returning a result")

    proc.join(timeout=1.0)
    parent_conn.close()
    if status == "ok":
        return payload
    err_name, msg, line = payload
    if err_name == "QasmParseError":
        from app.qasm_parser import QasmParseError
        raise QasmParseError(msg.replace(f"Line {line}: ", "") if line else msg, line or 1)
    if err_name == "ImportError":
        raise ImportError(msg)
    raise RuntimeError(f"{err_name}: {msg}")
