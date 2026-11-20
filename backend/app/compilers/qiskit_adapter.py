"""Production Qiskit 1.4/2.0 transpiler adapter returning normalized stage snapshots."""

from __future__ import annotations

from typing import Any


def _extract_circuit_summary(circuit: Any) -> dict[str, Any]:
    ops_dict = dict(circuit.count_ops())
    one_q = 0
    two_q = 0
    swaps = int(ops_dict.get("swap", 0))
    ops_list = []
    for inst in circuit.data:
        name = inst.operation.name
        q_indices = [circuit.find_bit(q).index for q in inst.qubits]
        if name not in ("barrier", "measure"):
            if name == "swap":
                two_q += 3
            elif len(q_indices) == 1:
                one_q += 1
            elif len(q_indices) == 2:
                two_q += 1
        ops_list.append({
            "name": name,
            "qubits": q_indices,
            "params": [str(p) for p in inst.operation.params],
            "source_line": 0,
            "is_swap": name == "swap",
        })
    return {
        "metrics": {
            "total_gates": sum(v for k, v in ops_dict.items() if k not in ("barrier", "measure")),
            "single_qubit_gates": one_q,
            "two_qubit_gates": two_q,
            "inserted_swaps": swaps,
            "depth": int(circuit.depth()),
        },
        "ops": ops_list,
    }


def transpile_with_qiskit(
    qasm_source: str,
    topology: dict[str, Any],
    opt_level: int = 2,
    layout_strategy: str = "degree_aware",
) -> dict[str, Any]:
    """Transpile OpenQASM 3 using Qiskit Target + generate_preset_pass_manager callback."""
    from qiskit import qasm3
    from qiskit.converters import dag_to_circuit
    from qiskit.transpiler import CouplingMap, Target, generate_preset_pass_manager

    circuit = qasm3.loads(qasm_source)
    logical_summary = _extract_circuit_summary(circuit)
    coupling_map = CouplingMap(topology["edges"])
    basis_gates = list(dict.fromkeys(topology["basis_gates"] + ["measure"]))
    target = Target.from_configuration(
        basis_gates=basis_gates,
        num_qubits=topology["patch_qubits"],
        coupling_map=coupling_map,
    )

    layout_method = "trivial" if layout_strategy == "trivial" else "sabre"
    pm = generate_preset_pass_manager(
        optimization_level=opt_level,
        target=target,
        layout_method=layout_method,
    )

    stages: list[dict[str, Any]] = [
        {
            "stage": "logical",
            "label": "Logical",
            "qasm": qasm3.dumps(circuit),
            **logical_summary,
        }
    ]
    last_sig: tuple[int, int] | None = None
    swap_edges: dict[str, int] = {}

    def _callback(**kwargs: Any) -> None:
        nonlocal last_sig
        dag = kwargs["dag"]
        pass_obj = kwargs["pass_"]
        depth = int(dag.depth())
        ops = dag.count_ops()
        sig = (depth, sum(ops.values()))
        if sig == last_sig:
            return
        last_sig = sig
        snap = dag_to_circuit(dag)
        summary = _extract_circuit_summary(snap)
        for op in summary["ops"]:
            if op["name"] == "swap" and len(op["qubits"]) == 2:
                u, v = sorted(op["qubits"])
                ek = f"{u}-{v}"
                swap_edges[ek] = swap_edges.get(ek, 0) + 1
        stages.append({
            "stage": pass_obj.__class__.__name__.lower(),
            "label": pass_obj.__class__.__name__[:14],
            "qasm": qasm3.dumps(snap),
            **summary,
        })

    transpiled = pm.run(circuit, callback=_callback)
    final_summary = _extract_circuit_summary(transpiled)
    edge_usage: dict[str, int] = {}
    for op in final_summary["ops"]:
        if len(op["qubits"]) == 2:
            u, v = sorted(op["qubits"])
            ek = f"{u}-{v}"
            edge_usage[ek] = edge_usage.get(ek, 0) + 1

    initial_layout: dict[str, int] = {}
    final_layout: dict[str, int] = {}
    if getattr(transpiled, "layout", None) is not None:
        try:
            init_indices = transpiled.layout.initial_index_layout()
            if init_indices is not None:
                initial_layout = {str(v): int(p) for v, p in enumerate(init_indices[:circuit.num_qubits])}
        except Exception:
            pass
        try:
            final_indices = transpiled.layout.final_index_layout()
            if final_indices is not None:
                final_layout = {str(v): int(p) for v, p in enumerate(final_indices[:circuit.num_qubits])}
        except Exception:
            pass

    if not initial_layout:
        initial_layout = {str(i): i for i in range(circuit.num_qubits)}
    if not final_layout:
        final_layout = dict(initial_layout)

    # Keep UI tabs concise (Logical + up to 4 most significant passes including final)
    if len(stages) > 5:
        stages = [stages[0]] + stages[-4:]

    return {
        "compiler": "qiskit",
        "target_id": topology["id"],
        "logical_metrics": logical_summary["metrics"],
        "initial_layout": initial_layout,
        "final_layout": final_layout,
        "edge_usage": edge_usage,
        "swap_edges": swap_edges,
        "inserted_swaps": sum(swap_edges.values()),
        "stages": stages,
        "final_metrics": final_summary["metrics"],
        "final_qasm": qasm3.dumps(transpiled),
    }
