import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from data.portfolio import load_portfolio
from data.fetcher import fetch_iima_factors, fetch_all_fundamentals, fetch_tickertape_prices, fetch_all_prices, compute_monthly_returns
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
    try:
        return fetch_all_fundamentals(list(tickers_tuple), force_refresh=force)
    except Exception:
        return pd.DataFrame({"ticker": list(tickers_tuple)})

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
# TAB 2 — Factor Regression
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader(f"Carhart 4-Factor Regression ({window_years}Y window)")
    st.caption("Source: IIMA Indian Fama-French-Momentum dataset (survivorship-bias adjusted)")

    @st.cache_data(show_spinner="Fetching price history…")
    def get_all_prices(tickers_tuple, force):
        return fetch_all_prices(list(tickers_tuple), years=6, force_refresh=force)

    stock_returns_df = get_all_prices(tuple(portfolio["ticker"].tolist()), force_refresh)
    weights_dict = portfolio.set_index("ticker")["weight"].to_dict()

    if stock_returns_df.empty:
        st.warning("No price data available. Click Refresh Data to fetch.")
    else:
        port_returns = build_portfolio_returns(stock_returns_df, weights_dict)
        reg_result = run_carhart_regression(port_returns, iima_factors, window_years=window_years)

        factors_display = ["mkt_rf", "smb", "hml", "wml"]
        factor_labels = {"mkt_rf": "Market (Rm-Rf)", "smb": "Size (SMB)",
                         "hml": "Value (HML)", "wml": "Momentum (WML)"}

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Alpha (monthly)", f"{reg_result['alpha']*100:.3f}%",
                    f"t = {reg_result['alpha_t']:.2f}")
        col2.metric("R²", f"{reg_result['r_squared']:.3f}")
        col3.metric("Observations", reg_result["n_obs"])

        # Factor table
        reg_rows = []
        for f in factors_display:
            sig = "✓" if reg_result["p_values"][f] < 0.05 else "—"
            reg_rows.append({
                "Factor": factor_labels[f],
                "Beta": round(reg_result["betas"][f], 3),
                "t-stat": round(reg_result["t_stats"][f], 2),
                "p-value": round(reg_result["p_values"][f], 3),
                "Significant (5%)": sig,
            })
        reg_df = pd.DataFrame(reg_rows)
        st.dataframe(reg_df, hide_index=True, use_container_width=True)

        # Beta bar chart
        fig = go.Figure()
        colors = ["#2ecc71" if b > 0 else "#e74c3c" for b in reg_result["betas"].values()]
        fig.add_trace(go.Bar(
            x=[factor_labels[f] for f in factors_display],
            y=[reg_result["betas"][f] for f in factors_display],
            marker_color=colors,
        ))
        fig.add_hline(y=0, line_width=1, line_color="gray")
        fig.update_layout(title="Factor Betas", yaxis_title="Beta", height=350)
        st.plotly_chart(fig, use_container_width=True)

        # Plain-English summary
        tilts = []
        for f in factors_display:
            if reg_result["p_values"][f] < 0.05:
                b = reg_result["betas"][f]
                label = factor_labels[f]
                direction = "positive" if b > 0 else "negative"
                tilts.append(f"{direction} {label} (β={b:.2f})")
        if tilts:
            st.info("**Significant factor tilts:** " + ", ".join(tilts) + ".")
        else:
            st.info("No statistically significant factor tilts detected at 5% level.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Style Scorecard
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Per-Stock Style Scorecard (z-scores vs universe)")
    st.caption("Green = strong positive tilt, Red = negative tilt. Scores are z-scored relative to peer universe.")

    # Merge momentum into fundamentals
    if "stock_returns_df" in dir() and not stock_returns_df.empty:
        mom = {}
        for ticker in portfolio["ticker"]:
            if ticker in stock_returns_df.columns:
                r = stock_returns_df[ticker].dropna()
                if len(r) >= 13:
                    mom[ticker] = (1 + r.iloc[-12:-1]).prod() - 1  # 12M-1M
                elif len(r) > 1:
                    mom[ticker] = (1 + r).prod() - 1
        fundamentals["momentum_12m_1m"] = fundamentals["ticker"].map(mom).fillna(0)
    else:
        fundamentals["momentum_12m_1m"] = 0.0

    if "revenue_cagr_3y" not in fundamentals.columns:
        fundamentals["revenue_cagr_3y"] = 0.0
    if "net_margin" not in fundamentals.columns:
        fundamentals["net_margin"] = 0.0

    style_scores = compute_style_scores(fundamentals)
    weights_series = portfolio.set_index("ticker")["weight"]
    port_scores = compute_portfolio_scores(style_scores, weights_series)

    # Heatmap
    dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
    heatmap_df = style_scores.set_index("ticker")[dims]
    heatmap_df.index = [
        portfolio.loc[portfolio["ticker"] == t, "name"].values[0]
        if t in portfolio["ticker"].values else t
        for t in heatmap_df.index
    ]

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_df.values,
        x=[d.capitalize() for d in dims],
        y=heatmap_df.index.tolist(),
        colorscale="RdYlGn",
        zmid=0,
        text=heatmap_df.round(2).values,
        texttemplate="%{text}",
        hovertemplate="Stock: %{y}<br>Factor: %{x}<br>Z-score: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(title="Style Score Heatmap", height=700)
    st.plotly_chart(fig, use_container_width=True)

    # Radar chart — portfolio vs benchmark (zero)
    st.subheader("Portfolio Factor Profile vs Nifty 500 Baseline")
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=port_scores[dims].values.tolist() + [port_scores[dims[0]]],
        theta=[d.capitalize() for d in dims] + [dims[0].capitalize()],
        fill="toself", name="Portfolio", line_color="#3498db",
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=[0] * (len(dims) + 1),
        theta=[d.capitalize() for d in dims] + [dims[0].capitalize()],
        fill="toself", name="Nifty 500 Baseline", line_color="#95a5a6",
        line_dash="dash",
    ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(range=[-2, 2])), height=450)
    st.plotly_chart(fig_radar, use_container_width=True)

    # Sortable table
    st.subheader("Sortable Factor Table")
    sort_dim = st.selectbox("Sort by", dims, index=0)
    sortable = style_scores.merge(portfolio[["ticker", "name"]], on="ticker")
    sortable = sortable[["name", "ticker"] + dims].sort_values(sort_dim, ascending=False)
    st.dataframe(sortable.rename(columns={"name": "Stock", "ticker": "Ticker"}).reset_index(drop=True),
                 hide_index=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Stock Deep-Dive
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Stock Deep-Dive")

    stock_options = portfolio[["name", "ticker"]].apply(
        lambda r: f"{r['name']} ({r['ticker']})", axis=1
    ).tolist()
    selected = st.selectbox("Select a holding", stock_options)
    selected_ticker = selected.split("(")[-1].rstrip(")")
    selected_row = portfolio[portfolio["ticker"] == selected_ticker].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Sector", selected_row["sector"])
    col2.metric("Portfolio Weight", f"{selected_row['weight']*100:.2f}%")
    col3.metric("Value (INR)", f"₹{selected_row['value']:,.0f}")

    # Style profile for selected stock
    if "style_scores" in dir():
        stock_scores = style_scores[style_scores["ticker"] == selected_ticker]
        if not stock_scores.empty:
            st.subheader("Style Profile")
            dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
            scores_row = stock_scores.iloc[0]
            score_data = pd.DataFrame({
                "Dimension": [d.capitalize() for d in dims],
                "Z-Score": [round(scores_row[d], 3) for d in dims],
                "Interpretation": [
                    "Cheap vs peers" if scores_row[d] > 0.5
                    else "Expensive vs peers" if scores_row[d] < -0.5
                    else "Neutral"
                    if d == "value" else
                    "Strong" if scores_row[d] > 0.5
                    else "Weak" if scores_row[d] < -0.5
                    else "Neutral"
                    for d in dims
                ]
            })
            st.dataframe(score_data, hide_index=True, use_container_width=True)

            # Mini radar for single stock
            fig_single = go.Figure(go.Scatterpolar(
                r=[scores_row[d] for d in dims] + [scores_row[dims[0]]],
                theta=[d.capitalize() for d in dims] + [dims[0].capitalize()],
                fill="toself", line_color="#e67e22",
            ))
            fig_single.update_layout(
                polar=dict(radialaxis=dict(range=[-3, 3])),
                title=f"Factor Profile: {selected_row['name']}",
                height=400,
            )
            st.plotly_chart(fig_single, use_container_width=True)

    # External links
    st.subheader("Research Links")
    screener_url = f"https://www.screener.in/company/{selected_ticker}/consolidated/"
    tickertape_url = f"https://www.tickertape.in/stocks/{selected_ticker.lower()}-{selected_ticker}"
    st.markdown(f"- [Screener.in — {selected_ticker}]({screener_url})")
    st.markdown(f"- [Tickertape — {selected_ticker}]({tickertape_url})")

    st.divider()
    st.subheader("Full Research Report")
    st.info(
        f"To generate a full Buy/Sell/Hold research report for **{selected_row['name']}**, "
        f"invoke the `india-equity-report` skill in a Claude Code session:\n\n"
        f"```\nAnalyse {selected_ticker} NSE\n```\n\n"
        f"The skill is installed globally at `~/.claude/skills/india-equity-report/`."
    )
