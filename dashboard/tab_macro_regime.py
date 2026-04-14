"""Tab 6 — Macro Regime. Renders three sections (A cards, B table, C heatmap)."""
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
