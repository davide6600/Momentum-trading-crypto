"""
run_backtest.py — CLI entry point for running the historical backtest.
Compiles a comparison between filtered and unfiltered versions of the strategy.
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.universe import load_all_price_data
from src.backtest import run_backtest
from src.analytics import compute_metrics, print_metrics, save_csvs, compute_btc_benchmark
from src.utils import setup_logging, ensure_dirs

logger = setup_logging("run_backtest", log_file="backtest.log")


def plot_comparison(filtered_res, unfiltered_res, btc_bench, out_dir):
    """Plot filtered vs unfiltered vs BTC benchmark on a single chart."""
    plt.figure(figsize=(12, 6))
    
    # Filtered
    f_curve = filtered_res.equity_curve
    plt.plot(f_curve["date"], f_curve["equity"], label="Momentum (With Regime Filters)", color="#1f77b4", linewidth=2)
    
    # Unfiltered
    uf_curve = unfiltered_res.equity_curve
    plt.plot(uf_curve["date"], uf_curve["equity"], label="Momentum (No Filters)", color="#ff7f0e", linewidth=1.5, linestyle="--")
    
    # BTC
    if not btc_bench.empty:
        plt.plot(btc_bench["date"], btc_bench["equity"], label="BTC Buy & Hold", color="#7f7f7f", alpha=0.7)
        
    plt.title("Equity Curve Comparison")
    plt.xlabel("Date")
    plt.ylabel("Equity (USD)")
    plt.yscale("log")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "comparison_equity_curve.png", dpi=150)
    plt.close()

    # Drawdown comparison
    plt.figure(figsize=(12, 4))
    plt.fill_between(f_curve["date"], f_curve["drawdown"] * 100, 0, label="With Regime Filters", color="#1f77b4", alpha=0.4)
    plt.plot(uf_curve["date"], uf_curve["drawdown"] * 100, label="No Filters", color="#ff7f0e", linestyle="--")
    plt.title("Drawdown Comparison (%)")
    plt.xlabel("Date")
    plt.ylabel("Drawdown %")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "comparison_drawdown.png", dpi=150)
    plt.close()


def print_comparison_table(f_metrics, uf_metrics):
    """Print a clean comparative table of the two runs."""
    metrics_to_compare = [
        ("Initial Capital", "initial_capital", "${:,.2f}"),
        ("Final Equity", "final_equity", "${:,.2f}"),
        ("Total Return", "total_return", "{:+.1%}"),
        ("CAGR", "cagr", "{:+.1%}"),
        ("Ann. Volatility", "ann_volatility", "{:.1%}"),
        ("Sharpe Ratio", "sharpe", "{:.2f}"),
        ("Sortino Ratio", "sortino", "{:.2f}"),
        ("Max Drawdown", "max_drawdown", "{:.1%}"),
        ("Hit Rate (weeks)", "hit_rate", "{:.1%}"),
        ("Total Trades", "total_trades", "{:d}"),
        ("Total Fees Paid", "total_fees_usd", "${:,.2f}"),
        ("Avg Turnover/Rebal", "avg_turnover_per_rebalance", "{:.1%}"),
        ("Stop-Losses Hit", "stop_losses_hit", "{:d}"),
        ("Take-Profits Hit", "take_profits_hit", "{:d}")
    ]
    
    print("\n" + "=" * 80)
    print("  STRATEGY COMPARISON: REGIME FILTERS VS RAW MOMENTUM")
    print("=" * 80)
    print(f"  {'Metric':<25s} | {'With Regime Filters':^20s} | {'No Filters (Raw)':^20s}")
    print("-" * 80)
    for label, key, fmt in metrics_to_compare:
        val_f = f_metrics.get(key, 0.0)
        val_uf = uf_metrics.get(key, 0.0)
        
        # Check for None values
        str_f = fmt.format(val_f) if val_f is not None else "N/A"
        str_uf = fmt.format(val_uf) if val_uf is not None else "N/A"
        
        print(f"  {label:<25s} | {str_f:>20s} | {str_uf:>20s}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run altcoin momentum backtest")
    parser.add_argument("--config", default="config", help="Path to config directory")
    parser.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Parse dates
    end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.utcnow()
    start_date = (datetime.strptime(args.start, "%Y-%m-%d") if args.start
                  else end_date - timedelta(days=1825))

    ensure_dirs()
    logger.info("Loading price data...")
    price_data = load_all_price_data()

    if not price_data:
        logger.error("No price data found. Run data download first.")
        sys.exit(1)

    # Run 1: With Regime Filters (config default: True)
    logger.info("Running backtest WITH regime filters...")
    f_res = run_backtest(config, start_date, end_date, price_data)
    f_metrics = compute_metrics(f_res)

    # Run 2: Without Regime Filters
    logger.info("Running backtest WITHOUT regime filters...")
    uf_res = run_backtest(
        config, start_date, end_date, price_data,
        override_filters={"enable_btc_ma_filter": False, "enable_breadth_filter": False}
    )
    uf_metrics = compute_metrics(uf_res)

    # Compute BTC benchmark
    btc_bench = compute_btc_benchmark(
        price_data, start_date, end_date, config.strategy.strategy_capital_usd
    )

    # Output comparison table
    print_comparison_table(f_metrics, uf_metrics)

    if not btc_bench.empty:
        btc_ret = btc_bench["equity"].iloc[-1] / btc_bench["equity"].iloc[0] - 1
        print(f"  BTC Buy & Hold Return: {btc_ret:+.1%}\n")

    # Save CSVs for the active (filtered) run
    save_csvs(f_res)

    # Save comparison charts
    out_dir = Path("output")
    plot_comparison(f_res, uf_res, btc_bench, out_dir)
    logger.info(f"Saved comparison charts to {out_dir}/")


if __name__ == "__main__":
    main()
