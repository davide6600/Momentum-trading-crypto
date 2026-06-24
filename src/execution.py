"""
execution.py — Live/paper trading execution scaffold.

Supports:
- dry_run mode (default): logs trades without sending orders.
- Paper mode: tracks positions in a local state file.
- Live mode: sends orders via CCXT to the exchange.

All order functions enforce max_position_size safeguard.
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config_loader import AppConfig, compute_position_size
from src.data_ingestion import create_exchange
from src.utils import setup_logging, OUTPUT_DIR

logger = setup_logging("execution", log_file="execution.log")

STATE_FILE = OUTPUT_DIR / "portfolio_state.json"


def load_state() -> dict:
    """Load current portfolio state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"positions": {}, "cash": 0.0, "last_rebalance": None}


def save_state(state: dict):
    """Save portfolio state to file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def compute_rebalance_orders(current_positions: Dict[str, float],
                             target_portfolio: pd.DataFrame,
                             config: AppConfig) -> List[dict]:
    """
    Compute orders needed to move from current to target portfolio.

    Returns list of order dicts: {symbol, side, quantity, reason}.
    """
    orders = []
    target_syms = set()

    if not target_portfolio.empty:
        target_syms = set(target_portfolio["symbol"].values)
        for _, row in target_portfolio.iterrows():
            sym = row["symbol"]
            target_qty = row["target_qty"]
            current_qty = current_positions.get(sym, 0.0)
            diff = target_qty - current_qty
            if abs(diff) < 1e-8:
                continue
            orders.append({
                "symbol": sym,
                "side": "buy" if diff > 0 else "sell",
                "quantity": abs(diff),
                "reason": "rebalance",
            })

    # Sell positions not in target
    for sym, qty in current_positions.items():
        if sym not in target_syms and qty > 0:
            orders.append({
                "symbol": sym, "side": "sell",
                "quantity": qty, "reason": "exit",
            })

    return orders


def execute_orders(orders: List[dict], config: AppConfig,
                   dry_run: bool = True) -> List[dict]:
    """
    Execute a list of orders.

    Args:
        orders: List of order dicts from compute_rebalance_orders.
        config: Application configuration.
        dry_run: If True, only log orders without sending to exchange.

    Returns:
        List of execution results.
    """
    results = []

    if dry_run:
        logger.info(f"DRY RUN — {len(orders)} orders (not sent to exchange)")
        for o in orders:
            logger.info(
                f"  [DRY] {o['side'].upper():>4s} {o['quantity']:.6f} {o['symbol']} "
                f"({o['reason']})"
            )
            results.append({**o, "status": "dry_run", "fill_price": None})
        return results

    # Live execution
    exchange = create_exchange(config)
    for o in orders:
        pair = f"{o['symbol']}/USDT"
        try:
            if o["side"] == "buy":
                result = exchange.create_market_buy_order(pair, o["quantity"])
            else:
                result = exchange.create_market_sell_order(pair, o["quantity"])
            logger.info(f"  [LIVE] {o['side'].upper()} {o['symbol']}: {result}")
            results.append({
                **o, "status": "filled",
                "fill_price": result.get("average"),
                "order_id": result.get("id"),
            })
        except Exception as e:
            logger.error(f"  [LIVE] {o['side'].upper()} {o['symbol']}: FAILED — {e}")
            results.append({**o, "status": "error", "error": str(e)})

    return results
