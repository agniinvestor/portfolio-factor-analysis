"""Fetch live macro signals and map them to regime labels + factor recommendations.

All fetches fall back to "unknown" on failure (logged as warnings). Cached to
data/cache/macro_regime.json for 24 hours.

Data source notes:
- US rates: yfinance ^TNX (daily, reliable)
- India/Japan/Europe rates: FRED monthly 10Y series (OECD)
- Growth (all regions): OECD Composite Leading Indicator (CLI) via FRED when api_key
  available; falls back to yfinance equity index 3M return proxy otherwise.
  CLI series: USALOLITONOSTSAM / INDLOLITONOSTSAM / JPNLOLITONOSTSAM / DEULOLITONOSTSAM
- US/Europe inflation: FRED CPI index series (CPIAUCSL / CP0000EZ19M086NEST),
  YoY acceleration formula, needs >= 18 valid monthly obs
- India inflation: FRED OECD YoY % series (CPALTT01INM657N), needs >= 6 obs
- Japan inflation: FRED OECD YoY % series (CPALTT01JPM657N), limit=36 to
  reach data past FRED's ~2-year lag; signal reflects most recent available
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Static lookup tables
# --------------------------------------------------------------------------

REGIME_MAP: dict[tuple[str, str, str], tuple[str, str]] = {
    ("falling", "expanding",   "falling"): ("Goldilocks",             "#27ae60"),
    ("rising",  "expanding",   "rising"):  ("Overheating",            "#f39c12"),
    ("rising",  "contracting", "rising"):  ("Stagflation",            "#e74c3c"),
    ("falling", "contracting", "falling"): ("Deflation / Bust",       "#2c3e50"),
    ("rising",  "expanding",   "falling"): ("Recovery / Tightening",  "#16a085"),
    ("falling", "contracting", "rising"):  ("Stagflation-Lite",       "#c0392b"),
    ("rising",  "contracting", "falling"): ("Recession / Tightening", "#2980b9"),
    ("falling", "expanding",   "rising"):  ("Reflation",              "#d35400"),
}

UNKNOWN_REGIME: tuple[str, str] = ("Unknown", "#7f8c8d")

FACTOR_MATRIX: dict[str, dict[str, str]] = {
    "Goldilocks":             {"Mkt Beta": "●", "Size": "●", "Value": "○", "Momentum": "●", "Quality": "○", "Low Vol": "✕", "Growth": "●"},
    "Overheating":            {"Mkt Beta": "○", "Size": "✕", "Value": "●", "Momentum": "●", "Quality": "○", "Low Vol": "✕", "Growth": "○"},
    "Stagflation":            {"Mkt Beta": "✕", "Size": "✕", "Value": "●", "Momentum": "✕", "Quality": "●", "Low Vol": "●", "Growth": "✕"},
    "Deflation / Bust":       {"Mkt Beta": "✕", "Size": "✕", "Value": "✕", "Momentum": "○", "Quality": "●", "Low Vol": "●", "Growth": "✕"},
    "Recovery / Tightening":  {"Mkt Beta": "●", "Size": "●", "Value": "●", "Momentum": "○", "Quality": "○", "Low Vol": "✕", "Growth": "○"},
    "Stagflation-Lite":       {"Mkt Beta": "✕", "Size": "✕", "Value": "●", "Momentum": "✕", "Quality": "●", "Low Vol": "○", "Growth": "✕"},
    "Recession / Tightening": {"Mkt Beta": "✕", "Size": "○", "Value": "✕", "Momentum": "✕", "Quality": "●", "Low Vol": "●", "Growth": "✕"},
    "Reflation":              {"Mkt Beta": "●", "Size": "●", "Value": "●", "Momentum": "●", "Quality": "✕", "Low Vol": "✕", "Growth": "●"},
}

FACTORS: list[str] = ["Mkt Beta", "Size", "Value", "Momentum", "Quality", "Low Vol", "Growth"]

# US 10Y via yfinance; India/Japan/Europe via FRED monthly OECD series
YIELD_TICKERS: dict[str, str] = {
    "US": "^TNX",
}
YIELD_FRED_SERIES: dict[str, str] = {
    "India":  "INDIRLTLT01STM",
    "Japan":  "IRLTLT01JPM156N",
    "Europe": "IRLTLT01DEM156N",
}

# OECD Composite Leading Indicators (CLI) — primary growth signal when FRED key available.
# Normalised around 100: >100 = above-trend expansion, <100 = below-trend contraction.
# Compare recent 3M avg vs prior 3M avg for direction.
CLI_FRED_SERIES: dict[str, str] = {
    "US":     "USALOLITONOSTSAM",
    "India":  "INDLOLITONOSTSAM",
    "Japan":  "JPNLOLITONOSTSAM",
    "Europe": "DEULOLITONOSTSAM",  # Germany as dominant European economy
}

# Fallback growth proxy when FRED key unavailable: 3M equity index return.
EQUITY_TICKERS: dict[str, str] = {
    "US":     "^GSPC",
    "India":  "^BSESN",
    "Japan":  "^N225",
    "Europe": "^STOXX50E",
}

# CPI index series (US, Europe): needs >= 18 valid monthly obs for YoY formula
CPI_SERIES_INDEX: dict[str, str] = {
    "US":     "CPIAUCSL",
    "Europe": "CP0000EZ19M086NEST",
}

# CPI YoY % change series (OECD CPALTT01): fetch limit=36 so we reach valid obs
# past FRED's publication lag. Needs >= 6 valid obs. Signal reflects most recent
# available data even if lagged ~2 years (better than "unknown").
CPI_SERIES_YOY: dict[str, str] = {
    "India": "CPALTT01INM657N",
    "Japan": "CPALTT01JPM657N",
}
CPI_YOY_FETCH_LIMIT: dict[str, int] = {
    "India": 12,   # updated frequently; 12 obs enough
    "Japan": 36,   # ~2-year lag on FRED; fetch more to find valid data
}

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
CACHE_PATH = Path(__file__).parent / "cache" / "macro_regime.json"
CACHE_TTL = timedelta(hours=24)

MIN_RATES_LOOKBACK = 64  # ~63 trading-day separation (≈3 months)
RATES_BPS_THRESHOLD = 0.05  # 5 basis points — treat flat as "unknown"

# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------

def _determine_regime(rates: str, growth: str, inflation: str) -> tuple[str, str]:
    """Look up regime label + color from the 3-signal triple. Unknown on miss."""
    return REGIME_MAP.get((rates, growth, inflation), UNKNOWN_REGIME)


def _get_factor_recommendations(regime_label: str) -> tuple[list[str], list[str]]:
    """Return (favored, avoided) factor lists for the regime. Empty lists if unknown."""
    row = FACTOR_MATRIX.get(regime_label)
    if row is None:
        return [], []
    favored = [f for f, s in row.items() if s == "●"]
    avoided = [f for f, s in row.items() if s == "✕"]
    return favored, avoided


def _signal_arrow(signal: str) -> str:
    """Convert a signal string to an arrow glyph."""
    if signal in ("rising", "expanding"):
        return "↑"
    if signal in ("falling", "contracting"):
        return "↓"
    return "?"


# --------------------------------------------------------------------------
# Live signal fetchers
# --------------------------------------------------------------------------

def _fetch_rates_signal(region: str, ticker: str) -> tuple[str, str]:
    """Compare 10Y yield today vs ~63 trading days ago. Returns (signal, value_str)."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo", interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            logger.warning("rates: empty history for %s (%s)", region, ticker)
            return "unknown", "—"
        closes = hist["Close"].dropna()
        if len(closes) < MIN_RATES_LOOKBACK:
            logger.warning("rates: too few points (%d) for %s (%s)", len(closes), region, ticker)
            return "unknown", "—"
        latest = float(closes.iloc[-1])
        prior = float(closes.iloc[-MIN_RATES_LOOKBACK])
        diff = latest - prior
        if abs(diff) < RATES_BPS_THRESHOLD:
            return "unknown", f"{latest:.2f}%"
        signal = "rising" if diff > 0 else "falling"
        return signal, f"{latest:.2f}%"
    except Exception as exc:
        logger.warning("rates: fetch failed for %s (%s): %s", region, ticker, exc)
        return "unknown", "—"


def _fetch_rates_signal_fred(region: str, series_id: str, fred_api_key: Optional[str]) -> tuple[str, str]:
    """Fetch 10Y yield from FRED monthly series. Returns (signal, value_str)."""
    if not fred_api_key:
        logger.warning("rates_fred(%s): no FRED api_key; returning unknown", region)
        return "unknown", "—"
    try:
        params = {
            "series_id": series_id,
            "api_key": fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 6,
        }
        resp = requests.get(FRED_URL, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        values: list[float] = []
        for o in obs:
            v = o.get("value")
            if v not in (None, ".", ""):
                try:
                    values.append(float(v))
                except ValueError:
                    pass
        if len(values) < 4:
            logger.warning("rates_fred(%s): only %d observations", region, len(values))
            return "unknown", "—"
        latest = values[0]
        prior = values[3]  # ~3 months ago
        diff = latest - prior
        if abs(diff) < RATES_BPS_THRESHOLD:
            return "unknown", f"{latest:.2f}%"
        signal = "rising" if diff > 0 else "falling"
        return signal, f"{latest:.2f}%"
    except Exception as exc:
        logger.warning("rates_fred(%s): FRED fetch failed: %s", region, exc)
        return "unknown", "—"


def _fetch_growth_signal_cli(region: str, series_id: str, fred_api_key: str) -> tuple[str, str]:
    """
    OECD Composite Leading Indicator from FRED.
    Compares recent 3M avg vs prior 3M avg for direction. Value = latest CLI level.
    CLI is normalised around 100: >100 above-trend, <100 below-trend.
    Returns (signal, value_str).
    """
    try:
        params = {
            "series_id": series_id,
            "api_key": fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 9,
        }
        resp = requests.get(FRED_URL, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        values: list[float] = []
        for o in obs:
            v = o.get("value")
            if v not in (None, ".", ""):
                try:
                    values.append(float(v))
                except ValueError:
                    pass
        if len(values) < 6:
            logger.warning("growth_cli(%s): only %d valid obs", region, len(values))
            return "unknown", "—"
        recent_avg = sum(values[0:3]) / 3.0
        prior_avg  = sum(values[3:6]) / 3.0
        signal = "expanding" if recent_avg > prior_avg else "contracting"
        return signal, f"{values[0]:.1f}"
    except Exception as exc:
        logger.warning("growth_cli(%s): FRED fetch failed: %s", region, exc)
        return "unknown", "—"


def _fetch_growth_signal(region: str, fred_api_key: Optional[str] = None) -> tuple[str, str]:
    """
    Growth signal: OECD CLI from FRED (primary) or equity 3M return (fallback).
    Returns (signal, value_str). Value is CLI level when available, else '—'.
    """
    if fred_api_key and region in CLI_FRED_SERIES:
        return _fetch_growth_signal_cli(region, CLI_FRED_SERIES[region], fred_api_key)

    # Fallback: equity index 3M return proxy (no meaningful display value)
    ticker = EQUITY_TICKERS.get(region)
    if ticker is None:
        logger.warning("growth: unknown region %s", region)
        return "unknown", "—"
    try:
        hist = yf.Ticker(ticker).history(period="6mo", interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return "unknown", "—"
        closes = hist["Close"].dropna()
        if len(closes) < MIN_RATES_LOOKBACK:
            return "unknown", "—"
        latest = float(closes.iloc[-1])
        prior = float(closes.iloc[-MIN_RATES_LOOKBACK])
        signal = "expanding" if latest > prior else "contracting"
        return signal, "—"
    except Exception as exc:
        logger.warning("growth(%s): fetch failed: %s", region, exc)
        return "unknown", "—"


def _fetch_inflation_signal(region: str, series_id: str, fred_api_key: Optional[str]) -> tuple[str, str]:
    """
    CPI index YoY trend: compare recent 3M avg YoY vs prior 3M avg YoY.
    Uses CPI price-index series. Needs >= 18 valid monthly observations.
    Returns (signal, value_str) where value_str is the recent YoY inflation rate.
    """
    if not fred_api_key:
        logger.warning("inflation(%s): no FRED api_key; returning unknown", region)
        return "unknown", "—"
    try:
        params = {
            "series_id": series_id,
            "api_key": fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 24,  # fetch extra to ensure 18 valid after filtering "."
        }
        resp = requests.get(FRED_URL, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        values: list[float] = []
        for o in obs:
            v = o.get("value")
            if v not in (None, ".", ""):
                try:
                    values.append(float(v))
                except ValueError:
                    pass
        if len(values) < 18:
            logger.warning("inflation(%s): only %d observations", region, len(values))
            return "unknown", "—"

        # values[0] = latest month (desc order)
        recent_3m_avg   = sum(values[0:3]) / 3.0    # months 0,1,2
        prior_3m_avg    = sum(values[3:6]) / 3.0    # months 3,4,5
        recent_yoy_base = sum(values[12:15]) / 3.0  # 12m earlier for recent window
        prior_yoy_base  = sum(values[15:18]) / 3.0  # 12m earlier for prior window

        if recent_yoy_base <= 0 or prior_yoy_base <= 0:
            return "unknown", "—"

        recent_yoy = (recent_3m_avg / recent_yoy_base) - 1.0
        prior_yoy  = (prior_3m_avg  / prior_yoy_base)  - 1.0

        signal = "rising" if recent_yoy > prior_yoy else "falling"
        return signal, f"{recent_yoy * 100:.1f}%"
    except Exception as exc:
        logger.warning("inflation(%s): FRED fetch failed: %s", region, exc)
        return "unknown", "—"


def _fetch_inflation_signal_yoy(region: str, series_id: str, fred_api_key: Optional[str],
                                 fetch_limit: int = 12) -> tuple[str, str]:
    """
    CPI YoY % change series (e.g. OECD CPALTT01 series).
    Compares recent 3M avg to prior 3M avg. Needs >= 6 valid observations.
    fetch_limit can be increased (e.g. 36) for series with long publication lags.
    Returns (signal, value_str) where value_str is the recent 3M avg YoY rate.
    """
    if not fred_api_key:
        logger.warning("inflation_yoy(%s): no FRED api_key; returning unknown", region)
        return "unknown", "—"
    try:
        params = {
            "series_id": series_id,
            "api_key": fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": fetch_limit,
        }
        resp = requests.get(FRED_URL, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        values: list[float] = []
        for o in obs:
            v = o.get("value")
            if v not in (None, ".", ""):
                try:
                    values.append(float(v))
                except ValueError:
                    pass
        if len(values) < 6:
            logger.warning("inflation_yoy(%s): only %d valid obs (limit=%d)", region, len(values), fetch_limit)
            return "unknown", "—"

        # values are already YoY % change; compare 3M averages
        recent_avg = sum(values[0:3]) / 3.0
        prior_avg  = sum(values[3:6]) / 3.0
        signal = "rising" if recent_avg > prior_avg else "falling"
        return signal, f"{recent_avg:.1f}%"
    except Exception as exc:
        logger.warning("inflation_yoy(%s): FRED fetch failed: %s", region, exc)
        return "unknown", "—"


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------

def _load_cache() -> Optional[dict]:
    if not CACHE_PATH.exists():
        return None
    try:
        raw = json.loads(CACHE_PATH.read_text())
        fetched_at = datetime.fromisoformat(raw["fetched_at"])
        if datetime.utcnow() - fetched_at > CACHE_TTL:
            return None
        return raw.get("signals")
    except Exception as exc:
        logger.warning("macro cache read failed: %s", exc)
        return None


def _save_cache(signals: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({
            "fetched_at": datetime.utcnow().isoformat(),
            "signals": signals,
        }, indent=2))
    except Exception as exc:
        logger.warning("macro cache write failed: %s", exc)


# --------------------------------------------------------------------------
# Top-level entry point
# --------------------------------------------------------------------------

def fetch_macro_signals(
    force_refresh: bool = False,
    fred_api_key: Optional[str] = None,
) -> dict[str, dict[str, str]]:
    """Return per-region macro signal dict. Cached in data/cache/macro_regime.json (24h)."""
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            return cached

    regions = ["US", "India", "Japan", "Europe"]
    signals: dict[str, dict[str, str]] = {}
    for region in regions:
        # Rates — each fetcher returns (signal, value_str)
        if region in YIELD_TICKERS:
            rates, rates_val = _fetch_rates_signal(region, YIELD_TICKERS[region])
        else:
            rates, rates_val = _fetch_rates_signal_fred(region, YIELD_FRED_SERIES[region], fred_api_key)

        # Growth — OECD CLI (primary) or equity 3M return proxy (fallback)
        growth, growth_val = _fetch_growth_signal(region, fred_api_key)

        # Inflation
        if region in CPI_SERIES_INDEX:
            inflation, inflation_val = _fetch_inflation_signal(region, CPI_SERIES_INDEX[region], fred_api_key)
        else:
            limit = CPI_YOY_FETCH_LIMIT.get(region, 12)
            inflation, inflation_val = _fetch_inflation_signal_yoy(region, CPI_SERIES_YOY[region], fred_api_key,
                                                                    fetch_limit=limit)

        regime_label, color = _determine_regime(rates, growth, inflation)
        signals[region] = {
            "rates": rates, "growth": growth, "inflation": inflation,
            "regime": regime_label, "color": color,
            "rates_value": rates_val, "growth_value": growth_val, "inflation_value": inflation_val,
        }

    _save_cache(signals)
    return signals
