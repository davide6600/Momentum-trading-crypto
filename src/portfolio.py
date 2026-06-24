"""
portfolio.py — Select momentum winners and construct target portfolio.

Selection pipeline (per altcoin-momentum.md §6):
1. Take top quantile (e.g., top 20%) by R30.
2. Filter: R30 > min_momentum_threshold.
3. Filter: R7 < max_short_term_runup.
4. Filter: Mean-reversion exclusion (retracement from 7D high).
5. Filter: 7-day avg volume > min_recent_volume_usd_7d.
6. Select up to n_winners.
7. Volatility-parity or equal-weight allocation with risk-based position sizing.
"""

import pandas as pd
from src.config_loader import AppConfig, compute_position_size
from src.utils import setup_logging

logger = setup_logging("portfolio")


def select_winners(signals_df: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    """Select momentum winners from signal DataFrame. Returns empty DF if none qualify."""
    if signals_df.empty:
        return pd.DataFrame()

    sc = config.strategy
    n_total = len(signals_df)
    candidates = signals_df.copy()

    # 1. Top quantile by R30
    cutoff = max(1, int(n_total * sc.top_quantile))
    candidates = candidates.head(cutoff)

    # 2. R30 > threshold
    candidates = candidates[candidates["r30"] > sc.min_momentum_threshold]

    # 3. R7 < max runup
    candidates = candidates[candidates["r7"] < sc.max_short_term_runup]

    # 4. Mean-reversion exclusion: skip coins that already reversed >X% from 7D high
    if sc.enable_mean_reversion_filter and "retracement_from_7d_high" in candidates.columns:
        before = len(candidates)
        candidates = candidates[candidates["retracement_from_7d_high"] < sc.max_retracement_from_7d_high]
        excluded = before - len(candidates)
        if excluded > 0:
            logger.info(f"  Mean-reversion filter excluded {excluded} coin(s)")

    # 5. Volume filter
    candidates = candidates[candidates["avg_volume_7d_usd"] >= sc.min_recent_volume_usd_7d]

    if candidates.empty:
        logger.info("  No winners this week - all cash")
        return pd.DataFrame()

    # 6. Top n_winners
    winners = candidates.head(sc.n_winners).copy()

    # 7. Weighting scheme and risk-based sizing
    n_pos = len(winners)
    if sc.weighting_scheme == "vol_parity" and "vol_30d" in winners.columns:
        # Avoid division by zero
        vols = winners["vol_30d"].replace(0, 1.0)
        inv_vol = 1.0 / vols
        winners["weight"] = inv_vol / inv_vol.sum()
    else:
        winners["weight"] = 1.0 / n_pos if n_pos > 0 else 0.0

    # Total capital to invest = pos_size * n_pos, then distribute by weights
    pos_size = compute_position_size(sc, n_pos)
    total_invest = pos_size * n_pos
    max_usd = sc.max_per_position_pct * sc.strategy_capital_usd
    winners["target_usd"] = (total_invest * winners["weight"]).clip(upper=max_usd)
    winners["target_qty"] = winners["target_usd"] / winners["close"]

    # Include ATR info for ATR-based stops
    output_cols = ["symbol", "close", "r30", "r7", "weight", "target_usd", "target_qty"]
    if "atr_14" in winners.columns:
        output_cols.append("atr_14")
    if "vol_30d" in winners.columns:
        output_cols.append("vol_30d")

    total_invested = winners["target_usd"].sum()
    logger.info(
        f"  {n_pos} winners | ${total_invested:.0f} invested | weighting: {sc.weighting_scheme}"
    )
    for _, r in winners.iterrows():
        wt_str = f" wt={r['weight']:.1%}" if sc.weighting_scheme == "vol_parity" else ""
        logger.info(f"    {r['symbol']:>8s} R30={r['r30']:+.1%} R7={r['r7']:+.1%}{wt_str}")

    return winners[output_cols]
