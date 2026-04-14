# Macro Regime Tab — Implementation Plan

**Date:** 2026-04-14
**Target:** Add Tab 6 "Macro Regime" to the portfolio_factor_analysis Streamlit dashboard.

## Goal

Add a sixth tab to the dashboard that surfaces the current macro regime (Goldilocks,
Overheating, Stagflation, etc.) for four regions (US, India, Japan, Europe) based on
three live binary signals — **rates direction**, **growth state**, **inflation trend** —
and maps each regime to a factor-tilt recommendation (Favor / Neutral / Avoid) across
seven factors (Mkt Beta, Size, Value, Momentum, Quality, Low Vol, Growth).

## Architecture

```
data/macro_fetcher.py          # NEW — live signal fetching, regime logic, JSON cache
dashboard/tab_macro_regime.py  # NEW — Section A cards / B table / C heatmap
tests/test_macro_fetcher.py    # NEW — pytest with monkeypatching
dashboard/app.py               # MODIFIED — add tab6 + wire render()
.streamlit/secrets.toml.example # NEW — FRED API key template
data/cache/macro_regime.json   # NEW — generated at runtime (gitignored via /data/cache)
```

Data flow:

```
tab_macro_regime.render(signals, force_refresh)
      ^
      | dict
      |
fetch_macro_signals(force_refresh, fred_api_key)
      |
      +-- read/write data/cache/macro_regime.json (24h TTL)
      |
      +-- _fetch_rates_signal(region, ticker)           # yfinance
      +-- _fetch_growth_signal(region, fred_api_key)    # FRED NAPM (US) / yfinance (others)
      +-- _fetch_inflation_signal(region, series_id, fred_api_key)  # FRED
      |
      +-- _determine_regime(rates, growth, inflation) -> (label, color)
      +-- _get_factor_recommendations(regime_label) -> (favored, avoided)
```

## Tech Stack

- Python 3.11+, Streamlit, pandas, plotly, requests, yfinance, pytest
- No new dependencies — FRED accessed via `requests` REST (no `fredapi`)
- Caching: plain JSON file, 24h TTL, hand-rolled (not `cache_manager.write_cache` which is parquet-only)

## Conventions

- Type hints on every public function
- All signal values are lowercase strings: `"rising"`, `"falling"`, `"expanding"`, `"contracting"`, `"unknown"`
- Failures never raise to caller — log a `logging.warning` and return `"unknown"`
- Region keys are capitalized: `"US"`, `"India"`, `"Japan"`, `"Europe"`

---

## Task 1 — Create `.streamlit/secrets.toml.example` with FRED key template

**Files:**
- `.streamlit/secrets.toml.example` (new)
- `.gitignore` (modified — ensure `.streamlit/secrets.toml` ignored)

**Steps:**

- [ ] Create `.streamlit/secrets.toml.example` with:

  ```toml
  # Copy this file to .streamlit/secrets.toml and fill in your API key.
  # Request a free FRED API key at: https://fred.stlouisfed.org/docs/api/api_key.html

  [fred]
  api_key = "YOUR_FRED_API_KEY_HERE"
  ```

- [ ] Append to `.gitignore` if not already present:

  ```
  .streamlit/secrets.toml
  ```

- [ ] Run:

  ```bash
  ls -la .streamlit/
  cat .streamlit/secrets.toml.example
  ```

  Expected: file exists and prints the template above.

- [ ] Commit:

  ```bash
  git add .streamlit/secrets.toml.example .gitignore
  git commit -m "chore: add Streamlit secrets template for FRED API key"
  ```

---

## Task 2 — `data/macro_fetcher.py` skeleton: constants + pure helpers + tests

Test-first (TDD). Write the test file, run it to confirm ImportError, then implement.

**Files:**
- `tests/test_macro_fetcher.py` (new)
- `data/macro_fetcher.py` (new)

**Steps:**

- [ ] Write `tests/test_macro_fetcher.py` (first pass — pure helpers only):

  ```python
  """Tests for data.macro_fetcher pure helpers and lookup tables."""
  import pytest

  from data import macro_fetcher as mf


  class TestRegimeMap:
      def test_all_8_combinations_present(self):
          assert len(mf.REGIME_MAP) == 8

      def test_goldilocks(self):
          label, color = mf.REGIME_MAP[("falling", "expanding", "falling")]
          assert label == "Goldilocks"
          assert color == "#27ae60"

      def test_stagflation(self):
          label, _ = mf.REGIME_MAP[("rising", "contracting", "rising")]
          assert label == "Stagflation"


  class TestFactorMatrix:
      def test_all_regimes_covered(self):
          expected = {
              "Goldilocks", "Overheating", "Stagflation", "Deflation / Bust",
              "Recovery / Tightening", "Stagflation-Lite",
              "Recession / Tightening", "Reflation",
          }
          assert set(mf.FACTOR_MATRIX.keys()) == expected

      def test_every_regime_has_7_factors(self):
          factors = {"Mkt Beta", "Size", "Value", "Momentum", "Quality", "Low Vol", "Growth"}
          for regime, row in mf.FACTOR_MATRIX.items():
              assert set(row.keys()) == factors, regime

      def test_symbols_valid(self):
          for regime, row in mf.FACTOR_MATRIX.items():
              for factor, sym in row.items():
                  assert sym in {"●", "○", "✕"}, (regime, factor, sym)


  class TestDetermineRegime:
      def test_known_triple(self):
          label, color = mf._determine_regime("falling", "expanding", "falling")
          assert label == "Goldilocks"
          assert color == "#27ae60"

      def test_unknown_returns_unknown(self):
          label, color = mf._determine_regime("unknown", "expanding", "falling")
          assert label == "Unknown"
          assert color == "#7f8c8d"

      def test_all_three_unknown(self):
          label, color = mf._determine_regime("unknown", "unknown", "unknown")
          assert label == "Unknown"
          assert color == "#7f8c8d"


  class TestFactorRecommendations:
      def test_goldilocks_favored(self):
          favored, avoided = mf._get_factor_recommendations("Goldilocks")
          assert "Mkt Beta" in favored
          assert "Growth" in favored
          assert "Low Vol" in avoided

      def test_unknown_regime_returns_empty(self):
          favored, avoided = mf._get_factor_recommendations("Unknown")
          assert favored == []
          assert avoided == []

      def test_stagflation(self):
          favored, avoided = mf._get_factor_recommendations("Stagflation")
          assert "Quality" in favored
          assert "Low Vol" in favored
          assert "Mkt Beta" in avoided


  class TestSignalArrow:
      def test_rising(self):
          assert mf._signal_arrow("rising") == "↑"

      def test_expanding(self):
          assert mf._signal_arrow("expanding") == "↑"

      def test_falling(self):
          assert mf._signal_arrow("falling") == "↓"

      def test_contracting(self):
          assert mf._signal_arrow("contracting") == "↓"

      def test_unknown(self):
          assert mf._signal_arrow("unknown") == "?"
  ```

- [ ] Run:

  ```bash
  cd /home/ubuntu/claude_projects/portfolio_factor_analysis && python -m pytest tests/test_macro_fetcher.py -x 2>&1 | head -30
  ```

  Expected: `ModuleNotFoundError: No module named 'data.macro_fetcher'`. Good — red.

- [ ] Implement `data/macro_fetcher.py`:

  ```python
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

  # Region -> data-source identifiers
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
  ```

- [ ] Run:

  ```bash
  cd /home/ubuntu/claude_projects/portfolio_factor_analysis && python -m pytest tests/test_macro_fetcher.py -x 2>&1 | tail -20
  ```

  Expected: all tests pass (green).

- [ ] Commit:

  ```bash
  git add data/macro_fetcher.py tests/test_macro_fetcher.py
  git commit -m "feat(macro): regime map, factor matrix, pure helpers + tests"
  ```

---

## Task 3 — `_fetch_rates_signal` (yfinance)

**Files:**
- `data/macro_fetcher.py` (extend)
- `tests/test_macro_fetcher.py` (extend)

**Steps:**

- [ ] Append to `tests/test_macro_fetcher.py`:

  ```python
  import pandas as pd


  class TestFetchRatesSignal:
      def test_rising_when_yield_up(self, monkeypatch):
          """Yield today > yield 3 months ago -> rising."""
          idx = pd.date_range("2026-01-01", periods=90, freq="D")
          series = pd.Series(range(90), index=idx, dtype="float64")  # strictly increasing
          df = pd.DataFrame({"Close": series})

          class FakeTicker:
              def __init__(self, ticker): self.ticker = ticker
              def history(self, period="6mo", interval="1d"):
                  return df

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_rates_signal("US", "^TNX") == "rising"

      def test_falling_when_yield_down(self, monkeypatch):
          idx = pd.date_range("2026-01-01", periods=90, freq="D")
          series = pd.Series(range(90, 0, -1), index=idx, dtype="float64")
          df = pd.DataFrame({"Close": series})

          class FakeTicker:
              def __init__(self, ticker): pass
              def history(self, period="6mo", interval="1d"):
                  return df

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_rates_signal("US", "^TNX") == "falling"

      def test_empty_returns_unknown(self, monkeypatch):
          class FakeTicker:
              def __init__(self, ticker): pass
              def history(self, period="6mo", interval="1d"):
                  return pd.DataFrame()

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_rates_signal("US", "^TNX") == "unknown"

      def test_exception_returns_unknown(self, monkeypatch):
          class FakeTicker:
              def __init__(self, ticker): pass
              def history(self, period="6mo", interval="1d"):
                  raise RuntimeError("network down")

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_rates_signal("US", "^TNX") == "unknown"
  ```

- [ ] Run to confirm red:

  ```bash
  python -m pytest tests/test_macro_fetcher.py::TestFetchRatesSignal -x 2>&1 | tail -15
  ```

  Expected: `AttributeError: module 'data.macro_fetcher' has no attribute '_fetch_rates_signal'`.

- [ ] Implement in `data/macro_fetcher.py`. Add at the top (after other imports):

  ```python
  import yfinance as yf
  ```

  And add after `_signal_arrow`:

  ```python
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
          if len(closes) < 20:
              logger.warning("rates: too few points for %s (%s)", region, ticker)
              return "unknown"
          latest = float(closes.iloc[-1])
          lookback_idx = max(0, len(closes) - 64)
          prior = float(closes.iloc[lookback_idx])
          return "rising" if latest > prior else "falling"
      except Exception as exc:
          logger.warning("rates: fetch failed for %s (%s): %s", region, ticker, exc)
          return "unknown"
  ```

- [ ] Run to confirm green:

  ```bash
  python -m pytest tests/test_macro_fetcher.py -x 2>&1 | tail -10
  ```

- [ ] Commit:

  ```bash
  git add data/macro_fetcher.py tests/test_macro_fetcher.py
  git commit -m "feat(macro): _fetch_rates_signal via yfinance"
  ```

---

## Task 4 — `_fetch_growth_signal` (FRED NAPM for US, yfinance equity for others)

**Files:**
- `data/macro_fetcher.py` (extend)
- `tests/test_macro_fetcher.py` (extend)

**Steps:**

- [ ] Append tests:

  ```python
  class TestFetchGrowthSignal:
      def test_us_expanding_when_pmi_above_50_and_rising(self, monkeypatch):
          # Descending order (FRED sort_order=desc): latest first
          payload = {
              "observations": [
                  {"date": "2026-03-01", "value": "54.2"},
                  {"date": "2026-02-01", "value": "53.0"},
                  {"date": "2026-01-01", "value": "52.1"},
              ]
          }

          class FakeResp:
              status_code = 200
              def json(self): return payload
              def raise_for_status(self): pass

          monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
          assert mf._fetch_growth_signal("US", "FAKE_KEY") == "expanding"

      def test_us_contracting_when_pmi_below_50(self, monkeypatch):
          payload = {
              "observations": [
                  {"date": "2026-03-01", "value": "48.0"},
                  {"date": "2026-02-01", "value": "49.0"},
                  {"date": "2026-01-01", "value": "49.5"},
              ]
          }

          class FakeResp:
              status_code = 200
              def json(self): return payload
              def raise_for_status(self): pass

          monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
          assert mf._fetch_growth_signal("US", "FAKE_KEY") == "contracting"

      def test_us_no_api_key_returns_unknown(self):
          assert mf._fetch_growth_signal("US", None) == "unknown"

      def test_india_uses_equity_proxy_positive(self, monkeypatch):
          idx = pd.date_range("2026-01-01", periods=90, freq="D")
          series = pd.Series(range(100, 190), index=idx, dtype="float64")
          df = pd.DataFrame({"Close": series})

          class FakeTicker:
              def __init__(self, t): pass
              def history(self, period="6mo", interval="1d"):
                  return df

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_growth_signal("India", None) == "expanding"

      def test_japan_equity_proxy_negative(self, monkeypatch):
          idx = pd.date_range("2026-01-01", periods=90, freq="D")
          series = pd.Series(range(200, 110, -1), index=idx, dtype="float64")
          df = pd.DataFrame({"Close": series})

          class FakeTicker:
              def __init__(self, t): pass
              def history(self, period="6mo", interval="1d"):
                  return df

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_growth_signal("Japan", None) == "contracting"

      def test_europe_exception_returns_unknown(self, monkeypatch):
          class FakeTicker:
              def __init__(self, t): pass
              def history(self, period="6mo", interval="1d"):
                  raise RuntimeError("boom")

          monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
          assert mf._fetch_growth_signal("Europe", None) == "unknown"
  ```

- [ ] Run — expect red (AttributeError + `requests` not imported yet).

- [ ] Implement. Add `import requests` at top of macro_fetcher.py. Append:

  ```python
  def _fetch_growth_signal(region: str, fred_api_key: Optional[str]) -> str:
      """
      US: FRED ISM PMI (NAPM). Expanding if latest > 50 OR latest > prior (direction).
          Strictly: expanding if latest >= 50 AND latest >= prior; else contracting.
          Simplified: expanding if (latest >= 50) else contracting. Direction used as tiebreak.
      Others: yfinance equity index proxy, 3M return sign.
      """
      if region == "US":
          if not fred_api_key:
              logger.warning("growth(US): no FRED api_key; returning unknown")
              return "unknown"
          try:
              params = {
                  "series_id": "NAPM",
                  "api_key": fred_api_key,
                  "file_type": "json",
                  "sort_order": "desc",
                  "limit": 18,
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
              if len(values) < 2:
                  logger.warning("growth(US): insufficient PMI observations")
                  return "unknown"
              latest, prior = values[0], values[1]
              return "expanding" if (latest >= 50.0 and latest >= prior) else "contracting"
          except Exception as exc:
              logger.warning("growth(US): FRED fetch failed: %s", exc)
              return "unknown"

      ticker = EQUITY_TICKERS.get(region)
      if ticker is None:
          logger.warning("growth: unknown region %s", region)
          return "unknown"
      try:
          hist = yf.Ticker(ticker).history(period="6mo", interval="1d")
          if hist is None or hist.empty or "Close" not in hist.columns:
              return "unknown"
          closes = hist["Close"].dropna()
          if len(closes) < 20:
              return "unknown"
          latest = float(closes.iloc[-1])
          lookback_idx = max(0, len(closes) - 64)
          prior = float(closes.iloc[lookback_idx])
          return "expanding" if latest > prior else "contracting"
      except Exception as exc:
          logger.warning("growth(%s): fetch failed: %s", region, exc)
          return "unknown"
  ```

- [ ] Run tests — expect green.

- [ ] Commit:

  ```bash
  git add data/macro_fetcher.py tests/test_macro_fetcher.py
  git commit -m "feat(macro): _fetch_growth_signal via FRED NAPM + equity proxies"
  ```

---

## Task 5 — `_fetch_inflation_signal` (FRED CPI YoY trend)

**Files:**
- `data/macro_fetcher.py` (extend)
- `tests/test_macro_fetcher.py` (extend)

**Steps:**

- [ ] Append tests:

  ```python
  class TestFetchInflationSignal:
      def _cpi_payload(self, values_desc):
          """Build a FRED-style response with 18 monthly CPI levels, latest first."""
          obs = [
              {"date": f"2026-{12 - i:02d}-01", "value": str(v)}
              for i, v in enumerate(values_desc)
          ]
          return {"observations": obs}

      def test_rising_when_recent_3m_yoy_gt_prior_3m_yoy(self, monkeypatch):
          # 18 months, latest first. recent YoY = avg(0:3)/avg(12:15) - 1 must exceed
          # prior YoY = avg(3:6)/avg(15:18) - 1. Use accelerating CPI in the recent window.
          values = [
              140, 138, 136,       # recent 3m (avg 138)
              128, 127, 126,       # 3-6 months ago (avg 127)
              125, 124, 123,       # 6-9
              122, 121, 120,       # 9-12
              119, 118, 117,       # 12-15 (avg 118) — recent YoY ≈ 138/118 - 1 ≈ 0.169
              116, 115, 114,       # 15-18 (avg 115) — prior YoY ≈ 127/115 - 1 ≈ 0.104
          ]
          payload = self._cpi_payload(values)

          class FakeResp:
              status_code = 200
              def json(self): return payload
              def raise_for_status(self): pass

          monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
          assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "rising"

      def test_falling_when_recent_3m_yoy_lt_prior_3m_yoy(self, monkeypatch):
          # Decelerating CPI
          values = [
              120.1, 120.0, 119.9,  # recent 3m
              119.8, 119.7, 119.6,
              119.5, 119.4, 119.3,
              119.2, 119.1, 119.0,
              117.0, 116.0, 115.0,  # 12-15 months ago
              113.0, 112.0, 111.0,  # 15-18 months ago (big jump earlier -> prior YoY higher)
          ]
          payload = self._cpi_payload(values)

          class FakeResp:
              status_code = 200
              def json(self): return payload
              def raise_for_status(self): pass

          monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
          assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "falling"

      def test_no_api_key_returns_unknown(self):
          assert mf._fetch_inflation_signal("US", "CPIAUCSL", None) == "unknown"

      def test_http_error_returns_unknown(self, monkeypatch):
          class FakeResp:
              status_code = 500
              def json(self): return {}
              def raise_for_status(self): raise RuntimeError("500")

          monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
          assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "unknown"

      def test_insufficient_observations_returns_unknown(self, monkeypatch):
          payload = {"observations": [{"date": "2026-03-01", "value": "130"}]}

          class FakeResp:
              status_code = 200
              def json(self): return payload
              def raise_for_status(self): pass

          monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
          assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "unknown"
  ```

- [ ] Run — expect red.

- [ ] Implement. Append to macro_fetcher.py:

  ```python
  def _fetch_inflation_signal(region: str, series_id: str, fred_api_key: Optional[str]) -> str:
      """
      CPI YoY trend: compare (recent 3M avg CPI / CPI 12m earlier) vs (prior 3M avg CPI / CPI 12m earlier).
      Needs >= 18 months of observations. Returns rising/falling/unknown.
      """
      if not fred_api_key:
          logger.warning("inflation(%s): no FRED api_key; returning unknown", region)
          return "unknown"
      try:
          params = {
              "series_id": series_id,
              "api_key": fred_api_key,
              "file_type": "json",
              "sort_order": "desc",
              "limit": 18,
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
              return "unknown"

          # values[0] = latest month, values[17] = 17 months ago
          recent_3m_avg = sum(values[0:3]) / 3.0    # months 0,1,2
          prior_3m_avg  = sum(values[3:6]) / 3.0    # months 3,4,5
          recent_yoy_base = sum(values[12:15]) / 3.0  # 12m earlier for recent window
          prior_yoy_base  = sum(values[15:18]) / 3.0  # 12m earlier for prior window

          if recent_yoy_base <= 0 or prior_yoy_base <= 0:
              return "unknown"

          recent_yoy = (recent_3m_avg / recent_yoy_base) - 1.0
          prior_yoy  = (prior_3m_avg  / prior_yoy_base)  - 1.0

          return "rising" if recent_yoy > prior_yoy else "falling"
      except Exception as exc:
          logger.warning("inflation(%s): FRED fetch failed: %s", region, exc)
          return "unknown"
  ```

- [ ] Run tests — expect green.

- [ ] Commit:

  ```bash
  git add data/macro_fetcher.py tests/test_macro_fetcher.py
  git commit -m "feat(macro): _fetch_inflation_signal via FRED CPI YoY trend"
  ```

---

## Task 6 — Top-level `fetch_macro_signals` with JSON caching

**Files:**
- `data/macro_fetcher.py` (extend)
- `tests/test_macro_fetcher.py` (extend)

**Steps:**

- [ ] Append tests:

  ```python
  class TestFetchMacroSignals:
      def test_uses_cache_when_fresh(self, monkeypatch, tmp_path):
          cache_file = tmp_path / "macro_regime.json"
          payload = {
              "fetched_at": datetime.utcnow().isoformat(),
              "signals": {
                  "US":     {"rates": "rising", "growth": "expanding", "inflation": "rising",
                             "regime": "Overheating", "color": "#f39c12"},
                  "India":  {"rates": "falling","growth": "expanding", "inflation": "falling",
                             "regime": "Goldilocks", "color": "#27ae60"},
                  "Japan":  {"rates": "rising", "growth": "contracting","inflation": "rising",
                             "regime": "Stagflation", "color": "#e74c3c"},
                  "Europe": {"rates": "falling","growth": "contracting","inflation": "falling",
                             "regime": "Deflation / Bust", "color": "#2c3e50"},
              },
          }
          cache_file.write_text(json.dumps(payload))
          monkeypatch.setattr(mf, "CACHE_PATH", cache_file)

          def _boom(*a, **k): raise AssertionError("should not fetch")
          monkeypatch.setattr(mf, "_fetch_rates_signal", _boom)
          monkeypatch.setattr(mf, "_fetch_growth_signal", _boom)
          monkeypatch.setattr(mf, "_fetch_inflation_signal", _boom)

          out = mf.fetch_macro_signals(force_refresh=False, fred_api_key="X")
          assert out["US"]["regime"] == "Overheating"
          assert out["India"]["color"] == "#27ae60"

      def test_force_refresh_ignores_cache(self, monkeypatch, tmp_path):
          cache_file = tmp_path / "macro_regime.json"
          monkeypatch.setattr(mf, "CACHE_PATH", cache_file)

          monkeypatch.setattr(mf, "_fetch_rates_signal",     lambda r, t: "falling")
          monkeypatch.setattr(mf, "_fetch_growth_signal",    lambda r, k: "expanding")
          monkeypatch.setattr(mf, "_fetch_inflation_signal", lambda r, s, k: "falling")

          out = mf.fetch_macro_signals(force_refresh=True, fred_api_key="X")
          assert out["US"]["regime"] == "Goldilocks"
          assert out["India"]["regime"] == "Goldilocks"
          assert cache_file.exists()

      def test_stale_cache_triggers_refresh(self, monkeypatch, tmp_path):
          cache_file = tmp_path / "macro_regime.json"
          stale = datetime.utcnow() - timedelta(hours=48)
          cache_file.write_text(json.dumps({
              "fetched_at": stale.isoformat(),
              "signals": {"US": {"rates": "rising", "growth": "expanding",
                                 "inflation": "rising", "regime": "Overheating",
                                 "color": "#f39c12"}},
          }))
          monkeypatch.setattr(mf, "CACHE_PATH", cache_file)
          monkeypatch.setattr(mf, "_fetch_rates_signal",     lambda r, t: "falling")
          monkeypatch.setattr(mf, "_fetch_growth_signal",    lambda r, k: "expanding")
          monkeypatch.setattr(mf, "_fetch_inflation_signal", lambda r, s, k: "falling")

          out = mf.fetch_macro_signals(force_refresh=False, fred_api_key="X")
          assert out["US"]["regime"] == "Goldilocks"

      def test_output_shape(self, monkeypatch, tmp_path):
          cache_file = tmp_path / "macro_regime.json"
          monkeypatch.setattr(mf, "CACHE_PATH", cache_file)
          monkeypatch.setattr(mf, "_fetch_rates_signal",     lambda r, t: "rising")
          monkeypatch.setattr(mf, "_fetch_growth_signal",    lambda r, k: "contracting")
          monkeypatch.setattr(mf, "_fetch_inflation_signal", lambda r, s, k: "rising")

          out = mf.fetch_macro_signals(force_refresh=True, fred_api_key="X")
          assert set(out.keys()) == {"US", "India", "Japan", "Europe"}
          for region, d in out.items():
              assert set(d.keys()) == {"rates", "growth", "inflation", "regime", "color"}
          assert out["US"]["regime"] == "Stagflation"
  ```

- [ ] Run — expect red.

- [ ] Implement. Append to macro_fetcher.py:

  ```python
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
          yield_ticker = YIELD_TICKERS[region]
          cpi_series = CPI_SERIES[region]
          rates     = _fetch_rates_signal(region, yield_ticker)
          growth    = _fetch_growth_signal(region, fred_api_key)
          inflation = _fetch_inflation_signal(region, cpi_series, fred_api_key)
          regime_label, color = _determine_regime(rates, growth, inflation)
          signals[region] = {
              "rates": rates, "growth": growth, "inflation": inflation,
              "regime": regime_label, "color": color,
          }

      _save_cache(signals)
      return signals
  ```

- [ ] Run tests — expect green:

  ```bash
  python -m pytest tests/test_macro_fetcher.py -v 2>&1 | tail -25
  ```

- [ ] Commit:

  ```bash
  git add data/macro_fetcher.py tests/test_macro_fetcher.py
  git commit -m "feat(macro): fetch_macro_signals with 24h JSON cache"
  ```

---

## Task 7 — `dashboard/tab_macro_regime.py` Section A (region cards)

**Files:**
- `dashboard/tab_macro_regime.py` (new)

**Steps:**

- [ ] Create `dashboard/tab_macro_regime.py`:

  ```python
  """Tab 6 — Macro Regime. Renders three sections (A cards, B table, C heatmap)."""
  from __future__ import annotations

  import streamlit as st

  from data import macro_fetcher as mf

  REGION_FLAGS: dict[str, str] = {
      "US": "🇺🇸", "India": "🇮🇳", "Japan": "🇯🇵", "Europe": "🇪🇺",
  }
  REGION_ORDER: list[str] = ["US", "India", "Japan", "Europe"]


  def _render_region_card(region: str, signal: dict[str, str]) -> None:
      """Render one colored card for a region using markdown + inline HTML."""
      flag = REGION_FLAGS.get(region, "")
      regime = signal.get("regime", "Unknown")
      color = signal.get("color", "#7f8c8d")
      rates = signal.get("rates", "unknown")
      growth = signal.get("growth", "unknown")
      inflation = signal.get("inflation", "unknown")
      favored, avoided = mf._get_factor_recommendations(regime)

      rates_arrow     = mf._signal_arrow(rates)
      growth_arrow    = mf._signal_arrow(growth)
      inflation_arrow = mf._signal_arrow(inflation)

      favored_str = ", ".join(favored) if favored else "—"
      avoided_str = ", ".join(avoided) if avoided else "—"

      html = f"""
      <div style="border-left: 6px solid {color}; padding: 12px 16px; background: #f8f9fa;
                  border-radius: 6px; margin-bottom: 10px;">
        <div style="font-size: 18px; font-weight: 600;">{flag} {region}</div>
        <div style="font-size: 22px; font-weight: 700; color: {color}; margin: 6px 0;">
          {regime}
        </div>
        <div style="font-size: 14px; margin: 6px 0;">
          Rates {rates_arrow} &nbsp;|&nbsp; Growth {growth_arrow} &nbsp;|&nbsp; Inflation {inflation_arrow}
        </div>
        <div style="font-size: 13px; margin-top: 8px;">
          <b>Favor:</b> {favored_str}<br/>
          <b>Avoid:</b> {avoided_str}
        </div>
      </div>
      """
      st.markdown(html, unsafe_allow_html=True)


  def _render_section_a(signals: dict[str, dict[str, str]]) -> None:
      st.subheader("Section A — Current Regime by Region")
      cols = st.columns(4)
      for col, region in zip(cols, REGION_ORDER):
          with col:
              sig = signals.get(region, {})
              _render_region_card(region, sig)


  def render(signals: dict[str, dict[str, str]], force_refresh: bool = False) -> None:
      """Entry point called by app.py."""
      st.header("Macro Regime Monitor")
      st.caption(
          "Three live signals per region (rates, growth, inflation) mapped to one of "
          "eight macro regimes and a factor-tilt recommendation."
      )
      _render_section_a(signals)
  ```

- [ ] Run a syntax check:

  ```bash
  python -c "from dashboard import tab_macro_regime; print('ok')"
  ```

  Expected: `ok`.

- [ ] Commit:

  ```bash
  git add dashboard/tab_macro_regime.py
  git commit -m "feat(tab6): section A — per-region regime cards"
  ```

---

## Task 8 — Section B (side-by-side comparison table)

**Files:**
- `dashboard/tab_macro_regime.py` (extend)

**Steps:**

- [ ] Add `import pandas as pd` at the top, then append before `render`:

  ```python
  def _render_section_b(signals: dict[str, dict[str, str]]) -> None:
      st.subheader("Section B — Side-by-Side Comparison")

      rows: dict[str, list[str]] = {
          "Rates":                [],
          "Growth":               [],
          "Inflation":            [],
          "Regime":               [],
          "Top Favored Factors":  [],
          "Top Avoided Factors":  [],
      }
      for region in REGION_ORDER:
          sig = signals.get(region, {})
          favored, avoided = mf._get_factor_recommendations(sig.get("regime", "Unknown"))
          rows["Rates"].append(f"{sig.get('rates', 'unknown')} {mf._signal_arrow(sig.get('rates', 'unknown'))}")
          rows["Growth"].append(f"{sig.get('growth', 'unknown')} {mf._signal_arrow(sig.get('growth', 'unknown'))}")
          rows["Inflation"].append(f"{sig.get('inflation', 'unknown')} {mf._signal_arrow(sig.get('inflation', 'unknown'))}")
          rows["Regime"].append(sig.get("regime", "Unknown"))
          rows["Top Favored Factors"].append(", ".join(favored) if favored else "—")
          rows["Top Avoided Factors"].append(", ".join(avoided) if avoided else "—")

      df = pd.DataFrame(rows, index=REGION_ORDER).T
      df.columns = [f"{REGION_FLAGS[r]} {r}" for r in REGION_ORDER]
      st.dataframe(df, use_container_width=True)
  ```

- [ ] Call it from `render`:

  ```python
  def render(signals: dict[str, dict[str, str]], force_refresh: bool = False) -> None:
      st.header("Macro Regime Monitor")
      st.caption(
          "Three live signals per region (rates, growth, inflation) mapped to one of "
          "eight macro regimes and a factor-tilt recommendation."
      )
      _render_section_a(signals)
      _render_section_b(signals)
  ```

- [ ] Syntax check + commit:

  ```bash
  python -c "from dashboard import tab_macro_regime; print('ok')"
  git add dashboard/tab_macro_regime.py
  git commit -m "feat(tab6): section B — side-by-side comparison table"
  ```

---

## Task 9 — Section C (factor × regime heatmap)

**Files:**
- `dashboard/tab_macro_regime.py` (extend)

**Steps:**

- [ ] Add `import plotly.graph_objects as go` at top. Append before `render`:

  ```python
  _SYMBOL_TO_SCORE: dict[str, int] = {"●":  1, "○":  0, "✕": -1}
  _COLORSCALE = [
      [0.0, "#e74c3c"],   # ✕ Avoid
      [0.5, "#bdc3c7"],   # ○ Neutral
      [1.0, "#27ae60"],   # ● Favor
  ]


  def _render_section_c(signals: dict[str, dict[str, str]]) -> None:
      st.subheader("Section C — Factor × Regime Matrix")

      regimes = list(mf.FACTOR_MATRIX.keys())
      factors = mf.FACTORS

      z: list[list[float]] = []
      text: list[list[str]] = []
      for regime in regimes:
          row = mf.FACTOR_MATRIX[regime]
          z.append([float(_SYMBOL_TO_SCORE[row[f]]) for f in factors])
          text.append([row[f] for f in factors])

      # Which regimes are currently active (for bold y-tick highlight).
      active_regimes = {sig.get("regime") for sig in signals.values()}
      y_labels = [
          f"<b>★ {r}</b>" if r in active_regimes else r
          for r in regimes
      ]

      fig = go.Figure(data=go.Heatmap(
          z=z,
          x=factors,
          y=y_labels,
          text=text,
          texttemplate="%{text}",
          textfont={"size": 18},
          colorscale=_COLORSCALE,
          zmin=-1, zmax=1,
          showscale=False,
          hovertemplate="Regime: %{y}<br>Factor: %{x}<br>Tilt: %{text}<extra></extra>",
      ))
      fig.update_layout(
          height=420,
          margin=dict(l=10, r=10, t=30, b=30),
          xaxis=dict(side="top"),
          yaxis=dict(autorange="reversed"),
      )
      st.plotly_chart(fig, use_container_width=True)
      st.caption(
          "Legend: ● Favor (green) &nbsp;·&nbsp; ○ Neutral (grey) &nbsp;·&nbsp; "
          "✕ Avoid (red). Rows marked ★ are currently active in at least one region."
      )
  ```

- [ ] Update `render` to call it last:

  ```python
  def render(signals: dict[str, dict[str, str]], force_refresh: bool = False) -> None:
      st.header("Macro Regime Monitor")
      st.caption(
          "Three live signals per region (rates, growth, inflation) mapped to one of "
          "eight macro regimes and a factor-tilt recommendation."
      )
      _render_section_a(signals)
      _render_section_b(signals)
      _render_section_c(signals)
  ```

- [ ] Syntax check + commit:

  ```bash
  python -c "from dashboard import tab_macro_regime; print('ok')"
  git add dashboard/tab_macro_regime.py
  git commit -m "feat(tab6): section C — factor × regime heatmap"
  ```

---

## Task 10 — Wire Tab 6 into `dashboard/app.py`

**Files:**
- `dashboard/app.py` (modify only)

**Steps:**

- [ ] Open `dashboard/app.py` and locate the `st.tabs(...)` call. Add imports near the
  other dashboard-module imports at the top:

  ```python
  from dashboard import tab_macro_regime
  from data.macro_fetcher import fetch_macro_signals
  ```

- [ ] Change the existing `st.tabs([...])` from 5 tabs to 6. Example diff — replace:

  ```python
  tab1, tab2, tab3, tab4, tab5 = st.tabs([
      "Overview", "Factors", "Attribution", "Stocks", "Portfolio Profile",
  ])
  ```

  with:

  ```python
  tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
      "Overview", "Factors", "Attribution", "Stocks", "Portfolio Profile",
      "Macro Regime",
  ])
  ```

  (If the current labels differ, keep them verbatim and just append `"Macro Regime"`.)

- [ ] After the existing `with tab5:` block, add:

  ```python
  with tab6:
      force_refresh = st.button("Refresh macro signals", key="macro_refresh")
      fred_api_key = st.secrets.get("fred", {}).get("api_key") if hasattr(st, "secrets") else None
      try:
          signals = fetch_macro_signals(
              force_refresh=force_refresh,
              fred_api_key=fred_api_key,
          )
      except Exception as exc:
          st.error(f"Failed to fetch macro signals: {exc}")
          signals = {}
      tab_macro_regime.render(signals, force_refresh=force_refresh)
  ```

- [ ] Run the full test suite to make sure nothing regressed:

  ```bash
  cd /home/ubuntu/claude_projects/portfolio_factor_analysis && python -m pytest 2>&1 | tail -15
  ```

  Expected: all tests pass (existing + new `test_macro_fetcher`).

- [ ] Commit:

  ```bash
  git add dashboard/app.py
  git commit -m "feat(app): wire Tab 6 Macro Regime into Streamlit layout"
  ```

---

## Task 11 — Smoke test

**Steps:**

- [ ] Copy the secrets template and (optionally) add a real FRED key:

  ```bash
  cp .streamlit/secrets.toml.example .streamlit/secrets.toml
  # edit .streamlit/secrets.toml and paste api_key
  ```

- [ ] Launch the app:

  ```bash
  cd /home/ubuntu/claude_projects/portfolio_factor_analysis && streamlit run dashboard/app.py
  ```

- [ ] In the browser:
  - Click **Macro Regime** tab.
  - Verify 4 region cards render with regime label, signal arrows, Favor/Avoid lists.
  - Verify comparison table has 4 region columns and 6 rows.
  - Verify heatmap shows 8 regime rows × 7 factor columns; active regime rows marked ★.
  - Click **Refresh macro signals** and confirm `data/cache/macro_regime.json` timestamp updates.
  - Without a FRED key, growth (US) and inflation (all) should render as `?` / "Unknown"
    but yield-based signals + non-US growth should still populate.

- [ ] Verify the cache file is valid JSON:

  ```bash
  python -c "import json; print(list(json.load(open('data/cache/macro_regime.json'))['signals'].keys()))"
  ```

  Expected: `['US', 'India', 'Japan', 'Europe']`.

- [ ] No commit needed — smoke test only.

---

## Self-review checklist

- [x] No "similar to above" or placeholder code — every task has full code
- [x] Every file path is absolute or clearly relative-to-repo-root
- [x] TDD order (red → green → commit) preserved in tasks 2–6
- [x] Type hints on all public functions (`fetch_macro_signals`, `render`, `_fetch_*`)
- [x] Signal vocabulary consistent: `rising` / `falling` / `expanding` / `contracting` / `unknown`
- [x] Output-shape contract matches spec exactly (keys: rates, growth, inflation, regime, color)
- [x] Cache path/TTL/format consistent across load, save, tests
- [x] No use of `write_cache` / `read_cache` (parquet-only) — JSON handled manually
- [x] FRED key passed as parameter; `None` → `unknown`, never raises
- [x] All 8 regime triples covered in REGIME_MAP; FACTOR_MATRIX has 8 regimes × 7 factors
- [x] UI sections match spec: A cards, B dataframe, C plotly heatmap with ★ for active
