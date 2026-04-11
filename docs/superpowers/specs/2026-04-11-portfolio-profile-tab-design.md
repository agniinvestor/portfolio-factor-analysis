# Portfolio Profile Tab — Design Spec

**Date:** 2026-04-11  
**Feature:** Tab 5 — Portfolio Profile  
**Location:** `dashboard/app.py` (new tab added to existing 4-tab layout)

---

## Goal

Add a fifth tab to the dashboard that gives a comprehensive, readable description of the entire portfolio's factor character and style — combining an executive-level narrative with quantitative depth.

---

## Architecture

All data already computed upstream by Tabs 2 and 3:
- `iima_factors` — IIMA monthly factor returns
- `fundamentals` — Screener.in fundamentals (from snapshot fallback)
- `stock_returns_df` — monthly returns per stock (yfinance)
- `port_returns` — weighted portfolio monthly returns
- `reg_result` — Carhart 4-factor OLS result dict
- `style_scores` — per-stock 6-dimension z-scores
- `port_scores` — portfolio-level weighted style z-scores

Tab 5 is a **pure consumer** — it reads these shared variables, does no new fetches, and adds only display logic.

New helper functions live in `factors/regression.py`:
- `rolling_carhart_betas(portfolio_returns, factor_returns, window_months)` → DataFrame of rolling betas indexed by date
- `factor_return_attribution(portfolio_returns, factor_returns, reg_result)` → DataFrame of monthly factor contributions

New helper function in `factors/scorer.py`:
- `compute_nifty500_percentile_scores(portfolio_fundamentals, nifty500_snapshot_path)` → Series of portfolio style percentile ranks (0–100) vs Nifty 500 universe

---

## Section A — Summary Cards + Narrative

**6 metric cards** in a single `st.columns(6)` row:

| Card | Value | Source |
|---|---|---|
| Dominant Factor | Highest-beta significant factor name + β value | `reg_result["betas"]`, `reg_result["p_values"]` |
| Alpha (monthly) | Alpha % + t-stat | `reg_result["alpha"]`, `reg_result["alpha_t"]` |
| R² | Regression fit | `reg_result["r_squared"]` |
| Top Style Tilt | Strongest dimension name + z-score | `port_scores` |
| Portfolio HHI | Σw² (stock concentration) | `portfolio["weight"]` |
| Effective N | 1/HHI | derived |

**Auto-generated narrative paragraph** below cards. Template logic:
- Opens with market beta description (high/moderate/low vs 1.0)
- Lists statistically significant factor tilts (p < 0.05) with direction
- Describes top 2 style dimensions by absolute z-score
- Closes with size characterisation (negative size = large-cap tilt)

Narrative rendered in `st.info()` box with italic formatting.

---

## Section B — Investment Memo (3 Expanders)

### Expander 1: Factor Tilts

Table with columns: Factor | Beta | t-stat | p-value | Sig (5%) | Interpretation

One-line interpretations (auto-generated from beta sign + magnitude):
- Market β > 1.1: "Aggressive market exposure — amplifies index moves"
- Market β 0.9–1.1: "Neutral market exposure — tracks index closely"
- Market β < 0.9: "Defensive market exposure — lower sensitivity to index"
- SMB β > 0.2 sig: "Positive size tilt — overweight small/mid caps"
- SMB β < -0.2 sig: "Negative size tilt — large-cap bias"
- HML β > 0.2 sig: "Positive value tilt — cheaper stocks by P/B"
- HML β < -0.2 sig: "Growth tilt — higher-valuation stocks"
- WML β > 0.2 sig: "Momentum tilt — recent winners overweighted"
- WML β < -0.2 sig: "Contrarian tilt — recent underperformers"
- Not significant: "No statistically significant exposure"

### Expander 2: Style Characteristics

- Radar chart (larger version, height=500) of portfolio vs Nifty 500 baseline (zero)
- Ranked table: dimension | portfolio z-score | percentile vs Nifty 500 | interpretation
  - > +0.5: "Strong positive tilt"
  - +0.2 to +0.5: "Mild positive tilt"
  - -0.2 to +0.2: "Neutral"
  - -0.5 to -0.2: "Mild negative tilt"
  - < -0.5: "Strong negative tilt"

### Expander 3: Risk Profile

Three sub-sections:

**Stock Concentration**
- HHI value + label (< 0.1 = diversified, 0.1–0.18 = moderate, > 0.18 = concentrated)
- Effective N
- Top 5 holdings weight %

**Sector Concentration**
- Sector HHI
- Top 2 sectors by weight with %

**Factor R² Breakdown**
- Pie chart: variance explained by each factor + residual
- Each factor's contribution = (beta_i × std(factor_i))² / var(port_excess)
- Residual = 1 − R²

---

## Section C — Quantitative Detail (4 Charts)

### Chart 1: Rolling Factor Betas

- Function: `rolling_carhart_betas(port_returns, iima_factors, window_months=24)`
- Implementation: rolling OLS using `statsmodels.regression.rolling.RollingOLS`
- Output: line chart (Plotly), one line per factor, x = date, y = beta
- Window selector: radio buttons [12M / 24M / 36M] — default 24M
- Height: 400px

### Chart 2: Factor Return Attribution

- Function: `factor_return_attribution(port_returns, iima_factors, reg_result)`
- For each month: alpha_contrib + Σ(beta_i × factor_i_return) + residual = port_excess_return
- Stacked bar chart (Plotly), positive above zero, negative below
- Colours: Market=blue, SMB=green, HML=orange, WML=purple, Alpha=gold, Residual=grey
- Height: 400px

### Chart 3: Style Score vs Nifty 500 Percentile

- Function: `compute_nifty500_percentile_scores(port_scores, nifty500_snapshot_path)`
- Cross-sectional percentile rank of portfolio score vs Nifty 500 universe
- Horizontal bar chart, x = percentile (0–100), y = dimension
- Reference line at 50th percentile (= index neutral)
- Height: 350px

### Chart 4: Weight Distribution

- Bar chart: stocks sorted by weight descending, x = stock name, y = weight %
- Overlay: cumulative weight line (right y-axis, 0–100%)
- Reference lines at 50% and 80% cumulative
- Height: 350px

---

## Data Files Used

| File | Used for |
|---|---|
| `data/nifty500_screener_snapshot.csv` | Nifty 500 peer universe for percentile ranks |
| `data/price_returns_snapshot.csv` | Fallback price returns |
| `data/screener_snapshot.csv` | Fallback fundamentals |

---

## Files Modified

| File | Change |
|---|---|
| `dashboard/app.py` | Add Tab 5 content block |
| `factors/regression.py` | Add `rolling_carhart_betas`, `factor_return_attribution` |
| `factors/scorer.py` | Add `compute_nifty500_percentile_scores` |
| `tests/test_regression.py` | Tests for new regression helpers |
| `tests/test_scorer.py` | Test for new scorer helper |

---

## Out of Scope

- Historical weight data (not available — weight distribution is point-in-time only)
- Benchmark return series (no Nifty 500 price data fetched)
- PDF export
