# Portfolio Factor Analysis — Analytical Methodology

> **Audience:** Portfolio managers, analysts, and investors who want to understand *how* this dashboard analyses a portfolio — without needing to read the source code.

---

## Table of Contents

1. [Overview & Purpose](#1-overview--purpose)
2. [Data Sources](#2-data-sources)
3. [Portfolio Construction](#3-portfolio-construction)
4. [Carhart 4-Factor Regression](#4-carhart-4-factor-regression)
5. [Style Scorecard](#5-style-scorecard)
6. [Nifty 500 Percentile Ranking](#6-nifty-500-percentile-ranking)
7. [Rolling Beta Analysis](#7-rolling-beta-analysis)
8. [Factor Return Attribution](#8-factor-return-attribution)
9. [Portfolio Profile & Concentration Metrics](#9-portfolio-profile--concentration-metrics)
10. [Limitations & Caveats](#10-limitations--caveats)
11. [Next Steps & Expansion](#11-next-steps--expansion)

---

## 1. Overview & Purpose

This dashboard answers a single core question: **what bets is this portfolio actually taking?**

A portfolio of 33 Indian large-cap stocks may look diversified by name or sector, but underneath it can carry concentrated factor exposures — leaning into value stocks, avoiding momentum, tilting toward large caps — that drive risk and return in ways that sector labels do not capture.

The analysis uses two complementary lenses:

| Lens | Method | What it reveals |
|---|---|---|
| **Statistical** | Carhart 4-factor OLS regression on monthly returns | Time-series factor exposures (betas), alpha, explained variance |
| **Fundamental** | 6-dimension style scorecard from financial ratios | Cross-sectional positioning of each stock vs peers |

The two lenses are independent and often confirm each other. When they diverge, that divergence is itself informative — for example, a portfolio with a statistically insignificant HML (value) beta but a strong fundamental value z-score may be holding cheap stocks whose prices haven't yet re-rated.

---

## 2. Data Sources

### 2.1 IIMA Indian Fama-French-Momentum Dataset

**Source:** Indian Institute of Management Ahmedabad (IIMA) — [https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/](https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/)

This is the **primary factor dataset** for all regression analysis.

| Property | Detail |
|---|---|
| Coverage | October 1993 — present (monthly updates) |
| Survivorship bias | Adjusted — delisted firms are included in historical data |
| Factors | Market (MF/Rm-Rf), SMB, HML, WML, Risk-Free rate (RF) |
| Units | Percentage points (converted to decimals on ingestion) |
| Universe | All BSE-listed stocks |

The dataset is constructed following the methodology of Fama & French (1993) and Carhart (1997), adapted for Indian markets by IIMA researchers. Survivorship-bias adjustment is critical: without it, factor premiums are overstated because failing companies are retrospectively excluded.

The dashboard discovers the download URL dynamically by scraping the IIMA page, preferring the survivorship-bias-adjusted monthly four-factor file.

### 2.2 Screener.in — Fundamental Ratios

**Source:** [https://www.screener.in](https://www.screener.in)

Scraped for each portfolio holding to provide:

| Field | Use |
|---|---|
| P/E (Price-to-Earnings) | Value dimension |
| P/B (Price-to-Book) | Value dimension |
| ROE (Return on Equity) | Quality dimension |
| ROCE (Return on Capital Employed) | Quality dimension |
| D/E (Debt-to-Equity) | Quality dimension |
| Market Cap (₹ Cr) | Size dimension |
| Revenue CAGR 3Y | Growth dimension |
| Net Margin | Profitability dimension |

The consolidated balance sheet view is used (not standalone), which is standard for holding companies and conglomerates.

A **committed snapshot** (`data/screener_snapshot.csv`) is included in the repository as a fallback when Screener.in is unreachable (rate-limiting, network issues). The snapshot is refreshed manually before major analysis runs.

### 2.3 Price History — yfinance (NSE)

**Source:** Yahoo Finance via the `yfinance` Python library, using `.NS` suffix for NSE-listed tickers.

- **Interval:** Monthly closing prices
- **History:** 6 years (to support 5-year regression windows with buffer)
- **Adjustment:** Auto-adjusted for splits and dividends

Monthly returns are computed as simple percentage changes: `r_t = (P_t / P_{t-1}) - 1`.

A **committed price snapshot** (`data/price_returns_snapshot.csv`) serves as the offline fallback.

### 2.4 Nifty 500 Universe — Screener.in Snapshot

A snapshot of fundamentals for all ~500 Nifty 500 constituents (`data/nifty500_screener_snapshot.csv`) is used exclusively for percentile ranking. This provides a meaningful benchmark universe — broad enough to cover large, mid, and small caps, but excluding micro-caps and illiquid stocks.

---

## 3. Portfolio Construction

### 3.1 Input

The portfolio is loaded from `portfolio.xlsx`, sheet `Long`, with columns:

| Column | Description |
|---|---|
| Name | Company name |
| ISIN | 12-character ISIN (International Securities Identification Number) |
| Sector | Sector classification |
| Weight formula | Original weight (may be a formula cell — not used directly) |
| Value | Current market value in INR |

### 3.2 Weight Computation

Weights are computed from **current market value**, not from any formula column:

```
w_i = Value_i / Σ Value_j
```

This ensures weights sum to exactly 1.0 and reflect the current portfolio composition, not any target or historical allocation.

### 3.3 ISIN → NSE Ticker Mapping

Each ISIN is mapped to its NSE ticker via `ticker_map.json`. This mapping was constructed manually for all 33 holdings and is static — it must be updated if the portfolio changes. The NSE ticker is required for both the price feed (yfinance) and the Screener.in URL.

---

## 4. Carhart 4-Factor Regression

### 4.1 The Model

The Carhart (1997) 4-factor model extends the Fama-French 3-factor model (1993) with a momentum factor:

```
R_p,t - R_f,t = α + β_mkt(R_m,t - R_f,t) + β_smb · SMB_t + β_hml · HML_t + β_wml · WML_t + ε_t
```

Where:
- `R_p,t` = portfolio return in month t
- `R_f,t` = risk-free rate in month t (from IIMA dataset)
- `α` (alpha) = excess return not explained by the four factors
- `β_mkt` = market beta — sensitivity to the market premium
- `β_smb` = Small-Minus-Big — exposure to the size premium
- `β_hml` = High-Minus-Low — exposure to the value premium
- `β_wml` = Winners-Minus-Losers — exposure to the momentum premium
- `ε_t` = residual (idiosyncratic return)

### 4.2 What Each Factor Measures

**Market (Rm-Rf):** The excess return of the broad market over the risk-free rate. A beta > 1 means the portfolio amplifies market moves (aggressive); beta < 1 means it dampens them (defensive).

**SMB (Small-Minus-Big):** Return of a portfolio of small-cap stocks minus large-cap stocks. A positive SMB beta means the portfolio behaves like small caps — higher expected return but higher volatility. A negative SMB beta confirms a large-cap bias.

**HML (High-Minus-Low book-to-market):** Return of high book-to-market (value) stocks minus low book-to-market (growth) stocks. A positive HML beta signals a value tilt; negative signals a growth tilt.

**WML (Winners-Minus-Losers):** Return of recent-12-month winners minus recent losers. A positive WML beta means the portfolio holds recent outperformers (momentum tilt); negative means it holds recent underperformers (contrarian tilt).

### 4.3 Portfolio Return Construction

The portfolio monthly return is a **value-weighted average** of individual stock monthly returns:

```
R_p,t = Σ w_i · r_i,t
```

Weights are renormalised to sum to 1 using only the tickers for which price data is available.

### 4.4 Regression Procedure

The regression is run via **Ordinary Least Squares (OLS)** using the `statsmodels` library:

1. Align portfolio returns and factor returns on their common date range
2. Compute portfolio excess return: `r_excess = R_p - R_f`
3. Apply the user-selected trailing window (1, 3, or 5 years from the most recent common date)
4. Add a constant (intercept = alpha) to the factor matrix
5. Fit OLS; extract coefficients, t-statistics, p-values, R²

**Regression window:** The user selects 1Y, 3Y, or 5Y. Shorter windows are more responsive to recent regime changes; longer windows are more statistically stable (more observations). At monthly frequency, 3Y ≈ 36 observations and 5Y ≈ 60 observations.

### 4.5 Interpreting Results

| Output | Interpretation |
|---|---|
| Alpha (α) | Monthly excess return after controlling for factor exposures. Positive and significant alpha suggests genuine stock-selection skill. |
| Beta significance (p < 0.05) | A factor beta is only reported as a meaningful tilt if statistically significant at the 5% level. |
| R² | Fraction of portfolio return variance explained by the four factors. High R² (>0.90) means factor exposures drive most of the return. Low R² leaves more room for idiosyncratic risk. |
| t-statistic | Number of standard errors the estimate is from zero. |t| > 2 ≈ p < 0.05 for typical sample sizes. |

---

## 5. Style Scorecard

The style scorecard is a **cross-sectional, fundamentals-based** factor profile — independent of price history. It answers: *relative to its peers, where does each stock sit on six investment style dimensions?*

### 5.1 The Six Dimensions

| Dimension | Inputs | Formula | Direction |
|---|---|---|---|
| **Value** | P/E, P/B | z(-P/E)×0.5 + z(-P/B)×0.5 | Higher = cheaper vs peers |
| **Quality** | ROE, ROCE, D/E | z(ROE)×0.4 + z(ROCE)×0.4 + z(-D/E)×0.2 | Higher = more profitable, less leveraged |
| **Momentum** | 12M-1M return | z(momentum_12m_1m) | Higher = stronger recent price performance |
| **Size** | Market Cap (₹ Cr) | z(-log(Market Cap)) | Higher = smaller cap relative to peers |
| **Growth** | Revenue CAGR 3Y | z(Revenue CAGR 3Y) | Higher = faster revenue growth |
| **Profitability** | Net Margin | z(Net Margin) | Higher = more profitable |

### 5.2 Z-Scoring

Each raw metric is cross-sectionally z-scored across the 33-stock portfolio universe:

```
z_i = (x_i - μ) / σ
```

Where μ and σ are the mean and standard deviation across all stocks in the portfolio. A z-score of +1.0 means the stock is 1 standard deviation above the portfolio average on that dimension; −1.0 means 1 standard deviation below.

**Important:** The z-scores are computed relative to the 33 stocks in the portfolio, not relative to the Nifty 500 universe. A stock can have a high value z-score within this portfolio but still be expensive relative to the broader market.

### 5.3 Composite Scores

Where a dimension uses multiple inputs (Value, Quality), the sub-components are combined with fixed weights before z-scoring. For example, Quality = 40% ROE + 40% ROCE + 20% leverage. These weights reflect standard academic practice for quality factor construction.

### 5.4 Momentum Calculation

The momentum signal uses the **12M-1M** convention from academic factor literature: the cumulative return over the 12 months ending one month ago (skipping the most recent month to avoid short-term reversal):

```
momentum_12m_1m = (1 + r_{t-12}) × (1 + r_{t-11}) × ... × (1 + r_{t-2}) × (1 + r_{t-1}) − 1
```

### 5.5 Portfolio-Level Style Score

The portfolio style score is the **weight-averaged z-score** across all holdings:

```
Portfolio_score_d = Σ w_i × z_i,d
```

This gives the net factor tilt of the portfolio weighted by position size.

---

## 6. Nifty 500 Percentile Ranking

The percentile ranking answers: **where does this portfolio's style score sit relative to the full Nifty 500 universe?**

### Procedure

1. Load the Nifty 500 fundamentals snapshot (~500 stocks)
2. Run the same style scoring algorithm on the Nifty 500 universe
3. For each dimension, rank the portfolio score against the distribution of Nifty 500 stock scores:

```
Percentile_d = P(Nifty500_score_d < Portfolio_score_d) × 100
```

A percentile of 75 on Quality means the portfolio's quality score exceeds 75% of individual Nifty 500 stocks.

### Interpretation

| Percentile | Meaning |
|---|---|
| > 75 | Strong tilt in this direction vs Nifty 500 |
| 40–60 | Broadly in line with the index |
| < 25 | Tilt against this factor vs Nifty 500 |

This benchmark is more informative than the within-portfolio z-score for understanding the portfolio's absolute positioning, because the 33 stocks in the portfolio could all be expensive relative to the market even if their within-portfolio value z-scores are distributed around zero.

---

## 7. Rolling Beta Analysis

Rolling betas show how the portfolio's factor exposures have **changed over time**, using a rolling OLS window.

### Method

At each month t, the Carhart model is re-estimated using the prior `W` months of data (where W = 12, 24, or 36 months as selected). This produces a time series of betas — one set per month — showing how exposures evolved.

### What Rolling Betas Reveal

- **Regime shifts:** Did the portfolio's market beta increase before a drawdown?
- **Style drift:** Has the value/growth tilt changed as holdings were rebalanced?
- **Stability:** Betas that fluctuate wildly suggest unstable or noisy exposures; stable betas indicate persistent factor positioning.

### Window Choice

| Window | Observations | Best for |
|---|---|---|
| 12M | 12 | Detecting recent regime shifts quickly |
| 24M | 24 | Balance between responsiveness and stability (default) |
| 36M | 36 | Stable, long-term structural exposures |

---

## 8. Factor Return Attribution

Factor return attribution **decomposes each month's portfolio excess return** into the contribution from each of the four factors, alpha, and the unexplained residual.

### Decomposition Identity

For each month t:

```
r_excess,t = α + β_mkt × (Rm-Rf)_t + β_smb × SMB_t + β_hml × HML_t + β_wml × WML_t + ε_t
```

This is an identity — the components sum exactly to the portfolio excess return. Each term represents:

| Component | Calculation | Meaning |
|---|---|---|
| **Alpha contribution** | α (constant) | Same each month — the structural excess return from stock selection |
| **Market contribution** | β_mkt × MktRf_t | How much the portfolio gained/lost from market moves |
| **SMB contribution** | β_smb × SMB_t | Gain/loss from size factor realisation |
| **HML contribution** | β_hml × HML_t | Gain/loss from value factor realisation |
| **WML contribution** | β_wml × WML_t | Gain/loss from momentum factor realisation |
| **Residual** | ε_t | Return not explained by the four factors |

### Reading the Attribution Chart

The stacked bar chart shows the monthly contribution of each component. In months where the market fell sharply, the market contribution bar will be a large negative. If the portfolio had a positive HML beta and value stocks outperformed, the HML bar will be positive. The sum of all bars equals the portfolio excess return for that month.

---

## 9. Portfolio Profile & Concentration Metrics

### Herfindahl-Hirschman Index (HHI)

HHI measures **portfolio concentration** at the stock level:

```
HHI = Σ w_i²
```

A portfolio where all 33 stocks are equally weighted gives HHI = 1/33 ≈ 0.03. A portfolio concentrated in one stock gives HHI ≈ 1.

| HHI | Interpretation |
|---|---|
| < 0.10 | Well diversified |
| 0.10 – 0.18 | Moderate concentration |
| > 0.18 | Concentrated |

### Effective N

Effective N is the implied number of equal-weight positions that would produce the same HHI:

```
Effective_N = 1 / HHI
```

If Effective N = 12 in a 33-stock portfolio, it means 21 positions are too small to materially affect portfolio outcomes — the risk is concentrated in the top 12.

### Sector HHI

The same HHI formula applied to sector-level weights. A high sector HHI indicates sector concentration risk even if the stock-level HHI looks reasonable.

### Variance Decomposition (Factor R² Breakdown)

The pie chart approximates each factor's contribution to **total portfolio return variance**:

```
Variance_share_f ≈ (β_f × σ_f)² / Var(r_excess)
```

This is an approximation — it assumes factor returns are uncorrelated. The residual share = 1 − R².

---

## 10. Limitations & Caveats

### What this analysis cannot tell you

**1. Factor premiums are not guaranteed.**
The Fama-French-Carhart factors represent empirical regularities that have held historically in Indian markets. They may not persist, can experience prolonged drawdowns, and can be crowded out.

**2. The regression uses historical data only.**
Betas estimated from past returns describe past behaviour. The portfolio may have changed its character if holdings or weights have shifted significantly.

**3. Style scores are point-in-time.**
Fundamentals from Screener.in are the most recently published figures. They do not capture intra-year changes or forward-looking estimates.

**4. Weights are fixed at the current snapshot.**
The regression uses current weights applied to historical prices. A more rigorous analysis would use time-varying historical weights (requires a transaction history feed).

**5. RMW and CMA are excluded.**
The IIMA dataset does not provide Profitability (RMW) and Investment (CMA) factors from the Fama-French 5-factor model. Profitability and investment tilts are covered only through the style scorecard, not through the regression.

**6. 33 stocks is a small universe for z-scoring.**
Within-portfolio z-scores can be dominated by outliers. The Nifty 500 percentile ranking provides a more meaningful absolute benchmark.

**7. The price data has a one-month lag.**
yfinance monthly bars are end-of-month. Momentum calculations and factor alignment assume this.

---

## 11. Next Steps & Expansion

### 11.1 Long-Short Portfolio Analysis

The current analysis is **long-only**: all 33 stocks carry positive weights. A natural extension is to support **long-short portfolios**, which are the native habitat of factor investing.

**What changes analytically:**

In a long-short portfolio, some stocks carry negative weights. The portfolio excess return is still a weighted sum of individual stock excess returns — but negative-weight stocks *subtract* from factor exposures:

```
R_p,t = Σ w_i × r_i,t   (where some w_i < 0)
```

This allows **factor neutralisation**: a manager can go long value stocks and short growth stocks to isolate the HML premium, eliminating market beta in the process. The regression framework works identically — the OLS model is agnostic to the sign of weights.

**Enhancements to add:**

- **Long book / Short book split:** Run the Carhart regression separately on the long leg and the short leg, then on the combined portfolio. Compare the factor loading of each leg.
- **Net and gross exposure:** Report net exposure (Σ long weights + Σ short weights), gross exposure (Σ|w_i|), and leverage ratio (gross / net).
- **Factor isolation score:** How much of the target factor premium is captured per unit of residual risk? Analogous to the information ratio but factor-specific.
- **Input:** Extend `portfolio.xlsx` to include a `Side` column (`Long` / `Short`) and modify `load_portfolio` to assign negative weights to short positions.

### 11.2 Portfolio Analysis Over Time — Historical Evolution

The current dashboard shows the portfolio as it stands today with today's weights applied retroactively. A richer analysis tracks how the **portfolio itself has evolved** — holdings added/removed, weights drifted, factor exposures changed.

**What this requires:**

A **transaction history** or **periodic snapshot history** — a time-series of portfolio compositions, not just the current one. For example:
- A folder of monthly `portfolio_YYYY-MM.xlsx` snapshots, or
- A transaction log: date, stock, quantity, buy/sell

**Analytical enhancements:**

| Analysis | Description |
|---|---|
| **Factor exposure time series** | Run the Carhart regression on each monthly snapshot; plot how β_mkt, β_smb, β_hml, β_wml evolved as the portfolio changed. |
| **Style drift chart** | Plot portfolio-level z-scores for all 6 dimensions month-by-month. Did the value tilt increase as the manager added cheap stocks in 2022? |
| **Alpha evolution** | Plot rolling alpha with confidence bands — is alpha stable or does it vary with market regime? |
| **Active share over time** | Track how far the portfolio has deviated from the Nifty 500 benchmark as positions changed. |
| **Factor timing analysis** | Did the manager increase the value tilt before value outperformed? Regress factor exposure changes on subsequent factor returns. |
| **Attribution by period** | Break down total return by year or by market regime (bull/bear), showing how much came from each factor in each period. |

**Regime analysis:**

Define market regimes (e.g., using Nifty 500 drawdown > 15% = bear; recovery = transition; Nifty 500 at all-time highs = bull) and show:
- Which factor exposures provided protection in bear markets?
- Which factor exposures drove outperformance in bull markets?
- How has the manager's factor positioning changed across regimes?

### 11.3 Multi-Portfolio Comparison

When managing multiple mandates (e.g., a large-cap fund, a value fund, a multi-cap fund), comparing their factor profiles side-by-side reveals overlap, diversification, and unintended concentration. A comparison tab could accept multiple `portfolio.xlsx` files and render all factor profiles on the same radar chart.

### 11.4 Factor Timing & Macro Integration

Factor premiums are cyclical. Value outperforms in early recovery; momentum outperforms in trending markets; defensive low-beta outperforms in recessions. Overlaying macroeconomic indicators (RBI rate cycle, PMI, credit spreads) on the factor return attribution chart would show whether the portfolio's factor tilts are aligned with the prevailing macro regime.

### 11.5 Live Rebalancing Recommendations

Given a target factor profile (e.g., "I want a Quality tilt of z = +0.5 and Value tilt of z = +0.3"), the system could solve for the weight vector that minimises tracking error to that target while staying within position limit constraints — a quadratic programming problem. This transforms the dashboard from descriptive to prescriptive.
