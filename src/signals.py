"""
signals.py — Compute cross-sectional momentum signals (R30, R7) and rankings.

For each coin in the filtered universe on a given decision date:
- R30 = close(t) / close(t-30) - 1   (30-day return, primary ranking signal)
- R7  = close(t) / close(t-7)  - 1   (7-day return, blow-off filter)
- Percentile rank by R30 (1.0 = best momentum)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config_loader import AppConfig
from src.utils import setup_logging

logger = setup_logging("signals")


def compute_signals(price_data: Dict[str, pd.DataFrame],
                    symbols: List[str],
                    as_of_date: datetime,
                    config: AppConfig) -> pd.DataFrame:
    """
    Compute momentum signals for all symbols in the filtered universe.

    Args:
        price_data: Dict of symbol -> DataFrame (date-indexed OHLCV).
        symbols: List of symbols that passed universe filters.
        as_of_date: Decision date (use data up to this date only).
        config: App configuration (for lookback parameters).

    Returns:
        DataFrame with columns: symbol, close, r30, r7, r30_rank, r30_percentile,
                                avg_volume_7d_usd
        Sorted by r30 descending (best momentum first).
    """
    sc = config.strategy
    as_of = pd.Timestamp(as_of_date)
    records = []

    for symbol in symbols:
        if symbol not in price_data:
            continue

        df = price_data[symbol]
        df_up_to = df[df.index <= as_of]

        if len(df_up_to) < sc.lookback_days + 5:
            continue

        # Current close
        close_now = df_up_to["close"].iloc[-1]

        # R30: 30-day return
        lookback_date_30 = as_of - pd.Timedelta(days=sc.lookback_days)
        df_around_30 = df_up_to[df_up_to.index <= lookback_date_30]
        if df_around_30.empty:
            continue
        close_30d_ago = df_around_30["close"].iloc[-1]

        if close_30d_ago <= 0:
            continue
        r30 = close_now / close_30d_ago - 1.0

        # R7: 7-day return
        lookback_date_7 = as_of - pd.Timedelta(days=sc.short_lookback_days)
        df_around_7 = df_up_to[df_up_to.index <= lookback_date_7]
        if df_around_7.empty:
            continue
        close_7d_ago = df_around_7["close"].iloc[-1]

        if close_7d_ago <= 0:
            continue
        r7 = close_now / close_7d_ago - 1.0

        # 7-day average volume in USD
        recent_7d = df_up_to.tail(7)
        avg_vol_7d_usd = (recent_7d["close"] * recent_7d["volume"]).mean()

        # 30-day volatility of daily returns
        daily_returns = df_up_to["close"].pct_change().tail(sc.lookback_days)
        vol_30d = daily_returns.std()
        if pd.isna(vol_30d) or vol_30d <= 0:
            vol_30d = 1.0
        r30_vol_adj = r30 / vol_30d

        # ATR(14) for ATR-based trailing stops
        atr_period = getattr(sc, 'atr_period', 14)
        if len(df_up_to) >= atr_period + 1:
            high = df_up_to["high"].tail(atr_period + 1)
            low = df_up_to["low"].tail(atr_period + 1)
            close_prev = df_up_to["close"].shift(1).tail(atr_period + 1)
            tr = pd.concat([
                high - low,
                (high - close_prev).abs(),
                (low - close_prev).abs()
            ], axis=1).max(axis=1)
            atr_14 = tr.tail(atr_period).mean()
        else:
            atr_14 = close_now * vol_30d  # fallback: approximate ATR from vol

        # 7-day high and retracement (for mean-reversion exclusion)
        high_7d = df_up_to["high"].tail(7).max()
        retracement_from_7d_high = (high_7d - close_now) / high_7d if high_7d > 0 else 0.0

        records.append({
            "symbol": symbol,
            "close": close_now,
            "r30": r30,
            "r30_vol_adj": r30_vol_adj,
            "r7": r7,
            "vol_30d": vol_30d,
            "avg_volume_7d_usd": avg_vol_7d_usd,
            "atr_14": atr_14,
            "high_7d": high_7d,
            "retracement_from_7d_high": retracement_from_7d_high,
        })

    if not records:
        logger.warning(f"No signals computed for {as_of_date.strftime('%Y-%m-%d')}")
        return pd.DataFrame()

    df_signals = pd.DataFrame(records)

    # Sort by the configured ranking metric
    sort_col = "r30_vol_adj" if sc.ranking_metric == "vol_adj" else "r30"
    df_signals = df_signals.sort_values(sort_col, ascending=False).reset_index(drop=True)
    df_signals["r30_rank"] = range(1, len(df_signals) + 1)

    # Percentile (1.0 = top momentum, 0.0 = worst)
    n = len(df_signals)
    df_signals["r30_percentile"] = 1.0 - (df_signals["r30_rank"] - 1) / max(n - 1, 1)

    logger.info(
        f"Signals for {as_of_date.strftime('%Y-%m-%d')}: "
        f"{len(df_signals)} coins, sorted by {sort_col}, "
        f"top R30={df_signals['r30'].iloc[0]:.1%} ({df_signals['symbol'].iloc[0]})"
    )

    return df_signals
