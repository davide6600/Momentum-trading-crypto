"""
run_btc_strategy.py — Backtest script for the BTC-USDT Trend-Following Strategy.
Compares the strategy against BTC, QQQ, and SPY buy-and-hold benchmarks.
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set up paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "daily"
OUTPUT_DIR = PROJECT_ROOT / "output_btc"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Load Configuration ──
def load_strategy_config():
    config_path = PROJECT_ROOT / "config" / "strategy_btc.yaml"
    if not config_path.exists():
        # Fallback defaults
        return {
            "lookback_days": 260,
            "rebalance_day": "sunday",
            "strategy_capital_usd": 2000.0,
            "fee_per_side_pct": 0.001,
            "slippage_pct": 0.001
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ── Data Loader ──
def load_price_data(filename):
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date")
    return df

# ── Metrics Calculator ──
def calculate_metrics(equity_series, dates):
    df = pd.DataFrame({"date": dates, "equity": equity_series})
    df["drawdown"] = (df["equity"] - df["equity"].cummax()) / df["equity"].cummax()
    
    initial = df["equity"].iloc[0]
    final = df["equity"].iloc[-1]
    days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    years = days / 365.25 if days > 0 else 1
    
    cagr = (final / initial) ** (1.0 / years) - 1.0 if initial > 0 else 0.0
    
    # Calculate daily returns for vol
    daily_rets = df["equity"].pct_change().dropna()
    ann_vol = daily_rets.std() * np.sqrt(365.25)
    sharpe = cagr / ann_vol if ann_vol > 0 else 0.0
    
    # Sortino
    downside_rets = daily_rets[daily_rets < 0]
    downside_std = downside_rets.std() * np.sqrt(365.25)
    sortino = cagr / downside_std if downside_std > 0 else 0.0
    
    max_dd = df["drawdown"].min()
    
    return {
        "initial_capital": initial,
        "final_equity": final,
        "total_return": (final / initial) - 1.0,
        "cagr": cagr,
        "ann_volatility": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
    }

# ── Simulation Engine ──
def run_backtest(btc_df, config):
    lookback = config.get("lookback_days", 260)
    fee_pct = config.get("fee_per_side_pct", 0.001)
    slippage_pct = config.get("slippage_pct", 0.001)
    capital = config.get("strategy_capital_usd", 2000.0)
    
    dates = btc_df.index
    prices = btc_df["close"].values
    
    # Calculate 260-day SMA signal
    sma = btc_df["close"].rolling(window=lookback).mean()
    # Signal: 1 if close > SMA, 0 otherwise
    raw_signals = (btc_df["close"] > sma).astype(int)
    # Shift signal by 1 day to eliminate look-ahead bias (decision made based on yesterday's close)
    signals = raw_signals.shift(1).fillna(0).astype(int).values
    
    cash = capital
    btc_shares = 0.0
    position = 0  # 0: cash, 1: BTC
    equity = np.zeros(len(prices))
    
    trade_log = []
    fees_paid = 0.0
    
    tx_multiplier_buy = 1.0 + fee_pct + slippage_pct
    tx_multiplier_sell = 1.0 - (fee_pct + slippage_pct)
    
    for i in range(len(prices)):
        date = dates[i]
        price = prices[i]
        
        # We rebalance only on Sunday (dayofweek == 6)
        is_rebalance_day = (date.dayofweek == 6)
        
        if is_rebalance_day:
            target_pos = signals[i]
            if target_pos != position:
                date_str = date.strftime("%Y-%m-%d")
                if target_pos == 1 and position == 0:
                    # Buy BTC
                    btc_shares = cash / (price * tx_multiplier_buy)
                    trade_fee = cash * fee_pct
                    trade_slippage = cash * slippage_pct
                    fees_paid += trade_fee + trade_slippage
                    exec_price = price * tx_multiplier_buy
                    trade_log.append({
                        "date": date_str,
                        "symbol": "BTC",
                        "side": "buy",
                        "raw_price": price,
                        "exec_price": exec_price,
                        "quantity": btc_shares,
                        "usd_value": cash,
                        "fee_usd": trade_fee + trade_slippage,
                        "reason": "trend_entry"
                    })
                    cash = 0.0
                    position = 1
                elif target_pos == 0 and position == 1:
                    # Sell BTC
                    value_at_market = btc_shares * price
                    proceeds = value_at_market * tx_multiplier_sell
                    trade_fee = value_at_market * fee_pct
                    trade_slippage = value_at_market * slippage_pct
                    fees_paid += trade_fee + trade_slippage
                    exec_price = price * tx_multiplier_sell
                    trade_log.append({
                        "date": date_str,
                        "symbol": "BTC",
                        "side": "sell",
                        "raw_price": price,
                        "exec_price": exec_price,
                        "quantity": btc_shares,
                        "usd_value": proceeds,
                        "fee_usd": trade_fee + trade_slippage,
                        "reason": "trend_exit"
                    })
                    cash = proceeds
                    btc_shares = 0.0
                    position = 0
                    
        # Calculate daily equity
        if position == 1:
            equity[i] = btc_shares * price
        else:
            equity[i] = cash
            
    metrics = calculate_metrics(equity, dates)
    metrics["trades"] = len(trade_log)
    metrics["fees"] = fees_paid
    
    # Save equity curve df
    eq_df = pd.DataFrame({
        "date": dates,
        "equity": equity,
        "cash": [cash if p == 0 else 0.0 for p in signals],
        "invested": [btc_shares * price if p == 1 else 0.0 for p, price in zip(signals, prices)]
    })
    eq_df["drawdown"] = (eq_df["equity"] - eq_df["equity"].cummax()) / eq_df["equity"].cummax()
    
    # Save weekly returns
    weekly_rets = eq_df.set_index("date")["equity"].resample("W").last().pct_change().dropna().reset_index()
    weekly_rets.columns = ["date", "return"]
    
    return metrics, eq_df, weekly_rets, pd.DataFrame(trade_log)

# ── Premium Plotting ──
def plot_results(strategy_eq, btc_eq, qqq_eq, spy_eq):
    # Set premium plotting style (sleek off-white theme with high contrast)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Inter", "Outfit", "DejaVu Sans", "Arial"]
    
    # Colors
    color_strategy = "#0F172A"  # Slate 900
    color_btc = "#F59E0B"       # Amber 500
    color_qqq = "#3B82F6"       # Blue 500
    color_spy = "#10B981"       # Emerald 500
    
    # ── 1. Equity Curves Plot ──
    fig, ax = plt.subplots(figsize=(14, 8), facecolor="#F8FAFC")
    ax.set_facecolor("#FFFFFF")
    
    ax.plot(strategy_eq["date"], strategy_eq["equity"], label="BTC Weekly SMA 260 Strategy", color=color_strategy, linewidth=2.5, zorder=5)
    ax.plot(btc_eq["date"], btc_eq["equity"], label="BTC Buy & Hold", color=color_btc, linewidth=1.5, alpha=0.8, linestyle="--", zorder=3)
    ax.plot(qqq_eq["date"], qqq_eq["equity"], label="QQQ Buy & Hold", color=color_qqq, linewidth=1.5, alpha=0.8, zorder=2)
    ax.plot(spy_eq["date"], spy_eq["equity"], label="SPY Buy & Hold", color=color_spy, linewidth=1.5, alpha=0.8, zorder=1)
    
    ax.set_yscale("log")
    ax.set_title("Equity Growth Comparison (Log Scale) — Initial $2,000", fontsize=16, fontweight="bold", pad=20, color="#1E293B")
    ax.set_xlabel("Date", fontsize=12, labelpad=10, color="#475569")
    ax.set_ylabel("Equity (USD)", fontsize=12, labelpad=10, color="#475569")
    
    # Grid lines
    ax.grid(True, which="both", linestyle=":", color="#E2E8F0", alpha=0.7)
    
    # Format axes
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax.tick_params(colors="#475569", labelsize=10)
    
    # Border removal
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#CBD5E1")
        
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=11, loc="upper left")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "comparison_equity_curve.png", dpi=200, facecolor=fig.get_facecolor())
    plt.close()
    
    # ── 2. Drawdowns Plot ──
    fig, ax = plt.subplots(figsize=(14, 5), facecolor="#F8FAFC")
    ax.set_facecolor("#FFFFFF")
    
    ax.fill_between(strategy_eq["date"], strategy_eq["drawdown"] * 100, 0, label="Strategy Drawdown", color="#334155", alpha=0.3)
    ax.plot(strategy_eq["date"], strategy_eq["drawdown"] * 100, color=color_strategy, linewidth=1.5)
    
    ax.plot(btc_eq["date"], btc_eq["drawdown"] * 100, label="BTC Drawdown", color=color_btc, linewidth=1.0, alpha=0.7, linestyle=":")
    
    ax.set_title("Drawdown Comparison (%)", fontsize=14, fontweight="bold", pad=15, color="#1E293B")
    ax.set_xlabel("Date", fontsize=11, labelpad=8, color="#475569")
    ax.set_ylabel("Drawdown %", fontsize=11, labelpad=8, color="#475569")
    
    ax.grid(True, linestyle=":", color="#E2E8F0", alpha=0.7)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0f}%"))
    ax.tick_params(colors="#475569", labelsize=9)
    
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#CBD5E1")
        
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=10, loc="lower left")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "comparison_drawdown.png", dpi=200, facecolor=fig.get_facecolor())
    plt.close()

# ── Main Entry ──
def main():
    print("================================================================================")
    print("  RUNNING BTC-USDT TREND-FOLLOWING STRATEGY BACKTEST")
    print("================================================================================")
    
    config = load_strategy_config()
    
    # Load all benchmarks and symbol prices
    btc_df = load_price_data("BTC.csv")
    qqq_df = load_price_data("QQQ.csv")
    spy_df = load_price_data("SPY.csv")
    
    # Align dates
    start_date = max(btc_df.index.min(), qqq_df.index.min(), spy_df.index.min())
    end_date = min(btc_df.index.max(), qqq_df.index.max(), spy_df.index.max())
    
    btc_df = btc_df.loc[start_date:end_date]
    qqq_df = qqq_df.loc[start_date:end_date].ffill()
    spy_df = spy_df.loc[start_date:end_date].ffill()
    
    print(f"Simulation Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Initial Capital  : ${config.get('strategy_capital_usd', 2000.0):,.2f}")
    print(f"Trading Fee + Slip: {config.get('fee_per_side_pct', 0.001):.2%} fee, {config.get('slippage_pct', 0.001):.2%} slippage per side")
    print(f"SMA Lookback     : {config.get('lookback_days', 260)} days")
    print("--------------------------------------------------------------------------------")
    
    # Run Backtest
    m_strat, eq_strat, wr_strat, trades = run_backtest(btc_df, config)
    
    # Compute Benchmark Metrics
    initial_cap = config.get("strategy_capital_usd", 2000.0)
    
    # BTC Benchmark
    btc_eq = pd.DataFrame({
        "date": btc_df.index,
        "equity": initial_cap * btc_df["close"] / btc_df["close"].iloc[0]
    })
    m_btc = calculate_metrics(btc_eq["equity"].values, btc_df.index)
    btc_eq["drawdown"] = (btc_eq["equity"] - btc_eq["equity"].cummax()) / btc_eq["equity"].cummax()
    
    # QQQ Benchmark
    qqq_eq = pd.DataFrame({
        "date": qqq_df.index,
        "equity": initial_cap * qqq_df["close"] / qqq_df["close"].iloc[0]
    })
    m_qqq = calculate_metrics(qqq_eq["equity"].values, qqq_df.index)
    qqq_eq["drawdown"] = (qqq_eq["equity"] - qqq_eq["equity"].cummax()) / qqq_eq["equity"].cummax()
    
    # SPY Benchmark
    spy_eq = pd.DataFrame({
        "date": spy_df.index,
        "equity": initial_cap * spy_df["close"] / spy_df["close"].iloc[0]
    })
    m_spy = calculate_metrics(spy_eq["equity"].values, spy_df.index)
    spy_eq["drawdown"] = (spy_eq["equity"] - spy_eq["equity"].cummax()) / spy_eq["equity"].cummax()
    
    # ── Display Metrics Table ──
    metrics_to_print = [
        ("Final Equity", "final_equity", "${:,.2f}"),
        ("Total Return", "total_return", "{:+.1%}"),
        ("CAGR", "cagr", "{:+.1%}"),
        ("Ann. Volatility", "ann_volatility", "{:.1%}"),
        ("Sharpe Ratio", "sharpe", "{:.2f}"),
        ("Sortino Ratio", "sortino", "{:.2f}"),
        ("Max Drawdown", "max_drawdown", "{:.1%}"),
    ]
    
    lookback_val = config.get("lookback_days", 273)
    print(f"  {'Metric':<20s} | {f'Strategy (SMA {lookback_val})':^20s} | {'BTC B&H':^13s} | {'QQQ B&H':^13s} | {'SPY B&H':^13s}")
    print("-" * 92)
    for label, key, fmt in metrics_to_print:
        val_strat = fmt.format(m_strat.get(key, 0.0))
        val_btc = fmt.format(m_btc.get(key, 0.0))
        val_qqq = fmt.format(m_qqq.get(key, 0.0))
        val_spy = fmt.format(m_spy.get(key, 0.0))
        print(f"  {label:<20s} | {val_strat:>20s} | {val_btc:>13s} | {val_qqq:>13s} | {val_spy:>13s}")
    
    print("-" * 92)
    print(f"  Total Trades       | {m_strat['trades']:>20d} | {'-':^13s} | {'-':^13s} | {'-':^13s}")
    print(f"  Total Fees Paid    | ${m_strat['fees']:>19,.2f} | {'-':^13s} | {'-':^13s} | {'-':^13s}")
    print("================================================================================\n")
    
    # Save files
    eq_strat.to_csv(OUTPUT_DIR / "equity_curve.csv", index=False)
    wr_strat.to_csv(OUTPUT_DIR / "weekly_returns.csv", index=False)
    trades.to_csv(OUTPUT_DIR / "trade_log.csv", index=False)
    print(f"Saved CSV results to: {OUTPUT_DIR}/")
    
    # Plot results
    plot_results(eq_strat, btc_eq, qqq_eq, spy_eq)
    print(f"Saved comparison charts to: {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
