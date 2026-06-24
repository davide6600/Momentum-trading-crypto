"""
run_robustness_sweep.py — Run a parameter grid search to test strategy stability.

Tests combinations of:
- Lookback window (R30)
- Holding period (weeks)
- Number of winners
- Stop-loss threshold
- Regime filters status
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.universe import load_all_price_data
from src.backtest import run_backtest
from src.analytics import compute_metrics
from src.utils import setup_logging, ensure_dirs

# Use a separate logger to avoid cluttering standard backtest logs too much
logger = setup_logging("robustness_sweep", log_file="robustness_sweep.log")


def main():
    parser = argparse.ArgumentParser(description="Run robustness parameter sweep")
    parser.add_argument("--config", default="config", help="Path to config directory")
    parser.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    config = load_config(args.config)

    # Parse dates
    end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.utcnow()
    start_date = (datetime.strptime(args.start, "%Y-%m-%d") if args.start
                  else end_date - timedelta(days=730))

    ensure_dirs()
    print("Loading price data (this might take a few seconds)...")
    price_data = load_all_price_data()

    if not price_data:
        print("Error: No price data found. Download data first.")
        sys.exit(1)

    # Define Parameter Grid
    lookbacks = [15, 30, 45]
    holding_periods = [1, 2]
    winners_counts = [3, 5]
    stop_losses = [-0.08, -0.12, -0.16]
    ranking_metrics = ["return", "vol_adj"]
    
    # Filter combinations: (enable_btc_ma, enable_breadth)
    filter_combos = [
        (False, False, "None"),
        (True, False, "BTC_Only"),
        (False, True, "Breadth_Only"),
        (True, True, "Both")
    ]

    total_runs = len(lookbacks) * len(holding_periods) * len(winners_counts) * len(stop_losses) * len(filter_combos) * len(ranking_metrics)
    print(f"\nStarting Robustness Grid Sweep: {total_runs} combinations...")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("This will take a few minutes. Progress will be printed below.\n")

    results = []
    run_idx = 0

    # Temporarily set log level of other modules to WARNING to avoid printing millions of logs
    import logging
    logging.getLogger("backtest").setLevel(logging.WARNING)
    logging.getLogger("portfolio").setLevel(logging.WARNING)
    logging.getLogger("universe").setLevel(logging.WARNING)
    logging.getLogger("signals").setLevel(logging.WARNING)

    for lb in lookbacks:
        for hp in holding_periods:
            for n_win in winners_counts:
                for sl in stop_losses:
                    for enable_btc, enable_br, filter_name in filter_combos:
                        for r_metric in ranking_metrics:
                            run_idx += 1
                            if run_idx % 25 == 0 or run_idx == 1:
                                print(f"  Progress: Run {run_idx}/{total_runs} ({(run_idx/total_runs):.1%})")

                            # Set overrides
                            overrides = {
                                "lookback_days": lb,
                                "holding_period_weeks": hp,
                                "n_winners": n_win,
                                "stop_loss_pct": sl,
                                "enable_btc_ma_filter": enable_btc,
                                "enable_breadth_filter": enable_br,
                                "ranking_metric": r_metric
                            }

                            try:
                                # Run backtest
                                res = run_backtest(config, start_date, end_date, price_data, override_filters=overrides)
                                metrics = compute_metrics(res)

                                # Record results
                                results.append({
                                    "Lookback": lb,
                                    "Hold Weeks": hp,
                                    "Winners": n_win,
                                    "Stop Loss": sl,
                                    "Filters": filter_name,
                                    "Metric": r_metric,
                                    "Total Return": metrics["total_return"],
                                    "CAGR": metrics["cagr"],
                                    "Ann Vol": metrics["ann_volatility"],
                                    "Sharpe": metrics["sharpe"],
                                    "Sortino": metrics["sortino"],
                                    "MaxDD": metrics["max_drawdown"],
                                    "Trades": metrics["total_trades"],
                                    "Fees": metrics["total_fees_usd"],
                                    "Avg Turnover": metrics["avg_turnover_per_rebalance"],
                                    "Stops Hit": metrics["stop_losses_hit"]
                                })
                            except Exception as e:
                                logger.error(f"Failed run with params {overrides}: {e}")

    # Build DataFrame
    df_results = pd.DataFrame(results)
    
    # Save results to CSV
    sweep_path = Path("output/robustness_sweep.csv")
    df_results.to_csv(sweep_path, index=False)
    print(f"\nAll runs completed! Saved full sweep results to {sweep_path}")

    # Display Top 15 combinations by Sharpe Ratio
    df_sorted = df_results.sort_values(by="Sharpe", ascending=False)
    top15 = df_sorted.head(15).copy()
    
    # Format percentages and floats for printing
    for pct_col in ["Total Return", "CAGR", "Ann Vol", "MaxDD", "Avg Turnover"]:
        top15[pct_col] = top15[pct_col].map(lambda x: f"{x:+.1%}" if x is not None else "N/A")
    for flt_col in ["Sharpe", "Sortino"]:
        top15[flt_col] = top15[flt_col].map(lambda x: f"{x:.2f}" if x is not None else "N/A")
    top15["Fees"] = top15["Fees"].map(lambda x: f"${x:,.2f}" if x is not None else "N/A")

    print("\n" + "=" * 110)
    print("  TOP 15 PARAMETER COMBINATIONS BY SHARPE RATIO")
    print("=" * 110)
    print(tabulate(top15, headers="keys", showindex=False, tablefmt="psql"))
    print("=" * 110 + "\n")

    # Display Best and Worst filter configurations overall
    print("Performance by Filter Type (averaged across all other parameters):")
    filter_summary = df_results.groupby("Filters")[["Total Return", "Sharpe", "MaxDD", "Trades", "Fees"]].mean()
    print(tabulate(filter_summary, headers="keys", numalign="right", tablefmt="psql"))
    print()


if __name__ == "__main__":
    main()
