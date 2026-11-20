"""Production Google Cirq adapter returning normalized stage snapshots."""

from __future__ import annotations

import math
from typing import Any

from app.qasm_parser import parse_openqasm3


def _evaluate_param(p_str: str) -> float:
    p = p_str.strip().lower()
    if p == "pi":
        return math.pi
    if p == "pi/2":
        return math.pi / 2
    if p == "pi/4":
        return math.pi / 4
    if p == "-pi/2":
        return -math.pi / 2
    if p == "-pi/4":
        return -math.pi / 4
    try:
        return float(p)
    except ValueError:
        return 0.0


def _build_cirq_circuit(parsed_ops: list[Any], num_qubits: int) -> tuple[Any, list[dict[str, Any]]]:
    import cirq

    qubits = [cirq.LineQubit(i) for i in range(num_qubits)]
    circuit = cirq.Circuit()
    ops_summary: list[dict[str, Any]] = []

    for op in parsed_ops:
        name = op.name
        qs = op.qubits
        p = [_evaluate_param(x) for x in op.params]

        inst = None
        if name == "h":
            inst = cirq.H(qubits[qs[0]])
        elif name == "x":
            inst = cirq.X(qubits[qs[0]])
        elif name == "y":
            inst = cirq.Y(qubits[qs[0]])
        elif name == "z":
            inst = cirq.Z(qubits[qs[0]])
        elif name == "s":
            inst = cirq.S(qubits[qs[0]])
        elif name == "t":
            inst = cirq.T(qubits[qs[0]])
        elif name == "sx":
            inst = cirq.XPowGate(exponent=0.5)(qubits[qs[0]])
        elif name == "rx":
            inst = cirq.rx(p[0] if p else 0.0)(qubits[qs[0]])
        elif name == "ry":
            inst = cirq.ry(p[0] if p else 0.0)(qubits[qs[0]])
        elif name == "rz":
            inst = cirq.rz(p[0] if p else 0.0)(qubits[qs[0]])
        elif name == "cx":
            inst = cirq.CNOT(qubits[qs[0]], qubits[qs[1]])
        elif name == "cz":
            inst = cirq.CZ(qubits[qs[0]], qubits[qs[1]])
        elif name == "swap":
            inst = cirq.SWAP(qubits[qs[0]], qubits[qs[1]])
        elif name == "ccx":
            inst = cirq.TOFFOLI(qubits[qs[0]], qubits[qs[1]], qubits[qs[2]])
        elif name == "measure":
            inst = cirq.measure(qubits[qs[0]])

        if inst is not None:
            circuit.append(inst)
            ops_summary.append({
                "name": name,
                "qubits": qs,
                "params": op.params,
                "source_line": getattr(op, "line_no", 0),
                "is_swap": name == "swap",
            })

    return circuit, ops_summary


def _extract_cirq_summary(circuit: Any, num_qubits: int) -> dict[str, Any]:
    import cirq

    ops_list = []
    one_q = 0
    two_q = 0
    swaps = 0

    for moment in circuit:
        for op in moment:
            gate_name = op.gate.__class__.__name__.lower()
            q_indices = [q.x for q in op.qubits if isinstance(q, cirq.LineQubit)]
            is_swap = "swap" in gate_name
            if is_swap:
                swaps += 1
                two_q += 3
            elif len(q_indices) == 1 and "measure" not in gate_name:
                one_q += 1
            elif len(q_indices) == 2 and "measure" not in gate_name:
                two_q += 1

            ops_list.append({
                "name": gate_name,
                "qubits": q_indices,
                "params": [],
                "source_line": 0,
                "is_swap": is_swap,
            })

    total_gates = one_q + two_q + swaps
    return {
        "metrics": {
            "total_gates": total_gates,
            "single_qubit_gates": one_q,
            "two_qubit_gates": two_q,
            "inserted_swaps": swaps,
            "depth": len(circuit),
        },
        "ops": ops_list,
    }


def transpile_with_cirq(
    qasm_source: str,
    topology: dict[str, Any],
    opt_level: int = 2,
    layout_strategy: str = "degree_aware",
) -> dict[str, Any]:
    """Transpile OpenQASM 3 using Google Cirq compilation and optimization passes."""
    import cirq

    parsed = parse_openqasm3(qasm_source)
    logical_circuit, _ = _build_cirq_circuit(parsed.ops, parsed.num_qubits)
    logical_summary = _extract_cirq_summary(logical_circuit, parsed.num_qubits)

    # Initial qubit placement
    patch_size = topology["patch_qubits"]
    if layout_strategy == "trivial":
        initial_layout = {str(i): i for i in range(parsed.num_qubits)}
    else:
        # Degree-aware placement: prioritize highest degree hardware nodes
        degrees = {node: 0 for node in range(patch_size)}
        for u, v in topology["edges"]:
            degrees[u] = degrees.get(u, 0) + 1
            degrees[v] = degrees.get(v, 0) + 1
        sorted_nodes = sorted(degrees.keys(), key=lambda n: degrees[n], reverse=True)
        initial_layout = {str(i): sorted_nodes[i] for i in range(parsed.num_qubits)}

    # Map circuit onto physical line qubits
    phys_qubits = [cirq.LineQubit(initial_layout[str(i)]) for i in range(parsed.num_qubits)]
    mapped_circuit = cirq.Circuit()
    for moment in logical_circuit:
        for op in moment:
            new_qubits = [cirq.LineQubit(initial_layout[str(q.x)]) for q in op.qubits]
            mapped_circuit.append(op.gate.on(*new_qubits))

    stages: list[dict[str, Any]] = [
        {
            "stage": "logical",
            "label": "Logical",
            "qasm": cirq.qasm(logical_circuit),
            **logical_summary,
        },
        {
            "stage": "layout",
            "label": "Layout",
            "qasm": cirq.qasm(mapped_circuit),
            **_extract_cirq_summary(mapped_circuit, patch_size),
        },
    ]

    # Optimization passes based on opt_level
    current_circuit = mapped_circuit.copy()
    swap_edges: dict[str, int] = {}

    if opt_level >= 1:
        # Pass 1: Drop empty moments and merge single-qubit rotations
        current_circuit = cirq.drop_empty_moments(current_circuit)
        current_circuit = cirq.merge_single_qubit_gates_to_phxz(current_circuit)
        stages.append({
            "stage": "merge_rotations",
            "label": "MergeRotations",
            "qasm": cirq.qasm(current_circuit),
            **_extract_cirq_summary(current_circuit, patch_size),
        })

    if opt_level >= 2:
        # Pass 2: Eject Z and Phased XZ gates
        current_circuit = cirq.eject_z(current_circuit)
        current_circuit = cirq.drop_negligible_operations(current_circuit)
        stages.append({
            "stage": "eject_z",
            "label": "EjectZ",
            "qasm": cirq.qasm(current_circuit),
            **_extract_cirq_summary(current_circuit, patch_size),
        })

    if opt_level >= 3:
        # Pass 3: Full moment compaction
        current_circuit = cirq.drop_empty_moments(current_circuit)
        stages.append({
            "stage": "compaction",
            "label": "Compacted",
            "qasm": cirq.qasm(current_circuit),
            **_extract_cirq_summary(current_circuit, patch_size),
        })

    final_summary = _extract_cirq_summary(current_circuit, patch_size)
    edge_usage: dict[str, int] = {}
    for op in final_summary["ops"]:
        if len(op["qubits"]) == 2:
            u, v = sorted(op["qubits"])
            ek = f"{u}-{v}"
            edge_usage[ek] = edge_usage.get(ek, 0) + 1

    return {
        "compiler": "cirq",
        "target_id": topology["id"],
        "logical_metrics": logical_summary["metrics"],
        "initial_layout": initial_layout,
        "final_layout": initial_layout,
        "edge_usage": edge_usage,
        "swap_edges": swap_edges,
        "inserted_swaps": sum(swap_edges.values()),
        "stages": stages,
        "final_metrics": final_summary["metrics"],
        "final_qasm": cirq.qasm(current_circuit),
    }
