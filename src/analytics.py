"""
analytics.py — Performance metrics, benchmarks, and plotting for backtest results.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Optional

from src.backtest import BacktestResult, Trade
from src.universe import load_all_price_data
from src.utils import OUTPUT_DIR, setup_logging

logger = setup_logging("analytics")


def compute_metrics(result: BacktestResult) -> dict:
    """Compute key performance metrics from backtest results."""
    eq = result.equity_curve
    wr = result.weekly_returns

    if eq.empty or wr.empty:
        return {"error": "No data"}

    initial = eq["equity"].iloc[0]
    final = eq["equity"].iloc[-1]
    days = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days
    years = days / 365.25 if days > 0 else 1

    # CAGR
    cagr = (final / initial) ** (1.0 / years) - 1.0 if years > 0 and initial > 0 else 0.0

    # Annualized volatility (from weekly returns)
    weekly_rets = wr["return"].values
    ann_vol = np.std(weekly_rets, ddof=1) * np.sqrt(52) if len(weekly_rets) > 1 else 0.0

    # Sharpe (assuming 0% risk-free)
    sharpe = cagr / ann_vol if ann_vol > 0 else 0.0

    # Sortino
    downside = weekly_rets[weekly_rets < 0]
    down_std = np.std(downside, ddof=1) * np.sqrt(52) if len(downside) > 1 else 0.0
    sortino = cagr / down_std if down_std > 0 else 0.0

    # Max drawdown
    max_dd = eq["drawdown"].min() if "drawdown" in eq.columns else 0.0

    # Hit rate
    n_positive = np.sum(weekly_rets > 0)
    hit_rate = n_positive / len(weekly_rets) if len(weekly_rets) > 0 else 0.0

    # Avg win / avg loss
    wins = weekly_rets[weekly_rets > 0]
    losses = weekly_rets[weekly_rets < 0]
    avg_win = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0

    # Turnover (from trade log)
    capital = result.config.strategy.strategy_capital_usd
    trades = result.trade_log
    n_rebalances = len(result.weekly_returns)
    total_traded = sum(t.usd_value for t in trades)
    avg_turnover = total_traded / (capital * n_rebalances) if n_rebalances > 0 else 0.0

    # Total fees
    total_fees = sum(t.fee_usd for t in trades)

    # Trade stats
    n_stops = sum(1 for t in trades if t.reason == "stop_loss")
    n_tp = sum(1 for t in trades if t.reason == "take_profit")

    metrics = {
        "initial_capital": initial,
        "final_equity": final,
        "total_return": final / initial - 1.0,
        "cagr": cagr,
        "ann_volatility": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "hit_rate": hit_rate,
        "avg_weekly_win": avg_win,
        "avg_weekly_loss": avg_loss,
        "win_loss_ratio": abs(avg_win / avg_loss) if avg_loss != 0 else float("inf"),
        "avg_turnover_per_rebalance": avg_turnover,
        "total_fees_usd": total_fees,
        "total_trades": len(trades),
        "stop_losses_hit": n_stops,
        "take_profits_hit": n_tp,
        "n_weeks": len(weekly_rets),
        "backtest_days": days,
    }
    return metrics


def compute_btc_benchmark(price_data: Dict[str, pd.DataFrame],
                          start_date, end_date, capital: float) -> pd.DataFrame:
    """Compute buy-and-hold BTC equity curve over the same period."""
    if "BTC" not in price_data:
        return pd.DataFrame()
    df = price_data["BTC"]
    mask = (df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))
    df_period = df[mask].copy()
    if df_period.empty:
        return pd.DataFrame()
    initial_price = df_period["close"].iloc[0]
    df_period = df_period.reset_index()
    df_period["equity"] = capital * df_period["close"] / initial_price
    return df_period[["date", "equity"]]


def print_metrics(metrics: dict):
    """Print formatted metrics table to console."""
    print("\n" + "=" * 60)
    print("  BACKTEST PERFORMANCE SUMMARY")
    print("=" * 60)
    fmt = [
        ("Initial Capital",      f"${metrics['initial_capital']:,.2f}"),
        ("Final Equity",         f"${metrics['final_equity']:,.2f}"),
        ("Total Return",         f"{metrics['total_return']:+.1%}"),
        ("CAGR",                 f"{metrics['cagr']:+.1%}"),
        ("Ann. Volatility",      f"{metrics['ann_volatility']:.1%}"),
        ("Sharpe Ratio",         f"{metrics['sharpe']:.2f}"),
        ("Sortino Ratio",        f"{metrics['sortino']:.2f}"),
        ("Max Drawdown",         f"{metrics['max_drawdown']:.1%}"),
        ("Hit Rate (weeks)",     f"{metrics['hit_rate']:.1%}"),
        ("Avg Weekly Win",       f"{metrics['avg_weekly_win']:+.2%}"),
        ("Avg Weekly Loss",      f"{metrics['avg_weekly_loss']:+.2%}"),
        ("Win/Loss Ratio",       f"{metrics['win_loss_ratio']:.2f}"),
        ("Avg Turnover/Rebal",   f"{metrics['avg_turnover_per_rebalance']:.1%}"),
        ("Total Fees",           f"${metrics['total_fees_usd']:.2f}"),
        ("Total Trades",         f"{metrics['total_trades']}"),
        ("Stop-Losses Hit",      f"{metrics['stop_losses_hit']}"),
        ("Take-Profits Hit",     f"{metrics['take_profits_hit']}"),
        ("Weeks",                f"{metrics['n_weeks']}"),
    ]
    for label, val in fmt:
        print(f"  {label:<25s} {val:>15s}")
    print("=" * 60 + "\n")


def plot_results(result: BacktestResult, metrics: dict,
                 btc_bench: Optional[pd.DataFrame] = None,
                 save_dir: Optional[Path] = None):
    """Generate and save backtest plots."""
    if save_dir is None:
        save_dir = OUTPUT_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    eq = result.equity_curve
    wr = result.weekly_returns

    # 1. Equity curve
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(eq["date"], eq["equity"], label="Momentum Strategy", linewidth=1.5, color="#2196F3")
    if btc_bench is not None and not btc_bench.empty:
        ax.plot(btc_bench["date"], btc_bench["equity"],
                label="BTC Buy & Hold", linewidth=1.2, color="#FF9800", alpha=0.8)
    ax.set_ylabel("Equity (USD)")
    ax.set_title("Equity Curve — Altcoin Momentum Strategy")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(save_dir / "equity_curve.png", dpi=150)
    plt.close(fig)
    logger.info(f"Saved equity_curve.png")

    # 2. Drawdown
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(eq["date"], eq["drawdown"], 0, color="#F44336", alpha=0.4)
    ax.plot(eq["date"], eq["drawdown"], color="#F44336", linewidth=0.8)
    ax.set_ylabel("Drawdown")
    ax.set_title("Drawdown Curve")
    ax.grid(True, alpha=0.3)
    import matplotlib.ticker as mtick
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(save_dir / "drawdown.png", dpi=150)
    plt.close(fig)
    logger.info(f"Saved drawdown.png")

    # 3. Weekly returns distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(wr["return"], bins=40, color="#4CAF50", alpha=0.7, edgecolor="white")
    ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
    ax.axvline(wr["return"].mean(), color="#2196F3", linestyle="--",
               linewidth=1.2, label=f"Mean: {wr['return'].mean():.2%}")
    ax.set_xlabel("Weekly Return")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Weekly Returns")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_dir / "weekly_returns_dist.png", dpi=150)
    plt.close(fig)
    logger.info(f"Saved weekly_returns_dist.png")

    # 4. Rolling 12-week Sharpe
    if len(wr) > 12:
        fig, ax = plt.subplots(figsize=(14, 4))
        rolling_mean = wr["return"].rolling(12).mean()
        rolling_std = wr["return"].rolling(12).std()
        rolling_sharpe = (rolling_mean / rolling_std * np.sqrt(52)).dropna()
        ax.plot(wr["date"].iloc[11:], rolling_sharpe.values, color="#9C27B0", linewidth=1.2)
        ax.axhline(0, color="black", linestyle="--", linewidth=0.5)
        ax.set_ylabel("Rolling 12-Week Sharpe (ann.)")
        ax.set_title("Rolling Sharpe Ratio")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(save_dir / "rolling_sharpe.png", dpi=150)
        plt.close(fig)
        logger.info(f"Saved rolling_sharpe.png")


def save_csvs(result: BacktestResult, save_dir: Optional[Path] = None):
    """Save backtest outputs as CSV files."""
    if save_dir is None:
        save_dir = OUTPUT_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    # Equity curve
    result.equity_curve.to_csv(save_dir / "equity_curve.csv", index=False)

    # Weekly returns
    result.weekly_returns.to_csv(save_dir / "weekly_returns.csv", index=False)

    # Trade log
    trades_data = [{
        "date": t.date, "symbol": t.symbol, "side": t.side,
        "raw_price": t.raw_price, "exec_price": t.exec_price,
        "quantity": t.quantity, "usd_value": t.usd_value,
        "fee_usd": t.fee_usd, "reason": t.reason,
    } for t in result.trade_log]
    pd.DataFrame(trades_data).to_csv(save_dir / "trade_log.csv", index=False)

    # Positions history
    pd.DataFrame(result.positions_history).to_csv(
        save_dir / "positions_history.csv", index=False
    )

    logger.info(f"Saved CSVs to {save_dir}")
