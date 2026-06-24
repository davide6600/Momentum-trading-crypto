# Performance Report: BTC-USDT Trend-Following Strategy

## Executive Summary
This report analyzes a single-asset tactical allocation strategy on Bitcoin (BTC) using a 273-day Simple Moving Average (SMA) regime filter. The strategy shifts dynamically between 100% BTC exposure (during uptrends) and 100% USDT (cash/defensive hold, during downtrends).

Over the simulation period from **June 26, 2021, to June 23, 2026**, the strategy achieved a **+324.5% total return** (**+33.6% CAGR**), significantly outperforming the BTC Buy-and-Hold benchmark (**+94.3% return**, **+14.2% CAGR**) and equity benchmarks: Nasdaq-100/QQQ (**+107.9% return**, **+15.8% CAGR**) and S&P 500/SPY (**+83.6% return**, **+13.0% CAGR**).

---

## Strategy Characteristics & Mechanics

1. **Trend Filter**: 273-day SMA on close price.
2. **Weekly Execution**: Rebalancing occurs on Sundays at the daily close.
3. **No Look-Ahead Bias**: Rebalance decisions are made using the signal of the prior day (Saturday close), ensuring execution is fully tradeable.
4. **USDT Modeling**: Held as risk-free cash inside the portfolio to eliminate slippage and trading costs of stablecoin peg adjustments.
5. **Transaction Costs**: Employs a conservative fee model of **0.10% taker fee** and **0.10% slippage** on both buy and sell orders (0.20% per side).
6. **Execution Efficiency**: Only **4 trades** executed over a 5-year period.

---

## Performance Comparison (June 26, 2021 – June 23, 2026)

| Metric | Strategy (SMA 273) | BTC Buy & Hold | QQQ Buy & Hold | SPY Buy & Hold |
| :--- | :---: | :---: | :---: | :---: |
| **Initial Capital** | $2,000.00 | $2,000.00 | $2,000.00 | $2,000.00 |
| **Final Equity** | **$8,490.49** | $3,886.46 | $4,157.93 | $3,672.25 |
| **Total Return** | **+324.5%** | +94.3% | +107.9% | +83.6% |
| **CAGR** | **+33.6%** | +14.2% | +15.8% | +13.0% |
| **Annualized Volatility** | 34.9% | 53.0% | 27.3% | **20.7%** |
| **Sharpe Ratio** | **0.96** | 0.27 | 0.58 | 0.63 |
| **Sortino Ratio** | **1.13** | 0.38 | 0.82 | 0.87 |
| **Max Drawdown** | -28.1% | -76.6% | -35.1% | **-24.5%** |
| **Total Trades** | 4 | - | - | - |
| **Total Fees Paid** | $40.29 | - | - | - |

---

## Analytical Key Findings

### 1. Superior Risk-Adjusted Returns
By avoiding extended bear markets, the strategy achieved a **Sharpe Ratio of 0.96** and a **Sortino Ratio of 1.13**, more than tripling BTC B&H's risk-adjusted return (Sharpe 0.27, Sortino 0.38). This also significantly outpaces the stock market indexes (SPY Sharpe 0.63, QQQ Sharpe 0.58).

### 2. Drawdown Mitigation (The "Bear Market Escape")
BTC Buy-and-Hold suffered a devastating drawdown of **-76.6%** during the 2022 crypto winter. In contrast, the SMA 273 strategy moved to cash in late 2021/early 2022, shielding capital and capping its maximum historical drawdown at **-28.1%** (better than QQQ's -35.1% drawdown, and only slightly higher than SPY's -24.5%).

### 3. Frictional Cost Minimization (Low Turnover)
Whipsaw losses are the primary weakness of trend-following strategies. By employing a long-term lookback (273 days) and rebalancing only once a week (Sundays), the strategy filters out daily market noise. With only 4 total trades over 5 years, transaction costs and slippage consumed only **$40.29** (less than 2.0% of the initial capital), ensuring the backtest results translate directly to live performance.

### 4. Compounding Advantage
Because capital is preserved during downtrends, the strategy starts new bull runs with a much higher cash base. For example, exiting BTC near $104k in late 2025 protected the accumulated profits when BTC fell back to $67k in mid-2026, allowing the strategy to lock in a final equity of **$8,490.49** versus BTC B&H's **$3,886.46**.
