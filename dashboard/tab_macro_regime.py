"""Tab 6 — Macro Regime. Renders four sections (A cards, B table, C heatmap, D glossary)."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data import macro_fetcher as mf

REGION_FLAGS: dict[str, str] = {
    "US": "🇺🇸", "India": "🇮🇳", "Japan": "🇯🇵", "Europe": "🇪🇺",
}
REGION_ORDER: list[str] = ["US", "India", "Japan", "Europe"]


def _render_region_card(region: str, signal: dict[str, str]) -> None:
    """Render one colored card for a region using markdown + inline HTML."""
    flag = REGION_FLAGS.get(region, "")
    regime = signal.get("regime", "Unknown")
    color = signal.get("color", "#7f8c8d")
    rates = signal.get("rates", "unknown")
    growth = signal.get("growth", "unknown")
    inflation = signal.get("inflation", "unknown")
    favored, avoided = mf._get_factor_recommendations(regime)

    rates_arrow     = mf._signal_arrow(rates)
    growth_arrow    = mf._signal_arrow(growth)
    inflation_arrow = mf._signal_arrow(inflation)

    favored_str = ", ".join(favored) if favored else "—"
    avoided_str = ", ".join(avoided) if avoided else "—"

    html = f"""
    <div style="border-left: 6px solid {color}; padding: 12px 16px; background: #f8f9fa;
                border-radius: 6px; margin-bottom: 10px;">
      <div style="font-size: 18px; font-weight: 600;">{flag} {region}</div>
      <div style="font-size: 22px; font-weight: 700; color: {color}; margin: 6px 0;">
        {regime}
      </div>
      <div style="font-size: 14px; margin: 6px 0;">
        Rates {rates_arrow} &nbsp;|&nbsp; Growth {growth_arrow} &nbsp;|&nbsp; Inflation {inflation_arrow}
      </div>
      <div style="font-size: 13px; margin-top: 8px;">
        <b>Favor:</b> {favored_str}<br/>
        <b>Avoid:</b> {avoided_str}
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def _render_section_a(signals: dict[str, dict[str, str]]) -> None:
    st.subheader("Current Regime by Region")
    cols = st.columns(4)
    for col, region in zip(cols, REGION_ORDER):
        with col:
            sig = signals.get(region, {})
            _render_region_card(region, sig)


def _render_section_b(signals: dict[str, dict[str, str]]) -> None:
    st.subheader("Side-by-Side Comparison")

    rows: dict[str, list[str]] = {
        "Rates":                [],
        "Growth":               [],
        "Inflation":            [],
        "Regime":               [],
        "Top Favored Factors":  [],
        "Top Avoided Factors":  [],
    }
    for region in REGION_ORDER:
        sig = signals.get(region, {})
        favored, avoided = mf._get_factor_recommendations(sig.get("regime", "Unknown"))
        rows["Rates"].append(f"{sig.get('rates', 'unknown')} {mf._signal_arrow(sig.get('rates', 'unknown'))}")
        rows["Growth"].append(f"{sig.get('growth', 'unknown')} {mf._signal_arrow(sig.get('growth', 'unknown'))}")
        rows["Inflation"].append(f"{sig.get('inflation', 'unknown')} {mf._signal_arrow(sig.get('inflation', 'unknown'))}")
        rows["Regime"].append(sig.get("regime", "Unknown"))
        rows["Top Favored Factors"].append(", ".join(favored) if favored else "—")
        rows["Top Avoided Factors"].append(", ".join(avoided) if avoided else "—")

    df = pd.DataFrame(rows, index=REGION_ORDER).T
    df.columns = [f"{REGION_FLAGS[r]} {r}" for r in REGION_ORDER]
    st.dataframe(df, use_container_width=True)


_SYMBOL_TO_SCORE: dict[str, int] = {"●": 1, "○": 0, "✕": -1}
_COLORSCALE = [
    [0.0, "#e74c3c"],   # ✕ Avoid
    [0.5, "#bdc3c7"],   # ○ Neutral
    [1.0, "#27ae60"],   # ● Favor
]


def _render_section_c(signals: dict[str, dict[str, str]]) -> None:
    st.subheader("Factor × Regime Reference Matrix")

    regimes = list(mf.FACTOR_MATRIX.keys())
    factors = mf.FACTORS

    z: list[list[float]] = []
    text: list[list[str]] = []
    for regime in regimes:
        row = mf.FACTOR_MATRIX[regime]
        z.append([float(_SYMBOL_TO_SCORE[row[f]]) for f in factors])
        text.append([row[f] for f in factors])

    # Highlight rows that are currently active in any region
    active_regimes = {sig.get("regime") for sig in signals.values()}
    y_labels = [
        f"<b>★ {r}</b>" if r in active_regimes else r
        for r in regimes
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=factors,
        y=y_labels,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 18},
        colorscale=_COLORSCALE,
        zmin=-1, zmax=1,
        showscale=False,
        hovertemplate="Regime: %{y}<br>Factor: %{x}<br>Tilt: %{text}<extra></extra>",
    ))
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=30, b=30),
        xaxis=dict(side="top"),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Legend: ● Favor (green) &nbsp;·&nbsp; ○ Neutral (grey) &nbsp;·&nbsp; "
        "✕ Avoid (red). Rows marked ★ are currently active in at least one region."
    )


_REGIME_GLOSSARY: list[dict[str, str]] = [
    {
        "Regime": "Goldilocks",
        "Signals": "Rates ↓ · Growth ↑ · Inflation ↓",
        "Color": "#27ae60",
        "Description": (
            "The ideal macro backdrop — growth is expanding while both rates and inflation "
            "are falling. Risk assets thrive. Equities broadly rally with a tilt toward "
            "cyclicals, small caps, and high-beta names. Central banks are accommodative or easing."
        ),
    },
    {
        "Regime": "Overheating",
        "Signals": "Rates ↑ · Growth ↑ · Inflation ↑",
        "Color": "#f39c12",
        "Description": (
            "The economy is running hot — strong growth but rising prices force central banks "
            "to hike rates. Value and commodity-linked sectors outperform. Momentum works while "
            "the trend holds. Long-duration assets (Growth, Low Vol) face headwinds from "
            "higher discount rates."
        ),
    },
    {
        "Regime": "Stagflation",
        "Signals": "Rates ↑ · Growth ↓ · Inflation ↑",
        "Color": "#e74c3c",
        "Description": (
            "The worst macro environment — growth is contracting while inflation and rates are "
            "both rising. Equities are broadly pressured. Defensive Quality and Low Vol factors "
            "hold up best. Value (especially financials and commodities) can still work. "
            "Historically rare but painful for portfolios."
        ),
    },
    {
        "Regime": "Deflation / Bust",
        "Signals": "Rates ↓ · Growth ↓ · Inflation ↓",
        "Color": "#2c3e50",
        "Description": (
            "A deflationary contraction — growth collapses and prices fall alongside rates. "
            "Think 2008-09 or early Covid. Capital preservation dominates. Quality and Low Vol "
            "factors significantly outperform. Most other factors, especially Value and Beta, "
            "suffer heavily."
        ),
    },
    {
        "Regime": "Recovery / Tightening",
        "Signals": "Rates ↑ · Growth ↑ · Inflation ↓",
        "Color": "#16a085",
        "Description": (
            "Growth is recovering and expanding, but central banks are already tightening "
            "even as inflation stays contained. A broad cyclical recovery — Value, Size, and "
            "Market Beta all tend to do well. The window before inflation heats up and the "
            "regime shifts to Overheating."
        ),
    },
    {
        "Regime": "Stagflation-Lite",
        "Signals": "Rates ↓ · Growth ↓ · Inflation ↑",
        "Color": "#c0392b",
        "Description": (
            "Growth is weakening and inflation is rising, but rates are not yet responding — "
            "central banks may be behind the curve. A softer version of Stagflation. Quality "
            "and defensive Value outperform while cyclicals and high-beta names struggle. "
            "Often a transitional regime that resolves into full Stagflation or Reflation."
        ),
    },
    {
        "Regime": "Recession / Tightening",
        "Signals": "Rates ↑ · Growth ↓ · Inflation ↓",
        "Color": "#2980b9",
        "Description": (
            "Growth is contracting while central banks are still tightening (or haven't yet "
            "pivoted to easing). A classic late-cycle environment. Quality and Low Vol "
            "defensives outperform. Market Beta, Momentum, and Growth factors tend to suffer. "
            "Often precedes Deflation/Bust or a policy pivot into Goldilocks."
        ),
    },
    {
        "Regime": "Reflation",
        "Signals": "Rates ↓ · Growth ↑ · Inflation ↑",
        "Color": "#d35400",
        "Description": (
            "Growth is expanding and inflation is picking up, with rates still falling or "
            "accommodative — central banks are deliberately stimulating. Early-cycle recovery "
            "dynamic. Cyclicals, commodities, and Value shine. Momentum and Growth also work "
            "well. The regime that follows a Bust or policy pivot."
        ),
    },
]


def _render_section_d(signals: dict[str, dict[str, str]]) -> None:
    st.subheader("Regime Glossary")
    active_regimes = {sig.get("regime") for sig in signals.values()}

    for entry in _REGIME_GLOSSARY:
        name = entry["Regime"]
        color = entry["Color"]
        is_active = name in active_regimes
        active_badge = (
            f'<span style="background:{color}; color:white; font-size:11px; '
            f'padding:2px 8px; border-radius:10px; margin-left:8px;">ACTIVE</span>'
            if is_active else ""
        )
        html = f"""
        <div style="border-left: 5px solid {color}; padding: 10px 16px;
                    background: #f8f9fa; border-radius: 6px; margin-bottom: 10px;">
          <div style="font-size:16px; font-weight:700; color:{color};">
            {name}{active_badge}
          </div>
          <div style="font-size:12px; color:#666; margin: 2px 0 6px 0;">
            {entry["Signals"]}
          </div>
          <div style="font-size:13px; line-height:1.5;">
            {entry["Description"]}
          </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)


def render(signals: dict[str, dict[str, str]], force_refresh: bool = False) -> None:
    """Entry point called by app.py."""
    st.header("Macro Regime Monitor")
    st.caption(
        "Three live signals per region (rates, growth, inflation) mapped to one of "
        "eight macro regimes and a factor-tilt recommendation."
    )
    _render_section_a(signals)
    _render_section_b(signals)
    _render_section_c(signals)
    st.divider()
    _render_section_d(signals)
