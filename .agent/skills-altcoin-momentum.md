# Skills: Altcoin Momentum Strategy

## 1. `download_ohlcv_data`
- **Module**: `src/data_ingestion.py`
- **Input**: Config (exchange, symbols, date range)
- **Output**: CSV files in `data/daily/{SYMBOL}.csv`
- **Failure modes**: API rate limits, network errors, missing pairs
- **Handling**: Retry with backoff, skip failed symbols with logging

## 2. `build_universe_and_filters`
- **Module**: `src/universe.py`
- **Input**: Price data CSVs, `universe.yaml` config, as-of date
- **Output**: List of eligible symbols for a given date
- **Failure modes**: Missing data, inconsistent symbols
- **Handling**: Drop symbols with insufficient history, log warnings

## 3. `compute_momentum_signals`
- **Module**: `src/signals.py`
- **Input**: Price data for filtered universe, as-of date, strategy config
- **Output**: DataFrame with R30, R7, rankings, percentiles per symbol
- **Failure modes**: Insufficient history for lookback calculation
- **Handling**: Exclude affected symbols

## 4. `select_winners`
- **Module**: `src/portfolio.py`
- **Input**: Signal DataFrame, strategy config
- **Output**: Target portfolio (symbols, weights, USD allocation, quantities)
- **Failure modes**: No symbols pass all filters
- **Handling**: Return empty portfolio (all-cash week)

## 5. `run_weekly_cross_sectional_backtest`
- **Module**: `src/backtest.py`
- **Input**: Price data, config, date range
- **Output**: Equity curve, trade log, weekly returns, position history
- **Failure modes**: Data gaps, parameter misconfigurations
- **Handling**: Skip affected weeks, log warnings

## 6. `generate_weekly_signals`
- **Script**: `scripts/run_signals.py`
- **Input**: Latest daily data (optionally refreshed), config
- **Output**: Formatted signal report with target portfolio
- **Failure modes**: Stale data, API errors
- **Handling**: Warn if data is >1 day old

## 7. `execute_rebalance_orders`
- **Module**: `src/execution.py`
- **Script**: `scripts/run_rebalance.py`
- **Input**: Current positions, target portfolio, execution config
- **Output**: Order list, execution results (dry-run or live)
- **Failure modes**: API errors, partial fills, insufficient balance
- **Handling**: Retry logic, dry_run default, max_position_size guard

## 8. `monitor_and_log_pnl`
- **Module**: `src/analytics.py` + `src/risk.py`
- **Input**: Portfolio state, price data
- **Output**: Metrics, equity curves, risk alerts
- **Failure modes**: Missing prices, stale data
- **Handling**: Use last known values, alert if stale
