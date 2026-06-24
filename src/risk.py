"""
risk.py — Stop-loss, take-profit, and kill-switch logic.

Used by both the backtest engine and the live/paper trading scaffold.
"""

from src.config_loader import StrategyConfig
from src.utils import setup_logging

logger = setup_logging("risk")


def check_stop_loss(entry_price: float, current_price: float,
                    stop_loss_pct: float) -> bool:
    """Return True if current_price has breached the stop-loss level."""
    if entry_price <= 0:
        return False
    pnl_pct = current_price / entry_price - 1.0
    return pnl_pct <= stop_loss_pct  # stop_loss_pct is negative, e.g. -0.12


def check_take_profit(entry_price: float, current_price: float,
                      take_profit_pct: float) -> bool:
    """Return True if current_price has reached the take-profit level."""
    if entry_price <= 0:
        return False
    pnl_pct = current_price / entry_price - 1.0
    return pnl_pct >= take_profit_pct


def check_kill_switch(weekly_pnl_pct: float, threshold: float) -> bool:
    """Return True if weekly PnL has breached the kill-switch threshold."""
    return weekly_pnl_pct <= threshold


def apply_entry_cost(price: float, fee_pct: float, slippage_pct: float) -> float:
    """Adjust price upward for entry costs (buying)."""
    return price * (1.0 + fee_pct + slippage_pct)


def apply_exit_cost(price: float, fee_pct: float, slippage_pct: float) -> float:
    """Adjust price downward for exit costs (selling)."""
    return price * (1.0 - fee_pct - slippage_pct)
