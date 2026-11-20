# Contributing to Quantum Compiler Explorer

Thank you for your interest in contributing to Quantum Compiler Explorer! We welcome contributions to compiler adapters, hardware topologies, pricing models, visualizations, and documentation.

## Development Workflow

### Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- Docker (optional, for containerized local bring-up)

### Backend Setup & Testing
1. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
2. Verify hardware and pricing registry schemas:
   ```bash
   python scripts/verify_registries.py
   ```
3. Run test suites with coverage:
   ```bash
   pytest backend/tests --cov=backend/app --cov-report=term-missing
   ```

### Frontend Setup & Build
1. Install Node dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Run development server:
   ```bash
   npm run dev
   ```
3. Run strict TypeScript check and production build:
   ```bash
   npm run build
   ```

### Adding a New Compiler Adapter
1. Add an adapter under `backend/app/compilers/<name>_adapter.py`.
2. Follow the normalized schema returned by `qiskit_adapter.py`, `pytket_adapter.py`, and `cirq_adapter.py`:
   - `compiler`, `target_id`, `logical_metrics`, `initial_layout`, `final_layout`
   - `edge_usage`, `swap_edges`, `inserted_swaps`
   - `stages[]` with `stage`, `label`, `qasm`, `metrics`, `ops[]`
   - `final_metrics`, `final_qasm`
3. Register the compiler in `backend/app/main.py` and `frontend/src/types/compiler.ts`.
4. Add unit and integration tests in `backend/tests/`.

### Code Style & Guidelines
- Follow PEP 8 and use type annotations for all Python code.
- Ensure strict TypeScript compilation without errors or warnings.
- Keep security in mind: all compiler jobs run in isolated subprocesses with timeouts.
