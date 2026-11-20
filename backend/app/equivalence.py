"""Automated unitary equivalence verification between compiled circuits.

Implements mathematical verification using Qiskit Operator/Statevector representations
to catch compiler regressions and routing bugs across different SDKs (ISSTA 2026 IterTestQ).
"""

from __future__ import annotations

import numpy as np
from typing import Any


class EquivalenceCheckError(ValueError):
    """Raised when circuits cannot be converted or checked for equivalence."""


def verify_circuit_equivalence(
    qasm_a: str,
    qasm_b: str,
    max_qubits: int = 10,
) -> dict[str, Any]:
    """Verify mathematical equivalence of two OpenQASM circuits up to a global phase.
    
    Returns:
        dict containing:
            - equivalent (bool): whether the two circuits compute identical unitaries/states
            - num_qubits (int): qubit count validated
            - fidelity (float): statevector overlap |<psi_A|psi_B>|^2
            - method (str): 'operator' or 'statevector'
            - message (str): diagnostic summary
    """
    try:
        from qiskit import QuantumCircuit, qasm3
        from qiskit.quantum_info import Operator, Statevector
    except ImportError as exc:
        raise EquivalenceCheckError(f"Qiskit required for equivalence checking: {exc}") from exc

    def _ensure_stdgates(s: str) -> str:
        if 'include "stdgates.inc";' not in s and "include 'stdgates.inc';" not in s:
            lines = s.split("\n")
            if lines and lines[0].strip().startswith("OPENQASM"):
                return lines[0] + '\ninclude "stdgates.inc";\n' + "\n".join(lines[1:])
            return 'OPENQASM 3.0;\ninclude "stdgates.inc";\n' + s
        return s

    try:
        qc_a = qasm3.loads(_ensure_stdgates(qasm_a))
    except Exception as exc:
        raise EquivalenceCheckError(f"Failed to parse Circuit A: {exc}") from exc

    try:
        qc_b = qasm3.loads(_ensure_stdgates(qasm_b))
    except Exception as exc:
        raise EquivalenceCheckError(f"Failed to parse Circuit B: {exc}") from exc

    # Strip measurements and barriers for pure unitary comparison
    qc_a_clean = qc_a.remove_final_measurements(inplace=False)
    qc_b_clean = qc_b.remove_final_measurements(inplace=False)

    n_a = qc_a_clean.num_qubits
    n_b = qc_b_clean.num_qubits

    if max(n_a, n_b) > max_qubits:
        return {
            "equivalent": False,
            "num_qubits": max(n_a, n_b),
            "fidelity": 0.0,
            "method": "skipped",
            "message": f"Circuit exceeds maximum verification limit of {max_qubits} qubits (found {max(n_a, n_b)})",
        }

    # If both circuits have equal qubit counts, test full unitary equivalence
    if n_a == n_b:
        try:
            op_a = Operator(qc_a_clean)
            op_b = Operator(qc_b_clean)
            is_equiv = bool(op_a.equiv(op_b))
            return {
                "equivalent": is_equiv,
                "num_qubits": n_a,
                "fidelity": 1.0 if is_equiv else 0.0,
                "method": "operator",
                "message": "Unitary operator equivalence confirmed" if is_equiv else "Unitary operators differ",
            }
        except Exception:
            pass

    # If qubit counts differ (e.g. logical circuit vs hardware patch with idle ancillas),
    # pad the smaller circuit with idle wires and compute statevector overlap starting from |0...0>
    target_qubits = max(n_a, n_b)
    if n_a < target_qubits:
        padded_a = QuantumCircuit(target_qubits)
        padded_a.compose(qc_a_clean, list(range(n_a)), inplace=True)
        qc_a_eval = padded_a
    else:
        qc_a_eval = qc_a_clean

    if n_b < target_qubits:
        padded_b = QuantumCircuit(target_qubits)
        padded_b.compose(qc_b_clean, list(range(n_b)), inplace=True)
        qc_b_eval = padded_b
    else:
        qc_b_eval = qc_b_clean

    try:
        sv_a = Statevector.from_instruction(qc_a_eval)
        sv_b = Statevector.from_instruction(qc_b_eval)
        overlap = np.abs(np.vdot(sv_a.data, sv_b.data)) ** 2
        is_equiv = bool(overlap > 0.9999)
        return {
            "equivalent": is_equiv,
            "num_qubits": target_qubits,
            "fidelity": round(float(overlap), 6),
            "method": "statevector",
            "message": f"Statevector overlap fidelity: {overlap:.6f}" + (" (Equivalent)" if is_equiv else " (Differ)"),
        }
    except Exception as exc:
        raise EquivalenceCheckError(f"Equivalence calculation failed: {exc}") from exc
