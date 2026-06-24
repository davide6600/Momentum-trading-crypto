"""
run_signals.py — Generate this week's momentum signal report with regime check.

Usage:
    python scripts/run_signals.py [--config CONFIG_DIR]
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config
from src.data_ingestion import download_all_symbols
from src.universe import load_all_price_data, filter_universe, compute_regime_filters
from src.signals import compute_signals
from src.portfolio import select_winners
from src.utils import setup_logging

logger = setup_logging("run_signals")


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="Generate weekly momentum signals")
    parser.add_argument("--config", default="config", help="Config directory")
    parser.add_argument("--refresh", action="store_true", help="Download latest data first")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.refresh:
        logger.info("Refreshing data...")
        download_all_symbols(config, incremental=True)

    price_data = load_all_price_data()
    if not price_data:
        logger.error("No price data. Run with --refresh or download data first.")
        sys.exit(1)

    now = datetime.utcnow()
    logger.info(f"Generating signals as of {now.strftime('%Y-%m-%d %H:%M UTC')}")

    universe = filter_universe(price_data, config, now)
    
    # Compute regime filter values
    btc_above_ma, breadth_pct, breadth_pass = compute_regime_filters(price_data, universe, config, now)
    
    signals = compute_signals(price_data, universe, now, config)
    winners = select_winners(signals, config)

    print("\n" + "=" * 70)
    print("  WEEKLY SIGNAL & REGIME REPORT")
    print(f"  Date: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    
    sc = config.strategy
    print(f"  REGIME FILTERS STATUS:")
    btc_status = "PASS" if btc_above_ma else "FAIL"
    breadth_status = "PASS" if breadth_pass else "FAIL"
    
    print(f"    BTC 200D MA Filter:    {btc_status} (BTC is {'above' if btc_above_ma else 'below'} 200D MA)")
    print(f"    Market Breadth Filter: {breadth_status} ({breadth_pct:.1%} of universe above 200D MA, required >= {sc.min_breadth_pct:.1%})")
    
    overall_halt = not ((not sc.enable_btc_ma_filter or btc_above_ma) and (not sc.enable_breadth_filter or breadth_pass))
    if overall_halt:
        print("\n  [HALT] STRATEGY REGIME HALT: Recommended to stay 100% in CASH this week.")
    else:
        print("\n  [ACTIVE] STRATEGY REGIME ACTIVE: Trading allowed.")

    if winners.empty or overall_halt:
        print("\n  TARGET PORTFOLIO: Stay in Cash (0 positions).\n")
    else:
        print(f"\n  TARGET PORTFOLIO ({len(winners)} positions):\n")
        for _, w in winners.iterrows():
            print(
                f"    {w['symbol']:>8s}  |  "
                f"R30={w['r30']:+6.1%}  |  "
                f"R7={w['r7']:+6.1%}  |  "
                f"Price=${w['close']:.4f}  |  "
                f"Alloc=${w['target_usd']:.0f}  |  "
                f"Qty={w['target_qty']:.4f}"
            )
        print()
        sl = config.strategy.stop_loss_pct
        tp = config.strategy.take_profit_pct
        print(f"  Stop-loss: {sl:.0%} from entry  |  Take-profit: {tp:.0%} from entry")
        
    print("=" * 70 + "\n")

    # Also show top 20 by momentum for context
    if not signals.empty:
        print("  TOP 20 by R30 (full ranking):\n")
        top20 = signals.head(20)
        for _, s in top20.iterrows():
            print(
                f"    {s['symbol']:>8s}  R30={s['r30']:+6.1%}  "
                f"R7={s['r7']:+6.1%}  Vol7d=${s['avg_volume_7d_usd']/1e6:.1f}M"
            )
        print()


if __name__ == "__main__":
    main()
