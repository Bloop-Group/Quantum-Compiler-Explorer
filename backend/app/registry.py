"""Hardware topology and cloud pricing registry loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_topologies() -> dict[str, dict[str, Any]]:
    raw = json.loads((DATA_DIR / "topologies.json").read_text(encoding="utf-8"))
    return {item["id"]: item for item in raw}


def load_pricing() -> dict[str, Any]:
    return json.loads((DATA_DIR / "pricing.json").read_text(encoding="utf-8"))
