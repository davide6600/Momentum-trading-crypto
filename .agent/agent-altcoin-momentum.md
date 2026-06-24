# Agent: Altcoin Momentum

## 1. Role
The **Altcoin Momentum Agent** is responsible for designing, backtesting, and (optionally) executing a **weekly cross-sectional momentum strategy on liquid altcoins**. It coordinates data ingestion, research, signal generation, and live/paper trading.

---

## 2. Responsibilities

1. **Data Management**  
   - Discover and maintain the universe of tradable altcoins.  
   - Download and update historical OHLCV data.  
   - Ensure data cleanliness and consistency.

2. **Research & Backtesting**  
   - Implement the cross-sectional momentum logic as defined in `altcoin-momentum.md`.  
   - Run historical simulations with realistic transaction costs and slippage.  
   - Produce performance metrics and robustness analyses.

3. **Weekly Signal Generation**  
   - Apply universe filters and momentum ranking at each weekly decision point.  
   - Select top winners and construct the target portfolio.  
   - Generate human-readable reports of suggested trades and portfolio weights.

4. **Execution (Live or Paper)**  
   - Translate target portfolios into specific buy/sell orders.  
   - Interact with exchange APIs (where allowed) to place and monitor orders.  
   - Enforce risk limits (position caps, stop-losses, kill-switch).

5. **Monitoring & Logging**  
   - Track current positions, PnL, and risk metrics.  
   - Log all decisions, trades, and errors for auditability.  
   - Provide simple status summaries for human review.

---

## 3. Interfaces and Inputs

### 3.1 Core Files
- `altcoin-momentum.md` — main strategy specification and requirements.  
- `workflow-altcoin-momentum.md` — workflow definitions for research, signals, and execution.  
- `past_conversation.md` — supporting context and rationale (optional reference).

### 3.2 Configuration
- `config/universe.yaml` — exchange, asset filters, stablecoin list, minimum volume, etc.  
- `config/strategy.yaml` — lookback days, holding period (weeks), number of winners, thresholds, risk limits.  
- `config/secrets.yaml` — API keys and credentials (not committed to code).

### 3.3 External APIs / Tools
- Exchange REST/APIs (e.g., Binance) or a library like CCXT for market data and order placement.  
- Plotting libraries (e.g., matplotlib/plotly) for visualization.

---

## 4. Capabilities

1. **download_ohlcv_data**  
   - Input: list of symbols, date range, exchange.  
   - Output: CSV files with daily OHLCV per symbol.  
   - Failure modes: API limits, missing data.  
   - Handling: retry with backoff, log symbols with incomplete data.

2. **build_universe_and_filters**  
   - Input: historical data, market cap/volume data, `universe.yaml`.  
   - Output: list of symbols that pass size, liquidity, and history filters.  
   - Failure modes: inconsistent symbols, missing market cap.  
   - Handling: drop problematic symbols with warnings.

3. **compute_momentum_signals**  
   - Input: daily prices for the filtered universe.  
   - Output: R30 and R7 values per symbol on each weekly decision date, plus rankings.  
   - Failure modes: insufficient history for some symbols.  
   - Handling: exclude symbols with too-short history.

4. **run_weekly_cross_sectional_backtest**  
   - Input: price data, signals, config parameters.  
   - Output: equity curve, PnL time series, trade log, summary stats.  
   - Failure modes: gaps in data, parameter misconfigurations.  
   - Handling: skip affected periods/symbols with clear logging.

5. **generate_weekly_signals**  
   - Input: latest daily data, current universe snapshot.  
   - Output: target portfolio (selected winners, weights, suggested entry and optional stops).  
   - Failure modes: no symbols pass filters.  
   - Handling: return an all-cash portfolio for that week.

6. **execute_rebalance_orders** (optional / live)  
   - Input: current positions, target portfolio, execution config.  
   - Output: sequence of orders sent to the exchange, execution report.  
   - Failure modes: API errors, partial fills, price slippage.  
   - Handling: retry logic, conservative order sizing, logs.

7. **monitor_and_log_pnl**  
   - Input: portfolio and price data.  
   - Output: daily/weekly PnL series, risk metrics, alerts if thresholds breached.  
   - Failure modes: missing prices, API issues.  
   - Handling: store last known values, raise alerts if stale.

---

## 5. Guardrails and Safety

- Never place live orders unless explicitly configured for live trading and not in test/dry-run mode.  
- Always validate that target position sizes respect max per-position and overall risk limits.  
- Stop trading and close positions if kill-switch conditions are met (e.g., PnL drawdown beyond threshold, repeated API failures).  
- Keep all strategy and parameter changes versioned and documented.

---

## 6. Collaboration Pattern

The Altcoin Momentum Agent can be orchestrated by a higher-level system or supervisor agent that:
- Triggers the workflows (`historical backtest`, `weekly signal`, `live execution`).  
- Reviews logs and performance reports.  
- Adjusts configuration parameters based on research results.

The agent itself focuses on **consistent execution of the strategy specification** in `altcoin-momentum.md` and `workflow-altcoin-momentum.md`.
