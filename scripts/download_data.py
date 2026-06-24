"""
download_data.py — Download historical OHLCV data for all eligible symbols.

Usage:
    python scripts/download_data.py [--config CONFIG_DIR] [--days 730]
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.data_ingestion import download_all_symbols
from src.utils import setup_logging

logger = setup_logging("download_data")


def main():
    parser = argparse.ArgumentParser(description="Download OHLCV data")
    parser.add_argument("--config", default="config", help="Config directory")
    parser.add_argument("--days", type=int, default=730, help="Days of history")
    parser.add_argument("--full", action="store_true", help="Full re-download")
    args = parser.parse_args()

    config = load_config(args.config)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=args.days)

    logger.info(f"Downloading {args.days} days of data ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")

    results = download_all_symbols(
        config, start_date=start_date, end_date=end_date,
        incremental=not args.full
    )

    # Summary
    ok = sum(1 for v in results.values() if v == "ok")
    skipped = sum(1 for v in results.values() if v == "skipped")
    errors = sum(1 for v in results.values() if v in ("error", "no_data"))
    print(f"\nDownload complete: {ok} downloaded, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
