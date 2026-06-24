"""
run_rebalance.py — Execute weekly rebalance (paper or live).

Usage:
    python scripts/run_rebalance.py [--config CONFIG_DIR] [--dry-run] [--live]

Default is --dry-run (no real orders).
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.data_ingestion import download_all_symbols
from src.universe import load_all_price_data, filter_universe, compute_regime_filters
from src.signals import compute_signals
from src.portfolio import select_winners
from src.execution import load_state, save_state, compute_rebalance_orders, execute_orders
from src.utils import setup_logging

logger = setup_logging("run_rebalance", log_file="rebalance.log")


def main():
    parser = argparse.ArgumentParser(description="Execute weekly rebalance")
    parser.add_argument("--config", default="config", help="Config directory")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Log orders without executing (default)")
    parser.add_argument("--live", action="store_true",
                        help="Send real orders to exchange")
    args = parser.parse_args()

    dry_run = not args.live
    config = load_config(args.config)

    # Refresh data
    logger.info("Refreshing data before rebalance...")
    download_all_symbols(config, incremental=True)

    price_data = load_all_price_data()
    now = datetime.utcnow()

    # Generate signals
    universe = filter_universe(price_data, config, now)
    
    # Compute regime filters
    btc_above_ma, breadth_pct, breadth_pass = compute_regime_filters(price_data, universe, config, now)
    sc = config.strategy
    
    trade_allowed = True
    reasons = []
    if sc.enable_btc_ma_filter and not btc_above_ma:
        trade_allowed = False
        reasons.append("BTC below 200D MA")
    if sc.enable_breadth_filter and not breadth_pass:
        trade_allowed = False
        reasons.append(f"Market breadth {breadth_pct:.1%} < {sc.min_breadth_pct:.1%}")

    if not trade_allowed:
        logger.warning(f"REGIME HALT ACTIVE: {', '.join(reasons)}. Rebalancing portfolio to CASH.")
        target = pd.DataFrame()
    else:
        signals = compute_signals(price_data, universe, now, config)
        target = select_winners(signals, config)

    # Load current state
    state = load_state()
    current_positions = state.get("positions", {})

    # Compute orders
    orders = compute_rebalance_orders(current_positions, target, config)

    if not orders:
        logger.info("No orders needed — portfolio is already aligned.")
        return

    # Execute
    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info(f"Executing {len(orders)} orders ({mode})...")
    results = execute_orders(orders, config, dry_run=dry_run)

    # Update state
    new_positions = {}
    if not target.empty:
        for _, w in target.iterrows():
            new_positions[w["symbol"]] = float(w["target_qty"])

    state["positions"] = new_positions
    state["cash"] = config.strategy.strategy_capital_usd - (
        target["target_usd"].sum() if not target.empty else 0
    )
    state["last_rebalance"] = now.isoformat()
    save_state(state)

    logger.info(f"Rebalance complete. State saved.")


if __name__ == "__main__":
    main()
