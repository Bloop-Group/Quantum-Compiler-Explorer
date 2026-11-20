"""Comprehensive integration tests for the Quantum Compiler Explorer FastAPI service."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app, RATE_LIMITER


GHZ_QASM = """OPENQASM 3.0;
include "stdgates.inc";
qubit[3] q;
bit[3] c;
h q[0];
cx q[0], q[1];
cx q[1], q[2];
c[0] = measure q[0];
"""

BELL_A = """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
h q[0];
cx q[0], q[1];
"""

BELL_B = """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
h q[0];
h q[1];
cz q[0], q[1];
h q[1];
"""


class TestApiIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        RATE_LIMITER.clear()

    def test_health_endpoint(self) -> None:
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("cache_backend", data)

    def test_targets_endpoint(self) -> None:
        resp = self.client.get("/api/v1/targets")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("targets", data)
        self.assertIn("pricing", data)
        self.assertGreaterEqual(len(data["targets"]), 5)

    def test_transpile_builtin_with_cache_hit(self) -> None:
        payload = {
            "qasm": GHZ_QASM,
            "target_id": "ibm_heron_r3_patch",
            "compiler": "builtin",
            "opt_level": 2,
            "layout_strategy": "degree_aware",
            "shots": 4000,
        }
        # First request: cache miss
        r1 = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertFalse(d1["cache_hit"])
        self.assertEqual(d1["compiler"], "builtin")
        self.assertIn("estimated_fidelity", d1)
        self.assertIn("cost_estimate", d1)

        # Second request: cache hit
        r2 = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertTrue(d2["cache_hit"])

    def test_transpile_qiskit_live(self) -> None:
        payload = {
            "qasm": GHZ_QASM,
            "target_id": "ibm_heron_r3_patch",
            "compiler": "qiskit",
            "opt_level": 2,
        }
        resp = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["compiler"], "qiskit")
        self.assertIn("final_layout", data)
        self.assertGreaterEqual(len(data["stages"]), 2)

    def test_transpile_pytket_live(self) -> None:
        payload = {
            "qasm": GHZ_QASM,
            "target_id": "ibm_heron_r3_patch",
            "compiler": "pytket",
            "opt_level": 2,
        }
        resp = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["compiler"], "pytket")
        self.assertIn("initial_layout", data)
        self.assertGreaterEqual(len(data["stages"]), 2)

    def test_transpile_cirq_live(self) -> None:
        payload = {
            "qasm": GHZ_QASM,
            "target_id": "ibm_heron_r3_patch",
            "compiler": "cirq",
            "opt_level": 2,
        }
        resp = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["compiler"], "cirq")
        self.assertIn("final_layout", data)
        self.assertGreaterEqual(len(data["stages"]), 2)

    def test_compare_endpoint(self) -> None:
        payload = {
            "qasm": GHZ_QASM,
            "shots": 5000,
            "ibm_tier": "payg",
            "target_a": {"target_id": "ibm_heron_r3_patch", "compiler": "qiskit", "opt_level": 2},
            "target_b": {"target_id": "ionq_forte_clique", "compiler": "builtin", "opt_level": 2},
            "verify_equivalence": True,
        }
        resp = self.client.post("/api/v1/compare", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("target_a", data)
        self.assertIn("target_b", data)
        self.assertEqual(data["target_a"]["compiler"], "qiskit")
        self.assertEqual(data["target_b"]["compiler"], "builtin")
        self.assertIn("equivalence", data)

    def test_verify_equivalence_endpoint(self) -> None:
        payload = {
            "qasm_a": BELL_A,
            "qasm_b": BELL_B,
            "max_qubits": 6,
        }
        resp = self.client.post("/api/v1/verify_equivalence", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["equivalent"])
        self.assertEqual(data["fidelity"], 1.0)

    def test_error_handling_unknown_target(self) -> None:
        payload = {
            "qasm": GHZ_QASM,
            "target_id": "nonexistent_chip",
            "compiler": "builtin",
        }
        resp = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(resp.status_code, 404)

    def test_error_handling_invalid_qasm(self) -> None:
        payload = {
            "qasm": "OPENQASM 3.0;\nqubit[2] q;\ninvalid_gate q[0];\n",
            "target_id": "ibm_heron_r3_patch",
            "compiler": "builtin",
        }
        resp = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_security_rejection_null_byte(self) -> None:
        payload = {
            "qasm": "OPENQASM 3.0;\x00qubit[2] q;\n",
            "target_id": "ibm_heron_r3_patch",
            "compiler": "builtin",
        }
        resp = self.client.post("/api/v1/transpile", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_rate_limiting(self) -> None:
        # Fill the rate limiter bucket
        for _ in range(RATE_LIMITER.max_requests):
            RATE_LIMITER.allow("testclient")
        resp = self.client.post(
            "/api/v1/transpile",
            json={"qasm": GHZ_QASM, "target_id": "ibm_heron_r3_patch", "compiler": "builtin"},
        )
        self.assertEqual(resp.status_code, 429)

    def test_prometheus_metrics(self) -> None:
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("qce_uptime_seconds", resp.text)
        self.assertIn("qce_http_requests_total", resp.text)

    def test_ast_security_scanner(self) -> None:
        from app.ast_security import screen_python_ast, screen_qasm_input

        # Safe code
        safe = screen_python_ast("import math\ndef f(x):\n    return math.sin(x)\n")
        self.assertTrue(safe.is_safe)

        # Disallowed imports
        bad_import = screen_python_ast("import os\nos.system('echo 1')\n")
        self.assertFalse(bad_import.is_safe)
        self.assertIn("os", bad_import.reason or "")

        bad_from = screen_python_ast("from subprocess import Popen\n")
        self.assertFalse(bad_from.is_safe)

        # Disallowed calls
        bad_eval = screen_python_ast("eval('1 + 1')\n")
        self.assertFalse(bad_eval.is_safe)

        # Disallowed dunder
        bad_dunder = screen_python_ast("x = ().__class__.__subclasses__()\n")
        self.assertFalse(bad_dunder.is_safe)

        # QASM checks
        self.assertFalse(screen_qasm_input("A" * 70000).is_safe)
        self.assertFalse(screen_qasm_input("OPENQASM\x003.0;").is_safe)
        self.assertTrue(screen_qasm_input("OPENQASM 3.0;\nqubit[2] q;\n").is_safe)

    def test_direct_compilers_and_equivalence(self) -> None:
        from app.compilers.qiskit_adapter import transpile_with_qiskit
        from app.compilers.pytket_adapter import transpile_with_pytket
        from app.compilers.cirq_adapter import transpile_with_cirq
        from app.equivalence import verify_circuit_equivalence, EquivalenceCheckError
        from app.registry import load_topologies

        topologies = load_topologies()
        topo = topologies["ibm_heron_r3_patch"]

        # Qiskit
        q_res = transpile_with_qiskit(GHZ_QASM, topo, opt_level=1)
        self.assertEqual(q_res["compiler"], "qiskit")
        self.assertIn("final_metrics", q_res)

        # Pytket
        p_res = transpile_with_pytket(GHZ_QASM, topo, opt_level=1)
        self.assertEqual(p_res["compiler"], "pytket")

        # Cirq
        c_res = transpile_with_cirq(GHZ_QASM, topo, opt_level=3)
        self.assertEqual(c_res["compiler"], "cirq")

        # Equivalence edge cases
        res_skipped = verify_circuit_equivalence(GHZ_QASM, GHZ_QASM, max_qubits=2)
        self.assertEqual(res_skipped["method"], "skipped")

        with self.assertRaises(EquivalenceCheckError):
            verify_circuit_equivalence("invalid qasm", GHZ_QASM)


if __name__ == "__main__":
    unittest.main()
