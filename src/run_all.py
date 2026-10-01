"""One-command DAG: ingest → transform → query."""

from __future__ import annotations

import argparse
import sys

from src.config import load_config
from src.ingest import run_ingest
from src.query_examples import run_queries
from src.transform import run_transform


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run full public-data-pipeline (ingest → transform → query)"
    )
    parser.add_argument("--config", default=None, help="Path to YAML config")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use checked-in fixture instead of live Open-Meteo API",
    )
    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    print("── 1/3 ingest ──")
    run_ingest(cfg, use_fixture=True if args.fixture else None)
    print("── 2/3 transform ──")
    run_transform(cfg)
    print("── 3/3 query ──")
    run_queries(cfg)
    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
