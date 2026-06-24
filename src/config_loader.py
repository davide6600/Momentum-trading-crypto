"""
config_loader.py — Load and validate YAML configuration files.

Provides typed access to universe, strategy, and secrets configs.
Fails fast with clear error messages if required keys are missing.
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


# ── Default config directory (relative to project root) ──
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class UniverseConfig:
    exchange: str = "binance"
    top_n_by_marketcap: int = 150
    min_avg_volume_usd_30d: float = 5_000_000
    min_history_days: int = 90
    quote_currency: str = "USDT"
    stablecoin_blacklist: List[str] = field(default_factory=list)
    wrapped_blacklist: List[str] = field(default_factory=list)


@dataclass
class StrategyConfig:
    # Signal
    lookback_days: int = 30
    short_lookback_days: int = 7
    rebalance_day: str = "sunday"
    rebalance_hour_utc: int = 13
    holding_period_weeks: int = 1
    ranking_metric: str = "return"
    weighting_scheme: str = "equal"     # equal or vol_parity
    # Selection
    top_quantile: float = 0.20
    min_momentum_threshold: float = 0.15
    max_short_term_runup: float = 0.50
    n_winners: int = 5
    min_recent_volume_usd_7d: float = 3_000_000
    # Regime Filters
    enable_btc_ma_filter: bool = True
    enable_breadth_filter: bool = True
    min_breadth_pct: float = 0.50
    defensive_asset: str = "cash"       # cash, BTC, QQQ, SPY, etc.
    # Re-Entry Acceleration
    enable_breadth_acceleration: bool = False
    breadth_accel_delta: float = 0.10   # breadth rise >10pp triggers re-entry
    breadth_accel_capital_pct: float = 0.50  # use 50% of capital on accel re-entry
    # Capital & sizing
    strategy_capital_usd: float = 2000.0
    risk_per_trade_pct: float = 0.03
    max_per_position_pct: float = 0.25
    leverage: float = 1.0
    # Risk
    stop_loss_pct: float = -0.12
    take_profit_pct: float = 0.35
    kill_switch_weekly_pct: float = -0.15
    # ATR-based trailing stop
    enable_atr_stop: bool = False
    atr_period: int = 14
    atr_multiplier: float = 2.5
    # Mean-Reversion Exclusion
    enable_mean_reversion_filter: bool = False
    max_retracement_from_7d_high: float = 0.20
    # Costs
    fee_per_side_pct: float = 0.001
    slippage_pct: float = 0.001


@dataclass
class SecretsConfig:
    api_key: str = ""
    api_secret: str = ""


@dataclass
class AppConfig:
    universe: UniverseConfig
    strategy: StrategyConfig
    secrets: Optional[SecretsConfig] = None


def _load_yaml(filepath: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    return data


def _dict_to_dataclass(cls, data: dict):
    """Create a dataclass instance from a dict, ignoring unknown keys."""
    valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in valid_keys}
    return cls(**filtered)


def load_config(config_dir: Optional[str] = None) -> AppConfig:
    """
    Load all configuration files from the given directory.

    Args:
        config_dir: Path to config directory. Defaults to project_root/config/.

    Returns:
        AppConfig with universe, strategy, and (optionally) secrets.
    """
    config_path = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR

    # Universe config (required)
    universe_data = _load_yaml(config_path / "universe.yaml")
    universe = _dict_to_dataclass(UniverseConfig, universe_data)

    # Strategy config (required)
    strategy_data = _load_yaml(config_path / "strategy.yaml")
    strategy = _dict_to_dataclass(StrategyConfig, strategy_data)

    # Secrets (optional — only needed for live/paper trading)
    secrets = None
    secrets_path = config_path / "secrets.yaml"
    if secrets_path.exists():
        secrets_data = _load_yaml(secrets_path)
        # Secrets file has exchange name as top-level key
        exchange_key = universe.exchange
        if exchange_key in secrets_data:
            secrets = _dict_to_dataclass(SecretsConfig, secrets_data[exchange_key])

    return AppConfig(universe=universe, strategy=strategy, secrets=secrets)


def compute_position_size(config: StrategyConfig, n_positions: int) -> float:
    """
    Compute the USD size per position, respecting:
    1. Risk-based sizing: risk_per_trade_pct * capital / |stop_loss_pct|
    2. Max per-position cap: max_per_position_pct * capital
    3. Total capital constraint: capital / n_positions

    Returns the minimum of all three constraints.
    """
    capital = config.strategy_capital_usd
    stop_dist = abs(config.stop_loss_pct)

    risk_based = (config.risk_per_trade_pct * capital) / stop_dist if stop_dist > 0 else capital
    max_cap = config.max_per_position_pct * capital
    capital_constrained = capital / n_positions if n_positions > 0 else capital

    return min(risk_based, max_cap, capital_constrained)
