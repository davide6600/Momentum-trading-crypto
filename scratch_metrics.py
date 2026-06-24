import pandas as pd
import numpy as np

eq = pd.read_csv('output/equity_curve.csv')
wr = pd.read_csv('output/weekly_returns.csv')

initial = eq['equity'].iloc[0]
final = eq['equity'].iloc[-1]
days = (pd.to_datetime(eq['date'].iloc[-1]) - pd.to_datetime(eq['date'].iloc[0])).days
years = days / 365.25 if days > 0 else 1
cagr = (final / initial) ** (1.0 / years) - 1.0

ann_vol = np.std(wr['return'].values, ddof=1) * np.sqrt(52)
sharpe = cagr / ann_vol if ann_vol > 0 else 0

print(f'Initial: {initial:.2f}, Final: {final:.2f}')
print(f'CAGR: {cagr:.2%}')
print(f'Ann Vol: {ann_vol:.2%}')
print(f'Sharpe: {sharpe:.2f}')
print(f'Max DD: {eq["drawdown"].min():.2%}')
