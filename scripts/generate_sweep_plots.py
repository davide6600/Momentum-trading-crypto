"""
generate_sweep_plots.py — Parse sweep results and generate heatmaps of Sharpe Ratio and Max Drawdown.
Saves heatmaps to output/sweep_heatmap.png.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    csv_path = Path("output/robustness_sweep.csv")
    if not csv_path.exists():
        print("Error: robustness_sweep.csv not found in output/. Run robustness sweep first.")
        return

    df = pd.read_csv(csv_path)
    df["Filters"] = df["Filters"].fillna("None")

    # Filter to stable/optimal dimensions: Hold Weeks = 2, Winners = 3, Filters = Both, Metric = return
    sub_df = df[
        (df["Hold Weeks"] == 2) & 
        (df["Winners"] == 3) & 
        (df["Filters"] == "Both") &
        (df["Metric"] == "return")
    ]

    if sub_df.empty:
        print("No matching data for specified filter slice. Generating heatmap from all Hold Weeks = 2, Winners = 3, Filters = Both.")
        sub_df = df[
            (df["Hold Weeks"] == 2) & 
            (df["Winners"] == 3) & 
            (df["Filters"] == "Both")
        ]

    # Pivot for Sharpe
    pivot_sharpe = sub_df.pivot(index="Lookback", columns="Stop Loss", values="Sharpe")
    # Pivot for MaxDD
    pivot_maxdd = sub_df.pivot(index="Lookback", columns="Stop Loss", values="MaxDD")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Sharpe Heatmap
    im_sharpe = axes[0].imshow(pivot_sharpe.values, cmap="RdYlGn", aspect="auto")
    axes[0].set_title("Sharpe Ratio (Hold=2w, Winners=3, Filters=Both)", fontsize=12, fontweight="bold")
    axes[0].set_xticks(np.arange(len(pivot_sharpe.columns)))
    axes[0].set_xticklabels([f"{val:+.0%}" for val in pivot_sharpe.columns])
    axes[0].set_yticks(np.arange(len(pivot_sharpe.index)))
    axes[0].set_yticklabels([f"{val}d" for val in pivot_sharpe.index])
    axes[0].set_xlabel("Stop Loss")
    axes[0].set_ylabel("Lookback Period")
    
    # Annotate Sharpe cells
    for i in range(len(pivot_sharpe.index)):
        for j in range(len(pivot_sharpe.columns)):
            val = pivot_sharpe.values[i, j]
            axes[0].text(j, i, f"{val:.2f}", ha="center", va="center", 
                         color="black" if 0.2 < val < 0.8 else "white", fontweight="bold")

    fig.colorbar(im_sharpe, ax=axes[0], label="Sharpe Ratio")

    # MaxDD Heatmap
    im_maxdd = axes[1].imshow(pivot_maxdd.values, cmap="RdYlGn_r", aspect="auto")
    axes[1].set_title("Max Drawdown (Hold=2w, Winners=3, Filters=Both)", fontsize=12, fontweight="bold")
    axes[1].set_xticks(np.arange(len(pivot_maxdd.columns)))
    axes[1].set_xticklabels([f"{val:+.0%}" for val in pivot_maxdd.columns])
    axes[1].set_yticks(np.arange(len(pivot_maxdd.index)))
    axes[1].set_yticklabels([f"{val}d" for val in pivot_maxdd.index])
    axes[1].set_xlabel("Stop Loss")
    axes[1].set_ylabel("Lookback Period")

    # Annotate MaxDD cells
    for i in range(len(pivot_maxdd.index)):
        for j in range(len(pivot_maxdd.columns)):
            val = pivot_maxdd.values[i, j]
            axes[1].text(j, i, f"{val:+.1%}", ha="center", va="center",
                         color="black" if abs(val) < 0.3 else "white", fontweight="bold")

    fig.colorbar(im_maxdd, ax=axes[1], label="Max Drawdown")

    plt.tight_layout()
    out_path = Path("output/sweep_heatmap.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Heatmap successfully saved to {out_path}")

if __name__ == "__main__":
    main()
