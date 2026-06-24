"""
universe.py — Build and filter the investable universe at any point in time.

Applies filters from universe.yaml:
- Exclude stablecoins and wrapped tokens (done at download time too).
- Require minimum history (min_history_days).
- Require minimum 30-day average daily USD volume.

All filters are point-in-time: for a given date, only data up to that date is used.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config_loader import AppConfig
from src.utils import setup_logging, DATA_DIR

logger = setup_logging("universe")


def load_all_price_data(symbols: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
    """
    Load OHLCV CSVs for all symbols (or a specific list) from data/daily/.

    Returns dict mapping symbol -> DataFrame with 'date' as datetime index.
    """
    if not DATA_DIR.exists():
        logger.warning(f"Data directory does not exist: {DATA_DIR}")
        return {}

    price_data = {}
    csv_files = list(DATA_DIR.glob("*.csv"))

    for csv_path in csv_files:
        symbol = csv_path.stem  # filename without extension
        if symbols and symbol not in symbols:
            continue
        try:
            df = pd.read_csv(csv_path, parse_dates=["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df = df.set_index("date")
            # Ensure numeric columns
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            if not df.empty:
                price_data[symbol] = df
        except Exception as e:
            logger.warning(f"Error loading {csv_path.name}: {e}")

    logger.info(f"Loaded price data for {len(price_data)} symbols")
    return price_data


def filter_universe(price_data: Dict[str, pd.DataFrame],
                    config: AppConfig,
                    as_of_date: datetime) -> List[str]:
    """
    Filter the universe of symbols as of a given date.

    Filters applied (in order):
    1. Symbol must have data up to as_of_date (within 3 days tolerance).
    2. Symbol must have at least min_history_days of data.
    3. 30-day average daily USD volume must be >= min_avg_volume_usd_30d.

    Args:
        price_data: Dict of symbol -> DataFrame (date-indexed OHLCV).
        config: Application configuration.
        as_of_date: The decision date (only use data up to this date).

    Returns:
        Sorted list of symbols that pass all filters.
    """
    uc = config.universe
    eligible = []

    as_of = pd.Timestamp(as_of_date)

    for symbol, df in price_data.items():
        if symbol in ("QQQ", "SPY"):
            continue
        # 1. Must have recent data (within 3 days of as_of_date)
        df_up_to = df[df.index <= as_of]
        if df_up_to.empty:
            continue
        last_date = df_up_to.index[-1]
        if (as_of - last_date).days > 3:
            continue

        # 2. Minimum history
        if len(df_up_to) < uc.min_history_days:
            continue

        # 3. 30-day average daily USD volume
        recent_30d = df_up_to.tail(30)
        if len(recent_30d) < 20:  # need at least 20 of 30 days
            continue

        # Volume in USD = volume * close_price
        avg_vol_usd = (recent_30d["close"] * recent_30d["volume"]).mean()

        if avg_vol_usd < uc.min_avg_volume_usd_30d:
            continue

        eligible.append(symbol)

    logger.info(
        f"Universe as of {as_of_date.strftime('%Y-%m-%d')}: "
        f"{len(eligible)} symbols pass filters (from {len(price_data)} total)"
    )
    return sorted(eligible)


def compute_regime_filters(price_data: Dict[str, pd.DataFrame],
                            eligible_universe: List[str],
                            config: AppConfig,
                            as_of_date: datetime) -> Tuple[bool, float, bool]:
    """
    Compute BTC MA status and market breadth as of a given date.

    Returns:
        btc_above_ma: bool (True if BTC close > BTC 200D MA, or if BTC data missing)
        breadth_pct: float (fraction of eligible universe above their 200D MA)
        breadth_pass: bool (True if breadth_pct >= min_breadth_pct)
    """
    sc = config.strategy
    as_of = pd.Timestamp(as_of_date)

    # 1. BTC MA check
    btc_above_ma = True
    if "BTC" in price_data:
        btc_df = price_data["BTC"]
        btc_up_to = btc_df[btc_df.index <= as_of]
        if len(btc_up_to) >= 200:
            btc_close = float(btc_up_to["close"].iloc[-1])
            btc_ma200 = float(btc_up_to["close"].tail(200).mean())
            btc_above_ma = btc_close > btc_ma200
        else:
            logger.warning("BTC has less than 200 days of history as of this date. Defaulting BTC MA pass to True.")

    # 2. Market breadth check
    above_count = 0
    total_valid = 0
    for symbol in eligible_universe:
        if symbol not in price_data:
            continue
        df = price_data[symbol]
        df_up_to = df[df.index <= as_of]
        if len(df_up_to) >= 200:
            close_price = float(df_up_to["close"].iloc[-1])
            ma200 = float(df_up_to["close"].tail(200).mean())
            if close_price > ma200:
                above_count += 1
            total_valid += 1

    breadth_pct = above_count / total_valid if total_valid > 0 else 1.0
    breadth_pass = breadth_pct >= sc.min_breadth_pct

    return btc_above_ma, breadth_pct, breadth_pass


def get_price_matrix(price_data: Dict[str, pd.DataFrame],
                      symbols: List[str],
                      column: str = "close") -> pd.DataFrame:
    """
    Build a date × symbol matrix for a given column (e.g., 'close').

    Returns DataFrame with DatetimeIndex and symbol columns.
    Missing values are forward-filled (max 5 days) then left as NaN.
    """
    frames = {}
    for sym in symbols:
        if sym in price_data:
            frames[sym] = price_data[sym][column]

    if not frames:
        return pd.DataFrame()

    matrix = pd.DataFrame(frames)
    matrix = matrix.sort_index()
    matrix = matrix.ffill(limit=5)  # forward-fill gaps up to 5 days
    return matrix
