"""Pre-flight cloud QPU cost and gate-error survival fidelity estimator."""

from __future__ import annotations

from typing import Any


def estimate_fidelity(
    single_qubit_gates: int,
    two_qubit_gates: int,
    p_1q: float,
    p_2q: float,
) -> float:
    """Simplified independent gate-error product estimate."""
    n1 = max(0, single_qubit_gates)
    n2 = max(0, two_qubit_gates)
    f = ((1.0 - p_1q) ** n1) * ((1.0 - p_2q) ** n2)
    return max(0.0, min(1.0, f))


def estimate_job_cost(
    topology: dict[str, Any],
    pricing_data: dict[str, Any],
    shots: int,
    circuit_depth: int,
    ibm_tier: str = "payg",
) -> dict[str, Any]:
    """Compute estimated cloud QPU job cost from verified Nov 2026 rate cards."""
    shots = max(1, int(shots))
    provider_key = topology["pricing_provider"]
    provider = pricing_data["providers"][provider_key]

    if provider["model"] == "per_task_plus_shot":
        task_fee = float(provider["per_task_usd"])
        shot_fee = shots * float(provider["per_shot_usd"])
        total = task_fee + shot_fee
        return {
            "provider": provider["label"],
            "model": "per_task_plus_shot",
            "is_exact_formula": True,
            "shots": shots,
            "estimated_seconds": None,
            "estimated_cost_usd": round(total, 4),
            "formula": f"${task_fee:.2f} task + {shots:,} x ${provider['per_shot_usd']:.6f}/shot",
        }

    tiers = provider["tiers"]
    tier_info = tiers.get(ibm_tier) or next(iter(tiers.values()))
    cps = max(1.0, float(topology.get("circuits_per_second", 4000)))
    depth_factor = 1.0 + (max(0, circuit_depth) * 0.005)
    raw_seconds = (shots / cps) * depth_factor + 0.25
    billable_seconds = max(float(provider.get("min_billable_seconds", 1.0)), raw_seconds)
    rate_per_min = float(tier_info["rate_per_min"])
    total = (billable_seconds / 60.0) * rate_per_min
    return {
        "provider": tier_info["label"],
        "model": "per_minute",
        "is_exact_formula": False,
        "shots": shots,
        "estimated_seconds": round(billable_seconds, 2),
        "estimated_cost_usd": round(total, 4),
        "formula": f"~{billable_seconds:.2f}s est. runtime @ ${rate_per_min:.2f}/min",
    }
