"""
data_ingestion.py — Download and maintain historical daily OHLCV data from Binance via CCXT.

Responsibilities:
- Discover all /USDT spot pairs on Binance.
- Download daily OHLCV candles (2+ years where available).
- Incremental updates: only fetch new candles since last stored date.
- Store as data/daily/{BASE}.csv with columns: date, open, high, low, close, volume.

Known limitation: delisted pairs are not captured (survivorship bias).
"""

import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from src.config_loader import AppConfig
from src.utils import setup_logging, retry_with_backoff, DATA_DIR, ensure_dirs

logger = setup_logging("data_ingestion", log_file="data_ingestion.log")


def create_exchange(config: AppConfig) -> ccxt.Exchange:
    """Create a CCXT exchange instance (Binance)."""
    exchange_id = config.universe.exchange
    exchange_class = getattr(ccxt, exchange_id)

    params = {
        "enableRateLimit": True,
        "options": {
            "adjustForTimeDifference": True,
            "recvWindow": 60000
        }
    }
    if config.secrets and config.secrets.api_key:
        params["apiKey"] = config.secrets.api_key
        params["secret"] = config.secrets.api_secret

    exchange = exchange_class(params)
    return exchange


def get_usdt_spot_symbols(exchange: ccxt.Exchange, config: AppConfig) -> List[str]:
    """
    Get all active /USDT spot trading pairs, excluding stablecoins and wrapped tokens.

    Returns list of base symbols (e.g., ['BTC', 'ETH', 'SOL', ...]).
    """
    exchange.load_markets()
    quote = config.universe.quote_currency
    blacklist = set(
        config.universe.stablecoin_blacklist +
        config.universe.wrapped_blacklist
    )

    symbols = []
    for market_id, market in exchange.markets.items():
        if (market.get("spot", False)
            and market.get("active", False)
            and market.get("quote") == quote
            and market.get("base") not in blacklist):
            symbols.append(market["base"])

    logger.info(f"Found {len(symbols)} active {quote} spot pairs after blacklist filtering")
    return sorted(set(symbols))


@retry_with_backoff(max_retries=3, base_delay=2.0)
def _fetch_ohlcv_chunk(exchange: ccxt.Exchange, symbol: str,
                       since_ms: int, limit: int = 1000) -> list:
    """Fetch a single chunk of OHLCV data from the exchange."""
    pair = f"{symbol}/USDT"
    return exchange.fetch_ohlcv(pair, timeframe="1d", since=since_ms, limit=limit)


def download_symbol_ohlcv(exchange: ccxt.Exchange, symbol: str,
                          start_date: datetime,
                          end_date: Optional[datetime] = None) -> Optional[pd.DataFrame]:
    """
    Download daily OHLCV for a single symbol from start_date to end_date.
    Handles pagination if needed (>1000 candles).

    Returns a DataFrame with columns: date, open, high, low, close, volume.
    Returns None if no data available.
    """
    if end_date is None:
        end_date = datetime.utcnow()

    since_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    all_candles = []

    while since_ms < end_ms:
        try:
            candles = _fetch_ohlcv_chunk(exchange, symbol, since_ms)
        except Exception as e:
            logger.warning(f"Failed to fetch {symbol}: {e}")
            break

        if not candles:
            break

        all_candles.extend(candles)
        # Move since to after the last candle timestamp
        last_ts = candles[-1][0]
        since_ms = last_ts + 86400 * 1000  # next day

        if len(candles) < 1000:
            break  # no more data

        time.sleep(0.1)  # extra rate limit courtesy

    if not all_candles:
        return None

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.strftime("%Y-%m-%d")
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)

    # Filter to end_date
    df = df[df["date"] <= end_date.strftime("%Y-%m-%d")]

    return df


def save_symbol_csv(df: pd.DataFrame, symbol: str):
    """Save OHLCV DataFrame to data/daily/{SYMBOL}.csv."""
    ensure_dirs()
    filepath = DATA_DIR / f"{symbol}.csv"
    df.to_csv(filepath, index=False)


def load_symbol_csv(symbol: str) -> Optional[pd.DataFrame]:
    """Load OHLCV DataFrame from CSV. Returns None if file doesn't exist."""
    filepath = DATA_DIR / f"{symbol}.csv"
    if not filepath.exists():
        return None
    df = pd.read_csv(filepath)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def get_last_stored_date(symbol: str) -> Optional[str]:
    """Get the last date stored in a symbol's CSV. Returns None if no data."""
    df = load_symbol_csv(symbol)
    if df is None or df.empty:
        return None
    return df["date"].iloc[-1]


def download_all_symbols(config: AppConfig,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         incremental: bool = True) -> dict:
    """
    Download/refresh OHLCV data for all eligible symbols.

    Args:
        config: Application configuration.
        start_date: Backtest start date. Defaults to 2 years ago.
        end_date: End date. Defaults to now.
        incremental: If True, only fetch new candles since last stored date.

    Returns:
        Dict mapping symbol -> status ('ok', 'skipped', 'error').
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=730)  # ~2 years
    if end_date is None:
        end_date = datetime.utcnow()

    exchange = create_exchange(config)
    symbols = get_usdt_spot_symbols(exchange, config)

    results = {}
    total = len(symbols)

    for i, symbol in enumerate(symbols, 1):
        # Determine fetch start date
        fetch_start = start_date
        if incremental:
            last_date = get_last_stored_date(symbol)
            if last_date:
                last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                if last_dt >= end_date - timedelta(days=1):
                    logger.debug(f"[{i}/{total}] {symbol}: up to date, skipping")
                    results[symbol] = "skipped"
                    continue
                fetch_start = last_dt + timedelta(days=1)

        logger.info(f"[{i}/{total}] Downloading {symbol} from {fetch_start.strftime('%Y-%m-%d')}...")
        try:
            df_new = download_symbol_ohlcv(exchange, symbol, fetch_start, end_date)
            if df_new is None or df_new.empty:
                logger.warning(f"  {symbol}: no data returned")
                results[symbol] = "no_data"
                continue

            # Merge with existing data if incremental
            if incremental:
                df_existing = load_symbol_csv(symbol)
                if df_existing is not None and not df_existing.empty:
                    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(
                        subset="date"
                    ).sort_values("date").reset_index(drop=True)
                    save_symbol_csv(df_combined, symbol)
                else:
                    save_symbol_csv(df_new, symbol)
            else:
                save_symbol_csv(df_new, symbol)

            results[symbol] = "ok"
        except Exception as e:
            logger.error(f"  {symbol}: error — {e}")
            results[symbol] = "error"

    # Summary
    ok = sum(1 for v in results.values() if v == "ok")
    skipped = sum(1 for v in results.values() if v == "skipped")
    errors = sum(1 for v in results.values() if v in ("error", "no_data"))
    logger.info(f"Download complete: {ok} updated, {skipped} skipped, {errors} errors/no_data")

    return results
