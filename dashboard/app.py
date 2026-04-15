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
from factors.scorer import compute_style_scores, compute_portfolio_scores, compute_nifty500_percentile_scores
from factors.regression import build_portfolio_returns, run_carhart_regression, rolling_carhart_betas, factor_return_attribution
from dashboard import tab_macro_regime
from dashboard.explanations import TOOLTIPS, TAB2_GLOSSARY, TAB3_GLOSSARY, TAB5_GLOSSARY
from data.macro_fetcher import fetch_macro_signals

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
    try:
        return fetch_iima_factors(force_refresh=force)
    except Exception as e:
        st.warning(f"Could not reach IIMA data source: {e}. Factor regression tabs will be unavailable.")
        return pd.DataFrame()

@st.cache_data(show_spinner="Fetching stock fundamentals from Screener.in…")
def get_fundamentals(tickers_tuple, force):
    try:
        return fetch_all_fundamentals(list(tickers_tuple), force_refresh=force)
    except Exception:
        return pd.DataFrame({"ticker": list(tickers_tuple)})

iima_factors = get_iima(force_refresh)
fundamentals = get_fundamentals(tuple(portfolio["ticker"].tolist()), force_refresh)

# ── Shared computation (sidebar + multiple tabs) ──────────────────────────────
@st.cache_data(show_spinner="Fetching price history…")
def get_all_prices(tickers_tuple, force):
    return fetch_all_prices(list(tickers_tuple), years=6, force_refresh=force)

stock_returns_df = get_all_prices(tuple(portfolio["ticker"].tolist()), force_refresh)
weights_dict = portfolio.set_index("ticker")["weight"].to_dict()

port_returns = None
reg_result = None
if not iima_factors.empty and not stock_returns_df.empty:
    port_returns = build_portfolio_returns(stock_returns_df, weights_dict)
    reg_result = run_carhart_regression(port_returns, iima_factors, window_years=window_years)

hhi = (portfolio["weight"] ** 2).sum()
effective_n = 1 / hhi if hhi > 0 else len(portfolio)

if not stock_returns_df.empty:
    mom = {}
    for ticker in portfolio["ticker"]:
        if ticker in stock_returns_df.columns:
            r = stock_returns_df[ticker].dropna()
            if len(r) >= 13:
                mom[ticker] = (1 + r.iloc[-12:-1]).prod() - 1
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

# ── Sidebar: Portfolio at a Glance ───────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.markdown("**Portfolio at a Glance**")
    total_value = portfolio["value"].sum()
    top_sector_row = portfolio.groupby("sector")["weight"].sum().idxmax()
    top_sector_wt = portfolio.groupby("sector")["weight"].sum().max()
    st.metric("Total Value", f"₹{total_value:,.0f}")
    st.metric("Holdings", f"{len(portfolio)} stocks")
    st.metric("Top Sector", f"{top_sector_row}  {top_sector_wt*100:.0f}%")
    if reg_result is not None:
        st.metric("Effective N", f"{effective_n:.1f}", help="1 ÷ HHI — equivalent equal-weight holdings")
        alpha_pct = reg_result["alpha"] * 100
        st.metric("Alpha (monthly)", f"{alpha_pct:+.3f}%", help="Excess return above factor model prediction")
    else:
        st.caption("Factor data loading…")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_macro, tab_profile, tab_holdings, tab_factor, tab_style, tab_deepdive = st.tabs([
    "Macro Regime",
    "Portfolio Summary",
    "Holdings",
    "Factor Analysis",
    "Style Scorecard",
    "Stock Deep-Dive",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: Macro Regime
# ═══════════════════════════════════════════════════════════════════════════════
with tab_macro:
    macro_refresh = st.button("Refresh macro signals", key="macro_refresh")

    # Robust secrets access — handles missing section header or unavailable secrets
    fred_api_key = None
    try:
        fred_api_key = st.secrets["fred"]["api_key"]
    except (KeyError, AttributeError, FileNotFoundError):
        try:
            fred_api_key = st.secrets.get("api_key")  # fallback: top-level key
        except Exception:
            fred_api_key = None

    if not fred_api_key:
        st.warning(
            "FRED API key not found in secrets. Inflation and some rates signals will show as Unknown. "
            "Add `[fred]\\napi_key = \\'YOUR_KEY\\'` to Streamlit secrets.",
            icon="⚠️",
        )

    try:
        signals = fetch_macro_signals(
            force_refresh=macro_refresh,
            fred_api_key=fred_api_key,
        )
    except Exception as exc:
        st.error(f"Failed to fetch macro signals: {exc}")
        signals = {}

    # Debug expander — shows raw signal values so users can see what resolved
    if signals:
        with st.expander("Signal details", expanded=False):
            rows = []
            for region, s in signals.items():
                rows.append({
                    "Region": region,
                    "Rates": s.get("rates", "—"),
                    "Growth": s.get("growth", "—"),
                    "Inflation": s.get("inflation", "—"),
                    "Regime": s.get("regime", "—"),
                })
            import pandas as pd
            st.dataframe(pd.DataFrame(rows).set_index("Region"), use_container_width=True)

    tab_macro_regime.render(signals, force_refresh=macro_refresh)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: Portfolio Summary
# ═══════════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.subheader("Portfolio Summary")
    with st.expander("📖 What do these numbers mean?"):
        st.markdown(TAB5_GLOSSARY)

    # Guard: needs IIMA factor data and regression results
    if iima_factors.empty or reg_result is None:
        st.info("IIMA factor data is currently unavailable (source unreachable). This tab will populate once the data source is back online.")
    else:

        # ── Section A: Summary Cards ───────────────────────────────────────────────
        st.markdown("### Executive Summary")

        factors_display_p5 = ["mkt_rf", "smb", "hml", "wml"]
        factor_labels_p5 = {
            "mkt_rf": "Market (Rm-Rf)", "smb": "Size (SMB)",
            "hml": "Value (HML)", "wml": "Momentum (WML)"
        }

        # Dominant factor: highest |beta| among significant factors (p < 0.05)
        sig_factors = {f: reg_result["betas"][f] for f in factors_display_p5
                       if reg_result["p_values"][f] < 0.05}
        if sig_factors:
            dominant_f = max(sig_factors, key=lambda f: abs(sig_factors[f]))
            dominant_label = f"{factor_labels_p5[dominant_f]} (β={sig_factors[dominant_f]:.2f})"
        else:
            dominant_label = "None (p>0.05)"

        # Top style tilt
        dims_6 = ["value", "quality", "momentum", "size", "growth", "profitability"]
        top_dim = port_scores[dims_6].abs().idxmax()
        top_score = port_scores[top_dim]

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Dominant Factor", dominant_label, help=TOOLTIPS["dominant_factor"])
        c2.metric(
            "Alpha (monthly)", f"{reg_result['alpha']*100:.3f}%",
            f"t = {reg_result['alpha_t']:.2f}",
            help=TOOLTIPS["alpha"],
        )
        c3.metric("R²", f"{reg_result['r_squared']:.3f}", help=TOOLTIPS["r_squared"])
        c4.metric("Top Style Tilt", f"{top_dim.capitalize()} ({top_score:+.2f})", help=TOOLTIPS["top_style_tilt"])
        c5.metric("Portfolio HHI", f"{hhi:.4f}", help=TOOLTIPS["hhi"])
        c6.metric("Effective N", f"{effective_n:.1f}", help=TOOLTIPS["effective_n"])

        # ── Auto-narrative ────────────────────────────────────────────────────────
        mkt_b = reg_result["betas"]["mkt_rf"]
        if mkt_b > 1.1:
            mkt_desc = f"**aggressive market exposure** (β={mkt_b:.2f}), amplifying index moves"
        elif mkt_b < 0.9:
            mkt_desc = f"**defensive market exposure** (β={mkt_b:.2f}), dampening index moves"
        else:
            mkt_desc = f"**neutral market exposure** (β={mkt_b:.2f}), tracking the index closely"

        sig_tilts = []
        for f in ["smb", "hml", "wml"]:
            if reg_result["p_values"][f] < 0.05:
                b = reg_result["betas"][f]
                direction = "positive" if b > 0 else "negative"
                sig_tilts.append(f"{direction} {factor_labels_p5[f]} tilt (β={b:.2f})")

        style_sorted = port_scores[dims_6].abs().sort_values(ascending=False)
        top2_dims = style_sorted.index[:2].tolist()
        style_desc_parts = []
        for d in top2_dims:
            z = port_scores[d]
            if z > 0.5:
                strength = "strong positive"
            elif z > 0.2:
                strength = "mild positive"
            elif z < -0.5:
                strength = "strong negative"
            elif z < -0.2:
                strength = "mild negative"
            else:
                strength = "neutral"
            style_desc_parts.append(f"{strength} {d} tilt (z={z:+.2f})")

        size_b = reg_result["betas"]["smb"]
        if size_b < -0.2 and reg_result["p_values"]["smb"] < 0.05:
            size_note = "The negative SMB beta confirms a **large-cap bias** in the portfolio."
        elif size_b > 0.2 and reg_result["p_values"]["smb"] < 0.05:
            size_note = "The positive SMB beta confirms a **small/mid-cap tilt** in the portfolio."
        else:
            size_note = "Size exposure is not statistically significant."

        narrative = f"This portfolio carries {mkt_desc}. "
        if sig_tilts:
            narrative += "Statistically significant factor tilts include: " + "; ".join(sig_tilts) + ". "
        else:
            narrative += "No other factor tilts are statistically significant at the 5% level. "
        if style_desc_parts:
            narrative += "Style analysis shows a " + " and ".join(style_desc_parts) + ". "
        narrative += size_note

        st.info(f"*{narrative}*")

        # ── Section B: Investment Memo ─────────────────────────────────────────────
        st.markdown("### Investment Memo")

        # Expander 1: Factor Tilts
        with st.expander("Factor Tilts", expanded=True):
            def _factor_interp(f, b, sig):
                if not sig:
                    return "No statistically significant exposure"
                if f == "mkt_rf":
                    if b > 1.1:
                        return "Aggressive market exposure — amplifies index moves"
                    elif b < 0.9:
                        return "Defensive market exposure — lower sensitivity to index"
                    else:
                        return "Neutral market exposure — tracks index closely"
                elif f == "smb":
                    if b > 0.2:
                        return "Positive size tilt — overweight small/mid caps"
                    else:
                        return "Negative size tilt — large-cap bias"
                elif f == "hml":
                    if b > 0.2:
                        return "Positive value tilt — cheaper stocks by P/B"
                    else:
                        return "Growth tilt — higher-valuation stocks"
                elif f == "wml":
                    if b > 0.2:
                        return "Momentum tilt — recent winners overweighted"
                    else:
                        return "Contrarian tilt — recent underperformers"
                return ""

            memo_rows = []
            for f in factors_display_p5:
                b = reg_result["betas"][f]
                t = reg_result["t_stats"][f]
                p = reg_result["p_values"][f]
                sig = p < 0.05
                memo_rows.append({
                    "Factor": factor_labels_p5[f],
                    "Beta": round(b, 3),
                    "t-stat": round(t, 2),
                    "p-value": round(p, 3),
                    "Sig (5%)": "✓" if sig else "—",
                    "Interpretation": _factor_interp(f, b, sig),
                })
            st.dataframe(pd.DataFrame(memo_rows), hide_index=True, use_container_width=True)

        # Expander 2: Style Characteristics
        with st.expander("Style Characteristics", expanded=False):
            NIFTY500_SNAPSHOT_PATH = str(
                Path(__file__).parent.parent / "data" / "nifty500_screener_snapshot.csv"
            )
            nifty_pct = compute_nifty500_percentile_scores(port_scores, NIFTY500_SNAPSHOT_PATH)

            fig_radar2 = go.Figure()
            fig_radar2.add_trace(go.Scatterpolar(
                r=port_scores[dims_6].values.tolist() + [port_scores[dims_6[0]]],
                theta=[d.capitalize() for d in dims_6] + [dims_6[0].capitalize()],
                fill="toself", name="Portfolio", line_color="#3498db",
            ))
            fig_radar2.add_trace(go.Scatterpolar(
                r=[0] * (len(dims_6) + 1),
                theta=[d.capitalize() for d in dims_6] + [dims_6[0].capitalize()],
                fill="toself", name="Nifty 500 Baseline", line_color="#95a5a6",
                line_dash="dash",
            ))
            fig_radar2.update_layout(
                polar=dict(radialaxis=dict(range=[-2, 2])),
                height=500,
                title="Portfolio Style vs Nifty 500 Baseline",
            )
            st.plotly_chart(fig_radar2, use_container_width=True)

            def _style_interp(z):
                if z > 0.5:
                    return "Strong positive tilt"
                elif z > 0.2:
                    return "Mild positive tilt"
                elif z < -0.5:
                    return "Strong negative tilt"
                elif z < -0.2:
                    return "Mild negative tilt"
                else:
                    return "Neutral"

            style_rows = []
            for d in dims_6:
                z = port_scores[d]
                style_rows.append({
                    "Dimension": d.capitalize(),
                    "Portfolio Z-Score": round(z, 3),
                    "Nifty 500 Percentile": nifty_pct.get(d, 50.0),
                    "Interpretation": _style_interp(z),
                })
            style_df = pd.DataFrame(style_rows).sort_values(
                "Portfolio Z-Score", key=abs, ascending=False
            )
            st.dataframe(style_df, hide_index=True, use_container_width=True)

        # Expander 3: Risk Profile
        with st.expander("Risk Profile", expanded=False):
            if hhi < 0.1:
                hhi_label = "Diversified"
            elif hhi < 0.18:
                hhi_label = "Moderate concentration"
            else:
                hhi_label = "Concentrated"

            top5_weight = portfolio.nlargest(5, "weight")["weight"].sum() * 100
            top2_sectors = (
                portfolio.groupby("sector")["weight"].sum()
                .nlargest(2)
                .reset_index()
            )
            sector_hhi = (portfolio.groupby("sector")["weight"].sum() ** 2).sum()

            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown("**Stock Concentration**")
                st.metric("HHI", f"{hhi:.4f}", hhi_label, help=TOOLTIPS["hhi"])
                st.metric("Effective N", f"{effective_n:.1f}", help=TOOLTIPS["effective_n"])
                st.metric("Top 5 Holdings Weight", f"{top5_weight:.1f}%")

            with rc2:
                st.markdown("**Sector Concentration**")
                st.metric("Sector HHI", f"{sector_hhi:.4f}", help=TOOLTIPS["sector_hhi"])
                for _, row in top2_sectors.iterrows():
                    st.metric(row["sector"], f"{row['weight']*100:.1f}%")

            st.markdown("**Factor R² Breakdown**")
            try:
                factors_idx = iima_factors.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
                aligned_p, aligned_f = port_returns.align(factors_idx, join="inner")
                port_excess_series = aligned_p - aligned_f["rf"]
                port_var = port_excess_series.var()

                factor_stds = {f: aligned_f[f].std() for f in ["mkt_rf", "smb", "hml", "wml"]}
                factor_variances = {
                    f: (reg_result["betas"][f] * factor_stds[f]) ** 2
                    for f in ["mkt_rf", "smb", "hml", "wml"]
                }
                residual_share = max(0.0, 1 - reg_result["r_squared"])
                total_explained = sum(factor_variances.values())
                if port_var > 0 and total_explained > 0:
                    pie_labels = [factor_labels_p5[f] for f in ["mkt_rf", "smb", "hml", "wml"]] + ["Residual"]
                    pie_values = [
                        factor_variances[f] / port_var * 100
                        for f in ["mkt_rf", "smb", "hml", "wml"]
                    ] + [residual_share * 100]
                    pie_colors = ["#3498db", "#2ecc71", "#e67e22", "#9b59b6", "#95a5a6"]
                    fig_pie = go.Figure(go.Pie(
                        labels=pie_labels,
                        values=pie_values,
                        marker_colors=pie_colors,
                        textinfo="label+percent",
                    ))
                    fig_pie.update_layout(height=350, title="Variance Explained by Factor")
                    st.plotly_chart(fig_pie, use_container_width=True)
            except Exception as e:
                st.caption(f"R² breakdown unavailable: {e}")

        # ── Section C: Quantitative Detail ────────────────────────────────────────
        st.markdown("### Quantitative Detail")

        # Chart 1: Rolling Factor Betas
        st.markdown("#### Rolling Factor Betas")
        window_sel = st.radio(
            "Rolling window", ["12M", "24M", "36M"], index=1, horizontal=True, key="tab5_window"
        )
        window_months = int(window_sel.replace("M", ""))

        try:
            rolling_betas = rolling_carhart_betas(port_returns, iima_factors, window_months=window_months)
            valid_rolling = rolling_betas.dropna()
            if not valid_rolling.empty:
                roll_colors = {
                    "mkt_rf": "#3498db", "smb": "#2ecc71",
                    "hml": "#e67e22", "wml": "#9b59b6"
                }
                fig_roll = go.Figure()
                for f in ["mkt_rf", "smb", "hml", "wml"]:
                    fig_roll.add_trace(go.Scatter(
                        x=valid_rolling.index,
                        y=valid_rolling[f],
                        name=factor_labels_p5[f],
                        line=dict(color=roll_colors[f]),
                    ))
                fig_roll.add_hline(y=0, line_width=1, line_color="gray", line_dash="dash")
                fig_roll.update_layout(
                    title=f"Rolling {window_sel} Factor Betas",
                    yaxis_title="Beta",
                    xaxis_title="Date",
                    height=400,
                    hovermode="x unified",
                )
                st.plotly_chart(fig_roll, use_container_width=True)
            else:
                st.caption("Insufficient data for rolling betas with selected window.")
        except Exception as e:
            st.caption(f"Rolling betas unavailable: {e}")

        # Chart 2: Factor Return Attribution
        st.markdown("#### Factor Return Attribution")
        try:
            attribution = factor_return_attribution(port_returns, iima_factors, reg_result)
            attr_colors = {
                "alpha": "#f39c12", "mkt_rf": "#3498db", "smb": "#2ecc71",
                "hml": "#e67e22", "wml": "#9b59b6", "residual": "#95a5a6",
            }
            attr_labels = {
                "alpha": "Alpha", "mkt_rf": "Market", "smb": "SMB",
                "hml": "HML", "wml": "WML", "residual": "Residual",
            }
            fig_attr = go.Figure()
            for col in ["alpha", "mkt_rf", "smb", "hml", "wml", "residual"]:
                fig_attr.add_trace(go.Bar(
                    x=attribution.index,
                    y=attribution[col] * 100,
                    name=attr_labels[col],
                    marker_color=attr_colors[col],
                ))
            fig_attr.update_layout(
                barmode="relative",
                title="Monthly Factor Return Attribution (%)",
                yaxis_title="Contribution (%)",
                xaxis_title="Date",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(fig_attr, use_container_width=True)
        except Exception as e:
            st.caption(f"Attribution chart unavailable: {e}")

        # Chart 3: Style Score vs Nifty 500 Percentile
        st.markdown("#### Style Score vs Nifty 500 Percentile")
        try:
            pct_values = [nifty_pct.get(d, 50.0) for d in dims_6]
            fig_pct = go.Figure(go.Bar(
                x=pct_values,
                y=[d.capitalize() for d in dims_6],
                orientation="h",
                marker_color=["#3498db" if v > 50 else "#e74c3c" for v in pct_values],
            ))
            fig_pct.add_vline(x=50, line_width=2, line_dash="dash", line_color="gray",
                              annotation_text="50th pct (index neutral)")
            fig_pct.update_layout(
                title="Portfolio Style Percentile vs Nifty 500",
                xaxis_title="Percentile Rank (0–100)",
                xaxis=dict(range=[0, 100]),
                height=350,
            )
            st.plotly_chart(fig_pct, use_container_width=True)
        except Exception as e:
            st.caption(f"Percentile chart unavailable: {e}")

        # Chart 4: Weight Distribution
        st.markdown("#### Portfolio Weight Distribution")
        port_sorted = portfolio.sort_values("weight", ascending=False).reset_index(drop=True)
        port_sorted["weight_pct"] = port_sorted["weight"] * 100
        port_sorted["cumulative_pct"] = port_sorted["weight_pct"].cumsum()

        fig_weights = go.Figure()
        fig_weights.add_trace(go.Bar(
            x=port_sorted["name"],
            y=port_sorted["weight_pct"],
            name="Weight (%)",
            marker_color="#3498db",
            yaxis="y",
        ))
        fig_weights.add_trace(go.Scatter(
            x=port_sorted["name"],
            y=port_sorted["cumulative_pct"],
            name="Cumulative Weight (%)",
            line=dict(color="#e74c3c", width=2),
            yaxis="y2",
        ))
        fig_weights.add_hline(y=50, line_width=1, line_dash="dot",
                              line_color="orange", yref="y2",
                              annotation_text="50%", annotation_position="right")
        fig_weights.add_hline(y=80, line_width=1, line_dash="dot",
                              line_color="red", yref="y2",
                              annotation_text="80%", annotation_position="right")
        fig_weights.update_layout(
            title="Holdings by Weight (Descending)",
            xaxis_title="Stock",
            yaxis=dict(title="Weight (%)"),
            yaxis2=dict(title="Cumulative Weight (%)", overlaying="y", side="right", range=[0, 100]),
            height=350,
            hovermode="x unified",
            legend=dict(x=0.01, y=0.99),
            xaxis=dict(tickangle=-45),
        )
        st.plotly_chart(fig_weights, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: Holdings
# ═══════════════════════════════════════════════════════════════════════════════
with tab_holdings:
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
# TAB: Factor Analysis
# ═══════════════════════════════════════════════════════════════════════════════
with tab_factor:
    st.subheader(f"Carhart 4-Factor Regression ({window_years}Y window)")
    st.caption("Source: IIMA Indian Fama-French-Momentum dataset (survivorship-bias adjusted)")
    with st.expander("📖 What do these numbers mean?"):
        st.markdown(TAB2_GLOSSARY)

    if iima_factors.empty or reg_result is None:
        st.info("IIMA factor data is currently unavailable (source unreachable). This tab will populate once the data source is back online.")
    else:
        if stock_returns_df.empty:
            st.warning("No price data available. Click Refresh Data to fetch.")
        else:
            factors_display = ["mkt_rf", "smb", "hml", "wml"]
            factor_labels = {"mkt_rf": "Market (Rm-Rf)", "smb": "Size (SMB)",
                             "hml": "Value (HML)", "wml": "Momentum (WML)"}

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Alpha (monthly)", f"{reg_result['alpha']*100:.3f}%",
                f"t = {reg_result['alpha_t']:.2f}",
                help=TOOLTIPS["alpha"],
            )
            col2.metric("R²", f"{reg_result['r_squared']:.3f}", help=TOOLTIPS["r_squared"])
            col3.metric("Observations", reg_result["n_obs"], help=TOOLTIPS["observations"])

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
# TAB: Style Scorecard
# ═══════════════════════════════════════════════════════════════════════════════
with tab_style:
    st.subheader("Per-Stock Style Scorecard (z-scores vs universe)")
    st.caption("Green = strong positive tilt, Red = negative tilt. Scores are z-scored relative to peer universe.")
    with st.expander("📖 What do these numbers mean?"):
        st.markdown(TAB3_GLOSSARY)

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
# TAB: Stock Deep-Dive
# ═══════════════════════════════════════════════════════════════════════════════
with tab_deepdive:
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
    if not stock_returns_df.empty:
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
