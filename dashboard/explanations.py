# dashboard/explanations.py
"""Plain-English explanations for dashboard metrics and terms.

Used by app.py to populate st.metric(help=...) tooltips and
expander glossary blocks. No logic — only text.
"""

# ── Metric tooltips (used as help= in st.metric) ──────────────────────────────

TOOLTIPS = {
    "alpha": (
        "Return your portfolio earns above what the four market factors predict. "
        "Positive alpha = outperformance; negative alpha = underperformance. "
        "The t-stat below the value shows how statistically reliable it is."
    ),
    "r_squared": (
        "How much of the portfolio's return swings are explained by the four "
        "factors (0 to 1). R² = 0.85 means 85% of performance is driven by "
        "factor tilts; the remaining 15% comes from stock selection or other forces."
    ),
    "observations": (
        "Number of monthly data points used in the regression. "
        "More observations = more reliable factor estimates."
    ),
    "beta": (
        "Sensitivity of the portfolio to this factor. "
        "A beta of 1.2 means the portfolio moves 1.2× with that factor; "
        "0.8 means it moves only 0.8×; negative beta means it moves against the factor."
    ),
    "t_stat": (
        "How many standard errors the estimate is from zero. "
        "Values above ~2 or below ~−2 indicate the result is unlikely to be noise "
        "(statistically significant at the 5% level)."
    ),
    "p_value": (
        "Probability this result occurred by chance. "
        "Below 0.05 = statistically significant (less than 5% chance it's noise). "
        "Above 0.05 = we cannot confidently distinguish the tilt from random variation."
    ),
    "hhi": (
        "Herfindahl-Hirschman Index — a portfolio concentration score from 0 to 1. "
        "Below 0.10 = well diversified; 0.10–0.18 = moderate concentration; "
        "above 0.18 = concentrated. Calculated as sum of squared weights."
    ),
    "effective_n": (
        "The 'equivalent number of equal-weight stocks' implied by your actual weights. "
        "A 33-stock portfolio with Effective N of 12 is acting like 12 equally-weighted "
        "holdings — the other 21 positions are too small to matter much."
    ),
    "dominant_factor": (
        "The single factor with the largest statistically significant beta (p < 0.05). "
        "This is the primary driver of the portfolio's systematic return behaviour."
    ),
    "top_style_tilt": (
        "The style dimension with the strongest z-score vs the Nifty 500 universe. "
        "A z-score of +1.5 means the portfolio scores 1.5 standard deviations above "
        "the average Nifty 500 stock on this dimension."
    ),
    "sector_hhi": (
        "Same concentration measure as Portfolio HHI, but applied to sector weights "
        "instead of individual stock weights. Low values = broad sector diversification."
    ),
}

# ── Tab 2: Factor Regression glossary ─────────────────────────────────────────

TAB2_GLOSSARY = """
**What is the Carhart 4-Factor Model?**
A statistical model that explains portfolio returns using four systematic risk factors.
Instead of asking "did the manager pick good stocks?", it asks "which types of stocks
does this portfolio systematically overweight?" Any return *not* explained by these four
factors is alpha — potentially genuine skill (or luck).

---

**Market (Rm-Rf)**
The market excess return — how much the portfolio moves with the broad Indian equity market.
Beta = 1.0 means the portfolio tracks the market exactly.
Beta > 1.0 means it amplifies market moves (more volatile); Beta < 1.0 means it dampens them.

**Size (SMB — Small Minus Big)**
The return difference between small-cap and large-cap stocks.
Positive SMB beta = the portfolio behaves more like small/mid-cap stocks.
Negative SMB beta = large-cap bias (typical for a blue-chip portfolio).

**Value (HML — High Minus Low)**
The return difference between value stocks (high book-to-price) and growth stocks (low book-to-price).
Positive HML beta = value tilt (cheaper stocks by P/B ratio).
Negative HML beta = growth tilt (higher-valuation, typically faster-growing companies).

**Momentum (WML — Winners Minus Losers)**
The return difference between recent winners and recent losers (typically past 12 months).
Positive WML beta = the portfolio overweights recent outperformers.
Negative WML beta = contrarian tilt — the portfolio tends to hold recent underperformers.

---

**Alpha** — Excess return unexplained by the factors. Monthly, so multiply by 12 for a rough annual figure.

**R²** — Fraction of return variance explained by the model (0–1). Higher = factor-driven portfolio.

**Beta** — Slope coefficient for each factor. Shows direction and magnitude of tilt.

**t-stat** — How many standard errors the estimate is from zero. |t| > 2 ≈ statistically significant.

**p-value** — Probability of seeing this result by chance. p < 0.05 is the conventional significance threshold.
"""

# ── Tab 3: Style Scorecard glossary ───────────────────────────────────────────

TAB3_GLOSSARY = """
**What is a z-score?**
A z-score measures how far a stock (or portfolio) sits from the average of the Nifty 500
universe, in units of standard deviation. Z = +1.5 means 1.5 standard deviations *above*
average; Z = −1.0 means 1.0 standard deviations *below* average. The heatmap colours this:
green = positive tilt, red = negative tilt, white/yellow = near-average.

---

**Value** — Cheapness relative to fundamentals. Derived from P/E and P/B ratios.
High score = the stock is cheap vs peers; low score = it trades at a premium.

**Quality** — Financial health and returns on capital. Derived from ROE and ROCE.
High score = consistently high returns on equity/capital; low score = mediocre capital efficiency.

**Momentum** — Recent price performance (12-month return, skipping last month).
High score = recent outperformer; low score = recent underperformer.

**Size** — Market capitalisation relative to universe. High score = larger company.
Negative size score = smaller-cap tilt; positive = large-cap bias.

**Growth** — Revenue and earnings expansion. Derived from revenue CAGR and net margin trends.
High score = faster-growing company; low score = slower or declining growth.

**Profitability** — Absolute margin level. Derived from net margin.
High score = high-margin business; low score = thin margins.
"""

# ── Tab 5: Portfolio Profile glossary ─────────────────────────────────────────

TAB5_GLOSSARY = """
**Alpha (monthly)** — Excess return above what the four factors predict. Positive = outperformance.
Multiply by 12 for a rough annual equivalent. The t-stat indicates reliability.

**R²** — Share of portfolio return variance explained by the Carhart factors (0–1).
High R² means factor tilts dominate performance; low R² means stock selection matters more.

**HHI (Herfindahl-Hirschman Index)** — Concentration score = sum of squared portfolio weights.
Below 0.10 = diversified; 0.10–0.18 = moderate concentration; above 0.18 = concentrated.

**Effective N** — Equivalent number of equal-weight holdings.
Formula: 1 ÷ HHI. A 33-stock portfolio with Effective N of 12 means the bottom 21 stocks
contribute little to risk or return.

**Factor R² Breakdown** — The pie chart decomposes portfolio variance into contributions from
each factor (β² × factor variance) plus unexplained residual. Larger slices = that factor
drives more of the portfolio's volatility.

**Rolling Factor Betas** — Betas recalculated using a rolling window (12/24/36 months).
Stable lines = consistent style; rising/falling lines = the portfolio's tilt is drifting over time.
This matters for clients monitoring style consistency.
"""
