# Macro Regime Tab — Design Spec
**Date:** 2026-04-14  
**Status:** Approved  
**Phase:** 1 of 2

---

## Overview

Add a new **Tab 6: Macro Regime** to the Portfolio Factor Analysis dashboard. The tab helps users understand the current macroeconomic regime across four global markets (US, India, Japan, Europe) and maps each regime to favored, neutral, and avoided factor/style exposures.

---

## Architecture

### Approach
Option B — Modular extraction. New tab and its data fetching are isolated into dedicated files. Existing tabs are not touched.

### New files
```
data/macro_fetcher.py          # Live signal fetching for rates, growth, inflation
dashboard/tab_macro_regime.py  # Tab rendering logic
```

### Integration in app.py
- Add `tab6` to the `st.tabs(...)` call
- Call `tab_macro_regime.render(force_refresh)` inside `with tab6:`
- Import `from dashboard import tab_macro_regime`

### Hosting compatibility
Fully compatible with Streamlit Community Cloud free tier. No additional memory or compute concerns beyond a FRED API key stored in Streamlit Secrets.

---

## Data Layer — `data/macro_fetcher.py`

### Three regime dimensions

Each dimension returns a binary signal: `"rising"` / `"falling"` (rates, inflation) or `"expanding"` / `"contracting"` (growth).

#### 1. Rates — 10Y Government Bond Yield
Direction computed as: current yield vs. yield 3 months ago.

| Region | Yahoo Finance ticker |
|--------|---------------------|
| US | `^TNX` |
| India | `IN10Y=X` |
| Japan | `JP10Y=X` |
| Europe | `DE10Y=X` (German Bund as EU proxy) |

#### 2. Growth — PMI + Equity Index Proxy
- **US:** FRED series `NAPM` (ISM Manufacturing PMI). Signal: above/below 50 combined with 3M direction.
- **India, Japan, Europe:** 3-month annualised return of equity index proxy as growth signal.

| Region | Yahoo Finance ticker |
|--------|---------------------|
| India | `^BSESN` (BSE Sensex) |
| Japan | `^N225` (Nikkei 225) |
| Europe | `^STOXX50E` (Euro Stoxx 50) |

Signal: positive 3M return → `"expanding"`, negative → `"contracting"`.

#### 3. Inflation — CPI YoY via FRED
Direction: compare latest 3-month CPI average vs. prior 3-month average.

| Region | FRED series |
|--------|------------|
| US | `CPIAUCSL` |
| India | `INDCPIALLMINMEI` |
| Japan | `JPNCPIALLMINMEI` |
| Europe | `CP0000EZ19M086NEST` |

### Output format
`macro_fetcher.py` returns a dict keyed by region:
```python
{
  "US":     {"rates": "rising",  "growth": "expanding",   "inflation": "rising"},
  "India":  {"rates": "falling", "growth": "expanding",   "inflation": "falling"},
  "Japan":  {"rates": "rising",  "growth": "contracting", "inflation": "rising"},
  "Europe": {"rates": "falling", "growth": "contracting", "inflation": "falling"},
}
```

### Caching
- Cache file: `cache/macro_regime.json`
- Stale threshold: 24 hours
- Refreshed when user clicks "Refresh Data" (same `force_refresh` flag)
- Graceful fallback: if any fetch fails, show a warning and use last cached value

### FRED API key
- Stored in `.streamlit/secrets.toml` locally as `[fred] api_key = "..."`
- Stored in Streamlit Cloud secrets manager for deployment
- Accessed via `st.secrets["fred"]["api_key"]`

---

## Regime Labeling

### Named labels (8 combinations)
Each combination of (Rates ↑/↓ × Growth ↑/↓ × Inflation ↑/↓) maps to a named label:

| Rates | Growth | Inflation | Label | Color |
|-------|--------|-----------|-------|-------|
| ↓ | ↑ | ↓ | Goldilocks | Green |
| ↑ | ↑ | ↑ | Overheating | Amber |
| ↑ | ↓ | ↑ | Stagflation | Red |
| ↓ | ↓ | ↓ | Deflation / Bust | Dark Blue |
| ↑ | ↑ | ↓ | Recovery / Tightening | Teal |
| ↓ | ↓ | ↑ | Stagflation-Lite | Orange-Red |
| ↑ | ↓ | ↓ | Recession / Tightening | Steel Blue |
| ↓ | ↑ | ↑ | Reflation | Amber-Green |

Display: named label shown prominently, signal trio (↑/↓ per dimension) shown as supporting detail underneath.

---

## UI Layout — `dashboard/tab_macro_regime.py`

### Section A — Region Regime Cards (hero)
Four `st.columns`, one card per region (US, India, Japan, Europe).

Each card contains:
- Region flag + name as header
- Regime label (color-coded, bold)
- Signal trio: Rates ↑/↓, Growth ↑/↓, Inflation ↑/↓
- Factor recommendations: ✅ Favor / ⚠️ Avoid / ➖ Neutral (top 2–3 each)

### Section B — Side-by-side Comparison Table
Single `st.dataframe` with regions as columns. Rows:
- Rates signal
- Growth signal
- Inflation signal
- Regime label
- Top favored factors
- Top avoided factors

### Section C — Full Factor × Regime Reference Matrix
Heatmap-style table rendered via Plotly or styled `st.dataframe`:
- **Rows:** 8 regime combinations (active regimes for each region highlighted)
- **Columns:** 7 factors/styles (Market Beta, Size, Value, Momentum, Quality, Low Vol, Growth)
- **Cell values:** ● Favor (green) / ○ Neutral (grey) / ✕ Avoid (red)

Currently active regimes per region are highlighted rows so users can instantly locate each market.

---

## Factor × Regime Matrix (Static Lookup Table)

| Regime | Label | Mkt Beta | Size | Value | Momentum | Quality | Low Vol | Growth |
|--------|-------|----------|------|-------|----------|---------|---------|--------|
| ↓R ↑G ↓I | Goldilocks | ● | ● | ○ | ● | ○ | ✕ | ● |
| ↑R ↑G ↑I | Overheating | ○ | ✕ | ● | ● | ○ | ✕ | ○ |
| ↑R ↓G ↑I | Stagflation | ✕ | ✕ | ● | ✕ | ● | ● | ✕ |
| ↓R ↓G ↓I | Deflation/Bust | ✕ | ✕ | ✕ | ○ | ● | ● | ✕ |
| ↑R ↑G ↓I | Recovery/Tightening | ● | ● | ● | ○ | ○ | ✕ | ○ |
| ↓R ↓G ↑I | Stagflation-Lite | ✕ | ✕ | ● | ✕ | ● | ○ | ✕ |
| ↑R ↓G ↓I | Recession/Tightening | ✕ | ○ | ✕ | ✕ | ● | ● | ✕ |
| ↓R ↑G ↑I | Reflation | ● | ● | ● | ● | ✕ | ✕ | ● |

### Key rationale
- **Quality** favored in all stress regimes (Stagflation, Bust, Recession) — defensive earnings quality holds up
- **Low Vol** avoided in Goldilocks/Recovery/Reflation — underperforms in risk-on environments
- **Value** shines in rising-rate environments (financial sector tilt, short duration characteristics)
- **Momentum** works in trending markets (Goldilocks, Overheating, Reflation) but breaks in sharp reversals
- **Growth** favored when rates are falling (low discount rate boosts long-duration cash flows); avoided in all rising-rate stress regimes

---

## Phase 2 Roadmap (deferred)

### Option B — Empirical backtest layer
Backtest how each factor actually performed during historical regime periods using:
- IIMA dataset for India (already in app)
- Equivalent factor indices for US/EU/Japan (AQR, Ken French data library)

Show a "what the data says" comparison alongside the academic consensus table.

### Option C — Hybrid view
Combine the static matrix (Section C) with empirical backtest results in a single unified panel, letting users toggle between "Consensus" and "Historical" views.

---

## Out of Scope (Phase 1)
- Regime transition signals or forecasts
- Portfolio alignment score vs. current regime
- Notifications or alerts when regime changes
- Sentiment indicators (credit spreads, VIX as regime input)
