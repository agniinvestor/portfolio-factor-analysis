# Portfolio Factor Analysis Dashboard — Design Spec

**Date:** 2026-04-11  
**Status:** Approved  
**Project:** `/home/ubuntu/claude_projects/portfolio_factor_analysis/`

---

## 1. Overview

A Streamlit dashboard that identifies the factor tilt of a given long-only Indian equity portfolio (`portfolio.xlsx`). The dashboard runs a 4-factor Fama-French regression (Market, SMB, HML, WML) using the IIMA Indian factor dataset and displays a per-stock style scorecard across 6 dimensions. It benchmarks the portfolio against the Nifty 500.

This is a **project**, not a new skill. It leverages the existing `india-equity-report` skill for data sourcing rules and single-stock deep-dives. The `india-equity-report` skill is installed globally at `~/.claude/skills/india-equity-report/`.

---

## 2. Input

- **`portfolio.xlsx`**: Single sheet named `Long`, 33 Indian large-cap equities.
  - Columns: `Name`, `ISIN`, `Sector`, `Weights` (formula), `Value` (INR)
  - Weights are computed as each holding's value divided by total portfolio value.

---

## 3. Architecture

### 3.1 File Structure

```
portfolio_factor_analysis/
├── portfolio.xlsx                        # Input (existing)
├── data/
│   ├── fetcher.py                        # All web fetches: IIMA CSVs, Screener.in, Tickertape, NSE
│   └── cache/                            # Parquet files, refreshed on demand
│       ├── portfolio_fundamentals.parquet
│       ├── iima_factors.parquet
│       └── stock_prices.parquet
├── factors/
│   ├── scorer.py                         # Per-stock style scores (6 dimensions)
│   └── regression.py                     # 4-factor OLS regression engine
├── dashboard/
│   └── app.py                            # Streamlit UI
├── docs/
│   └── superpowers/specs/
│       └── 2026-04-11-portfolio-factor-analysis-design.md
└── requirements.txt
```

### 3.2 Data Flow

```
portfolio.xlsx
    → fetcher.py
        ├── IIMA CSV downloads          → cache/iima_factors.parquet
        ├── Screener.in (per stock)     → cache/portfolio_fundamentals.parquet
        └── Tickertape (price history)  → cache/stock_prices.parquet
            → scorer.py    → per-stock style scorecard (DataFrame)
            → regression.py → 4-factor OLS output (betas, t-stats, alpha)
                → dashboard/app.py (Streamlit renders both)
```

---

## 4. Data Sources

All sources follow the rules in `india-equity-report/references/data-sources.md`. No sources outside that approved list are used.

### 4.1 Factor Return Series (Regression)

| Factor | Source | URL |
|---|---|---|
| Market (Rm-Rf) | IIMA Indian FF Dataset | `https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/` |
| Size (SMB) | IIMA Indian FF Dataset | Same — monthly CSV |
| Value (HML) | IIMA Indian FF Dataset | Same — monthly CSV |
| Momentum (WML) | IIMA Indian FF Dataset | Same — monthly CSV |

- Data spans Oct 1993–Dec 2025, monthly frequency, survivorship-bias adjusted.
- Downloaded as CSV, cached to `cache/iima_factors.parquet`.

### 4.2 Per-Stock Fundamentals (Style Scorecard)

| Metric | Source | Used for |
|---|---|---|
| P/B ratio | Screener.in | Value |
| P/E ratio | Screener.in | Value (secondary) |
| ROE (3yr avg) | Screener.in | Quality |
| ROCE | Screener.in | Quality |
| Debt/Equity | Screener.in | Quality (inverse) |
| CFO/PAT ratio | Screener.in (computed) | Quality (earnings integrity) |
| Revenue CAGR 3yr | Screener.in (computed) | Growth |
| Market Cap | Screener.in | Size |
| 12M-1M price return | Tickertape | Momentum |
| Net margin trend | Screener.in | Profitability |
| ROIC | Screener.in (computed) | Profitability |

URL pattern: `https://www.screener.in/company/[TICKER]/consolidated/`

### 4.3 Portfolio Return Series

- Monthly total returns computed from Tickertape price history per stock.
- Weighted by portfolio weights from `portfolio.xlsx`.
- Benchmark: Nifty 500 total return from NSE.

### 4.4 Caching

- All fetched data written to `data/cache/*.parquet` with a `fetched_at` timestamp.
- Cache is considered stale after 24 hours.
- "Refresh Data" button in Streamlit invalidates all cache and re-fetches.

---

## 5. Factor Model

### 5.1 Regression (4-Factor)

**Model:** Carhart 4-factor (Fama-French 3 + Momentum)

```
R_portfolio - R_f = α + β_mkt(Rm-Rf) + β_smb(SMB) + β_hml(HML) + β_wml(WML) + ε
```

- **Frequency:** Monthly
- **Window:** User-selectable — 1 year, 3 years, or 5 years (slider in dashboard)
- **Method:** OLS via `statsmodels`
- **Output:** α, β per factor, t-statistics, p-values, R²

Factor betas are interpreted as:
- `β_mkt > 1`: More volatile than market; `< 1`: defensive
- `β_smb > 0`: Small-cap tilt; `< 0`: large-cap tilt
- `β_hml > 0`: Value tilt; `< 0`: growth tilt
- `β_wml > 0`: Momentum tilt; `< 0`: contrarian tilt

### 5.2 Style Scorecard (6 Dimensions)

Each metric is z-scored against the Nifty 500 universe (fetched from Screener.in screener). Portfolio-level score = weighted average of individual stock z-scores.

| Dimension | Metrics | Direction |
|---|---|---|
| Value | P/B, P/E | Lower = better score |
| Quality | ROE, ROCE, CFO/PAT, D/E | Higher ROE/ROCE/CFO better; lower D/E better |
| Momentum | 12M-1M price return | Higher = better |
| Size | Log(Market Cap) | Lower = small-cap tilt |
| Growth | 3yr Revenue CAGR | Higher = better |
| Profitability | Net margin trend, ROIC | Higher = better |

---

## 6. Dashboard UI

**Technology:** Streamlit  
**Run command:** `streamlit run dashboard/app.py`

### Tab 1 — Portfolio Overview
- Holdings table: Name, Sector, Weight (%), Value (INR)
- Sector concentration bar chart — portfolio vs Nifty 500 benchmark weights
- Top 5 / Bottom 5 holdings by weight
- Last data refresh timestamp + "Refresh Data" button (top-right)

### Tab 2 — Factor Regression
- Time horizon slider: 1yr / 3yr / 5yr
- Factor exposure table: Beta, t-stat, significance flag per factor
- Horizontal bar chart of betas (green = positive tilt, red = negative)
- R² and regression summary stats
- Plain-English tilt summary auto-generated from betas and significance

### Tab 3 — Style Scorecard
- Per-stock heatmap: stocks × 6 style dimensions, z-scores colour-coded
- Portfolio-level radar/spider chart: weighted average z-score per dimension vs Nifty 500 baseline (zero)
- Sortable table: click any column to rank stocks by that factor

### Tab 4 — Stock Deep-Dive
- Dropdown: select any holding
- Full style profile: all 6 dimensions with raw values + z-scores
- Links to Screener.in and Tickertape pages
- "Generate Full Research Report" button — invokes `india-equity-report` skill for that stock

---

## 7. Skill Integration

### 7.1 `india-equity-report` — Global Install

The `india-equity-report` skill from `github.com/vishalmdi/india-equity-report-skill` is installed globally:

```bash
git clone https://github.com/vishalmdi/india-equity-report-skill.git /tmp/india-equity-report-skill
cp -r /tmp/india-equity-report-skill/india-equity-report ~/.claude/skills/
```

This makes it available in any Claude Code session, not just this project.

### 7.2 How This Project Uses the Skill

- **Data layer**: `data/fetcher.py` follows the approved source rules from `india-equity-report/references/data-sources.md` exactly — same Screener.in URL patterns, same Tickertape CMP method, same anti-hallucination rules.
- **Tab 4**: "Generate Full Research Report" hands off to the `india-equity-report` skill to produce a complete Buy/Sell/Hold report for the selected stock.
- No new skill is authored. This project is a consumer of the existing skill.

---

## 8. Dependencies

```
streamlit
pandas
numpy
openpyxl
statsmodels
plotly
requests
beautifulsoup4
pyarrow        # parquet support
```

---

## 9. Out of Scope

- Short positions (portfolio is long-only)
- Real-time streaming prices
- RMW / CMA factors (not in IIMA dataset; excluded from regression)
- Multi-portfolio comparison
- Authentication / user accounts
- Deployment to cloud (local run only for now)

---

## 10. Success Criteria

1. Dashboard launches with `streamlit run dashboard/app.py` with no errors.
2. Factor regression produces statistically interpretable betas for the portfolio.
3. Style scorecard heatmap renders for all 33 holdings.
4. "Refresh Data" button successfully re-fetches and updates cache.
5. Time horizon slider updates regression output in < 2 seconds (data already cached).
6. Tab 4 correctly links to Screener.in / Tickertape for each holding.
7. `india-equity-report` skill is accessible globally from any Claude Code session.
