# Quantum Compiler Explorer

[![CI](https://github.com/quantum-compiler-explorer/quantum-compiler-explorer/actions/workflows/ci.yml/badge.svg)](https://github.com/quantum-compiler-explorer/quantum-compiler-explorer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-blue.svg)](https://react.dev/)

A browser-first **"Godbolt for Quantum"** workbench for inspecting pass-by-pass OpenQASM 3 transpilation, SWAP-gate routing overhead, chip coupling-map heatmaps, unitary mathematical equivalence, and pre-flight cloud QPU costs across **Qiskit, pytket, Google Cirq, and Builtin** reference compilers.

---

## Key Features

1. **Multi-SDK Side-by-Side Inspection:**
   - Compare compilation across **IBM Qiskit 1.4/2.x**, **Quantinuum pytket 2.18+**, **Google Cirq 1.7+**, and a deterministic **Builtin** engine.
   - Scrub through individual pass stages (Logical IR, Initial Placement, SWAP Routing, Native Basis Translation, and Peephole Optimization $O_0$ to $O_3$).
2. **Interactive Hardware Visualizations:**
   - **Interactive SVG Circuit Diagrams:** Visual gate ordering and SWAP decomposition.
   - **Chip Coupling-Map Heatmaps:** Highlights physical layout and hot two-qubit SWAP routing links across real 2026 architectures (IBM Heron r3 heavy-hex, IBM Nighthawk r2 square grid, IonQ Forte all-to-all clique, IQM Garnet grid, and Linear chains).
3. **Automated Unitary Equivalence Checking:**
   - Confirms mathematical equivalence between compilers ($|\langle \psi_A | \psi_B \rangle|^2 = 1.0$) using operator matrix and statevector analysis to catch cross-SDK compiler regressions ([ISSTA 2026 IterTestQ](https://software-lab.org/publications/issta2026_IterTestQ.pdf)).
4. **Pre-Flight Fidelity & Cloud Cost Math:**
   - Real-time cloud pricing based on verified November 2026 billing formulas (IBM per-minute runtime tiers: Pay-As-You-Go, Flex, Premium; AWS Braket per-task + per-shot pricing for IonQ Forte and IQM Garnet; Azure Quantum).
   - Fidelity decay estimates driven by verified two-qubit hardware error rates.
5. **Zero-Setup Shareable Permalinks:**
   - Full workspace state (code, target selections, shots, optimization levels) compressed into URL hash using `lz-string`.
6. **Production-Hardened Security & Sandboxing:**
   - OpenQASM 3 AST pre-screen blocking forbidden imports, calls, and null bytes (`app/ast_security.py`).
   - Per-job wall-clock subprocess timeout isolation (`TRANSPILE_TIMEOUT_SEC=15.0`) over OS pipes.
   - Sliding-window per-client rate limiting (`RATE_LIMIT_MAX_REQ=90` req/min).
   - Multi-tier content-addressed Redis 7 cache with in-memory LRU fallback.
   - Prometheus metrics endpoint (`/metrics`) and structured JSON logging.

---

## Quick Start (Docker Compose)

Launch the full stack (Redis 7 cache, multi-worker FastAPI backend, multi-stage Nginx frontend):

```bash
docker compose up --build
```

- **Frontend Workbench:** [http://localhost:5173](http://localhost:5173)
- **Backend API & Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Prometheus Metrics:** [http://localhost:8000/metrics](http://localhost:8000/metrics)

---

## Local Development & Testing

### Backend
```bash
# Verify hardware and pricing schemas
python scripts/verify_registries.py

# Run all unit and integration tests with coverage
pytest backend/tests --cov=backend/app --cov-report=term-missing
```

### Frontend
```bash
cd frontend
npm install
npm run build
npm run dev
```

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service health status and active cache backend (`redis` or `memory_lru`) |
| `GET` | `/api/v1/targets` | List reference hardware topologies and pricing provider specs |
| `POST` | `/api/v1/transpile` | Transpile an OpenQASM 3 circuit to a specified compiler and topology |
| `POST` | `/api/v1/compare` | Transpile Target A vs. Target B and compute SWAP deltas, cost, and equivalence |
| `POST` | `/api/v1/verify_equivalence` | Check mathematical unitary equivalence between two circuits (up to 10Q) |
| `GET` | `/metrics` | Prometheus metrics (request counters, p95 durations, cache hit ratio) |

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Browser Client                       │
│    Monaco Editor + React 18 + TypeScript + Tailwind    │
│    (Circuit SVG, Chip Heatmap, QASM Diff, Permalinks)  │
└───────────────────────────┬────────────────────────────┘
                            │ Nginx Reverse Proxy (:80)
                            ▼
┌────────────────────────────────────────────────────────┐
│               FastAPI API Gateway (:8000)               │
│  - AST Security Screen (app/ast_security.py)           │
│  - Sliding-Window Rate Limiter (app/rate_limit.py)     │
│  - Redis 7 Content-Addressed Cache (app/cache.py)      │
│  - Prometheus Metrics & JSON Logs (app/metrics.py)     │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       Subprocess Isolation     Subprocess Isolation
        (app/worker.py)          (app/worker.py)
                ▼                        ▼
┌──────────────────────────────┐ ┌───────────────────────┐
│     Live Compiler Pool       │ │  Equivalence Engine   │
│ - Builtin (Deterministic)    │ │ - Qiskit Operator     │
│ - IBM Qiskit 1.4/2.x         │ │ - Statevector Overlap │
│ - Quantinuum pytket 2.18+    │ └───────────────────────┘
│ - Google Cirq 1.7+           │
└──────────────────────────────┘
```

---

## Documentation

- [`docs/THESIS.md`](docs/THESIS.md): Full motivation and vision for a Godbolt-grade Quantum Compiler Explorer.
- [`docs/TECH_SPEC_AND_PLAN.md`](docs/TECH_SPEC_AND_PLAN.md): Technical specification, data structures, and coverage report.
- [`docs/RESEARCH_NOTES.md`](docs/RESEARCH_NOTES.md): Verified compiler APIs, 2026 QPU topologies, and cloud pricing formulas.
- [`docs/PLAN_MVP_100.md`](docs/PLAN_MVP_100.md): Roadmap for 100% MVP coverage.
- [`docs/PLAN_PRODUCTION_100.md`](docs/PLAN_PRODUCTION_100.md): Production hardening specifications.

---

## Contributing & Security

- Contributions guidelines: see [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Security policy & vulnerability reporting: see [`SECURITY.md`](SECURITY.md).

## License

MIT License. See [`LICENSE`](LICENSE) for details.
