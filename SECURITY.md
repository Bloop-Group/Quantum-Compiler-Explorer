# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Security Architecture & Threat Model

Quantum Compiler Explorer is designed following lessons from Matt Godbolt's Compiler Explorer:
1. **Input Validation:** All input is restricted to declarative OpenQASM 3 circuits (max 64 KB). Null bytes and malformed tokens are rejected at the gateway.
2. **AST Pre-Screen:** Source inputs pass through `backend/app/ast_security.py` prior to compilation, blocking dangerous modules (`os`, `subprocess`, `socket`, `pathlib`) and eval/exec operations.
3. **Subprocess Isolation:** Each compilation job runs in an isolated subprocess with strict wall-clock timeouts (`TRANSPILE_TIMEOUT_SEC=15.0`) via OS pipes to protect against algorithmic complexity attacks.
4. **Container Hardening:** Containers run with non-root user (`qce`), `read_only: true`, ephemeral `/tmp`, `no-new-privileges: true`, and memory/CPU limits.
5. **Abuse Protection:** Sliding-window rate limiting (`RATE_LIMIT_MAX_REQ=90` req/min) prevents API abuse.

## Reporting a Vulnerability

If you discover a security vulnerability, please do NOT open a public issue. Instead, report it privately via email or GitHub Security Advisories.
We will acknowledge your report within 48 hours and work with you on a coordinated disclosure.
