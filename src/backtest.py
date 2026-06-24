"""
backtest.py — Weekly cross-sectional momentum backtest engine (IMPROVED).

Core loop:
  For each Sunday rebalance date:
    1. Build universe snapshot (no look-ahead)
    2. Compute momentum signals (R30, R7, ATR)
    3. Select winners and construct target portfolio
    4. Close previous positions at rebalance-day close + costs
    5. Open new positions at rebalance-day close + costs
    6. Simulate daily P&L through the week (ATR trailing stop / take-profit checks)
    7. Record positions, trades, daily equity

Improvements over original:
  - ATR-based trailing stops (adaptive to each coin's volatility)
  - Breadth acceleration re-entry (partial re-entry when breadth rises fast)
  - Vol-parity position sizing (actually applied to USD allocation)
  - Mean-reversion exclusion (via signals + portfolio selection)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from src.config_loader import AppConfig, compute_position_size
from src.universe import load_all_price_data, filter_universe, compute_regime_filters
from src.signals import compute_signals
from src.portfolio import select_winners
from src.risk import (check_stop_loss, check_take_profit, check_kill_switch,
                      apply_entry_cost, apply_exit_cost)
from src.utils import setup_logging, get_weekly_rebalance_dates, OUTPUT_DIR

logger = setup_logging("backtest", log_file="backtest.log")


@dataclass
class Position:
    symbol: str
    entry_date: str
    entry_price: float      # price paid (after costs)
    raw_entry_price: float   # market price at entry
    quantity: float
    usd_value: float         # initial USD value
    status: str = "open"     # open, stopped, profit_taken, closed, killed
    # ATR trailing stop fields
    atr_at_entry: float = 0.0       # ATR(14) at time of entry
    trailing_stop_price: float = 0.0  # current trailing stop level
    highest_price: float = 0.0       # highest price seen since entry


@dataclass
class Trade:
    date: str
    symbol: str
    side: str            # buy or sell
    raw_price: float     # market price
    exec_price: float    # price after fees/slippage
    quantity: float
    usd_value: float
    fee_usd: float
    reason: str          # entry, stop_loss, take_profit, rebalance


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame     # date, equity, cash, invested, drawdown
    trade_log: List[Trade]
    weekly_returns: pd.DataFrame   # date, return
    positions_history: List[dict]
    config: AppConfig


def run_backtest(config: AppConfig,
                 start_date: datetime,
                 end_date: datetime,
                 price_data: Optional[Dict[str, pd.DataFrame]] = None,
                 override_filters: Optional[dict] = None
                 ) -> BacktestResult:
    """
    Run the weekly cross-sectional momentum backtest.

    Args:
        config: Application configuration.
        start_date: Backtest start date.
        end_date: Backtest end date.
        price_data: Pre-loaded price data dict. If None, loads from CSVs.
        override_filters: Dict to override config filter settings (e.g. enable_btc_ma_filter, enable_breadth_filter)

    Returns:
        BacktestResult with equity curve, trade log, weekly returns.
    """
    # Create a copy of config to avoid modifying the original globally
    import copy
    config_copy = copy.deepcopy(config)
    sc = config_copy.strategy

    # Apply overrides
    if override_filters:
        for k, v in override_filters.items():
            if hasattr(sc, k):
                setattr(sc, k, v)
                logger.info(f"Overriding strategy param: {k} = {v}")

    # Load data
    if price_data is None:
        price_data = load_all_price_data()
    if not price_data:
        raise ValueError("No price data available. Run data download first.")

    # Build a combined date index for daily tracking
    all_dates = set()
    for df in price_data.values():
        all_dates.update(df.index.tolist())
    all_dates = sorted(all_dates)

    # Generate rebalance dates
    rebalance_dates = get_weekly_rebalance_dates(start_date, end_date, sc.rebalance_day)

    logger.info(
        f"Backtest: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} | "
        f"{len(rebalance_dates)} rebalance dates | {len(price_data)} symbols loaded"
    )

    # State
    capital = sc.strategy_capital_usd
    cash = capital
    positions: List[Position] = []
    all_trades: List[Trade] = []
    equity_records = []
    weekly_return_records = []
    positions_history = []
    prev_equity = capital
    skip_next_week = False  # kill-switch: skip 1 week, then resume
    weeks_since_rebalance = 0
    prev_breadth_pct = None  # Track breadth for acceleration re-entry

    for reb_idx, reb_date in enumerate(rebalance_dates):
        reb_str = reb_date.strftime("%Y-%m-%d")

        # Determine if we should rebalance this week (holding period check or empty positions)
        should_rebalance = (len(positions) == 0) or (weeks_since_rebalance >= sc.holding_period_weeks)

        if should_rebalance:
            # ── Step 1: Calculate new target portfolio first ──
            targets = {}
            targets_atr = {}  # ATR values for new positions
            regime_defensive_active = False

            # Calculate total equity at rebalance date (before closing positions)
            invested_val = sum(p.quantity * (_get_close(price_data, p.symbol, reb_date) or p.raw_entry_price)
                               for p in positions if p.status == "open")
            total_equity = cash + invested_val

            if skip_next_week:
                logger.info(f"[{reb_str}] Kill-switch cooldown — staying in cash this week")
                skip_next_week = False  # reset for next week
                targets = {}
            else:
                universe = filter_universe(price_data, config_copy, reb_date)
                if not universe:
                    logger.info(f"[{reb_str}] Empty universe — staying in cash")
                    targets = {}
                else:
                    # Regime filter check
                    btc_above_ma, breadth_pct, breadth_pass = compute_regime_filters(price_data, universe, config_copy, reb_date)
                    trade_allowed = True
                    reasons = []

                    if sc.enable_btc_ma_filter and not btc_above_ma:
                        trade_allowed = False
                        reasons.append("BTC below 200D MA")
                    if sc.enable_breadth_filter and not breadth_pass:
                        trade_allowed = False
                        reasons.append(f"Market breadth {breadth_pct:.1%} < {sc.min_breadth_pct:.1%}")

                    # ── Breadth Acceleration Re-Entry ──
                    breadth_accel_active = False
                    if (not trade_allowed and sc.enable_breadth_acceleration
                            and prev_breadth_pct is not None):
                        breadth_delta = breadth_pct - prev_breadth_pct
                        if breadth_delta >= sc.breadth_accel_delta:
                            breadth_accel_active = True
                            trade_allowed = True
                            logger.info(
                                f"[{reb_str}] BREADTH ACCELERATION: breadth rose "
                                f"{prev_breadth_pct:.1%} → {breadth_pct:.1%} "
                                f"(+{breadth_delta:.1%}), allowing partial re-entry"
                            )

                    prev_breadth_pct = breadth_pct  # track for next week

                    if trade_allowed:
                        signals = compute_signals(price_data, universe, reb_date, config_copy)
                        winners = select_winners(signals, config_copy)
                        if not winners.empty:
                            n_pos = len(winners)

                            # If breadth acceleration, use reduced capital
                            if breadth_accel_active:
                                available_capital = total_equity * sc.breadth_accel_capital_pct
                            else:
                                available_capital = total_equity

                            for _, w in winners.iterrows():
                                target_usd = w["target_usd"]
                                # Cap by available capital share
                                if breadth_accel_active:
                                    target_usd = min(target_usd, available_capital / n_pos)
                                else:
                                    target_usd = min(target_usd, total_equity / n_pos)
                                targets[w["symbol"]] = target_usd
                                # Store ATR for this symbol
                                if "atr_14" in w.index:
                                    targets_atr[w["symbol"]] = w["atr_14"]
                    else:
                        logger.info(f"[{reb_str}] Regime halt: {', '.join(reasons)}.")
                        if sc.defensive_asset != "cash" and sc.defensive_asset in price_data:
                            targets[sc.defensive_asset] = total_equity
                            regime_defensive_active = True
                            logger.info(f"[{reb_str}] Switching to defensive asset: {sc.defensive_asset}")
                        else:
                            logger.info(f"[{reb_str}] Staying in cash.")

            # ── Step 2: Close positions not in targets ──
            new_positions = []
            for pos in positions:
                if pos.status == "open":
                    if pos.symbol not in targets:
                        # Close position
                        close_price = _get_close(price_data, pos.symbol, reb_date)
                        if close_price is None:
                            close_price = pos.raw_entry_price  # fallback
                        exec_price = apply_exit_cost(close_price, sc.fee_per_side_pct, sc.slippage_pct)
                        proceeds = exec_price * pos.quantity
                        fee = abs(close_price - exec_price) * pos.quantity
                        cash += proceeds
                        pos.status = "closed"
                        all_trades.append(Trade(
                            date=reb_str, symbol=pos.symbol, side="sell",
                            raw_price=close_price, exec_price=exec_price,
                            quantity=pos.quantity, usd_value=proceeds,
                            fee_usd=fee, reason="rebalance"
                        ))
                    else:
                        # We keep it, so remove it from targets to avoid buying it again
                        new_positions.append(pos)
                        targets.pop(pos.symbol)
            positions = new_positions
            weeks_since_rebalance = 0

            # ── Step 3: Open remaining target positions ──
            if targets:
                # If we're holding a defensive asset, we use all available cash
                if regime_defensive_active and sc.defensive_asset in targets:
                    buy_size = cash
                    sym = sc.defensive_asset
                    raw_price = _get_close(price_data, sym, reb_date)
                    if raw_price is not None:
                        exec_price = apply_entry_cost(raw_price, sc.fee_per_side_pct, sc.slippage_pct)
                        quantity = buy_size / exec_price
                        cost = exec_price * quantity
                        fee = abs(exec_price - raw_price) * quantity
                        if cost <= cash and quantity > 0:
                            cash -= cost
                            pos = Position(
                                symbol=sym,
                                entry_date=reb_str,
                                entry_price=exec_price,
                                raw_entry_price=raw_price,
                                quantity=quantity,
                                usd_value=cost,
                            )
                            positions.append(pos)
                            all_trades.append(Trade(
                                date=reb_str, symbol=sym, side="buy",
                                raw_price=raw_price, exec_price=exec_price,
                                quantity=quantity, usd_value=cost,
                                fee_usd=fee, reason="defensive"
                            ))
                else:
                    for sym, target_usd in list(targets.items()):
                        # Cap buy size by remaining cash
                        buy_size = min(target_usd, cash)
                        raw_price = _get_close(price_data, sym, reb_date)
                        if raw_price is None:
                            continue
                        exec_price = apply_entry_cost(raw_price, sc.fee_per_side_pct, sc.slippage_pct)
                        quantity = buy_size / exec_price
                        cost = exec_price * quantity
                        fee = abs(exec_price - raw_price) * quantity

                        if cost > cash or quantity <= 0:
                            continue

                        cash -= cost

                        # Get ATR for this symbol
                        sym_atr = targets_atr.get(sym, 0.0)

                        # Compute initial trailing stop
                        if sc.enable_atr_stop and sym_atr > 0:
                            trailing_stop = raw_price - sc.atr_multiplier * sym_atr
                        else:
                            trailing_stop = raw_price * (1.0 + sc.stop_loss_pct)

                        pos = Position(
                            symbol=sym,
                            entry_date=reb_str,
                            entry_price=exec_price,
                            raw_entry_price=raw_price,
                            quantity=quantity,
                            usd_value=cost,
                            atr_at_entry=sym_atr,
                            trailing_stop_price=trailing_stop,
                            highest_price=raw_price,
                        )
                        positions.append(pos)
                        all_trades.append(Trade(
                            date=reb_str, symbol=sym, side="buy",
                            raw_price=raw_price, exec_price=exec_price,
                            quantity=quantity, usd_value=cost,
                            fee_usd=fee, reason="entry"
                        ))

        # Record equity at start of week
        invested = sum(p.quantity * (_get_close(price_data, p.symbol, reb_date) or p.raw_entry_price)
                       for p in positions if p.status == "open")
        equity = cash + invested
        equity_records.append({
            "date": reb_str, "equity": equity,
            "cash": cash, "invested": invested
        })

        # Record positions snapshot
        pos_snap = [{"date": reb_str, "symbol": p.symbol,
                     "entry_price": p.entry_price, "qty": p.quantity,
                     "usd": p.usd_value} for p in positions if p.status == "open"]
        positions_history.extend(pos_snap)

        # ── Step 4: Simulate daily through the week (stop/TP checks) ──
        if reb_idx < len(rebalance_dates) - 1:
            next_reb = rebalance_dates[reb_idx + 1]
        else:
            next_reb = end_date

        day = reb_date + timedelta(days=1)
        while day < next_reb:
            day_ts = pd.Timestamp(day)
            for pos in positions:
                if pos.status != "open":
                    continue
                if pos.symbol == sc.defensive_asset:
                    continue
                close_today = _get_close(price_data, pos.symbol, day)
                if close_today is None:
                    continue

                # Update highest price for trailing stop
                if close_today > pos.highest_price:
                    pos.highest_price = close_today
                    # Trail the stop up (only if ATR stop is active)
                    if sc.enable_atr_stop and pos.atr_at_entry > 0:
                        new_stop = close_today - sc.atr_multiplier * pos.atr_at_entry
                        if new_stop > pos.trailing_stop_price:
                            pos.trailing_stop_price = new_stop

                # Stop-loss check: use trailing stop if ATR mode, else fixed %
                stopped = False
                if sc.enable_atr_stop and pos.atr_at_entry > 0:
                    # ATR trailing stop
                    if close_today <= pos.trailing_stop_price:
                        stopped = True
                else:
                    # Fixed % stop-loss (fallback)
                    if check_stop_loss(pos.entry_price, close_today, sc.stop_loss_pct):
                        stopped = True

                if stopped:
                    exec_p = apply_exit_cost(close_today, sc.fee_per_side_pct, sc.slippage_pct)
                    proceeds = exec_p * pos.quantity
                    fee = abs(close_today - exec_p) * pos.quantity
                    cash += proceeds
                    pos.status = "stopped"
                    all_trades.append(Trade(
                        date=day.strftime("%Y-%m-%d"), symbol=pos.symbol,
                        side="sell", raw_price=close_today, exec_price=exec_p,
                        quantity=pos.quantity, usd_value=proceeds,
                        fee_usd=fee, reason="stop_loss"
                    ))

                # Take-profit check
                elif check_take_profit(pos.entry_price, close_today, sc.take_profit_pct):
                    exec_p = apply_exit_cost(close_today, sc.fee_per_side_pct, sc.slippage_pct)
                    proceeds = exec_p * pos.quantity
                    fee = abs(close_today - exec_p) * pos.quantity
                    cash += proceeds
                    pos.status = "profit_taken"
                    all_trades.append(Trade(
                        date=day.strftime("%Y-%m-%d"), symbol=pos.symbol,
                        side="sell", raw_price=close_today, exec_price=exec_p,
                        quantity=pos.quantity, usd_value=proceeds,
                        fee_usd=fee, reason="take_profit"
                    ))

            # Daily equity mark
            invested = 0
            for pos in positions:
                if pos.status == "open":
                    cp = _get_close(price_data, pos.symbol, day)
                    if cp:
                        invested += cp * pos.quantity
                    else:
                        invested += pos.raw_entry_price * pos.quantity
            equity = cash + invested
            equity_records.append({
                "date": day.strftime("%Y-%m-%d"),
                "equity": equity, "cash": cash, "invested": invested
            })

            day += timedelta(days=1)

        # Weekly return
        weekly_ret = equity / prev_equity - 1.0 if prev_equity > 0 else 0.0
        weekly_return_records.append({"date": reb_str, "return": weekly_ret})
        prev_equity = equity

        # Kill-switch check: if weekly loss exceeds threshold, skip next week
        if check_kill_switch(weekly_ret, sc.kill_switch_weekly_pct):
            logger.warning(
                f"[{reb_str}] KILL SWITCH: weekly return {weekly_ret:.1%} "
                f"< {sc.kill_switch_weekly_pct:.1%}. Skipping next week."
            )
            skip_next_week = True

        # Increment weeks count
        weeks_since_rebalance += 1

    # Build result DataFrames
    eq_df = pd.DataFrame(equity_records)
    if not eq_df.empty:
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.drop_duplicates(subset="date", keep="last").sort_values("date")
        peak = eq_df["equity"].cummax()
        eq_df["drawdown"] = (eq_df["equity"] - peak) / peak

    wr_df = pd.DataFrame(weekly_return_records)
    if not wr_df.empty:
        wr_df["date"] = pd.to_datetime(wr_df["date"])

    logger.info(
        f"Backtest complete: {len(all_trades)} trades, "
        f"final equity ${equity_records[-1]['equity']:.2f}" if equity_records else "No data"
    )

    return BacktestResult(
        equity_curve=eq_df,
        trade_log=all_trades,
        weekly_returns=wr_df,
        positions_history=positions_history,
        config=config_copy,
    )


def _get_close(price_data: Dict[str, pd.DataFrame],
               symbol: str, date: datetime) -> Optional[float]:
    """Get the closing price for a symbol on or just before a given date."""
    if symbol not in price_data:
        return None
    df = price_data[symbol]
    ts = pd.Timestamp(date)
    df_up_to = df[df.index <= ts]
    if df_up_to.empty:
        return None
    # Allow up to 3 days gap
    last = df_up_to.index[-1]
    if (ts - last).days > 3:
        return None
    return float(df_up_to["close"].iloc[-1])
