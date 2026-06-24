"""
run_experiments.py — Run strategy backtests across different defensive assets (cash, BTC, QQQ, SPY)
and compile a comparative table.
"""
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.universe import load_all_price_data
from src.backtest import run_backtest
from src.analytics import compute_metrics, compute_btc_benchmark

def main():
    config = load_config("config")
    
    # Run over the full 5 years
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=1825)
    
    print("Loading price data...")
    price_data = load_all_price_data()
    if not price_data:
        print("No price data found.")
        sys.exit(1)
        
    defensive_options = ["cash", "BTC", "QQQ", "SPY"]
    results = {}
    
    # Create experiments output directory
    exp_dir = Path("output_experiments")
    exp_dir.mkdir(exist_ok=True)
    
    # Plot setup
    plt.figure(figsize=(14, 7))
    
    # Load BTC benchmark
    btc_bench = compute_btc_benchmark(price_data, start_date, end_date, config.strategy.strategy_capital_usd)
    if not btc_bench.empty:
        plt.plot(btc_bench["date"], btc_bench["equity"], label="BTC Buy & Hold", color="gray", alpha=0.6, linestyle=":")
        
    colors = {"cash": "red", "BTC": "orange", "QQQ": "blue", "SPY": "green"}
    
    for asset in defensive_options:
        print(f"\nRunning experiment with defensive_asset = {asset}...")
        config.strategy.defensive_asset = asset
        
        # Run backtest
        res = run_backtest(config, start_date, end_date, price_data)
        metrics = compute_metrics(res)
        results[asset] = metrics
        
        # Save csvs for this asset
        asset_dir = exp_dir / f"output_{asset.lower()}"
        asset_dir.mkdir(exist_ok=True)
        
        res.equity_curve.to_csv(asset_dir / "equity_curve.csv", index=False)
        res.weekly_returns.to_csv(asset_dir / "weekly_returns.csv", index=False)
        
        # Plot this asset
        plt.plot(res.equity_curve["date"], res.equity_curve["equity"], label=f"Defensive: {asset}", color=colors[asset], linewidth=1.8)
        
    plt.title("Equity Curve Comparison — Different Defensive Assets (5 Years)")
    plt.xlabel("Date")
    plt.ylabel("Equity (USD)")
    plt.yscale("log")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(exp_dir / "defensive_assets_comparison.png", dpi=150)
    plt.close()
    
    # Print comparison table
    metrics_to_compare = [
        ("Final Equity", "final_equity", "${:,.2f}"),
        ("Total Return", "total_return", "{:+.1%}"),
        ("CAGR", "cagr", "{:+.1%}"),
        ("Ann. Volatility", "ann_volatility", "{:.1%}"),
        ("Sharpe Ratio", "sharpe", "{:.2f}"),
        ("Sortino Ratio", "sortino", "{:.2f}"),
        ("Max Drawdown", "max_drawdown", "{:.1%}"),
        ("Total Trades", "total_trades", "{:d}"),
        ("Total Fees Paid", "total_fees_usd", "${:,.2f}"),
    ]
    
    print("\n" + "=" * 100)
    print("  EXPERIMENT RESULTS: COMPARISON OF DEFENSIVE ASSETS")
    print("=" * 100)
    header = f"  {'Metric':<25s}"
    for asset in defensive_options:
        header += f" | {asset:^15s}"
    print(header)
    print("-" * 100)
    for label, key, fmt in metrics_to_compare:
        row = f"  {label:<25s}"
        for asset in defensive_options:
            val = results[asset].get(key, 0.0)
            str_val = fmt.format(val) if val is not None else "N/A"
            row += f" | {str_val:>15s}"
        print(row)
    print("=" * 100 + "\n")

if __name__ == "__main__":
    main()
