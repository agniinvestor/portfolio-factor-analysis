"""Fetch live macro signals and map them to regime labels + factor recommendations.

All fetches fall back to "unknown" on failure (logged as warnings). Cached to
data/cache/macro_regime.json for 24 hours.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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

YIELD_TICKERS: dict[str, str] = {
    "US": "^TNX", "India": "IN10Y=X", "Japan": "JP10Y=X", "Europe": "DE10Y=X",
}
EQUITY_TICKERS: dict[str, str] = {
    "India": "^BSESN", "Japan": "^N225", "Europe": "^STOXX50E",
}
CPI_SERIES: dict[str, str] = {
    "US":     "CPIAUCSL",
    "India":  "INDCPIALLMINMEI",
    "Japan":  "JPNCPIALLMINMEI",
    "Europe": "CP0000EZ19M086NEST",
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

def _fetch_rates_signal(region: str, ticker: str) -> str:
    """Compare 10Y yield today vs ~63 trading days ago. Returns rising/falling/unknown."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo", interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            logger.warning("rates: empty history for %s (%s)", region, ticker)
            return "unknown"
        closes = hist["Close"].dropna()
        if len(closes) < MIN_RATES_LOOKBACK:
            logger.warning("rates: too few points (%d) for %s (%s)", len(closes), region, ticker)
            return "unknown"
        latest = float(closes.iloc[-1])
        prior = float(closes.iloc[-MIN_RATES_LOOKBACK])
        diff = latest - prior
        if abs(diff) < RATES_BPS_THRESHOLD:
            return "unknown"
        return "rising" if diff > 0 else "falling"
    except Exception as exc:
        logger.warning("rates: fetch failed for %s (%s): %s", region, ticker, exc)
        return "unknown"
