"""Clean / normalize raw daily weather into analysis-ready tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

from src.config import load_config
from src.schema import validate_clean, validate_raw

RAW_TO_CLEAN = {
    "temperature_2m_max": "temp_max_c",
    "temperature_2m_min": "temp_min_c",
    "temperature_2m_mean": "temp_mean_c",
    "precipitation_sum": "precip_mm",
    "rain_sum": "rain_mm",
    "snowfall_sum": "snow_cm",
    "windspeed_10m_max": "wind_max_kmh",
    "weathercode": "weather_code",
}


def clean_frame(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    validate_raw(raw)
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    if df["date"].isna().any():
        bad = int(df["date"].isna().sum())
        raise ValueError(f"{bad} rows have unparseable dates")

    # Drop exact duplicate dates (keep first)
    before = len(df)
    df = df.drop_duplicates(subset=["date"], keep="first").sort_values("date")
    dropped_dupes = before - len(df)

    rename = {k: v for k, v in RAW_TO_CLEAN.items() if k in df.columns}
    df = df.rename(columns=rename)

    for col in [
        "temp_max_c",
        "temp_min_c",
        "temp_mean_c",
        "precip_mm",
        "rain_mm",
        "snow_cm",
        "wind_max_kmh",
    ]:
        if col not in df.columns:
            raise ValueError(f"Missing expected column after rename: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Impute rare null measures with column median (documented in README)
    null_counts = {c: int(df[c].isna().sum()) for c in [
        "temp_max_c", "temp_min_c", "temp_mean_c",
        "precip_mm", "rain_mm", "snow_cm", "wind_max_kmh",
    ]}
    for col, n in null_counts.items():
        if n:
            df[col] = df[col].fillna(df[col].median())

    if "weather_code" not in df.columns:
        df["weather_code"] = 0
    df["weather_code"] = (
        pd.to_numeric(df["weather_code"], errors="coerce").fillna(0).astype(int)
    )

    # Physical sanity: swap min/max if inverted
    inverted = df["temp_min_c"] > df["temp_max_c"]
    n_inv = int(inverted.sum())
    if n_inv:
        tmax = df.loc[inverted, "temp_max_c"].copy()
        df.loc[inverted, "temp_max_c"] = df.loc[inverted, "temp_min_c"]
        df.loc[inverted, "temp_min_c"] = tmax

    df["year"] = df["date"].dt.year.astype(int)
    df["month"] = df["date"].dt.month.astype(int)
    df["dow"] = df["date"].dt.dayofweek.astype(int)
    df["temp_range_c"] = (df["temp_max_c"] - df["temp_min_c"]).clip(lower=0)
    df["is_precip_day"] = df["precip_mm"] > 0.1
    df["is_freezing"] = df["temp_min_c"] <= 0.0
    df["location"] = cfg["location"]["name"]
    df["source"] = cfg["source"]["name"]

    # date as python date for pandera Date dtype
    df["date"] = df["date"].dt.date

    ordered = [
        "date",
        "year",
        "month",
        "dow",
        "temp_max_c",
        "temp_min_c",
        "temp_mean_c",
        "precip_mm",
        "rain_mm",
        "snow_cm",
        "wind_max_kmh",
        "weather_code",
        "is_precip_day",
        "is_freezing",
        "temp_range_c",
        "location",
        "source",
    ]
    clean = df[ordered].reset_index(drop=True)
    validate_clean(clean)

    meta = {
        "rows_in": before,
        "rows_out": len(clean),
        "duplicate_dates_dropped": dropped_dupes,
        "inverted_minmax_fixed": n_inv,
        "nulls_imputed": {k: v for k, v in null_counts.items() if v},
    }
    clean.attrs["transform_meta"] = meta
    return clean


def write_outputs(clean: pd.DataFrame, cfg: dict) -> dict[str, Path]:
    import shutil
    import tempfile

    paths = cfg["paths"]
    clean_dir = Path(paths["clean_dir"])
    clean_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = Path(paths["clean_parquet"])
    # Write with date as datetime for Parquet friendliness
    out = clean.copy()
    out["date"] = pd.to_datetime(out["date"])
    out.to_parquet(parquet_path, index=False)

    duckdb_path = Path(paths["clean_duckdb"])
    # Build DuckDB on a local temp filesystem, then copy — some network/FUSE
    # mounts reject DuckDB checkpoint writes even for tiny DBs.
    for stale in (duckdb_path, Path(str(duckdb_path) + ".wal")):
        if stale.exists():
            stale.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "toronto_weather.duckdb"
        con = duckdb.connect(str(tmp_db))
        con.execute("CREATE TABLE daily_weather AS SELECT * FROM out")
        con.execute("CHECKPOINT")
        con.close()
        shutil.copy2(tmp_db, duckdb_path)

    return {"parquet": parquet_path, "duckdb": duckdb_path}


def run_transform(cfg: dict, raw: pd.DataFrame | None = None) -> pd.DataFrame:
    if raw is None:
        raw_csv = Path(cfg["paths"]["raw_csv"])
        if not raw_csv.exists():
            raise FileNotFoundError(
                f"Raw CSV not found at {raw_csv}. Run ingest first "
                "(python -m src.ingest) or pass --fixture."
            )
        raw = pd.read_csv(raw_csv)

    clean = clean_frame(raw, cfg)
    meta = clean.attrs.get("transform_meta", {})
    written = write_outputs(clean, cfg)
    print(
        f"Cleaned {meta.get('rows_in')} → {meta.get('rows_out')} rows "
        f"(dupes dropped={meta.get('duplicate_dates_dropped')}, "
        f"minmax fixed={meta.get('inverted_minmax_fixed')})"
    )
    print(f"Parquet → {written['parquet']}")
    print(f"DuckDB  → {written['duckdb']}  (table: daily_weather)")
    return clean


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transform raw weather → clean tables")
    parser.add_argument("--config", default=None, help="Path to YAML config")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    run_transform(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
