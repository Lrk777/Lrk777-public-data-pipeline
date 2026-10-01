"""Schema validation tests — broken fixtures must fail."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.errors as pe
import pytest

from src.schema import validate_clean, validate_raw
from src.transform import clean_frame
from src.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_raw_sample_passes_schema():
    df = pd.read_csv(FIXTURES / "raw_sample.csv")
    validated = validate_raw(df)
    assert len(validated) == len(df)


def test_raw_broken_fails_schema():
    df = pd.read_csv(FIXTURES / "raw_broken.csv")
    with pytest.raises((pe.SchemaErrors, pe.SchemaError)):
        validate_raw(df)


def test_clean_schema_rejects_bad_month():
    cfg = load_config()
    raw = pd.read_csv(FIXTURES / "raw_sample.csv")
    clean = clean_frame(raw, cfg)
    bad = clean.copy()
    bad.loc[0, "month"] = 13
    with pytest.raises((pe.SchemaErrors, pe.SchemaError)):
        validate_clean(bad)
