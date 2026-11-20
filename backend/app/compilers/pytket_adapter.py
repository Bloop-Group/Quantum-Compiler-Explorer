"""Production Quantinuum pytket adapter with OpenQASM 3 -> Qiskit fallback bridge."""

from __future__ import annotations

from typing import Any


def _load_pytket_circuit(qasm_source: str) -> Any:
    """Parse OpenQASM directly in pytket, falling back to qiskit -> pytket-qiskit for QASM 3."""
    from pytket.qasm import circuit_from_qasm_str

    try:
        return circuit_from_qasm_str(qasm_source)
    except Exception:
        from qiskit import qasm3
        from pytket.extensions.qiskit import qiskit_to_tk

        qc = qasm3.loads(qasm_source)
        return qiskit_to_tk(qc)


def _summarize_tket(circ: Any) -> dict[str, Any]:
    ops_list = []
    one_q = 0
    two_q = 0
    swaps = 0
    for cmd in circ.get_commands():
        name = cmd.op.type.name.lower()
        qs = [q.index[0] for q in cmd.qubits]
        if name == "swap":
            swaps += 1
            two_q += 3
        elif len(qs) == 1 and name not in ("measure", "barrier"):
            one_q += 1
        elif len(qs) == 2 and name not in ("measure", "barrier"):
            two_q += 1
        ops_list.append({
            "name": name,
            "qubits": qs,
            "params": [],
            "source_line": 0,
            "is_swap": name == "swap",
        })
    return {
        "metrics": {
            "total_gates": int(circ.n_gates),
            "single_qubit_gates": one_q,
            "two_qubit_gates": two_q,
            "inserted_swaps": swaps,
            "depth": int(circ.depth()),
        },
        "ops": ops_list,
    }


def transpile_with_pytket(
    qasm_source: str,
    topology: dict[str, Any],
    opt_level: int = 2,
    layout_strategy: str = "degree_aware",
) -> dict[str, Any]:
    from pytket.architecture import Architecture
    from pytket.placement import GraphPlacement, LinePlacement
    from pytket.passes import (
        FullPeepholeOptimise,
        PlacementPass,
        RoutingPass,
        SequencePass,
        SynthesiseTket,
    )
    from pytket.predicates import CompilationUnit
    from pytket.qasm import circuit_to_qasm_str

    circuit = _load_pytket_circuit(qasm_source)
    logical_summary = _summarize_tket(circuit)
    arch = Architecture(topology["edges"])
    cu = CompilationUnit(circuit)

    placer = LinePlacement(arch) if layout_strategy == "trivial" else GraphPlacement(arch)
    pass_list = [PlacementPass(placer), RoutingPass(arch)]
    if opt_level >= 1:
        pass_list.append(SynthesiseTket())
    if opt_level >= 2:
        pass_list.append(FullPeepholeOptimise())

    stages: list[dict[str, Any]] = [
        {
            "stage": "logical",
            "label": "Logical",
            "qasm": circuit_to_qasm_str(circuit),
            **logical_summary,
        }
    ]
    swap_edges: dict[str, int] = {}

    def _cb(unit: CompilationUnit, summary: dict[str, Any]) -> None:
        c = unit.circuit
        s = _summarize_tket(c)
        for op in s["ops"]:
            if op["name"] == "swap" and len(op["qubits"]) == 2:
                u, v = sorted(op["qubits"])
                ek = f"{u}-{v}"
                swap_edges[ek] = swap_edges.get(ek, 0) + 1
        stages.append({
            "stage": summary.get("name", "pass").lower(),
            "label": str(summary.get("name", "Pass"))[:14],
            "qasm": circuit_to_qasm_str(c),
            **s,
        })

    for p in pass_list:
        p_name = p.to_dict().get("StandardPass", {}).get("name", type(p).__name__)
        p.apply(cu)
        _cb(cu, {"name": p_name})
    final_summary = _summarize_tket(cu.circuit)
    edge_usage: dict[str, int] = {}
    for op in final_summary["ops"]:
        if len(op["qubits"]) == 2:
            u, v = sorted(op["qubits"])
            ek = f"{u}-{v}"
            edge_usage[ek] = edge_usage.get(ek, 0) + 1

    initial_layout: dict[str, int] = {}
    final_layout: dict[str, int] = {}
    if getattr(cu, "initial_map", None):
        for q, node in cu.initial_map.items():
            try:
                v_idx = q.index[0] if getattr(q, "index", None) else int(str(q).split("[")[-1].replace("]", ""))
                p_idx = node.index[0] if getattr(node, "index", None) else int(str(node).split("[")[-1].replace("]", ""))
                initial_layout[str(v_idx)] = p_idx
            except Exception:
                pass
    if getattr(cu, "final_map", None):
        for q, node in cu.final_map.items():
            try:
                v_idx = q.index[0] if getattr(q, "index", None) else int(str(q).split("[")[-1].replace("]", ""))
                p_idx = node.index[0] if getattr(node, "index", None) else int(str(node).split("[")[-1].replace("]", ""))
                final_layout[str(v_idx)] = p_idx
            except Exception:
                pass
    if not initial_layout:
        initial_layout = {str(i): i for i in range(circuit.n_qubits)}
    if not final_layout:
        final_layout = dict(initial_layout)

    # Keep UI tabs concise (Logical + up to 4 most significant passes including final)
    if len(stages) > 5:
        stages = [stages[0]] + stages[-4:]

    return {
        "compiler": "pytket",
        "target_id": topology["id"],
        "logical_metrics": logical_summary["metrics"],
        "initial_layout": initial_layout,
        "final_layout": final_layout,
        "edge_usage": edge_usage,
        "swap_edges": swap_edges,
        "inserted_swaps": sum(swap_edges.values()),
        "stages": stages,
        "final_metrics": final_summary["metrics"],
        "final_qasm": circuit_to_qasm_str(cu.circuit),
    }
