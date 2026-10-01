"""Download Open-Meteo historical daily weather (or load a local fixture)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

from src.config import load_config
from src.schema import validate_raw

USER_AGENT = "public-data-pipeline/0.1 (+https://github.com/Lrk777/public-data-pipeline)"


def fetch_open_meteo(cfg: dict) -> dict:
    loc = cfg["location"]
    dr = cfg["date_range"]
    params = {
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "start_date": dr["start_date"],
        "end_date": dr["end_date"],
        "daily": ",".join(cfg["daily_variables"]),
        "timezone": loc["timezone"],
    }
    url = cfg["source"]["url"]
    resp = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "daily" not in payload:
        raise ValueError(f"Unexpected Open-Meteo response keys: {list(payload)}")
    return payload


def daily_json_to_frame(payload: dict) -> pd.DataFrame:
    daily = payload["daily"]
    if "time" not in daily:
        raise ValueError("Open-Meteo daily block missing 'time'")
    df = pd.DataFrame(daily).rename(columns={"time": "date"})
    return df


def load_fixture_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError(f"Fixture missing 'date' column: {path}")
    return df


def write_raw(df: pd.DataFrame, cfg: dict, payload: dict | None = None) -> Path:
    paths = cfg["paths"]
    raw_dir = Path(paths["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    csv_path = Path(paths["raw_csv"])
    df.to_csv(csv_path, index=False)

    json_path = Path(paths["raw_json"])
    if payload is not None:
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    else:
        # Reconstruct a minimal archive-shaped payload for provenance
        cols = [c for c in df.columns if c != "date"]
        archive = {
            "latitude": cfg["location"]["latitude"],
            "longitude": cfg["location"]["longitude"],
            "timezone": cfg["location"]["timezone"],
            "source": "fixture",
            "daily": {"time": df["date"].astype(str).tolist()},
        }
        for c in cols:
            archive["daily"][c] = df[c].tolist()
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2)

    return csv_path


def run_ingest(cfg: dict, *, use_fixture: bool | None = None) -> pd.DataFrame:
    fixture = cfg.get("use_fixture", False) if use_fixture is None else use_fixture
    payload = None
    if fixture:
        df = load_fixture_csv(cfg["fixture_path"])
        print(f"Loaded fixture: {cfg['fixture_path']} ({len(df)} rows)")
    else:
        print(
            f"Fetching Open-Meteo archive for {cfg['location']['name']} "
            f"{cfg['date_range']['start_date']} → {cfg['date_range']['end_date']} ..."
        )
        payload = fetch_open_meteo(cfg)
        df = daily_json_to_frame(payload)
        print(f"Downloaded {len(df)} daily rows")

    validate_raw(df)
    path = write_raw(df, cfg, payload=payload)
    print(f"Wrote raw CSV → {path}")
    print(f"Attribution: {cfg['source']['attribution']}")
    return df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest Open-Meteo daily weather")
    parser.add_argument("--config", default=None, help="Path to YAML config")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use checked-in fixture instead of live API",
    )
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    run_ingest(cfg, use_fixture=True if args.fixture else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
