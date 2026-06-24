# Altcoin Weekly Cross-Sectional Momentum Strategy

## 0. Role and Objective
You are an engineering + quant research agent. Your task is to **design, backtest, and implement** a simple, robust, *weekly* cross-sectional momentum strategy on liquid altcoins.

Constraints:
- **Low frequency**: rebalanced once per week (or at most once every few days), not intraday HFT.
- **Long-only** on altcoins (no mandatory shorting, no complex derivatives).
- **Universe filtered for liquidity and size** (avoid illiquid micro-caps).
- **Simple architecture, few points of failure**: ideally one main exchange, one codebase, minimal moving parts.
- **Research-grade process**: include backtests, basic robustness checks, and clear logging.

Output: a working research + trading pipeline that could be run live with real capital after sufficient validation.

---

## 1. High-Level Strategy Description
The core idea is **cross-sectional momentum** on altcoins:

- Once per week, you rank a universe of sufficiently liquid altcoins by their **past 30-day performance**.
- You select the strongest coins ("winners") that also pass additional filters (liquidity, volume, no extreme pumps).
- You construct an **equal-weight long-only basket** of these winners and hold it for one week.
- One week later, you fully rebalance: exit positions that no longer qualify and enter new winners.

This approach is supported by academic and practitioner evidence that cryptocurrencies exhibit short-term momentum over 1–4 week horizons, especially in larger, more liquid coins.

---

## 2. Technical Stack and Environment
You are running in an environment like Google Antigravity with access to:

- A Python runtime (preferred), with common libraries: `pandas`, `numpy`, `requests`, `matplotlib`/`plotly`, etc.
- Optionally, a unified crypto exchange library such as **CCXT** for market data and (later) order execution.
- Disk or object storage for saving CSVs, logs, and configuration files.

Design all code and modules in a way that:
- Can run headless on a VPS or cloud instance.
- Uses configuration files (YAML/JSON) for API keys, risk limits, and universe parameters.
- Separates **research/backtest code** from **live-trading/execution code**.

---

## 3. Data Ingestion Layer
### 3.1 Historical Data Requirements
You must be able to obtain at least 2–4 years of **daily OHLCV data** (Open, High, Low, Close, Volume) for a broad set of cryptocurrencies, including altcoins.

Data requirements:
- Daily bars (1D): close, volume, and ideally market cap if available.
- Coverage: at least top 100–200 coins by market cap.
- Survivor bias awareness: do your best to include delisted or dead coins when possible, but if not feasible, clearly document the limitation.

Implementation options:
- Use public APIs (e.g., exchange REST APIs or aggregators like CoinGecko/CoinMarketCap) to download historical daily candles into CSV files.
- Create a data pipeline that:
  - Normalizes symbol naming (e.g., unify `BTCUSDT`, `BTC-USD`, etc.).
  - Stores data in a consistent folder structure, e.g. `data/daily/{symbol}.csv`.

### 3.2 Live / Incremental Data
For live or paper trading:
- Implement a small module to fetch **the latest daily close** and volume for each coin in the universe before the weekly rebalance.
- Ensure rate-limiting and retry logic for API calls.

---

## 4. Universe Definition and Intelligent Filters
The universe must intentionally avoid illiquid, scammy, or micro-cap coins to reduce slippage and noise.

### 4.1 Base Universe
Define a **base universe** as:
- All non-stablecoin crypto assets listed on a primary exchange (e.g., Binance),
- That are also among the **top N coins by global market cap** (e.g., N = 100–150).

Exclude:
- Stablecoins (USDT, USDC, DAI, etc.).
- Purely wrapped duplicates unless needed (e.g., you might keep BTC and drop WBTC on the same exchange if redundant).

### 4.2 Liquidity Filters
On top of the base universe, apply **liquidity and trading filters**:

- Minimum average **daily trading volume** in USD over the last 30 days (e.g., \> 5M or \> 10M USD).
- Optional: maximum average bid–ask spread (if order book data is available) over recent days.
- Optional: exclude coins with fewer than X days of history (e.g., newly listed coins with < 90 days daily data).

### 4.3 Regime / Risk Filters (Optional but Recommended)
Implement simple regime-aware filters:

- Global market health:
  - Compute whether a majority of the base universe is currently above its 200-day moving average.
  - If the whole market is in a deep downtrend (e.g., \< 30% of coins above 200D), you may reduce capital allocation or skip some trades.

- BTC / ETH trend:
  - Track whether BTC and ETH are above or below their 200-day MA.
  - Use this as an additional signal for dialing risk up or down.

These filters are not mandatory for a first MVP but should be planned so you can integrate them later.

---

## 5. Momentum Signal Construction
Construct the momentum signal for each coin in the filtered universe as follows.

For coin *i* on day *t* (weekly decision date):

1. **30-day return** (primary cross-sectional ranking signal):
   - `R30_i(t) = Close_i(t) / Close_i(t-30) - 1`
2. **7-day return** (to avoid extreme blow-off tops):
   - `R7_i(t) = Close_i(t) / Close_i(t-7) - 1`

Procedure:
- For each weekly rebalance date, compute R30 and R7 for all coins in the current universe.
- Sort coins by R30 in descending order (best momentum at the top).
- Optionally compute percentile ranks instead of raw returns.

Additional filters on the signal:

- Require `R30_i(t) > threshold`, e.g. +15% or +20% over the last 30 days.
- Optionally enforce a **maximum** R7 (e.g. R7 < +100% or +150%) to avoid coins that have just gone parabolic and may be near exhaustion.

The momentum signal is **purely price-based** and cross-sectional: at each decision date, you only care about how each coin performed relative to others in the last 30 days.

---

## 6. Portfolio Construction and Weekly Rebalancing
### 6.1 Selection of Winners
At each weekly rebalance date (e.g., Sunday 00:00 UTC):

1. Start from the universe that passes all **size, liquidity, and non-stablecoin** filters.
2. Compute R30 and R7 for every coin.
3. Rank by R30 descending.
4. Build a set of **CANDIDATE WINNERS** by selecting the top **Q%** of the ranked list (e.g., top 20%, i.e. top quintile).
5. Apply the additional filters:
   - `R30 > min_momentum_threshold` (e.g. 15–20%),
   - `R7 < max_short_term_runup` (e.g. 100–150%),
   - Liquidity filters (recent 7-day volume > threshold).

6. From the resulting candidates set, choose up to **N coins** (e.g., 5–10) to include in the portfolio.

### 6.2 Weighting Scheme
Use a simple scheme to reduce complexity and instability:

- **Equal-weighting**: each selected coin gets a weight of `1/N` of the capital allocated to the strategy.
- If fewer than N coins pass filters, allocate only to those, and leave the rest in cash/stable.

### 6.3 Weekly Rebalance Logic
Once per week:

1. Close all existing strategy positions (or close any that are no longer in the new winner set).
2. Recompute signals and build the new winner basket.
3. Open new positions according to the equal-weight allocation.

You may allow some persistence (e.g., keep coins that remain in the top winners), but begin with the simple **full weekly rebalance**.

---

## 7. Risk Management and Position Sizing
Risk management must be simple and explicit.

### 7.1 Capital Allocation
- Define a dedicated **strategy capital** (e.g., 10k–20k USD) separate from any other portfolios.
- No or minimal leverage initially (target effective leverage ≤ 1.0–1.5x).

### 7.2 Per-Position Limits
- Maximum per-position allocation: e.g., 20–25% of strategy capital.
- This is naturally enforced by equal-weighting with N = 5–10 winners, but also codify a hard cap.

### 7.3 Stop-Loss and Take-Profit
Implement simple optional risk rules per position:

- **Stop-loss**: close a position early if price falls more than a fixed percentage from entry, e.g., -10% to -15%, or if price moves more than 1.5–2x its 14-day ATR against you.
- **Take-profit**: optionally take profits early if price rises more than, say, +30–40% during the week.
- **Time stop**: close any remaining positions at the weekly rebalance, even if neither stop-loss nor take-profit was hit.

### 7.4 Strategy-Level Kill Switch
Implement a basic kill-switch:
- If strategy daily or weekly PnL drops below a critical threshold (e.g., -X% of strategy capital), automatically close all positions and halt trading until manually restarted.

---

## 8. Backtesting Framework
You must build a backtesting engine for this strategy using historical daily data.

### 8.1 Simulation Frequency
- Use **weekly decision dates** (e.g., every Sunday) over the full available historical period.
- For each decision date:
  - Form the universe and apply filters based on data available up to that date (no look-ahead bias).
  - Compute R30 and R7 using only past prices.
  - Build and apply the portfolio for the following week.

### 8.2 Transaction Costs & Slippage
Include realistic assumptions for:

- Trading fees: use fee schedules from the target exchange (e.g., 0.04%–0.1% per side).
- Slippage: simple model, e.g., a small fraction of the bid–ask spread or a fixed % penalty on each trade.

### 8.3 Performance Metrics
For the full backtest horizon, compute at minimum:

- Annualized return (CAGR).
- Annualized volatility.
- Sharpe ratio (and optionally Sortino).
- Maximum drawdown.
- Hit rate (% of profitable weeks).
- Average win vs. average loss.
- Turnover (average % of portfolio traded per rebalance).

Compare the strategy to benchmarks such as:
- Buy-and-hold BTC.
- Buy-and-hold an altcoin index (e.g., equal-weight top N altcoins).

### 8.4 Robustness Checks
Run basic robustness tests:

- Vary lookback window, e.g., 21 vs 30 vs 45 days.
- Vary holding period, e.g., 1 vs 2 weeks.
- Vary N (number of winners) and momentum thresholds.

You do not need a full academic robustness suite, but you must verify that performance is **not entirely dependent on a single hyperparameter choice**.

---

## 9. Live (or Paper) Trading Architecture
Once backtesting is complete and results are acceptable, design a minimal live/paper trading architecture.

### 9.1 Components
- **Scheduler**: triggers weekly rebalance (e.g., cron job or cloud scheduler calling a script once per week).
- **Data fetcher**: obtains latest daily close and volumes before rebalancing.
- **Signal engine**: computes R30, R7, rankings, and selects winners.
- **Execution engine**:
  - Reads current portfolio and target portfolio.
  - Calculates required trades (sell old positions, buy new positions).
  - Sends market or limit orders via exchange API.
- **Risk module**: enforces position caps, stop-loss rules, and kill-switch.
- **Logging/Monitoring**: writes all actions and PnL to log files and sends alerts (e.g., email or Telegram) on failures.

### 9.2 Simplicity and Reliability
Design decisions to keep it robust:

- Prefer a single primary exchange for both backtesting (when possible) and live trading.
- Limit dependencies: one codebase, one data source, one place for secrets/config.
- Use environment variables or encrypted config files for API keys; never hardcode keys.
- Implement retry logic and simple error handling around API calls (network errors, timeouts, etc.).

---

## 10. Deliverables
You must produce, in a clearly organized and documented form:

1. **Research notebook(s)** (or scripts) that:
   - Download and clean historical OHLCV data.
   - Construct the universe and apply all filters.
   - Implement the weekly cross-sectional momentum backtest.
   - Output performance metrics and basic plots (equity curve, drawdowns, etc.).

2. **Configuration files** (YAML/JSON) for:
   - Universe and filter parameters.
   - Strategy hyperparameters (lookback window, holding period, N winners, thresholds).
   - Risk limits (per-position max, stop-loss, kill-switch thresholds).

3. **Execution script(s)** for live/paper trading that:
   - Use the same core logic as in the backtest.
   - Can be run on a schedule (weekly rebalance) with minimal manual intervention.

4. **Documentation (README)** describing:
   - Strategy concept and rationale.
   - Universe and filters.
   - Signal and portfolio construction.
   - Backtest setup and key results.
   - Live trading workflow and operational checklist.

---

## 11. Non-Goals and Constraints
To avoid scope creep, do **not** implement the following in the initial version:

- Intraday or high-frequency trading.
- Complex derivatives (options, perpetual futures) or leveraged structured products.
- On-chain MEV or DEX-level arbitrage.
- Cross-chain bridging logic.

Focus strictly on:
- **Daily data**,
- **Weekly decisions**,
- **Long-only altcoin basket**,
- **Simple but well-documented code**.

Once a robust core system exists, further extensions (e.g., risk-managed momentum scaling by volatility, additional factors, or multi-exchange execution) can be considered in future iterations.