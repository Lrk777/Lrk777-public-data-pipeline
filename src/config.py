"""Load and resolve pipeline configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "default.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Resolve relative paths against project root
    paths = cfg.get("paths", {})
    for key, val in list(paths.items()):
        p = Path(val)
        if not p.is_absolute():
            paths[key] = str(ROOT / p)
    cfg["paths"] = paths
    fixture = cfg.get("fixture_path")
    if fixture and not Path(fixture).is_absolute():
        cfg["fixture_path"] = str(ROOT / fixture)
    return cfg
