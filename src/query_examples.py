"""Run three documented analytical queries against the clean DuckDB warehouse."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

from src.config import load_config

QUERIES = {
    "q1_monthly_mean_temp": {
        "question": "What was the monthly mean temperature (°C) in Toronto for 2023–2024?",
        "sql": """
            SELECT year, month,
                   ROUND(AVG(temp_mean_c), 2) AS avg_temp_c,
                   ROUND(AVG(temp_max_c), 2) AS avg_max_c,
                   ROUND(AVG(temp_min_c), 2) AS avg_min_c,
                   COUNT(*) AS n_days
            FROM daily_weather
            GROUP BY year, month
            ORDER BY year, month
        """,
    },
    "q2_wettest_months": {
        "question": "Which months had the highest total precipitation?",
        "sql": """
            SELECT year, month,
                   ROUND(SUM(precip_mm), 1) AS total_precip_mm,
                   SUM(CASE WHEN is_precip_day THEN 1 ELSE 0 END) AS precip_days,
                   ROUND(AVG(temp_mean_c), 2) AS avg_temp_c
            FROM daily_weather
            GROUP BY year, month
            ORDER BY total_precip_mm DESC
            LIMIT 6
        """,
    },
    "q3_freezing_vs_mild": {
        "question": (
            "How many freezing nights (temp_min ≤ 0°C) occurred per winter-ish month, "
            "and what was the average daily temperature range on those days?"
        ),
        "sql": """
            SELECT year, month,
                   SUM(CASE WHEN is_freezing THEN 1 ELSE 0 END) AS freezing_nights,
                   COUNT(*) AS n_days,
                   ROUND(
                     AVG(CASE WHEN is_freezing THEN temp_range_c END), 2
                   ) AS avg_range_on_freezing_days_c,
                   ROUND(AVG(temp_range_c), 2) AS avg_range_all_days_c
            FROM daily_weather
            WHERE month IN (11, 12, 1, 2, 3)
            GROUP BY year, month
            ORDER BY year, month
        """,
    },
}


def run_queries(cfg: dict) -> dict:
    db_path = Path(cfg["paths"]["clean_duckdb"])
    if not db_path.exists():
        raise FileNotFoundError(
            f"DuckDB warehouse missing at {db_path}. Run transform first."
        )

    con = duckdb.connect(str(db_path), read_only=True)
    results: dict = {
        "source": cfg["source"],
        "location": cfg["location"],
        "date_range": cfg["date_range"],
        "answers": {},
    }

    for key, spec in QUERIES.items():
        df: pd.DataFrame = con.execute(spec["sql"]).fetchdf()
        print(f"\n=== {key} ===")
        print(spec["question"])
        print(df.to_string(index=False))
        results["answers"][key] = {
            "question": spec["question"],
            "sql": spec["sql"].strip(),
            "rows": json.loads(df.to_json(orient="records")),
        }

    con.close()

    out_path = Path(cfg["paths"]["query_results"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote query results → {out_path}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query clean weather DuckDB")
    parser.add_argument("--config", default=None, help="Path to YAML config")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    run_queries(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
