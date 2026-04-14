"""Tab 6 — Macro Regime. Renders three sections (A cards, B table, C heatmap)."""
from __future__ import annotations

import streamlit as st

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


def render(signals: dict[str, dict[str, str]], force_refresh: bool = False) -> None:
    """Entry point called by app.py."""
    st.header("Macro Regime Monitor")
    st.caption(
        "Three live signals per region (rates, growth, inflation) mapped to one of "
        "eight macro regimes and a factor-tilt recommendation."
    )
    _render_section_a(signals)
