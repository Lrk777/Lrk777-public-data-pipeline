"""Transform hygiene tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import load_config
from src.transform import clean_frame, run_transform
from src.ingest import run_ingest
from src.query_examples import run_queries

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_drops_duplicate_dates_and_fixes_inverted_minmax():
    cfg = load_config()
    raw = pd.read_csv(FIXTURES / "raw_sample.csv")
    # Fixture intentionally has 101 rows with one duplicate date
    assert len(raw) == 101
    clean = clean_frame(raw, cfg)
    meta = clean.attrs["transform_meta"]
    assert meta["duplicate_dates_dropped"] >= 1
    assert meta["inverted_minmax_fixed"] >= 1
    assert (clean["temp_min_c"] <= clean["temp_max_c"]).all()
    assert clean["date"].is_unique
    assert len(clean) == 100


def test_derived_flags():
    cfg = load_config()
    raw = pd.read_csv(FIXTURES / "raw_sample.csv")
    clean = clean_frame(raw, cfg)
    assert set(clean["is_precip_day"].unique()).issubset({True, False})
    assert (clean["temp_range_c"] >= 0).all()
    assert (clean.loc[clean["temp_min_c"] <= 0, "is_freezing"]).all()


def test_fixture_pipeline_end_to_end(tmp_path, monkeypatch):
    """Offline: ingest fixture → transform → query writes JSON."""
    cfg = load_config()
    # Redirect outputs into tmp so we don't clobber demo artifacts mid-test
    cfg = {
        **cfg,
        "paths": {
            **cfg["paths"],
            "raw_dir": str(tmp_path / "raw"),
            "clean_dir": str(tmp_path / "clean"),
            "reports_dir": str(tmp_path / "reports"),
            "raw_json": str(tmp_path / "raw" / "toronto.json"),
            "raw_csv": str(tmp_path / "raw" / "toronto.csv"),
            "clean_parquet": str(tmp_path / "clean" / "toronto.parquet"),
            "clean_duckdb": str(tmp_path / "clean" / "toronto.duckdb"),
            "query_results": str(tmp_path / "reports" / "query_results.json"),
        },
        "fixture_path": str(FIXTURES / "raw_sample.csv"),
    }
    run_ingest(cfg, use_fixture=True)
    clean = run_transform(cfg)
    assert len(clean) == 100
    results = run_queries(cfg)
    assert "q1_monthly_mean_temp" in results["answers"]
    assert "q2_wettest_months" in results["answers"]
    assert "q3_freezing_vs_mild" in results["answers"]
    assert Path(cfg["paths"]["query_results"]).exists()
    assert Path(cfg["paths"]["clean_parquet"]).exists()
