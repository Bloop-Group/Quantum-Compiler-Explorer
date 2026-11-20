"""Comprehensive unit tests for parser, router, cost estimator, cache, rate limiter, and worker timeouts."""

from __future__ import annotations

import sys
import time
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache import ResultCache
from app.cost_estimator import estimate_fidelity, estimate_job_cost
from app.qasm_parser import QasmParseError, compute_cache_key, parse_openqasm3, transpile_local
from app.rate_limit import SlidingWindowRateLimiter
from app.registry import load_pricing, load_topologies
from app.worker import TranspileTimeoutError, run_with_timeout


GHZ_3 = """OPENQASM 3.0;
include "stdgates.inc";
/* Multi-line comment check */
qubit[3] q;
bit[3] c;
h q[0]; // inline comment
cx q[0], q[1];
cx q[1], q[2];
barrier q;
c[0] = measure q[0];
"""

QFT_4 = """OPENQASM 3.0;
include "stdgates.inc";
qubit[4] q;
bit[4] c;
h q[0];
cx q[1], q[0];
cx q[2], q[0];
cx q[3], q[0];
h q[1];
cx q[2], q[1];
cx q[3], q[1];
h q[2];
cx q[3], q[2];
h q[3];
"""

GROVER_CCX = """OPENQASM 3.0;
include "stdgates.inc";
qubit[3] q;
h q[0];
ccx q[0], q[1], q[2];
"""


def _slow_job() -> str:
    time.sleep(1.5)
    return "done"


class TestQuantumCompilerCore(unittest.TestCase):
    def setUp(self) -> None:
        self.topologies = load_topologies()
        self.pricing = load_pricing()

    def test_parse_valid_ghz_with_comments_and_barrier(self) -> None:
        parsed = parse_openqasm3(GHZ_3)
        self.assertEqual(parsed.num_qubits, 3)
        self.assertEqual(parsed.num_bits, 3)
        self.assertEqual(len(parsed.ops), 5)

    def test_parse_rejects_missing_register(self) -> None:
        with self.assertRaises(QasmParseError):
            parse_openqasm3("OPENQASM 3.0;\n")

    def test_parse_rejects_out_of_range_qubit(self) -> None:
        bad = "OPENQASM 3.0;\nqubit[2] q;\ncx q[0], q[5];\n"
        with self.assertRaises(QasmParseError) as ctx:
            parse_openqasm3(bad)
        self.assertEqual(ctx.exception.line, 3)

    def test_parse_rejects_duplicate_operands(self) -> None:
        bad = "OPENQASM 3.0;\nqubit[2] q;\ncx q[0], q[0];\n"
        with self.assertRaises(QasmParseError):
            parse_openqasm3(bad)

    def test_parse_rejects_unsupported_gate(self) -> None:
        bad = "OPENQASM 3.0;\nqubit[2] q;\nfoo q[0];\n"
        with self.assertRaises(QasmParseError):
            parse_openqasm3(bad)

    def test_all_to_all_needs_zero_swaps(self) -> None:
        res = transpile_local(QFT_4, self.topologies["ionq_forte_clique"], opt_level=2)
        self.assertEqual(res["inserted_swaps"], 0)
        self.assertIn("ms", res["final_qasm"])
        self.assertEqual(res["compiler"], "builtin")

    def test_linear_chain_inserts_swaps_for_qft(self) -> None:
        res = transpile_local(QFT_4, self.topologies["linear_chain_12"], opt_level=2, layout_strategy="trivial")
        self.assertGreater(res["inserted_swaps"], 0)
        self.assertEqual(len(res["stages"]), 5)

    def test_ccx_expansion_and_heavy_hex_cz_basis(self) -> None:
        res = transpile_local(GROVER_CCX, self.topologies["ibm_heron_r3_patch"], opt_level=2)
        self.assertIn("cz", res["final_qasm"])
        self.assertNotIn("ccx ", res["final_qasm"])
        self.assertNotIn("cx ", res["final_qasm"])

    def test_optimization_cancels_inverses_and_merges_rz(self) -> None:
        redundant = "OPENQASM 3.0;\nqubit[2] q;\nx q[0];\nx q[0];\nrz(pi/2) q[1];\nrz(pi/2) q[1];\n"
        o0 = transpile_local(redundant, self.topologies["linear_chain_12"], opt_level=0)
        o2 = transpile_local(redundant, self.topologies["linear_chain_12"], opt_level=2)
        self.assertLess(o2["final_metrics"]["total_gates"], o0["final_metrics"]["total_gates"])

    def test_braket_ionq_forte_exact_cost(self) -> None:
        cost = estimate_job_cost(self.topologies["ionq_forte_clique"], self.pricing, shots=10000, circuit_depth=12)
        self.assertTrue(cost["is_exact_formula"])
        self.assertAlmostEqual(cost["estimated_cost_usd"], 800.30, places=2)

    def test_braket_iqm_garnet_exact_cost(self) -> None:
        cost = estimate_job_cost(self.topologies["iqm_garnet_grid"], self.pricing, shots=10000, circuit_depth=12)
        self.assertAlmostEqual(cost["estimated_cost_usd"], 14.80, places=2)

    def test_ibm_payg_and_open_tier_costs(self) -> None:
        c_open = estimate_job_cost(self.topologies["ibm_heron_r3_patch"], self.pricing, shots=4000, circuit_depth=20, ibm_tier="open")
        c_payg = estimate_job_cost(self.topologies["ibm_heron_r3_patch"], self.pricing, shots=4000, circuit_depth=20, ibm_tier="payg")
        self.assertEqual(c_open["estimated_cost_usd"], 0.0)
        self.assertGreater(c_payg["estimated_cost_usd"], 0.0)
        self.assertFalse(c_payg["is_exact_formula"])

    def test_fidelity_monotonic_decay(self) -> None:
        f_small = estimate_fidelity(5, 2, 0.00025, 0.00215)
        f_large = estimate_fidelity(50, 40, 0.00025, 0.00215)
        self.assertGreater(f_small, f_large)

    def test_cache_key_determinism_and_lru_eviction(self) -> None:
        k1 = compute_cache_key(GHZ_3, "ibm_heron_r3_patch", "qiskit", 2, "degree_aware")
        k2 = compute_cache_key(GHZ_3, "ibm_heron_r3_patch", "pytket", 2, "degree_aware")
        self.assertNotEqual(k1, k2)
        cache = ResultCache(max_entries=2, redis_url="")
        self.assertEqual(cache.backend_name, "memory_lru")
        cache.set("a", {"v": 1})
        cache.set("b", {"v": 2})
        self.assertEqual(cache.get("a"), {"v": 1})
        cache.set("c", {"v": 3})  # evicts "b"
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("c"), {"v": 3})

    def test_rate_limiter_enforces_sliding_window(self) -> None:
        rl = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0)
        self.assertTrue(rl.allow("10.0.0.1", now=100.0))
        self.assertTrue(rl.allow("10.0.0.1", now=101.0))
        self.assertFalse(rl.allow("10.0.0.1", now=102.0))
        self.assertTrue(rl.allow("10.0.0.1", now=111.0))

    def test_worker_executes_and_enforces_timeout(self) -> None:
        res = run_with_timeout(transpile_local, GHZ_3, self.topologies["ibm_heron_r3_patch"], timeout_seconds=5.0)
        self.assertEqual(res["target_id"], "ibm_heron_r3_patch")
        with self.assertRaises(TranspileTimeoutError):
            run_with_timeout(_slow_job, timeout_seconds=0.15)


if __name__ == "__main__":
    unittest.main()
