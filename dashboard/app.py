import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from data.portfolio import load_portfolio
from data.fetcher import fetch_iima_factors, fetch_all_fundamentals, fetch_tickertape_prices, compute_monthly_returns
from data.cache_manager import is_stale, CACHE_DIR
from factors.scorer import compute_style_scores, compute_portfolio_scores
from factors.regression import build_portfolio_returns, run_carhart_regression

PORTFOLIO_PATH = Path(__file__).parent.parent / "portfolio.xlsx"

st.set_page_config(page_title="Portfolio Factor Analysis", layout="wide")
st.title("Portfolio Factor Analysis Dashboard")

# ── Sidebar: Refresh ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Data")
    force_refresh = st.button("Refresh Data")
    iima_cache = CACHE_DIR / "iima_factors.parquet"
    if iima_cache.exists():
        import time as _time
        mtime = iima_cache.stat().st_mtime
        st.caption(f"Last updated: {pd.Timestamp(mtime, unit='s').strftime('%Y-%m-%d %H:%M')}")
    else:
        st.caption("No cache yet — click Refresh Data")
    window_years = st.select_slider(
        "Regression window",
        options=[1, 3, 5],
        value=3,
        help="Years of history used for the Carhart 4-factor regression"
    )

# ── Load portfolio ────────────────────────────────────────────────────────────
portfolio = load_portfolio(str(PORTFOLIO_PATH))

# ── Fetch data ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Fetching IIMA factors…")
def get_iima(force):
    return fetch_iima_factors(force_refresh=force)

@st.cache_data(show_spinner="Fetching stock fundamentals from Screener.in…")
def get_fundamentals(tickers_tuple, force):
    return fetch_all_fundamentals(list(tickers_tuple), force_refresh=force)

iima_factors = get_iima(force_refresh)
fundamentals = get_fundamentals(tuple(portfolio["ticker"].tolist()), force_refresh)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Portfolio Overview",
    "Factor Regression",
    "Style Scorecard",
    "Stock Deep-Dive",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Portfolio Overview
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Holdings")

    display_df = portfolio[["name", "sector", "weight", "value"]].copy()
    display_df["weight_pct"] = (display_df["weight"] * 100).round(2)
    display_df["value_inr"] = display_df["value"].apply(lambda x: f"₹{x:,.0f}")
    st.dataframe(
        display_df[["name", "sector", "weight_pct", "value_inr"]].rename(columns={
            "name": "Stock", "sector": "Sector",
            "weight_pct": "Weight (%)", "value_inr": "Value (INR)"
        }),
        use_container_width=True, hide_index=True
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sector Concentration")
        sector_weights = portfolio.groupby("sector")["weight"].sum().reset_index()
        sector_weights = sector_weights.sort_values("weight", ascending=True)
        fig = px.bar(
            sector_weights, x="weight", y="sector", orientation="h",
            labels={"weight": "Portfolio Weight", "sector": ""},
            color="weight", color_continuous_scale="Blues",
        )
        fig.update_layout(coloraxis_showscale=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 5 / Bottom 5 by Weight")
        top5 = portfolio.nlargest(5, "weight")[["name", "weight"]].copy()
        bot5 = portfolio.nsmallest(5, "weight")[["name", "weight"]].copy()
        top5["weight_pct"] = (top5["weight"] * 100).round(2)
        bot5["weight_pct"] = (bot5["weight"] * 100).round(2)
        st.markdown("**Top 5**")
        st.dataframe(top5[["name", "weight_pct"]].rename(
            columns={"name": "Stock", "weight_pct": "Weight (%)"}),
            hide_index=True, use_container_width=True)
        st.markdown("**Bottom 5**")
        st.dataframe(bot5[["name", "weight_pct"]].rename(
            columns={"name": "Stock", "weight_pct": "Weight (%)"}),
            hide_index=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — placeholder (will be filled in Task 12)
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.info("Factor Regression tab — coming soon.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — placeholder (will be filled in Task 13)
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.info("Style Scorecard tab — coming soon.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — placeholder (will be filled in Task 14)
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.info("Stock Deep-Dive tab — coming soon.")
