"""OpenQASM 3 parser, topological SWAP router, basis translator, and optimizer."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import re
from typing import Any


SINGLE_QUBIT_GATES = {"h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "id", "rx", "ry", "rz", "gpi", "gpi2"}
TWO_QUBIT_GATES = {"cx", "cz", "swap", "rzz", "ms"}
THREE_QUBIT_GATES = {"ccx"}


@dataclass
class GateOp:
    name: str
    qubits: list[int]
    params: list[str] = field(default_factory=list)
    source_line: int = 0
    is_swap_inserted: bool = False
    tag: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qubits": list(self.qubits),
            "params": list(self.params),
            "source_line": self.source_line,
            "is_swap": self.is_swap_inserted,
        }


@dataclass
class ParsedCircuit:
    num_qubits: int
    num_bits: int
    ops: list[GateOp]
    version: str = "3.0"


class QasmParseError(ValueError):
    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"Line {line}: {message}")
        self.line = line
        self.message = message


def _strip_comments(source: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    in_block = False
    for idx, raw in enumerate(source.splitlines(), start=1):
        line = raw
        if in_block:
            end = line.find("*/")
            if end == -1:
                continue
            line = line[end + 2 :]
            in_block = False
        while "/*" in line:
            start = line.find("/*")
            end = line.find("*/", start + 2)
            if end == -1:
                line = line[:start]
                in_block = True
                break
            line = line[:start] + line[end + 2 :]
        if "//" in line:
            line = line[: line.index("//")]
        line = line.strip()
        if line:
            lines.append((idx, line))
    return lines


def parse_openqasm3(source: str) -> ParsedCircuit:
    num_qubits = 0
    num_bits = 0
    version = "3.0"
    ops: list[GateOp] = []

    for line_no, raw_line in _strip_comments(source):
        for stmt in [s.strip() for s in raw_line.split(";") if s.strip()]:
            if stmt.upper().startswith("OPENQASM"):
                m = re.match(r"OPENQASM\s+([0-9.]+)$", stmt, re.IGNORECASE)
                if not m:
                    raise QasmParseError(f"Invalid OPENQASM header: {stmt}", line_no)
                version = m.group(1)
                continue
            if stmt.startswith("include "):
                continue
            m_q = re.match(r"^(?:qubit\[(\d+)\]\s+(\w+)|qreg\s+(\w+)\[(\d+)\])$", stmt)
            if m_q:
                count = int(m_q.group(1) or m_q.group(4))
                num_qubits = max(num_qubits, count)
                continue
            m_b = re.match(r"^(?:bit\[(\d+)\]\s+(\w+)|creg\s+(\w+)\[(\d+)\])$", stmt)
            if m_b:
                count = int(m_b.group(1) or m_b.group(4))
                num_bits = max(num_bits, count)
                continue
            if stmt.startswith("barrier"):
                ops.append(GateOp(name="barrier", qubits=[], source_line=line_no))
                continue
            if "measure" in stmt:
                m_meas = re.findall(r"\[(\d+)\]", stmt)
                if m_meas:
                    ops.append(GateOp(name="measure", qubits=[int(m_meas[0])], source_line=line_no))
                else:
                    ops.append(GateOp(name="measure", qubits=list(range(num_qubits)), source_line=line_no))
                continue

            m_gate = re.match(r"^([a-zA-Z_]\w*)(?:\(([^)]*)\))?\s+(.+)$", stmt)
            if not m_gate:
                raise QasmParseError(f"Unrecognized statement: {stmt}", line_no)
            gate_name = m_gate.group(1).lower()
            params = [p.strip() for p in m_gate.group(2).split(",")] if m_gate.group(2) else []
            args = [a.strip() for a in m_gate.group(3).split(",")]
            q_indices: list[int] = []
            for arg in args:
                mq = re.match(r"^\w+\[(\d+)\]$", arg)
                if not mq:
                    raise QasmParseError(f"Invalid qubit operand '{arg}'", line_no)
                idx = int(mq.group(1))
                if idx >= num_qubits:
                    raise QasmParseError(
                        f"Qubit index {idx} out of range for {num_qubits}-qubit register",
                        line_no,
                    )
                q_indices.append(idx)

            if gate_name in SINGLE_QUBIT_GATES and len(q_indices) != 1:
                raise QasmParseError(f"Gate '{gate_name}' requires 1 qubit", line_no)
            if gate_name in TWO_QUBIT_GATES and len(q_indices) != 2:
                raise QasmParseError(f"Gate '{gate_name}' requires 2 qubits", line_no)
            if gate_name in THREE_QUBIT_GATES and len(q_indices) != 3:
                raise QasmParseError(f"Gate '{gate_name}' requires 3 qubits", line_no)
            if (
                gate_name not in SINGLE_QUBIT_GATES
                and gate_name not in TWO_QUBIT_GATES
                and gate_name not in THREE_QUBIT_GATES
            ):
                raise QasmParseError(f"Unsupported gate '{gate_name}'", line_no)
            if len(set(q_indices)) != len(q_indices):
                raise QasmParseError(f"Duplicate qubit operands in '{stmt}'", line_no)

            ops.append(GateOp(name=gate_name, qubits=q_indices, params=params, source_line=line_no))

    if num_qubits == 0:
        raise QasmParseError("No qubit register declared (e.g. qubit[3] q;)", 1)
    return ParsedCircuit(num_qubits=num_qubits, num_bits=num_bits, ops=ops, version=version)


def circuit_depth(ops: list[GateOp], num_qubits: int) -> int:
    wire_depth = [0] * max(1, num_qubits)
    for op in ops:
        if op.name == "barrier":
            mx = max(wire_depth)
            wire_depth = [mx] * len(wire_depth)
            continue
        if not op.qubits:
            continue
        level = max(wire_depth[q] for q in op.qubits) + 1
        for q in op.qubits:
            wire_depth[q] = level
    return max(wire_depth) if wire_depth else 0


def circuit_metrics(ops: list[GateOp], num_qubits: int) -> dict[str, int]:
    one_q = 0
    two_q = 0
    for op in ops:
        if op.name in ("barrier", "measure"):
            continue
        if op.name == "swap":
            two_q += 3
        elif len(op.qubits) == 1:
            one_q += 1
        elif len(op.qubits) == 2:
            two_q += 1
        elif len(op.qubits) == 3:
            two_q += 6
    return {
        "total_gates": sum(1 for o in ops if o.name not in ("barrier", "measure")),
        "single_qubit_gates": one_q,
        "two_qubit_gates": two_q,
        "inserted_swaps": sum(1 for o in ops if o.name == "swap" and o.is_swap_inserted),
        "depth": circuit_depth(ops, num_qubits),
    }


def _build_adj(edges: list[list[int]], n: int) -> dict[int, list[int]]:
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def _shortest_path(adj: dict[int, list[int]], start: int, goal: int) -> list[int]:
    if start == goal:
        return [start]
    q: deque[list[int]] = deque([[start]])
    visited = {start}
    while q:
        path = q.popleft()
        node = path[-1]
        for nxt in adj.get(node, []):
            if nxt == goal:
                return path + [nxt]
            if nxt not in visited:
                visited.add(nxt)
                q.append(path + [nxt])
    return []


def _choose_layout(circuit: ParsedCircuit, adj: dict[int, list[int]], strategy: str) -> dict[int, int]:
    if strategy == "degree_aware":
        interaction = {q: 0 for q in range(circuit.num_qubits)}
        for op in circuit.ops:
            if len(op.qubits) >= 2:
                for q in op.qubits:
                    interaction[q] += 1
        logical_order = sorted(interaction.keys(), key=lambda q: (-interaction[q], q))
        physical_order = sorted(adj.keys(), key=lambda p: (-len(adj[p]), p))
        return {lq: physical_order[i] for i, lq in enumerate(logical_order)}
    return {q: q for q in range(circuit.num_qubits)}


def _expand_ccx(ops: list[GateOp]) -> list[GateOp]:
    out: list[GateOp] = []
    for op in ops:
        if op.name == "ccx":
            c1, c2, t = op.qubits
            seq = [
                ("h", [t]), ("cx", [c2, t]), ("tdg", [t]), ("cx", [c1, t]),
                ("t", [t]), ("cx", [c2, t]), ("tdg", [t]), ("cx", [c1, t]),
                ("t", [c2]), ("t", [t]), ("h", [t]), ("cx", [c1, c2]),
                ("t", [c1]), ("tdg", [c2]), ("cx", [c1, c2]),
            ]
            for name, qs in seq:
                out.append(GateOp(name=name, qubits=qs, source_line=op.source_line, tag="ccx_decomp"))
        else:
            out.append(op)
    return out


def _translate_basis(ops: list[GateOp], two_q_gate: str) -> list[GateOp]:
    out: list[GateOp] = []
    for op in ops:
        if op.name in ("barrier", "measure"):
            out.append(op)
            continue
        if op.name == "swap":
            a, b = op.qubits
            for name, qs in [("cx", [a, b]), ("cx", [b, a]), ("cx", [a, b])]:
                if two_q_gate == "cz":
                    out.append(GateOp("rz", [qs[1]], ["pi/2"], op.source_line, op.is_swap_inserted, "swap_decomp"))
                    out.append(GateOp("sx", [qs[1]], [], op.source_line, op.is_swap_inserted, "swap_decomp"))
                    out.append(GateOp("rz", [qs[1]], ["pi/2"], op.source_line, op.is_swap_inserted, "swap_decomp"))
                    out.append(GateOp("cz", qs, [], op.source_line, op.is_swap_inserted, "swap_decomp"))
                    out.append(GateOp("rz", [qs[1]], ["pi/2"], op.source_line, op.is_swap_inserted, "swap_decomp"))
                    out.append(GateOp("sx", [qs[1]], [], op.source_line, op.is_swap_inserted, "swap_decomp"))
                    out.append(GateOp("rz", [qs[1]], ["pi/2"], op.source_line, op.is_swap_inserted, "swap_decomp"))
                elif two_q_gate == "ms":
                    out.append(GateOp("ms", qs, ["0", "0"], op.source_line, op.is_swap_inserted, "swap_decomp"))
                else:
                    out.append(GateOp("cx", qs, [], op.source_line, op.is_swap_inserted, "swap_decomp"))
            continue
        if op.name == "cx" and two_q_gate == "cz":
            c, t = op.qubits
            out.append(GateOp("rz", [t], ["pi/2"], op.source_line, op.is_swap_inserted))
            out.append(GateOp("sx", [t], [], op.source_line, op.is_swap_inserted))
            out.append(GateOp("rz", [t], ["pi/2"], op.source_line, op.is_swap_inserted))
            out.append(GateOp("cz", [c, t], [], op.source_line, op.is_swap_inserted))
            out.append(GateOp("rz", [t], ["pi/2"], op.source_line, op.is_swap_inserted))
            out.append(GateOp("sx", [t], [], op.source_line, op.is_swap_inserted))
            out.append(GateOp("rz", [t], ["pi/2"], op.source_line, op.is_swap_inserted))
            continue
        if op.name == "cx" and two_q_gate == "ms":
            c, t = op.qubits
            out.append(GateOp("gpi2", [c], ["pi/2"], op.source_line, op.is_swap_inserted))
            out.append(GateOp("ms", [c, t], ["0", "0"], op.source_line, op.is_swap_inserted))
            out.append(GateOp("gpi2", [t], ["-pi/2"], op.source_line, op.is_swap_inserted))
            continue
        if op.name == "h" and two_q_gate in ("cz", "cx"):
            q = op.qubits[0]
            out.append(GateOp("rz", [q], ["pi/2"], op.source_line))
            out.append(GateOp("sx", [q], [], op.source_line))
            out.append(GateOp("rz", [q], ["pi/2"], op.source_line))
            continue
        if op.name == "h" and two_q_gate == "ms":
            q = op.qubits[0]
            out.append(GateOp("gpi2", [q], ["pi/2"], op.source_line))
            out.append(GateOp("gpi", [q], ["0"], op.source_line))
            continue
        out.append(op)
    return out


def _optimize_ops(ops: list[GateOp], opt_level: int) -> list[GateOp]:
    if opt_level <= 0:
        return list(ops)
    self_inverse = {"x", "y", "z", "h", "cx", "cz", "swap"}
    cur = list(ops)
    passes = 1 if opt_level == 1 else 3
    for _ in range(passes):
        nxt: list[GateOp] = []
        for op in cur:
            if (
                nxt
                and nxt[-1].name == op.name
                and nxt[-1].qubits == op.qubits
                and nxt[-1].params == op.params
                and op.name in self_inverse
            ):
                nxt.pop()
                continue
            if (
                opt_level >= 2
                and nxt
                and nxt[-1].name == "rz"
                and op.name == "rz"
                and nxt[-1].qubits == op.qubits
            ):
                merged = f"{nxt[-1].params[0]}+{op.params[0]}" if nxt[-1].params and op.params else "pi"
                nxt[-1] = GateOp("rz", op.qubits, [merged], op.source_line, op.is_swap_inserted, "merged_rz")
                continue
            nxt.append(op)
        cur = nxt
    return cur


def emit_openqasm3(ops: list[GateOp], num_qubits: int, num_bits: int) -> str:
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";', f"qubit[{num_qubits}] q;"]
    if num_bits > 0:
        lines.append(f"bit[{num_bits}] c;")
    for op in ops:
        if op.name == "barrier":
            lines.append("barrier q;")
        elif op.name == "measure":
            q = op.qubits[0]
            lines.append(f"c[{q}] = measure q[{q}];")
        else:
            p = f"({', '.join(op.params)})" if op.params else ""
            qs = ", ".join(f"q[{q}]" for q in op.qubits)
            comment = " // [SWAP]" if op.is_swap_inserted else ""
            lines.append(f"{op.name}{p} {qs};{comment}")
    return "\n".join(lines)


def compute_cache_key(source: str, target_id: str, compiler: str, opt_level: int, layout: str) -> str:
    payload = f"{source}|{target_id}|{compiler}|{opt_level}|{layout}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def transpile_local(
    source: str,
    topology: dict[str, Any],
    opt_level: int = 2,
    layout_strategy: str = "degree_aware",
) -> dict[str, Any]:
    parsed = parse_openqasm3(source)
    patch_qubits = int(topology["patch_qubits"])
    if parsed.num_qubits > patch_qubits:
        raise QasmParseError(
            f"Circuit uses {parsed.num_qubits} qubits, exceeding target patch capacity ({patch_qubits})",
            1,
        )

    adj = _build_adj(topology["edges"], patch_qubits)
    expanded = _expand_ccx(parsed.ops)
    layout_map = _choose_layout(parsed, adj, layout_strategy)
    laid_out = [
        GateOp(op.name, [layout_map[q] for q in op.qubits], op.params, op.source_line, False, op.tag)
        for op in expanded
    ]

    l2p = dict(layout_map)
    p2l = {p: l for l, p in l2p.items()}
    routed: list[GateOp] = []
    edge_usage: dict[str, int] = {}
    swap_edges: dict[str, int] = {}

    def _edge_key(u: int, v: int) -> str:
        return f"{min(u, v)}-{max(u, v)}"

    for op in expanded:
        if op.name in ("barrier", "measure"):
            routed.append(GateOp(op.name, [l2p[q] for q in op.qubits], op.params, op.source_line))
            continue
        if len(op.qubits) == 1:
            routed.append(GateOp(op.name, [l2p[op.qubits[0]]], op.params, op.source_line, False, op.tag))
            continue
        lq0, lq1 = op.qubits
        p0, p1 = l2p[lq0], l2p[lq1]
        if p1 not in adj[p0]:
            path = _shortest_path(adj, p0, p1)
            for i in range(len(path) - 2):
                u, v = path[i], path[i + 1]
                routed.append(GateOp("swap", [u, v], [], op.source_line, True, "routed_swap"))
                ek = _edge_key(u, v)
                swap_edges[ek] = swap_edges.get(ek, 0) + 1
                edge_usage[ek] = edge_usage.get(ek, 0) + 3
                lu, lv = p2l.get(u), p2l.get(v)
                if lu is not None:
                    l2p[lu] = v
                if lv is not None:
                    l2p[lv] = u
                p2l[u], p2l[v] = lv, lu
            p0, p1 = l2p[lq0], l2p[lq1]
        ek = _edge_key(p0, p1)
        edge_usage[ek] = edge_usage.get(ek, 0) + 1
        routed.append(GateOp(op.name, [p0, p1], op.params, op.source_line, False, op.tag))

    translated = _translate_basis(routed, topology["two_qubit_gate"])
    optimized = _optimize_ops(translated, opt_level)

    stage_defs = [
        ("logical", "Logical", parsed.ops, parsed.num_qubits),
        ("layout", "Layout", laid_out, patch_qubits),
        ("routing", "Routed", routed, patch_qubits),
        ("translation", "Native", translated, patch_qubits),
        ("optimization", f"Opt O{opt_level}", optimized, patch_qubits),
    ]
    stages = [
        {
            "stage": key,
            "label": lbl,
            "qasm": emit_openqasm3(ops, nq, parsed.num_bits),
            "metrics": circuit_metrics(ops, nq),
            "ops": [op.to_dict() for op in ops],
        }
        for key, lbl, ops, nq in stage_defs
    ]

    return {
        "compiler": "builtin",
        "target_id": topology["id"],
        "logical_metrics": stages[0]["metrics"],
        "initial_layout": {str(k): v for k, v in layout_map.items()},
        "final_layout": {str(k): v for k, v in l2p.items()},
        "edge_usage": edge_usage,
        "swap_edges": swap_edges,
        "inserted_swaps": sum(swap_edges.values()),
        "stages": stages,
        "final_metrics": stages[-1]["metrics"],
        "final_qasm": stages[-1]["qasm"],
    }
