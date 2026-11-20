"""FastAPI entrypoint for the Quantum Compiler Explorer backend."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.ast_security import screen_qasm_input
from app.cache import ResultCache
from app.cost_estimator import estimate_fidelity, estimate_job_cost
from app.equivalence import verify_circuit_equivalence, EquivalenceCheckError
from app.logging_config import setup_logging
from app.metrics import METRICS
from app.qasm_parser import QasmParseError, compute_cache_key, transpile_local
from app.rate_limit import SlidingWindowRateLimiter
from app.registry import load_pricing, load_topologies
from app.worker import TranspileTimeoutError, run_with_timeout

# Initialize logging (JSON in production, standard in development)
setup_logging(json_logs=os.getenv("LOG_FORMAT", "").lower() == "json")

app = FastAPI(title="Quantum Compiler Explorer API", version="1.0.0")

# Production CORS Origin Management
raw_cors = os.getenv("CORS_ORIGINS", "*")
if raw_cors.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOPOLOGIES = load_topologies()
PRICING = load_pricing()
CACHE = ResultCache(max_entries=int(os.getenv("CACHE_MAX_ENTRIES", "512")))
RATE_LIMITER = SlidingWindowRateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_MAX_REQ", "90")),
    window_seconds=float(os.getenv("RATE_LIMIT_WINDOW_SEC", "60")),
)
TRANSPILE_TIMEOUT_SEC = float(os.getenv("TRANSPILE_TIMEOUT_SEC", "15.0"))


class TranspileRequest(BaseModel):
    qasm: str = Field(..., min_length=10, max_length=65536)
    target_id: str = "ibm_heron_r3_patch"
    compiler: str = "builtin"  # builtin | qiskit | pytket | cirq
    opt_level: int = Field(2, ge=0, le=3)
    layout_strategy: str = "degree_aware"
    shots: int = Field(10000, ge=1, le=1000000)
    ibm_tier: str = "payg"


class CompareRequest(BaseModel):
    qasm: str = Field(..., min_length=10, max_length=65536)
    shots: int = Field(10000, ge=1, le=1000000)
    ibm_tier: str = "payg"
    target_a: dict[str, Any]
    target_b: dict[str, Any]
    verify_equivalence: bool = False


class EquivalenceRequest(BaseModel):
    qasm_a: str = Field(..., min_length=10, max_length=65536)
    qasm_b: str = Field(..., min_length=10, max_length=65536)
    max_qubits: int = Field(10, ge=1, le=16)


def _execute_transpile(req: TranspileRequest) -> dict[str, Any]:
    # AST security pre-screen
    sec = screen_qasm_input(req.qasm)
    if not sec.is_safe:
        raise HTTPException(status_code=400, detail={"line": sec.line or 1, "message": sec.reason})

    if req.target_id not in TOPOLOGIES:
        raise HTTPException(status_code=404, detail=f"Unknown target_id: {req.target_id}")
    topology = TOPOLOGIES[req.target_id]
    key = compute_cache_key(req.qasm, req.target_id, req.compiler, req.opt_level, req.layout_strategy)

    t0 = time.time()
    cached = CACHE.get(key)
    if cached is not None:
        result = dict(cached)
        result["cache_hit"] = True
        METRICS.record_transpile(req.compiler, req.target_id, time.time() - t0, cache_hit=True)
    else:
        try:
            if req.compiler == "qiskit":
                from app.compilers.qiskit_adapter import transpile_with_qiskit
                result = run_with_timeout(
                    transpile_with_qiskit,
                    req.qasm,
                    topology,
                    req.opt_level,
                    req.layout_strategy,
                    timeout_seconds=TRANSPILE_TIMEOUT_SEC,
                )
            elif req.compiler == "pytket":
                from app.compilers.pytket_adapter import transpile_with_pytket
                result = run_with_timeout(
                    transpile_with_pytket,
                    req.qasm,
                    topology,
                    req.opt_level,
                    req.layout_strategy,
                    timeout_seconds=TRANSPILE_TIMEOUT_SEC,
                )
            elif req.compiler == "cirq":
                from app.compilers.cirq_adapter import transpile_with_cirq
                result = run_with_timeout(
                    transpile_with_cirq,
                    req.qasm,
                    topology,
                    req.opt_level,
                    req.layout_strategy,
                    timeout_seconds=TRANSPILE_TIMEOUT_SEC,
                )
            else:
                result = run_with_timeout(
                    transpile_local,
                    req.qasm,
                    topology,
                    req.opt_level,
                    req.layout_strategy,
                    timeout_seconds=TRANSPILE_TIMEOUT_SEC,
                )
        except TranspileTimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except QasmParseError as exc:
            raise HTTPException(status_code=400, detail={"line": exc.line, "message": exc.message}) from exc
        except ImportError as exc:
            raise HTTPException(status_code=501, detail=f"Compiler backend not installed: {exc}") from exc

        CACHE.set(key, result)
        result = dict(result)
        result["cache_hit"] = False
        METRICS.record_transpile(req.compiler, req.target_id, time.time() - t0, cache_hit=False)

    metrics = result.get("final_metrics", {})
    depth = int(metrics.get("depth", 0))
    n1 = int(metrics.get("single_qubit_gates", 0))
    n2 = int(metrics.get("two_qubit_gates", 0))
    result["estimated_fidelity"] = round(
        estimate_fidelity(n1, n2, topology["single_qubit_error_rate"], topology["two_qubit_error_rate"]),
        4,
    )
    result["cost_estimate"] = estimate_job_cost(topology, PRICING, req.shots, depth, req.ibm_tier)
    return result


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    METRICS.record_request("GET", "/api/v1/health", 200)
    return {"status": "ok", "cache_backend": CACHE.backend_name}


@app.get("/api/v1/targets")
def list_targets() -> dict[str, Any]:
    METRICS.record_request("GET", "/api/v1/targets", 200)
    return {"targets": list(TOPOLOGIES.values()), "pricing": PRICING}


@app.post("/api/v1/transpile")
def transpile(req: TranspileRequest, request: Request) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "unknown"
    if not RATE_LIMITER.allow(client_ip):
        METRICS.record_rate_limit()
        METRICS.record_request("POST", "/api/v1/transpile", 429)
        raise HTTPException(status_code=429, detail="Rate limit exceeded; please retry shortly.")
    res = _execute_transpile(req)
    METRICS.record_request("POST", "/api/v1/transpile", 200)
    return res


@app.post("/api/v1/compare")
def compare(req: CompareRequest, request: Request) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "unknown"
    if not RATE_LIMITER.allow(client_ip):
        METRICS.record_rate_limit()
        METRICS.record_request("POST", "/api/v1/compare", 429)
        raise HTTPException(status_code=429, detail="Rate limit exceeded; please retry shortly.")

    req_a = TranspileRequest(
        qasm=req.qasm,
        shots=req.shots,
        ibm_tier=req.ibm_tier,
        target_id=req.target_a.get("target_id", "ibm_heron_r3_patch"),
        compiler=req.target_a.get("compiler", "builtin"),
        opt_level=int(req.target_a.get("opt_level", 2)),
        layout_strategy=req.target_a.get("layout_strategy", "degree_aware"),
    )
    req_b = TranspileRequest(
        qasm=req.qasm,
        shots=req.shots,
        ibm_tier=req.ibm_tier,
        target_id=req.target_b.get("target_id", "ionq_forte_clique"),
        compiler=req.target_b.get("compiler", "builtin"),
        opt_level=int(req.target_b.get("opt_level", 2)),
        layout_strategy=req.target_b.get("layout_strategy", "degree_aware"),
    )

    out_a = _execute_transpile(req_a)
    out_b = _execute_transpile(req_b)

    response_payload: dict[str, Any] = {"target_a": out_a, "target_b": out_b}

    if req.verify_equivalence:
        try:
            equiv = verify_circuit_equivalence(out_a.get("final_qasm", ""), out_b.get("final_qasm", ""))
            response_payload["equivalence"] = equiv
        except Exception as exc:
            response_payload["equivalence"] = {
                "equivalent": False,
                "fidelity": 0.0,
                "message": f"Equivalence check skipped: {exc}",
            }

    METRICS.record_request("POST", "/api/v1/compare", 200)
    return response_payload


@app.post("/api/v1/verify_equivalence")
def verify_equivalence_endpoint(req: EquivalenceRequest, request: Request) -> dict[str, Any]:
    client_ip = request.client.host if request.client else "unknown"
    if not RATE_LIMITER.allow(client_ip):
        METRICS.record_rate_limit()
        METRICS.record_request("POST", "/api/v1/verify_equivalence", 429)
        raise HTTPException(status_code=429, detail="Rate limit exceeded; please retry shortly.")
    try:
        res = verify_circuit_equivalence(req.qasm_a, req.qasm_b, max_qubits=req.max_qubits)
        METRICS.record_request("POST", "/api/v1/verify_equivalence", 200)
        return res
    except EquivalenceCheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/metrics")
def metrics() -> Response:
    return Response(
        content=METRICS.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
