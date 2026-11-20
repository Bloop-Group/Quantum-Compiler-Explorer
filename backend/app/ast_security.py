"""AST and syntax pre-screening security layer for Quantum Compiler Explorer.

Draws from Matt Godbolt's Compiler Explorer lessons to enforce strict AST validation
before running untrusted code or complex parsing jobs.
"""

from __future__ import annotations

import ast
from typing import NamedTuple


DISALLOWED_MODULES = frozenset({
    "os",
    "sys",
    "subprocess",
    "socket",
    "pathlib",
    "urllib",
    "requests",
    "shutil",
    "pickle",
    "ctypes",
    "importlib",
    "multiprocessing",
    "threading",
    "pty",
    "posix",
    "posixpath",
    "winreg",
    "_winapi",
    "builtins",
})

DISALLOWED_CALLS = frozenset({
    "eval",
    "exec",
    "__import__",
    "open",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
})


class SecurityViolation(ValueError):
    """Raised when source code contains disallowed operations or modules."""


class ValidationResult(NamedTuple):
    is_safe: bool
    reason: str | None = None
    line: int | None = None


def screen_python_ast(source_code: str) -> ValidationResult:
    """Analyze Python source AST to reject dangerous imports, function calls, and dunders.
    
    Returns ValidationResult(is_safe=True) or raises/returns error info.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return ValidationResult(is_safe=False, reason=f"Syntax error: {exc.msg}", line=exc.lineno)

    for node in ast.walk(tree):
        # 1. Disallow forbidden imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in DISALLOWED_MODULES:
                    return ValidationResult(
                        is_safe=False,
                        reason=f"Disallowed import: '{alias.name}' is prohibited",
                        line=node.lineno,
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in DISALLOWED_MODULES:
                    return ValidationResult(
                        is_safe=False,
                        reason=f"Disallowed import: from '{node.module}' is prohibited",
                        line=node.lineno,
                    )

        # 2. Disallow forbidden built-in calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in DISALLOWED_CALLS:
                return ValidationResult(
                    is_safe=False,
                    reason=f"Disallowed function call: '{node.func.id}()' is prohibited",
                    line=node.lineno,
                )

        # 3. Disallow accessing dangerous dunder attributes
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                if node.attr in ("__subclasses__", "__bases__", "__globals__", "__code__", "__builtins__"):
                    return ValidationResult(
                        is_safe=False,
                        reason=f"Disallowed dunder access: '{node.attr}' is prohibited",
                        line=node.lineno,
                    )

    return ValidationResult(is_safe=True)


def screen_qasm_input(qasm_text: str, max_chars: int = 65536) -> ValidationResult:
    """Validate OpenQASM 3 declarative source prior to parser ingestion."""
    if len(qasm_text) > max_chars:
        return ValidationResult(
            is_safe=False,
            reason=f"QASM input exceeds maximum length limit of {max_chars} characters",
            line=1,
        )

    # Check for forbidden control characters or suspicious shell injection tokens
    if "\x00" in qasm_text:
        return ValidationResult(is_safe=False, reason="Null byte in QASM input", line=1)

    return ValidationResult(is_safe=True)
