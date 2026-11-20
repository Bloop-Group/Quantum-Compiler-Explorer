"""Validates topologies.json and pricing.json referential integrity."""

from __future__ import annotations

import json
from pathlib import Path
import sys

DATA = Path(__file__).resolve().parent.parent / "backend" / "data"
topologies = json.loads((DATA / "topologies.json").read_text(encoding="utf-8"))
pricing = json.loads((DATA / "pricing.json").read_text(encoding="utf-8"))

providers = pricing.get("providers", {})
assert len(topologies) >= 4, "Expected at least 4 reference topologies"

for t in topologies:
    tid = t["id"]
    assert t["pricing_provider"] in providers, f"{tid}: unknown pricing_provider {t['pricing_provider']}"
    node_ids = {n["id"] for n in t["nodes"]}
    assert len(node_ids) == t["patch_qubits"], f"{tid}: node count mismatch"
    for u, v in t["edges"]:
        assert u in node_ids and v in node_ids, f"{tid}: edge ({u},{v}) references missing node"

print(f"OK: verified {len(topologies)} topologies and {len(providers)} pricing providers.")
