# Altcoin Weekly Cross-Sectional Momentum Strategy

A modular, config-driven Python system for researching, backtesting, and paper-trading a **weekly cross-sectional momentum strategy** on liquid altcoins.

## Strategy Concept

- **Once every 2 weeks** (Sunday 13:00 UTC), rank all eligible altcoins by their **30-day return (R30)**.
- Apply **Regime Filters**: Only enter positions when BTC is above its 200-day MA and > 50% of the universe is above its 200-day MA.
- Select the **top 3 winners** that pass momentum, volume, and blow-off filters.
- Construct an **equal-weight long-only basket** and hold for two weeks.
- Rebalance fully every 2 weeks (with daily stop-loss checks).

See [`docs/reports/altcoin-momentum.md`](docs/reports/altcoin-momentum.md) for the complete strategy specification.

## Documentation & Reports

The repository documentation has been organized into the following sections:

*   **Guides & Setup**:
    *   [`docs/guides/GUIDA_ATTIVAZIONE_AUTOMAZIONE.md`](docs/guides/GUIDA_ATTIVAZIONE_AUTOMAZIONE.md) — Step-by-step guide to set up the Telegram bot, GitHub Actions workflow, and GitHub Pages dashboard.
    *   [`docs/guides/SIMULATION_AND_ARCHITECTURE.md`](docs/guides/SIMULATION_AND_ARCHITECTURE.md) — System flowcharts, directory layouts, and execution parameters.
*   **Strategy Reports**:
    *   [`docs/reports/ANALISI_OTTIMIZZAZIONE_LOOKBACK.md`](docs/reports/ANALISI_OTTIMIZZAZIONE_LOOKBACK.md) — Lookback optimization grid search results comparing SMA, EMA, and WMA indicators.
    *   [`docs/reports/BTC_USDT_STRATEGY_REPORT.md`](docs/reports/BTC_USDT_STRATEGY_REPORT.md) — Detailed Italian report of the single-asset BTC-USDT strategy metrics and results.
    *   [`docs/reports/simulation_report_btc_strategy.md`](docs/reports/simulation_report_btc_strategy.md) — English report containing the performance summary of the optimal 273-day SMA strategy.
    *   [`docs/reports/altcoin-momentum.md`](docs/reports/altcoin-momentum.md) — Core specification of the cross-sectional altcoin momentum strategy.
*   **Research & Notes**:
    *   [`docs/research/avoided_overfitting.md`](docs/research/avoided_overfitting.md) — Explanation of overfitting and our neighbor stability analysis methodology.
    *   [`docs/research/past_conversation.md`](docs/research/past_conversation.md) — Historical conversation and session notes.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys (copy template and fill in)
cp config/secrets.yaml.template config/secrets.yaml
# Edit config/secrets.yaml with your Binance API keys

# 3. Download historical data (~2 years of daily OHLCV)
python scripts/download_data.py --config config --days 730

# 4. Run backtest
python scripts/run_backtest.py --config config --start 2024-06-15 --end 2026-06-14

# 5. Generate this week's signal report
python scripts/run_signals.py --config config --refresh

# 6. Paper-trade rebalance (dry-run, no real orders)
python scripts/run_rebalance.py --config config --dry-run
```

## Architecture

```
config/          Configuration files (universe, strategy, secrets)
src/             Core Python modules
  config_loader  Load and validate YAML configs
  data_ingestion Download/refresh OHLCV via CCXT (Binance)
  universe       Build and filter investable universe
  signals        Compute R30, R7, cross-sectional rankings
  portfolio      Select winners and construct target portfolio
  backtest       Weekly simulation engine with intra-week risk checks
  analytics      Performance metrics, benchmarks, and plots
  risk           Stop-loss, take-profit, kill-switch logic
  execution      Live/paper order execution scaffold
scripts/         CLI entry points
  download_data  Fetch historical OHLCV
  run_backtest   Run historical simulation
  run_signals    Generate weekly signal report
  run_rebalance  Execute weekly rebalance (paper/live)
data/daily/      OHLCV CSV files per symbol (auto-generated)
output/          Backtest results, plots, logs (auto-generated)
```

## Configuration

All parameters are in YAML config files — no hardcoded constants:

- **`config/universe.yaml`** — exchange, volume filters, stablecoin blacklist
- **`config/strategy.yaml`** — lookback, holding period, N winners, thresholds, risk limits
- **`config/secrets.yaml`** — API keys (gitignored)

## Key Parameters (Defaults)

| Parameter | Value | Description |
|-----------|-------|-------------|
| Capital | $2,000 | Total strategy capital |
| Winners | 3 | Max positions in basket (optimized from 5) |
| Lookback | 30 days | R30 ranking signal |
| Holding Period | 2 weeks | Hold duration (optimized from 1 week) |
| Min Momentum | +15% | R30 entry threshold |
| Max Blow-off | +50% | R7 cap to avoid parabolic entries (tightened from +100%) |
| BTC MA Filter | Enabled | Only trade when BTC > 200D MA |
| Breadth Filter| Enabled | Only trade when > 50% of universe > 200D MA |
| Stop-Loss | -12% | Per-position stop from entry |
| Take-Profit | +35% | Optional per-position target |
| Risk/Trade | 3% | Max capital at risk per position |
| Fee + Slippage | 0.2% | Round-trip cost model |

## Assumptions and Limitations

1. **Survivorship bias**: Only currently listed Binance pairs are included. Delisted coins are not captured.
2. **Market cap proxy**: Volume is used as a proxy for market cap ranking since Binance doesn't provide historical market cap.
3. **Execution at close**: Backtest assumes execution at daily close prices, which may not match real fills.
4. **No short selling**: Strategy is long-only; it goes to cash when no winners qualify.
5. **Data depth**: ~2 years of Binance daily data. CoinGecko integration for deeper history is a future enhancement.
