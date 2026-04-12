# Portfolio Factor Analysis — Developer Guide

> **Audience:** Developers who want to understand, extend, or maintain this codebase.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Setup & Running](#2-setup--running)
3. [Data Flow](#3-data-flow)
4. [Module Reference](#4-module-reference)
   - [data/portfolio.py](#41-dataportfoliopy)
   - [data/ticker_map.py](#42-dataticker_mappy)
   - [data/cache_manager.py](#43-datacache_managerpy)
   - [data/fetcher.py](#44-datafetcherpy)
   - [factors/scorer.py](#45-factorsscorerpy)
   - [factors/regression.py](#46-factorsregressionpy)
   - [dashboard/app.py](#47-dashboardapppy)
5. [Caching Layer](#5-caching-layer)
6. [Test Suite](#6-test-suite)
7. [Adding a New Factor Dimension](#7-adding-a-new-factor-dimension)
8. [Adding a New Data Source](#8-adding-a-new-data-source)
9. [Known Constraints](#9-known-constraints)
10. [Next Steps & Engineering Roadmap](#10-next-steps--engineering-roadmap)

---

## 1. Project Structure

```
portfolio_factor_analysis/
│
├── portfolio.xlsx                  # Input: 33 holdings (Name, ISIN, Sector, Value)
├── ticker_map.json                 # ISIN → NSE ticker mapping (33 entries)
├── requirements.txt                # Python dependencies
│
├── data/
│   ├── __init__.py
│   ├── portfolio.py                # Load + clean portfolio.xlsx
│   ├── ticker_map.py               # Load ticker_map.json; ISIN lookup
│   ├── cache_manager.py            # Parquet cache read/write + staleness check
│   ├── fetcher.py                  # All external data fetching (IIMA, Screener, prices)
│   ├── cache/                      # Runtime parquet cache (gitignored except .gitkeep)
│   │   └── .gitkeep
│   ├── screener_snapshot.csv       # Committed fallback: per-stock fundamentals
│   ├── price_returns_snapshot.csv  # Committed fallback: monthly returns matrix
│   └── nifty500_screener_snapshot.csv  # Nifty 500 fundamentals for percentile ranking
│
├── factors/
│   ├── __init__.py
│   ├── scorer.py                   # Style z-scores + portfolio weighting + Nifty 500 percentile
│   └── regression.py               # Carhart OLS + rolling betas + return attribution
│
├── dashboard/
│   ├── __init__.py
│   └── app.py                      # Streamlit app (5 tabs)
│
├── tests/
│   ├── __init__.py
│   ├── test_fetcher.py             # Cache logic + IIMA/Screener parsing
│   ├── test_scorer.py              # Z-scoring, weighting, percentile
│   ├── test_regression.py          # OLS, rolling betas, attribution
│   └── test_integration.py         # End-to-end smoke tests
│
└── docs/
    ├── METHODOLOGY.md              # Analytical methodology (this project)
    ├── DEVELOPER_GUIDE.md          # This file
    └── superpowers/                # Design specs and implementation plans
        ├── specs/
        └── plans/
```

---

## 2. Setup & Running

### Install dependencies

```bash
pip install -r requirements.txt
```

The project requires Python 3.12+. Dependencies:

| Package | Purpose |
|---|---|
| `streamlit` | Dashboard UI |
| `pandas` | DataFrames throughout |
| `numpy` | Numerical operations |
| `statsmodels` | OLS regression + RollingOLS |
| `plotly` | All charts |
| `yfinance` | NSE price history |
| `requests` + `beautifulsoup4` | Screener.in scraping |
| `pyarrow` | Parquet cache serialisation |
| `openpyxl` | Reading portfolio.xlsx |
| `python-dateutil` | Relative date arithmetic for regression window |

### Run the dashboard

```bash
cd portfolio_factor_analysis
streamlit run dashboard/app.py
```

The app opens at `http://localhost:8501`. On first run, click **Refresh Data** in the sidebar to populate the cache.

### Run the tests

```bash
python3 -m pytest tests/ -v
```

Two integration tests are skipped by default (they make live network calls to the IIMA website). All other 46 tests run offline using synthetic data.

---

## 3. Data Flow

```
portfolio.xlsx
      │
      ▼
data/portfolio.py ──────────────────────────────────────────────────────────────────┐
  load_portfolio()                                                                    │
  (weights from value, ISIN→ticker via ticker_map.json)                              │
      │                                                                               │
      ├── tickers list ──────────────────────┐                                        │
      │                                      │                                        │
      ▼                                      ▼                                        │
data/fetcher.py                       data/fetcher.py                                 │
  fetch_iima_factors()                  fetch_all_fundamentals()                      │
  (IIMA CSV → parquet cache)            (Screener.in → parquet cache)                 │
      │                                      │                                        │
      │             data/fetcher.py          │                                        │
      │               fetch_all_prices()     │                                        │
      │               (yfinance → snapshot)  │                                        │
      │                      │               │                                        │
      ▼                      ▼               ▼                                        │
factors/regression.py    factors/scorer.py                                            │
  build_portfolio_returns()   compute_style_scores()   ◄──── fundamentals             │
  run_carhart_regression()    compute_portfolio_scores() ◄─── weights from portfolio ─┘
  rolling_carhart_betas()     compute_nifty500_percentile_scores()
  factor_return_attribution()          │
      │                                │
      └────────────────┬───────────────┘
                       │
                       ▼
               dashboard/app.py
               (5-tab Streamlit UI)
               Tab 1: Portfolio Overview  ◄── portfolio df
               Tab 2: Factor Regression   ◄── reg_result
               Tab 3: Style Scorecard     ◄── style_scores, port_scores
               Tab 4: Stock Deep-Dive     ◄── style_scores, external links
               Tab 5: Portfolio Profile   ◄── reg_result + port_scores (shared)
```

All computationally expensive operations (`fetch_iima_factors`, `get_fundamentals`, `get_all_prices`) are wrapped in `@st.cache_data` to avoid re-running on every Streamlit rerender. They re-execute only when `force_refresh=True` (the Refresh Data button) or when the 24-hour parquet cache expires.

---

## 4. Module Reference

### 4.1 `data/portfolio.py`

**Responsibility:** Load `portfolio.xlsx` and return a clean DataFrame.

```python
load_portfolio(xlsx_path: str) -> pd.DataFrame
```

**Returns columns:** `name`, `isin`, `ticker`, `sector`, `weight`, `value`

- Weights are computed from the `value` column (current market value), not any formula column
- Tickers are resolved via `data/ticker_map.py`
- Rows with null ISINs are dropped

**Extension point:** To support long-short portfolios, add a `side` column here and assign negative weights to `Short` rows.

---

### 4.2 `data/ticker_map.py`

**Responsibility:** Load the static ISIN → NSE ticker JSON and provide lookup functions.

```python
load_ticker_map() -> dict[str, str]   # full map
get_ticker(isin: str) -> str          # single lookup, raises KeyError if missing
```

The map lives at `ticker_map.json` in the project root. Add new ISINs there when the portfolio changes.

---

### 4.3 `data/cache_manager.py`

**Responsibility:** Lightweight parquet cache. Three functions, no state.

```python
is_stale(path: Path, max_age_hours: int = 24) -> bool
write_cache(df: pd.DataFrame, path: Path) -> None
read_cache(path: Path) -> pd.DataFrame
```

All parquet files live in `data/cache/`. The cache directory is created on first import. Cache files are gitignored; snapshots (`*_snapshot.csv`) are committed.

**Staleness logic:** A file is stale if it does not exist OR its modification time is older than `max_age_hours`. Default is 24 hours. `force_refresh=True` bypasses this check entirely.

---

### 4.4 `data/fetcher.py`

**Responsibility:** All external data fetching. Four public functions plus parsing helpers.

#### `fetch_iima_factors(force_refresh: bool = False) -> pd.DataFrame`

- Scrapes the IIMA page to discover the current CSV URL (URL changes with each data update)
- Downloads and parses the CSV: percent → decimal, maps column names to `mkt_rf / smb / hml / wml / rf`
- Caches to `data/cache/iima_factors.parquet`
- **Returns:** DataFrame with columns `date, mkt_rf, smb, hml, wml, rf`; one row per month

URL discovery priority:
1. Survivorship-bias-adjusted monthly four-factor CSV
2. Any monthly four-factor CSV
3. Any monthly CSV (last resort)

#### `fetch_all_fundamentals(tickers: list[str], force_refresh: bool = False) -> pd.DataFrame`

- Calls `fetch_screener_fundamentals(ticker)` per stock (with 1.5s sleep between requests)
- Falls back to `data/screener_snapshot.csv` row for any ticker that returns no data
- **Returns:** DataFrame with one row per ticker; columns include `ticker, pe, pb, roe, roce, de, market_cap_cr, revenue_cagr_3y, net_margin`

#### `fetch_all_prices(tickers: list[str], years: int = 6, force_refresh: bool = False) -> pd.DataFrame`

- Batch-downloads NSE monthly prices via yfinance (`.NS` suffix)
- Computes simple monthly returns via `pct_change()`
- Falls back to `data/price_returns_snapshot.csv` on failure
- **Returns:** DataFrame indexed by date, one column per ticker, values are monthly returns

#### `compute_monthly_returns(prices_df: pd.DataFrame) -> pd.Series`

- Utility for single-stock price DataFrame (columns: `date`, `price`)
- Returns a Series of monthly returns indexed by date

#### Internal helpers

| Function | Purpose |
|---|---|
| `parse_iima_csv(csv_text)` | Parse test-fixture-style IIMA CSV (year/month columns) |
| `_parse_iima_live_csv(csv_text)` | Parse live IIMA CSV (Date column as YYYY-MM) |
| `_discover_iima_csv_url()` | Scrape IIMA page, return CSV URL |
| `parse_screener_fundamentals(html)` | Parse Screener.in company page HTML |
| `fetch_screener_fundamentals(ticker)` | Fetch and cache single-stock fundamentals |
| `_load_snapshot()` | Load `screener_snapshot.csv` |
| `_load_price_snapshot()` | Load `price_returns_snapshot.csv` |

---

### 4.5 `factors/scorer.py`

**Responsibility:** Cross-sectional style z-scores and portfolio weighting.

#### `compute_style_scores(fundamentals: pd.DataFrame) -> pd.DataFrame`

- **Input:** DataFrame with columns `ticker, pe, pb, roe, roce, de, market_cap_cr, momentum_12m_1m, revenue_cagr_3y, net_margin`
- **Output:** DataFrame with columns `ticker, value, quality, momentum, size, growth, profitability` — all z-scored
- Missing columns are filled with 0 before z-scoring
- Higher score = stronger positive tilt in that direction for all six dimensions

The internal `_zscore(series)` helper returns all zeros if the standard deviation is 0 (handles degenerate edge cases in tests).

#### `compute_portfolio_scores(style_scores: pd.DataFrame, weights: pd.Series) -> pd.Series`

- **Input:** Output of `compute_style_scores` + a Series of ticker → weight
- **Output:** Series of 6 weighted-average z-scores indexed by dimension name
- Weights are renormalised to sum to 1 over available tickers

#### `compute_nifty500_percentile_scores(port_scores: pd.Series, nifty500_snapshot_path: str) -> pd.Series`

- **Input:** Portfolio z-scores (from above) + path to Nifty 500 snapshot CSV
- **Output:** Series of percentile ranks 0–100 per dimension
- Falls back to 50.0 for all dimensions if the snapshot is missing or unreadable
- Uses `np.mean(universe < score) * 100` — fraction of Nifty 500 stocks below the portfolio score

---

### 4.6 `factors/regression.py`

**Responsibility:** Portfolio return construction and all Carhart regression variants.

#### `build_portfolio_returns(stock_returns: pd.DataFrame, weights: dict) -> pd.Series`

- **Input:** Wide returns DataFrame (index=date, columns=tickers) + weight dict
- **Output:** Series of monthly portfolio returns named `"portfolio"`
- Weights are renormalised to only the tickers present in `stock_returns`

#### `run_carhart_regression(portfolio_returns, factor_returns, window_years) -> dict`

- **Input:** Portfolio returns Series + IIMA factors DataFrame + window in years
- **Output:** dict with keys:
  - `alpha`, `alpha_t`, `alpha_p` — intercept, its t-stat, its p-value
  - `betas`, `t_stats`, `p_values` — each a dict keyed by `mkt_rf / smb / hml / wml`
  - `r_squared` — float
  - `n_obs` — int
- Window is applied as a trailing cutoff: `cutoff = max_date - relativedelta(years=window_years)`

#### `rolling_carhart_betas(portfolio_returns, factor_returns, window_months=24) -> pd.DataFrame`

- Uses `statsmodels.regression.rolling.RollingOLS`
- **Returns:** DataFrame indexed by date with columns `mkt_rf, smb, hml, wml`; NaN rows before the window fills

#### `factor_return_attribution(portfolio_returns, factor_returns, reg_result) -> pd.DataFrame`

- **Returns:** DataFrame indexed by date with columns `alpha, mkt_rf, smb, hml, wml, residual`
- The six columns sum exactly to the portfolio excess return for each month (verified by `test_factor_return_attribution_sums_to_port_excess`)

---

### 4.7 `dashboard/app.py`

**Responsibility:** Streamlit front-end. Consumes all modules above; contains no business logic.

The app follows this structure:

```
Sidebar
  └── Refresh button → force_refresh flag
  └── Regression window slider → window_years

@st.cache_data wrappers
  ├── get_iima(force)           → iima_factors
  ├── get_fundamentals(tickers, force) → fundamentals
  └── get_all_prices(tickers, force)  → stock_returns_df

Shared variables computed once (used across multiple tabs):
  ├── port_returns      (from build_portfolio_returns)
  ├── reg_result        (from run_carhart_regression)
  ├── style_scores      (from compute_style_scores)
  └── port_scores       (from compute_portfolio_scores)

Tab 1 — Portfolio Overview
  ├── Holdings table (weight %, value INR)
  ├── Sector concentration bar chart
  └── Top 5 / Bottom 5 by weight

Tab 2 — Factor Regression
  ├── Alpha / R² / N metric cards
  ├── Factor betas table (beta, t-stat, p-value, significance)
  ├── Beta bar chart
  └── Plain-English tilt summary

Tab 3 — Style Scorecard
  ├── 33×6 style score heatmap (RdYlGn)
  ├── Portfolio vs Nifty 500 baseline radar chart
  └── Sortable per-stock factor table

Tab 4 — Stock Deep-Dive
  ├── Position metrics (sector, weight, value)
  ├── Per-stock style profile table + interpretation
  ├── Single-stock radar chart
  ├── External links (Screener.in, Tickertape)
  └── india-equity-report skill invocation instructions

Tab 5 — Portfolio Profile
  ├── 6 executive summary metric cards
  ├── Auto-narrative paragraph
  ├── Expander: Factor Tilts memo table
  ├── Expander: Style Characteristics (radar + percentile table)
  ├── Expander: Risk Profile (HHI, Effective N, sector HHI, variance pie)
  ├── Rolling Factor Betas chart (12M/24M/36M selector)
  ├── Factor Return Attribution stacked bar chart
  ├── Style Percentile vs Nifty 500 bar chart
  └── Portfolio Weight Distribution (bar + cumulative line)
```

**Tab 5 dependency guard:** Tab 5 requires `reg_result` and `port_scores`, which are computed in Tabs 2 and 3 respectively. If price data is unavailable (empty `stock_returns_df`), Tab 2 shows a warning and skips regression — Tab 5 detects this and shows its own warning.

---

## 5. Caching Layer

The caching strategy has two tiers:

### Tier 1: Streamlit `@st.cache_data`

Memoises the result of a function call in Streamlit session memory. Cleared when the app restarts or when `force_refresh=True` is passed. Used for IIMA factors, fundamentals, and prices.

### Tier 2: Parquet file cache (`data/cache/`)

Persists to disk between Streamlit restarts. Parquet files are checked for staleness on every call to `fetch_*` functions. If the file exists and is less than 24 hours old, it is read from disk without hitting the network.

### Fallback: committed CSV snapshots

When both network and cache are unavailable, the app falls back to the committed CSVs:

| Snapshot file | Used by | Replaces |
|---|---|---|
| `data/screener_snapshot.csv` | `fetch_all_fundamentals` | Live Screener.in scraping |
| `data/price_returns_snapshot.csv` | `fetch_all_prices` | Live yfinance download |
| `data/nifty500_screener_snapshot.csv` | `compute_nifty500_percentile_scores` | Live Nifty 500 scraping |

This makes the app deployable to Streamlit Cloud without any network configuration.

### Refreshing snapshots manually

To update the committed snapshots with fresh data:

```bash
# From a Python shell or notebook:
from data.fetcher import fetch_all_fundamentals, fetch_all_prices
import json

with open("ticker_map.json") as f:
    ticker_map = json.load(f)
tickers = list(ticker_map.values())

# Refresh fundamentals snapshot
df = fetch_all_fundamentals(tickers, force_refresh=True)
df.to_csv("data/screener_snapshot.csv", index=False)

# Refresh price snapshot
prices = fetch_all_prices(tickers, years=6, force_refresh=True)
prices.to_csv("data/price_returns_snapshot.csv")
```

---

## 6. Test Suite

```
tests/
├── test_fetcher.py        13 tests — cache logic + IIMA and Screener parsing
├── test_scorer.py          9 tests — z-scoring, weighting, percentile ranking
├── test_regression.py     14 tests — OLS correctness, rolling betas, attribution
└── test_integration.py     4 tests — end-to-end with real portfolio.xlsx (2 live, 2 offline)
```

All tests run offline. The two skipped integration tests (`test_iima_factors_have_all_columns`, `test_iima_factors_sufficient_history`) require a live network call to IIMA and are marked with `pytest.mark.skip`.

### Key synthetic fixtures (in `test_regression.py`)

```python
# 60 months of synthetic factor data
FACTORS = pd.DataFrame({
    "date": [pd.Timestamp("2020-01-01") + pd.DateOffset(months=i) for i in range(60)],
    "mkt_rf": np.random.normal(0.01, 0.04, 60),
    "smb": np.random.normal(0.002, 0.02, 60),
    "hml": np.random.normal(0.002, 0.02, 60),
    "wml": np.random.normal(0.003, 0.025, 60),
    "rf": np.full(60, 0.005),
})

# Portfolio returns constructed with known beta (1.2 on mkt_rf) → regression should recover it
PORT_RETURNS = pd.Series(
    1.2 * FACTORS.set_index("date")["mkt_rf"] + np.random.normal(0, 0.01, 60),
    index=FACTORS.set_index("date").index,
)
```

The test `test_regression_recovers_market_beta_approximately` asserts that `|beta_mkt - 1.2| < 0.3`.

### Running specific test files

```bash
python3 -m pytest tests/test_regression.py -v           # regression only
python3 -m pytest tests/test_scorer.py -v               # scorer only
python3 -m pytest tests/ -k "not integration" -v        # skip integration
python3 -m pytest tests/ -v --tb=short                  # all, short tracebacks
```

---

## 7. Adding a New Factor Dimension

Example: add a **Dividend Yield** dimension to the style scorecard.

**Step 1: Add the data field to the Screener parser.**

In `data/fetcher.py`, extend `parse_screener_fundamentals` to extract dividend yield:

```python
elif "dividend yield" in name or "div yield" in name:
    result["div_yield"] = val
```

**Step 2: Update the snapshot.**

Refresh `data/screener_snapshot.csv` to include the new column (see section 5).

**Step 3: Compute the new dimension in `factors/scorer.py`.**

In `compute_style_scores`, add after the existing dimensions:

```python
# Dividend Yield: higher = more income tilt
if "div_yield" not in df.columns:
    df["div_yield"] = 0.0
else:
    df["div_yield"] = pd.to_numeric(df["div_yield"], errors="coerce").fillna(0.0)
df["dividend"] = _zscore(df["div_yield"])
```

Update the return statement to include `"dividend"`.

**Step 4: Add the dimension to all consumers.**

Search the codebase for the `dims` list:

```python
dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
```

Add `"dividend"` to every occurrence (found in `scorer.py` and `dashboard/app.py`).

**Step 5: Write a test.**

In `tests/test_scorer.py`:

```python
def test_higher_div_yield_gives_higher_dividend_score():
    df = MINIMAL_FUNDAMENTALS.copy()
    df["div_yield"] = [5.0, 4.0, 3.0, 2.0, 1.0]
    scores = compute_style_scores(df)
    assert scores.iloc[0]["dividend"] > scores.iloc[-1]["dividend"]
```

**Step 6: Run all tests to confirm nothing is broken.**

```bash
python3 -m pytest tests/ -v
```

---

## 8. Adding a New Data Source

Example: add **NSE bulk deals** as a flow signal.

**1. Add a fetcher function to `data/fetcher.py`:**

```python
NSE_BULKDEALS_CACHE = CACHE_DIR / "nse_bulk_deals.parquet"

def fetch_nse_bulk_deals(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and not is_stale(NSE_BULKDEALS_CACHE):
        return read_cache(NSE_BULKDEALS_CACHE)
    # ... download + parse ...
    write_cache(df, NSE_BULKDEALS_CACHE)
    return df
```

**2. Expose it in `dashboard/app.py` as a `@st.cache_data` call:**

```python
@st.cache_data(show_spinner="Fetching NSE bulk deals…")
def get_bulk_deals(force):
    return fetch_nse_bulk_deals(force_refresh=force)

bulk_deals = get_bulk_deals(force_refresh)
```

**3. Add a committed snapshot as the offline fallback.**

**4. Wire the new data into a tab or a new tab in `app.py`.**

---

## 9. Known Constraints

### Static weights in historical regression

`build_portfolio_returns` applies **current weights** to historical price data. If the portfolio was rebalanced significantly, the historical portfolio returns are a retrospective reconstruction, not actual returns. To fix this, a transaction history or periodic snapshot history is needed (see section 10).

### IIMA URL discovery is fragile

`_discover_iima_csv_url()` scrapes the IIMA page looking for a CSV link. If IIMA restructures their site, this will break. The fix is to hardcode the URL or maintain it in a config file once the URL pattern is stable.

### Screener.in rate limiting

`fetch_screener_fundamentals` sleeps 1.5 seconds between requests. With 33 stocks, a full refresh takes ~50 seconds. If Screener.in changes its HTML structure, `parse_screener_fundamentals` will need updating. The snapshot fallback mitigates this.

### yfinance reliability

yfinance is an unofficial API. Ticker symbol changes, exchange migrations, or Yahoo Finance outages can cause empty returns. The price snapshot fallback handles this.

### 33-stock z-score instability

Z-scores are computed over a 33-stock universe. A single extreme outlier (e.g., a stock with P/E = 200 while all others are 20–40) will compress all other z-scores toward zero. Consider winsorising inputs at the 5th/95th percentile for robustness:

```python
df["pe"] = df["pe"].clip(lower=df["pe"].quantile(0.05), upper=df["pe"].quantile(0.95))
```

---

## 10. Next Steps & Engineering Roadmap

### 10.1 Long-Short Portfolio Support

**What to change:**

1. **`portfolio.xlsx`:** Add a `Side` column (`Long` / `Short`).
2. **`data/portfolio.py` — `load_portfolio`:** Multiply weights by −1 for `Side == "Short"`.
3. **`factors/regression.py` — `build_portfolio_returns`:** No change needed — the weighted average works correctly with negative weights.
4. **`dashboard/app.py`:** Add a colour-coded column to the Holdings table (`Long` = green, `Short` = red). Show net exposure, gross exposure, and leverage ratio in Tab 1.
5. **New analytics:** Add a Tab 2 section that runs the regression separately on the long leg and the short leg to show how each contributes to the combined factor profile.

**New helper to write in `factors/regression.py`:**

```python
def split_portfolio_returns(
    stock_returns: pd.DataFrame,
    weights: dict[str, float],
) -> tuple[pd.Series, pd.Series]:
    """Return (long_leg_returns, short_leg_returns) separately."""
    long_w = {t: w for t, w in weights.items() if w > 0}
    short_w = {t: abs(w) for t, w in weights.items() if w < 0}
    return build_portfolio_returns(stock_returns, long_w), \
           build_portfolio_returns(stock_returns, short_w)
```

### 10.2 Portfolio Analysis Over Time

**Goal:** Show how factor exposures and style scores have evolved as the portfolio changed.

**Required input:** A folder of historical portfolio snapshots:

```
portfolio_history/
    portfolio_2024-01.xlsx
    portfolio_2024-04.xlsx
    portfolio_2024-07.xlsx
    portfolio_2024-10.xlsx
    portfolio_2025-01.xlsx
    ...
```

**New module: `data/history_loader.py`:**

```python
def load_portfolio_history(history_dir: str) -> dict[pd.Timestamp, pd.DataFrame]:
    """Load all portfolio snapshots from a directory. Returns {date: portfolio_df}."""
    ...
```

**New module: `factors/evolution.py`:**

```python
def compute_factor_evolution(
    portfolio_history: dict[pd.Timestamp, pd.DataFrame],
    factor_returns: pd.DataFrame,
    price_data: pd.DataFrame,
    window_years: int = 3,
) -> pd.DataFrame:
    """
    For each snapshot date, recompute portfolio returns using that snapshot's weights,
    run Carhart regression, return a DataFrame with one row per snapshot date and
    columns: alpha, beta_mkt, beta_smb, beta_hml, beta_wml, r_squared.
    """
    rows = []
    for snap_date, portfolio in sorted(portfolio_history.items()):
        weights = portfolio.set_index("ticker")["weight"].to_dict()
        port_ret = build_portfolio_returns(price_data, weights)
        # Restrict factor data to up to snap_date
        fac_up_to = factor_returns[factor_returns["date"] <= snap_date]
        result = run_carhart_regression(port_ret, fac_up_to, window_years)
        rows.append({"date": snap_date, **result["betas"], "alpha": result["alpha"],
                     "r_squared": result["r_squared"]})
    return pd.DataFrame(rows).set_index("date")
```

**New Tab 6 in `dashboard/app.py`:** "Evolution"

Charts:
- Line chart: `beta_mkt / beta_smb / beta_hml / beta_wml` over time
- Line chart: all 6 style z-scores over snapshot dates
- Bar chart: alpha evolution with confidence bands
- Heatmap: factor exposures × time (rows = factors, columns = dates, colour = beta value)

**Regime overlay:** Shade the chart background by bull/bear regime (Nifty 500 drawdown > 15% from peak = bear).

### 10.3 Active Share Tracking Over Time

Active share measures how different the portfolio is from its benchmark at the holdings level:

```
Active Share = 0.5 × Σ |w_portfolio,i - w_benchmark,i|
```

Values near 0 = index hugger; values near 100% = high-conviction active fund.

**Implementation:**
1. Add Nifty 500 constituent weights (downloadable from NSE as a CSV)
2. Compute active share for each historical snapshot
3. Plot active share evolution alongside factor exposure evolution in Tab 6

### 10.4 Factor Timing Scoring

Quantify whether factor tilts were additive to returns:

```python
def factor_timing_score(
    factor_exposure_ts: pd.DataFrame,    # output of compute_factor_evolution
    factor_returns: pd.DataFrame,
    lead_months: int = 1,
) -> pd.Series:
    """
    For each factor, compute the correlation between the portfolio's exposure to that factor
    at time t and the factor's realised return at time t+lead_months.
    A positive correlation = the manager increased exposure before the factor performed.
    """
    ...
```

### 10.5 Live Rebalancing Optimizer

Given a target factor profile (e.g., Quality z-score ≥ +0.5, Value z-score ≥ +0.3, market beta ≤ 0.95), solve for the weight vector that minimises tracking error to the current portfolio subject to those constraints.

**Libraries:** `cvxpy` (convex optimisation) or `scipy.optimize.minimize`.

**New module: `factors/optimizer.py`:**

```python
def solve_target_weights(
    style_scores: pd.DataFrame,         # from compute_style_scores on candidate universe
    current_weights: pd.Series,         # current portfolio weights
    target_style: dict[str, float],     # {"quality": 0.5, "value": 0.3}
    max_position: float = 0.08,         # max weight per stock
    min_position: float = 0.0,          # set > 0 to exclude stocks with tiny weights
) -> pd.Series:
    """Return a rebalanced weight vector that meets style targets."""
    ...
```

### 10.6 Deployment Considerations

The committed CSV snapshots make the app deployable to **Streamlit Cloud** without live network access. For a production deployment that refreshes data automatically:

- Add a GitHub Actions workflow that runs `python scripts/refresh_snapshots.py` nightly and commits updated CSV files
- Or deploy behind a VPN with outbound access to IIMA, Screener.in, and Yahoo Finance, and rely purely on the parquet cache
