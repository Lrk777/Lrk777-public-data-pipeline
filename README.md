# public-data-pipeline

Reproducible **ingest → validate → clean → warehouse → query** pipeline for **Toronto daily weather** from the public [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (no API key).

## Problem

Can we turn a messy public weather extract into **analysis-ready tables** with a documented schema, then answer concrete climate questions with SQL — without a cloud warehouse or Airflow?

## Demo

```text
$ python -m src.run_all

── 1/3 ingest ──
Downloaded 731 daily rows
── 2/3 transform ──
Cleaned 731 → 731 rows → Parquet + DuckDB (daily_weather)
── 3/3 query ──

# Wettest months (top of q2)
 year  month  total_precip_mm  precip_days  avg_temp_c
 2024      4            168.0           18        7.74
 2023      7            126.2           25       21.75
 2023      6            116.3           13       18.79
```

One command: `python -m src.run_all` (or `--fixture` for offline).  
Query JSON lands in `reports/query_results.json`.

## Method

1. **Ingest** — GET Open-Meteo `/v1/archive` for Toronto (43.65°N, 79.38°W), daily temps / precip / wind / weather code, date range from `configs/default.yaml`.
2. **Validate (raw)** — Pandera checks required columns and non-negative precip/wind.
3. **Transform** — rename to analysis-friendly names, parse dates, drop duplicate days, fix inverted min/max, impute rare nulls with column median, derive `is_precip_day`, `is_freezing`, `temp_range_c`, calendar fields.
4. **Validate (clean)** — strict Pandera schema on the warehouse table.
5. **Load** — write **Parquet** + **DuckDB** (`daily_weather`).
6. **Query** — three SQL answers (monthly means, wettest months, freezing nights).

Offline path: `python -m src.run_all --fixture` uses `tests/fixtures/raw_sample.csv`.

## Results (live run, 2023-01-01 → 2024-12-31)

**Q1 — Monthly mean temperature (°C)** — seasonal cycle is clear (Jul ~22°C; Jan ~−1 to −2°C). Full table in `reports/query_results.json`.

**Q2 — Wettest months**

| Year | Month | Total precip (mm) | Precip days | Avg temp (°C) |
|------|-------|-------------------|-------------|----------------|
| 2024 | Apr | 168.0 | 18 | 7.74 |
| 2023 | Jul | 126.2 | 25 | 21.75 |
| 2023 | Jun | 116.3 | 13 | 18.79 |
| 2023 | Apr | 109.2 | 19 | 8.02 |
| 2024 | Jan | 107.2 | 19 | −1.94 |
| 2023 | Aug | 104.4 | 16 | 19.82 |

**Q3 — Freezing nights (temp_min ≤ 0°C), Nov–Mar** — Jan/Feb typically 25–27 freezing nights; Nov 2024 was unusually mild (only 3).

### What changed: raw → clean

| Raw (Open-Meteo) | Clean warehouse |
|------------------|-----------------|
| `time`, `temperature_2m_*`, `precipitation_sum`, … | `date`, `temp_max_c` / `temp_min_c` / `temp_mean_c`, `precip_mm`, … |
| Nested JSON daily block | Flat Parquet + DuckDB table |
| No calendar dims | `year`, `month`, `dow` |
| No quality flags | `is_precip_day`, `is_freezing`, `temp_range_c` |
| Occasional inverted min/max or dup dates | Corrected / deduped (counts logged) |

## Data dictionary (clean `daily_weather`)

| Column | Type | Meaning |
|--------|------|---------|
| `date` | date | Local calendar day (America/Toronto) |
| `year`, `month`, `dow` | int | Calendar helpers (`dow`: Mon=0) |
| `temp_max_c`, `temp_min_c`, `temp_mean_c` | float | Daily 2 m temperatures (°C) |
| `precip_mm` | float | Total precipitation (mm) |
| `rain_mm` | float | Rain portion (mm) |
| `snow_cm` | float | Snowfall sum (cm, as provided by Open-Meteo) |
| `wind_max_kmh` | float | Max 10 m wind speed (km/h) |
| `weather_code` | int | WMO weather interpretation code |
| `is_precip_day` | bool | `precip_mm > 0.1` |
| `is_freezing` | bool | `temp_min_c ≤ 0` |
| `temp_range_c` | float | `temp_max_c − temp_min_c` (≥ 0) |
| `location` | str | Config location name |
| `source` | str | `open-meteo-historical` |

## Stack

- Python 3.11+
- pandas, PyYAML, requests, pandera, pyarrow, DuckDB, pytest

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

# Full live pipeline (needs network once)
python -m src.run_all

# Or step-by-step
python -m src.ingest
python -m src.transform
python -m src.query_examples

# Offline / CI
python -m src.run_all --fixture
pytest -q
```

Config: `configs/default.yaml` (lat/lon, date range, paths).

## Limitations

- **Point location, not a city average** — one lat/lon near downtown Toronto; not a multi-station blend.
- **Reanalysis / model-backed archive** — Open-Meteo historical values are not raw station observations; good for demos and trends, not legal climate attribution.
- **No streaming / orchestration** — local scripts only (intentional MVP).
- **Null imputation** is median-based and rare; not a full QC system.
- Live results can shift slightly if Open-Meteo revises archive fields; pin dates in config and re-run.

## License

MIT for this repository’s code.  
Weather data: **© Open-Meteo.com** under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — attribution required (see config `source.attribution`).

## Cite

- Zippenfenig, P. (2023). Open-Meteo.com Weather API. https://open-meteo.com/
- WMO weather interpretation codes as documented by Open-Meteo.
