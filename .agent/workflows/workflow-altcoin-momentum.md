# Workflow: Altcoin Weekly Cross-Sectional Momentum

## 1. Overview
This workflow defines the end-to-end process for the **weekly altcoin cross-sectional momentum strategy**: from data ingestion to backtesting to (later) live or paper trading. It is designed for low frequency, low complexity, and minimal points of failure.

---

## 2. Workflows

### 2.1 Historical Research & Backtest Workflow

1. **Load Configuration**  
   - Read `config/universe.yaml` and `config/strategy.yaml` for all parameters: exchange, volume thresholds, lookback window, holding period, number of winners, risk limits.

2. **Download / Refresh Historical Data**  
   - For each symbol in the broad candidate list (e.g., top 200 coins by market cap):  
     - Fetch daily OHLCV (at least 2–4 years where available).  
     - Store as `data/daily/{symbol}.csv`.

3. **Build Base Universe**  
   - Exclude stablecoins and obvious wrapped duplicates as specified in `universe.yaml`.  
   - Ensure each coin has at least `min_history_days` of data.

4. **Apply Liquidity & Size Filters**  
   - Compute 30-day average daily volume in USD for each coin.  
   - Keep only coins above `min_avg_volume_usd`.  
   - Optionally, keep only top N by global market cap.

5. **Weekly Simulation Loop**  
   For each weekly decision date `t` in the backtest period:
   - 5.1 Universe snapshot: determine the set of coins that pass filters using data up to `t` only.  
   - 5.2 Compute momentum signals:  
       - 30-day return `R30`, 7-day return `R7`.  
   - 5.3 Rank coins by `R30` descending.  
   - 5.4 Select winners:  
       - take top `Q%` (e.g., top 20%) of the ranked list,  
       - filter by `R30 > threshold`, `R7 < max_short_term_runup`,  
       - filter by recent volume (e.g., 7-day average volume).
   - 5.5 Construct portfolio:  
       - select up to `N_winners` coins,  
       - allocate equal weights,  
       - compute target portfolio for week `t → t+1`.
   - 5.6 Simulate execution:  
       - close previous week positions at open/close of `t`,  
       - open new positions at open/close of `t`,  
       - apply trading fees and slippage.  
       - track PnL daily or at least week-end.

6. **Compute Performance Statistics**  
   - Equity curve and drawdown curve.  
   - CAGR, annualized volatility, Sharpe, max drawdown, hit rate, turnover, average trade PnL.

7. **Robustness Checks**  
   - Repeat backtest with alternative parameters (lookback, holding period, N_winners, thresholds).  
   - Compare results and document sensitivity.

---

### 2.2 Weekly Signal Generation Workflow (Live/Paper)

1. **Load Latest Config & State**  
   - Read configs and current portfolio state (positions, cash, last rebalance date).

2. **Fetch Latest Daily Data**  
   - Retrieve the most recent daily close and volume for all coins in the candidate universe.

3. **Rebuild Universe Snapshot**  
   - Apply the same liquidity and size filters as in backtest, using recent data.

4. **Compute Signals & Select Winners**  
   - Compute `R30` and `R7` for each coin.  
   - Rank by `R30`, apply filters, select top `N_winners`.

5. **Generate Target Portfolio**  
   - Compute equal-weight target weights for selected winners.  
   - Generate a structured signal report (e.g., JSON/Markdown) listing target positions, entry prices, stops.

6. **(Optional) Manual Review Step**  
   - Allow a human operator to review the weekly signal report and approve or adjust before execution.

7. **Execute Rebalance (Live or Paper)**  
   - If approved, calculate trades needed to move from current to target portfolio.  
   - Place market/limit orders via exchange API (or log as paper trades).

8. **Log & Notify**  
   - Log all actions and outcomes to files/DB.  
   - Send summary notification (e.g., via email or chat).

---

### 2.3 Monitoring & Maintenance Workflow

1. **Daily Health Checks**  
   - Verify data freshness (latest daily bar is present).  
   - Check that API credentials are valid.  
   - Monitor balances and open positions.

2. **Risk and Kill-Switch Monitoring**  
   - Track daily/weekly PnL vs risk limits.  
   - If thresholds are breached, close positions and halt trading.

3. **Periodic Research Refresh**  
   - Run updated backtests with extended data.  
   - Review whether parameters remain robust.

4. **Logging & Audit**  
   - Ensure all trades, signals, configs used, and errors are logged with timestamps.  
   - Keep a changelog of strategy and parameter changes.
