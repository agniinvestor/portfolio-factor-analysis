# Portfolio Factor Analysis Dashboard

A Streamlit dashboard for analysing an Indian large-cap equity portfolio using the Carhart 4-Factor model, style scoring, and live macro regime signals across four global regions.

**Live app:** https://portfolio-factor-analysis-agni.streamlit.app/

---

## What it does

| Tab | Description |
|-----|-------------|
| **Macro Regime** | Live regime classification (Goldilocks / Stagflation / etc.) for US, India, Japan, Europe — with factor recommendations for each regime |
| **Portfolio Summary** | Executive summary with alpha, R², factor tilts, concentration metrics, and auto-generated portfolio narrative |
| **Holdings** | Full holdings table, sector concentration chart, top/bottom 5 by weight |
| **Factor Analysis** | Carhart 4-factor regression — factor betas, t-stats, p-values, beta bar chart |
| **Style Scorecard** | Per-stock z-score heatmap across 6 style dimensions vs Nifty 500 universe |
| **Stock Deep-Dive** | Individual stock style profile, radar chart, and links to Screener.in / Tickertape |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/agniinvestor/portfolio-factor-analysis.git
cd portfolio-factor-analysis
pip install -r requirements.txt
```

### 2. Add your portfolio

Edit `portfolio.xlsx` with your holdings. Required columns:

| Column | Description | Example |
|--------|-------------|---------|
| `ticker` | NSE ticker symbol | `RELIANCE` |
| `name` | Company display name | `Reliance Industries` |
| `sector` | Sector label | `Energy` |
| `weight` | Portfolio weight (decimal) | `0.08` |
| `value` | Position value in INR | `800000` |

### 3. Configure FRED API key

The Macro Regime tab uses [FRED](https://fred.stlouisfed.org/) for rates and inflation data.

1. Get a free API key at https://fred.stlouisfed.org/docs/api/api_key.html
2. Copy the example secrets file:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

3. Edit `.streamlit/secrets.toml` and replace `YOUR_FRED_API_KEY_HERE` with your key.

> `.streamlit/secrets.toml` is gitignored — your key will not be committed.

### 4. Run locally

```bash
streamlit run dashboard/app.py
```

---

## Deploying to Streamlit Cloud

1. Fork this repository to your GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set the main file path to `dashboard/app.py`
4. Add your FRED API key in **Settings → Secrets**:

```toml
[fred]
api_key = "your_key_here"
```

---

## Data sources

| Data | Source | Notes |
|------|--------|-------|
| Factor returns (Mkt-Rf, SMB, HML, WML) | [IIMA Indian Fama-French-Momentum](https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/) | Survivorship-bias adjusted, monthly |
| Stock prices | [yfinance](https://github.com/ranaroussi/yfinance) (NSE via Yahoo Finance) | Monthly |
| Stock fundamentals (P/E, P/B, ROE, etc.) | [Screener.in](https://www.screener.in/) | Scraped; subject to rate limits |
| US rates | yfinance `^TNX` (10Y Treasury yield) | Daily, converted to monthly |
| India / Japan / Europe rates | FRED (`INDIRLTLT01STM`, `IRLTLT01JPM156N`, `IRLTLT01DEM156N`) | Monthly |
| US / Europe inflation | FRED CPI indices | Monthly |
| India / Japan inflation | FRED OECD YoY series | Monthly |

A fallback snapshot (`data/iima_factors_snapshot.csv`) is included for when the IIMA site is temporarily unreachable.

---

## Running tests

```bash
pytest tests/ -q
```

100 tests covering factor regression, style scoring, macro signal logic, and data fetching.

---

## ⚠️ Disclaimers

**This tool is for informational and educational purposes only.**

- **Not financial advice.** Nothing in this dashboard constitutes investment advice, a recommendation to buy or sell any security, or an offer to provide investment advisory services. Always consult a qualified financial adviser before making investment decisions.

- **Past performance.** All factor analysis, alpha estimates, and historical returns shown are based on historical data. Past performance is not indicative of future results. Factor premiums may not persist.

- **Data accuracy.** Data is sourced from third-party providers (IIMA, FRED, Yahoo Finance, Screener.in). While reasonable efforts are made to ensure accuracy, no warranty is given as to the completeness, timeliness, or fitness for purpose of any data displayed. Always verify critical figures independently.

- **Macro regime signals.** Regime classifications are rule-based approximations derived from publicly available data. They are simplified models, not professional economic forecasts, and should not be the sole basis for asset allocation decisions.

- **Factor model limitations.** The Carhart 4-factor model explains systematic return patterns but does not capture all risks. Alpha estimates are subject to estimation error, particularly over short windows. Statistical significance (p < 0.05) does not guarantee economic significance.

- **No liability.** The authors accept no liability for investment losses or decisions made using this tool.

---

## Acknowledgements

- Factor data: [IIMA Centre for Financial Research](https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/) — Sobhesh Kumar Agarwalla, Joshy Jacob, Jayanth R. Varma, and Ellapulli Vasudevan
- Macro data: [Federal Reserve Bank of St. Louis (FRED)](https://fred.stlouisfed.org/)
- Built with [Streamlit](https://streamlit.io/), [Plotly](https://plotly.com/), and [yfinance](https://github.com/ranaroussi/yfinance)
