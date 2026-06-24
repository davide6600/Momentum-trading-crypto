"""
run_improved_backtest.py — Run the IMPROVED strategy vs the ORIGINAL, side by side.

Loads both strategy configs, runs both through the same price data, and outputs
a comprehensive comparison table + overlay equity curve chart.
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config, AppConfig, UniverseConfig, StrategyConfig, _load_yaml, _dict_to_dataclass
from src.universe import load_all_price_data
from src.backtest import run_backtest
from src.analytics import compute_metrics, print_metrics, save_csvs, compute_btc_benchmark
from src.utils import setup_logging, ensure_dirs, OUTPUT_DIR

logger = setup_logging("run_improved", log_file="improved_backtest.log")


def load_improved_config(config_dir: str = "config") -> AppConfig:
    """Load config using strategy_improved.yaml instead of strategy.yaml."""
    config_path = Path(config_dir)
    
    # Universe config (standard)
    universe_data = _load_yaml(config_path / "universe.yaml")
    universe = _dict_to_dataclass(UniverseConfig, universe_data)
    
    # Strategy config (IMPROVED)
    strategy_data = _load_yaml(config_path / "strategy_improved.yaml")
    strategy = _dict_to_dataclass(StrategyConfig, strategy_data)
    
    return AppConfig(universe=universe, strategy=strategy)


def plot_comparison(orig_res, improved_res, btc_bench, out_dir):
    """Plot original vs improved vs BTC benchmark."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
    
    # --- Equity Curve ---
    ax = axes[0]
    o_curve = orig_res.equity_curve
    i_curve = improved_res.equity_curve
    
    ax.plot(o_curve["date"], o_curve["equity"], 
            label="Original Strategy", color="#FF6B6B", linewidth=1.5, alpha=0.8)
    ax.plot(i_curve["date"], i_curve["equity"], 
            label="Improved Strategy", color="#4ECDC4", linewidth=2.0)
    
    if btc_bench is not None and not btc_bench.empty:
        ax.plot(btc_bench["date"], btc_bench["equity"],
                label="BTC Buy & Hold", color="#FFD93D", linewidth=1.2, alpha=0.6)
    
    ax.set_ylabel("Equity (USD)", fontsize=12)
    ax.set_title("Equity Curve — Original vs Improved Strategy", fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")
    
    # --- Drawdown ---
    ax2 = axes[1]
    ax2.fill_between(o_curve["date"], o_curve["drawdown"] * 100, 0, 
                     label="Original DD", color="#FF6B6B", alpha=0.3)
    ax2.fill_between(i_curve["date"], i_curve["drawdown"] * 100, 0,
                     label="Improved DD", color="#4ECDC4", alpha=0.3)
    ax2.plot(o_curve["date"], o_curve["drawdown"] * 100, color="#FF6B6B", linewidth=0.8)
    ax2.plot(i_curve["date"], i_curve["drawdown"] * 100, color="#4ECDC4", linewidth=0.8)
    ax2.set_ylabel("Drawdown %", fontsize=12)
    ax2.set_xlabel("Date", fontsize=12)
    ax2.set_title("Drawdown Comparison", fontsize=12)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    fig.tight_layout()
    fig.savefig(out_dir / "improved_comparison.png", dpi=150)
    plt.close(fig)
    logger.info(f"Saved improved_comparison.png")


def print_comparison_table(o_metrics, i_metrics):
    """Print clean comparison table."""
    metrics_to_compare = [
        ("Initial Capital",      "initial_capital",     "${:,.2f}"),
        ("Final Equity",         "final_equity",        "${:,.2f}"),
        ("Total Return",         "total_return",        "{:+.1%}"),
        ("CAGR",                 "cagr",                "{:+.1%}"),
        ("Ann. Volatility",      "ann_volatility",      "{:.1%}"),
        ("Sharpe Ratio",         "sharpe",              "{:.3f}"),
        ("Sortino Ratio",        "sortino",             "{:.3f}"),
        ("Max Drawdown",         "max_drawdown",        "{:.1%}"),
        ("Hit Rate (weeks)",     "hit_rate",            "{:.1%}"),
        ("Avg Weekly Win",       "avg_weekly_win",      "{:+.2%}"),
        ("Avg Weekly Loss",      "avg_weekly_loss",     "{:+.2%}"),
        ("Win/Loss Ratio",       "win_loss_ratio",      "{:.2f}"),
        ("Avg Turnover/Rebal",   "avg_turnover_per_rebalance", "{:.1%}"),
        ("Total Fees",           "total_fees_usd",      "${:,.2f}"),
        ("Total Trades",         "total_trades",        "{:d}"),
        ("Stop-Losses Hit",      "stop_losses_hit",     "{:d}"),
        ("Take-Profits Hit",     "take_profits_hit",    "{:d}"),
        ("Weeks",                "n_weeks",             "{:d}"),
    ]
    
    print("\n" + "=" * 85)
    print("  STRATEGY COMPARISON: ORIGINAL vs IMPROVED")
    print("=" * 85)
    print(f"  {'Metric':<25s} | {'Original':^20s} | {'Improved':^20s} | {'Delta':^12s}")
    print("-" * 85)
    
    for label, key, fmt in metrics_to_compare:
        val_o = o_metrics.get(key, 0.0)
        val_i = i_metrics.get(key, 0.0)
        
        str_o = fmt.format(val_o) if val_o is not None else "N/A"
        str_i = fmt.format(val_i) if val_i is not None else "N/A"
        
        # Compute delta for numeric values
        try:
            if isinstance(val_o, (int, float)) and isinstance(val_i, (int, float)):
                delta = val_i - val_o
                if "pct" in key or "return" in key or "cagr" in key or "volatility" in key or "drawdown" in key or "hit_rate" in key or "turnover" in key:
                    delta_str = f"{delta:+.1%}"
                elif "sharpe" in key or "sortino" in key or "ratio" in key:
                    delta_str = f"{delta:+.3f}"
                elif "fees" in key or "capital" in key or "equity" in key:
                    delta_str = f"${delta:+,.0f}"
                else:
                    delta_str = f"{delta:+.0f}"
            else:
                delta_str = ""
        except:
            delta_str = ""
        
        print(f"  {label:<25s} | {str_o:>20s} | {str_i:>20s} | {delta_str:>12s}")
    
    print("=" * 85 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run improved vs original backtest comparison")
    parser.add_argument("--config", default="config", help="Path to config directory")
    parser.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

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

    # Load both configs
    original_config = load_config(args.config)
    improved_config = load_improved_config(args.config)

    # Print config differences
    print("\n" + "=" * 60)
    print("  IMPROVED STRATEGY PARAMETERS")
    print("=" * 60)
    isc = improved_config.strategy
    osc = original_config.strategy
    param_diffs = [
        ("lookback_days", osc.lookback_days, isc.lookback_days),
        ("holding_period_weeks", osc.holding_period_weeks, isc.holding_period_weeks),
        ("ranking_metric", osc.ranking_metric, isc.ranking_metric),
        ("weighting_scheme", osc.weighting_scheme, isc.weighting_scheme),
        ("n_winners", osc.n_winners, isc.n_winners),
        ("max_short_term_runup", osc.max_short_term_runup, isc.max_short_term_runup),
        ("min_breadth_pct", osc.min_breadth_pct, isc.min_breadth_pct),
        ("stop_loss_pct", osc.stop_loss_pct, isc.stop_loss_pct),
        ("take_profit_pct", osc.take_profit_pct, isc.take_profit_pct),
        ("max_per_position_pct", osc.max_per_position_pct, isc.max_per_position_pct),
        ("enable_atr_stop", getattr(osc, 'enable_atr_stop', False), isc.enable_atr_stop),
        ("atr_multiplier", getattr(osc, 'atr_multiplier', 'N/A'), isc.atr_multiplier),
        ("enable_breadth_acceleration", getattr(osc, 'enable_breadth_acceleration', False), isc.enable_breadth_acceleration),
        ("enable_mean_reversion_filter", getattr(osc, 'enable_mean_reversion_filter', False), isc.enable_mean_reversion_filter),
    ]
    for param, old, new in param_diffs:
        marker = " * CHANGED" if old != new else ""
        print(f"  {param:<35s} {str(old):>10s} -> {str(new):>10s}{marker}")
    print("=" * 60 + "\n")

    # ── Run 1: Original Strategy ──
    print("Running ORIGINAL strategy backtest...")
    logger.info("Running original strategy backtest...")
    o_res = run_backtest(original_config, start_date, end_date, price_data)
    o_metrics = compute_metrics(o_res)

    # ── Run 2: Improved Strategy ──
    print("Running IMPROVED strategy backtest...")
    logger.info("Running improved strategy backtest...")
    i_res = run_backtest(improved_config, start_date, end_date, price_data)
    i_metrics = compute_metrics(i_res)

    # ── BTC Benchmark ──
    btc_bench = compute_btc_benchmark(
        price_data, start_date, end_date, original_config.strategy.strategy_capital_usd
    )

    # ── Output ──
    print_comparison_table(o_metrics, i_metrics)

    if not btc_bench.empty:
        btc_ret = btc_bench["equity"].iloc[-1] / btc_bench["equity"].iloc[0] - 1
        print(f"  BTC Buy & Hold Return: {btc_ret:+.1%}\n")

    # Save improved results
    improved_out = Path("output") / "improved"
    improved_out.mkdir(parents=True, exist_ok=True)
    save_csvs(i_res, save_dir=improved_out)
    logger.info(f"Saved improved CSVs to {improved_out}/")

    # Save comparison chart
    out_dir = Path("output")
    plot_comparison(o_res, i_res, btc_bench, out_dir)

    # Save summary metrics to CSV
    summary = pd.DataFrame([
        {"strategy": "original", **o_metrics},
        {"strategy": "improved", **i_metrics},
    ])
    summary.to_csv(out_dir / "improved_vs_original.csv", index=False)
    logger.info(f"Saved improved_vs_original.csv")

    print(f"\nDone! Charts saved to {out_dir}/")
    print(f"Improved CSVs saved to {improved_out}/")


if __name__ == "__main__":
    main()
