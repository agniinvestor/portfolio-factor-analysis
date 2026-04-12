# Portfolio Profile Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tab 5 "Portfolio Profile" to the Streamlit dashboard — a comprehensive factor/style summary with executive narrative, investment memo expanders, and 4 quantitative charts.

**Architecture:** Three pure helper functions (`rolling_carhart_betas`, `factor_return_attribution` in `factors/regression.py`; `compute_nifty500_percentile_scores` in `factors/scorer.py`) feed a pure display tab in `dashboard/app.py`. Tab 5 consumes existing shared variables (no new fetches). Tests added to existing test files.

**Tech Stack:** statsmodels RollingOLS, Plotly (bar/line/pie), Streamlit st.columns / st.expander / st.info

---

## File Map

| File | Change |
|---|---|
| `factors/regression.py` | Add `rolling_carhart_betas`, `factor_return_attribution` |
| `factors/scorer.py` | Add `compute_nifty500_percentile_scores` |
| `dashboard/app.py` | Change 4-tab → 5-tab; add Tab 5 content block |
| `tests/test_regression.py` | Add tests for two new regression helpers |
| `tests/test_scorer.py` | Add test for new scorer helper |

---

### Task 1: Rolling Beta and Attribution Helpers in `factors/regression.py`

**Files:**
- Modify: `factors/regression.py`
- Test: `tests/test_regression.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_regression.py`:

```python
from factors.regression import rolling_carhart_betas, factor_return_attribution

def test_rolling_carhart_betas_returns_dataframe():
    result = rolling_carhart_betas(PORT_RETURNS, FACTORS, window_months=12)
    assert isinstance(result, pd.DataFrame)

def test_rolling_carhart_betas_has_factor_columns():
    result = rolling_carhart_betas(PORT_RETURNS, FACTORS, window_months=12)
    for col in ["mkt_rf", "smb", "hml", "wml"]:
        assert col in result.columns, f"Missing column: {col}"

def test_rolling_carhart_betas_index_is_datetime():
    result = rolling_carhart_betas(PORT_RETURNS, FACTORS, window_months=12)
    assert pd.api.types.is_datetime64_any_dtype(result.index)

def test_rolling_carhart_betas_has_valid_rows():
    result = rolling_carhart_betas(PORT_RETURNS, FACTORS, window_months=12)
    valid = result.dropna()
    assert len(valid) > 0

def test_factor_return_attribution_returns_dataframe():
    reg_result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    result = factor_return_attribution(PORT_RETURNS, FACTORS, reg_result)
    assert isinstance(result, pd.DataFrame)

def test_factor_return_attribution_has_required_columns():
    reg_result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    result = factor_return_attribution(PORT_RETURNS, FACTORS, reg_result)
    for col in ["alpha", "mkt_rf", "smb", "hml", "wml", "residual"]:
        assert col in result.columns, f"Missing column: {col}"

def test_factor_return_attribution_sums_to_port_excess():
    reg_result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    result = factor_return_attribution(PORT_RETURNS, FACTORS, reg_result)
    contrib_cols = ["alpha", "mkt_rf", "smb", "hml", "wml", "residual"]
    row_sums = result[contrib_cols].sum(axis=1)
    # Align port excess
    factors_indexed = FACTORS.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
    aligned_port, aligned_fac = PORT_RETURNS.align(factors_indexed, join="inner")
    port_excess = aligned_port - aligned_fac["rf"]
    port_excess_aligned = port_excess.reindex(result.index)
    np.testing.assert_allclose(row_sums.values, port_excess_aligned.values, atol=1e-10)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python -m pytest tests/test_regression.py::test_rolling_carhart_betas_returns_dataframe tests/test_regression.py::test_factor_return_attribution_returns_dataframe -v
```

Expected: ImportError or AttributeError — functions not yet defined.

- [ ] **Step 3: Implement the two helper functions**

Append to `factors/regression.py`:

```python
from statsmodels.regression.rolling import RollingOLS


def rolling_carhart_betas(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    window_months: int = 24,
) -> pd.DataFrame:
    """Compute rolling Carhart 4-factor betas.

    Args:
        portfolio_returns: Monthly portfolio returns (Series, datetime index).
        factor_returns: DataFrame with columns date, mkt_rf, smb, hml, wml, rf.
        window_months: Rolling window size in months.
    Returns:
        DataFrame indexed by date with columns mkt_rf, smb, hml, wml.
        Rows before the window fills are NaN.
    """
    factors = factor_returns.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
    aligned_port, aligned_fac = portfolio_returns.align(factors, join="inner")
    port_excess = aligned_port - aligned_fac["rf"]

    X = sm.add_constant(aligned_fac[["mkt_rf", "smb", "hml", "wml"]])
    rols = RollingOLS(port_excess, X, window=window_months).fit()

    betas = rols.params[["mkt_rf", "smb", "hml", "wml"]].copy()
    betas.index = port_excess.index
    return betas


def factor_return_attribution(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    reg_result: dict,
) -> pd.DataFrame:
    """Decompose monthly portfolio excess returns into factor contributions.

    For each month: alpha + Σ(beta_i * factor_i) + residual = port_excess.

    Args:
        portfolio_returns: Monthly portfolio returns (Series, datetime index).
        factor_returns: DataFrame with columns date, mkt_rf, smb, hml, wml, rf.
        reg_result: Dict returned by run_carhart_regression.
    Returns:
        DataFrame indexed by date with columns alpha, mkt_rf, smb, hml, wml, residual.
    """
    factors = factor_returns.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
    aligned_port, aligned_fac = portfolio_returns.align(factors, join="inner")
    port_excess = aligned_port - aligned_fac["rf"]

    result = pd.DataFrame(index=port_excess.index)
    result["alpha"] = reg_result["alpha"]

    factor_cols = ["mkt_rf", "smb", "hml", "wml"]
    for f in factor_cols:
        result[f] = reg_result["betas"][f] * aligned_fac[f]

    explained = result["alpha"] + result[factor_cols].sum(axis=1)
    result["residual"] = port_excess - explained
    return result
```

- [ ] **Step 4: Run all regression tests**

```bash
python -m pytest tests/test_regression.py -v
```

Expected: All tests PASS (original 7 + new 7 = 14 total).

- [ ] **Step 5: Commit**

```bash
git add factors/regression.py tests/test_regression.py
git commit -m "feat: add rolling_carhart_betas and factor_return_attribution helpers"
```

---

### Task 2: Nifty 500 Percentile Scorer in `factors/scorer.py`

**Files:**
- Modify: `factors/scorer.py`
- Test: `tests/test_scorer.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scorer.py`:

```python
import tempfile
import os
from factors.scorer import compute_nifty500_percentile_scores

# Build a minimal Nifty 500 snapshot (10 rows) for testing
NIFTY_SNAPSHOT = pd.DataFrame({
    "ticker": [f"S{i}" for i in range(10)],
    "pe":     [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0],
    "pb":     [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5],
    "roe":    [30.0, 25.0, 20.0, 18.0, 15.0, 12.0, 10.0, 8.0, 6.0, 4.0],
    "roce":   [28.0, 24.0, 20.0, 17.0, 14.0, 11.0, 9.0, 7.0, 5.0, 3.0],
    "de":     [0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 2.0],
    "market_cap_cr": [50000.0, 40000.0, 30000.0, 20000.0, 15000.0,
                      10000.0, 5000.0, 3000.0, 1000.0, 500.0],
    "revenue_cagr_3y": [0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.06, 0.05, 0.03, 0.01],
    "net_margin": [0.25, 0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.06, 0.04, 0.02],
    "momentum_12m_1m": [0.30, 0.20, 0.15, 0.10, 0.05, 0.0, -0.05, -0.10, -0.15, -0.20],
    "div_yield": [1.0] * 10,
})

PORT_SCORES_FOR_NIFTY = pd.Series({
    "value": 0.5,
    "quality": 0.8,
    "momentum": 0.3,
    "size": -0.5,
    "growth": 0.4,
    "profitability": 0.6,
})

def test_compute_nifty500_percentile_scores_returns_series():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        NIFTY_SNAPSHOT.to_csv(f.name, index=False)
        path = f.name
    try:
        result = compute_nifty500_percentile_scores(PORT_SCORES_FOR_NIFTY, path)
        assert isinstance(result, pd.Series)
    finally:
        os.unlink(path)

def test_compute_nifty500_percentile_scores_has_6_dimensions():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        NIFTY_SNAPSHOT.to_csv(f.name, index=False)
        path = f.name
    try:
        result = compute_nifty500_percentile_scores(PORT_SCORES_FOR_NIFTY, path)
        for dim in ["value", "quality", "momentum", "size", "growth", "profitability"]:
            assert dim in result.index, f"Missing dimension: {dim}"
    finally:
        os.unlink(path)

def test_compute_nifty500_percentile_scores_in_0_to_100():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        NIFTY_SNAPSHOT.to_csv(f.name, index=False)
        path = f.name
    try:
        result = compute_nifty500_percentile_scores(PORT_SCORES_FOR_NIFTY, path)
        assert result.between(0, 100).all(), f"Values out of range: {result.values}"
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_scorer.py::test_compute_nifty500_percentile_scores_returns_series -v
```

Expected: ImportError — function not yet defined.

- [ ] **Step 3: Implement `compute_nifty500_percentile_scores`**

Append to `factors/scorer.py`:

```python
def compute_nifty500_percentile_scores(
    port_scores: pd.Series,
    nifty500_snapshot_path: str,
) -> pd.Series:
    """Rank portfolio style scores vs Nifty 500 universe distribution.

    Loads the Nifty 500 snapshot, computes style z-scores for that universe,
    then finds where each portfolio dimension score falls in the resulting
    cross-sectional distribution (0 = bottom, 100 = top).

    Args:
        port_scores: Series of weighted portfolio z-scores (from compute_portfolio_scores),
                     indexed by dimension name.
        nifty500_snapshot_path: Path to CSV with Nifty 500 fundamentals.
    Returns:
        Series indexed by dimension with percentile ranks 0–100.
    """
    dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
    try:
        nifty_df = pd.read_csv(nifty500_snapshot_path)
    except Exception:
        return pd.Series(50.0, index=dims)  # neutral fallback

    # Ensure required columns present; fill missing with defaults
    for col in ["momentum_12m_1m", "net_margin", "revenue_cagr_3y"]:
        if col not in nifty_df.columns:
            nifty_df[col] = 0.0

    nifty_scores = compute_style_scores(nifty_df)
    nifty_indexed = nifty_scores.set_index("ticker")[dims]

    percentiles = {}
    for dim in dims:
        universe = nifty_indexed[dim].dropna().values
        if len(universe) == 0:
            percentiles[dim] = 50.0
            continue
        score = port_scores.get(dim, 0.0)
        pct = float(np.mean(universe < score) * 100)
        percentiles[dim] = round(pct, 1)

    return pd.Series(percentiles)
```

- [ ] **Step 4: Run all scorer tests**

```bash
python -m pytest tests/test_scorer.py -v
```

Expected: All tests PASS (original 7 + new 3 = 10 total).

- [ ] **Step 5: Commit**

```bash
git add factors/scorer.py tests/test_scorer.py
git commit -m "feat: add compute_nifty500_percentile_scores helper"
```

---

### Task 3: Tab 5 — Update Imports, Tab List, Section A (Cards + Narrative)

**Files:**
- Modify: `dashboard/app.py`

- [ ] **Step 1: Update imports and tab definition**

In `dashboard/app.py`, replace:

```python
from factors.regression import build_portfolio_returns, run_carhart_regression
```

with:

```python
from factors.regression import build_portfolio_returns, run_carhart_regression, rolling_carhart_betas, factor_return_attribution
```

Replace:

```python
from factors.scorer import compute_style_scores, compute_portfolio_scores
```

with:

```python
from factors.scorer import compute_style_scores, compute_portfolio_scores, compute_nifty500_percentile_scores
```

Replace:

```python
tab1, tab2, tab3, tab4 = st.tabs([
    "Portfolio Overview",
    "Factor Regression",
    "Style Scorecard",
    "Stock Deep-Dive",
])
```

with:

```python
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Portfolio Overview",
    "Factor Regression",
    "Style Scorecard",
    "Stock Deep-Dive",
    "Portfolio Profile",
])
```

- [ ] **Step 2: Add Tab 5 Section A — metric cards and narrative**

Append to `dashboard/app.py` after the `with tab4:` block:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Portfolio Profile
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Portfolio Profile")

    # Guard: needs regression result from Tab 2
    if "reg_result" not in dir() or "port_scores" not in dir():
        st.warning("Run the Factor Regression tab first — Tab 5 depends on those results.")
        st.stop()

    # ── Section A: Summary Cards ───────────────────────────────────────────────
    st.markdown("### Executive Summary")

    factors_display = ["mkt_rf", "smb", "hml", "wml"]
    factor_labels = {
        "mkt_rf": "Market (Rm-Rf)", "smb": "Size (SMB)",
        "hml": "Value (HML)", "wml": "Momentum (WML)"
    }

    # Dominant factor: highest |beta| among significant factors (p < 0.05)
    sig_factors = {f: reg_result["betas"][f] for f in factors_display
                   if reg_result["p_values"][f] < 0.05}
    if sig_factors:
        dominant_f = max(sig_factors, key=lambda f: abs(sig_factors[f]))
        dominant_label = f"{factor_labels[dominant_f]} (β={sig_factors[dominant_f]:.2f})"
    else:
        dominant_label = "None (p>0.05)"

    # HHI and Effective N
    hhi = (portfolio["weight"] ** 2).sum()
    effective_n = 1 / hhi if hhi > 0 else len(portfolio)

    # Top style tilt
    dims_6 = ["value", "quality", "momentum", "size", "growth", "profitability"]
    top_dim = port_scores[dims_6].abs().idxmax()
    top_score = port_scores[top_dim]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Dominant Factor", dominant_label)
    c2.metric("Alpha (monthly)", f"{reg_result['alpha']*100:.3f}%",
              f"t = {reg_result['alpha_t']:.2f}")
    c3.metric("R²", f"{reg_result['r_squared']:.3f}")
    c4.metric("Top Style Tilt", f"{top_dim.capitalize()} ({top_score:+.2f})")
    c5.metric("Portfolio HHI", f"{hhi:.4f}")
    c6.metric("Effective N", f"{effective_n:.1f}")

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
            sig_tilts.append(f"{direction} {factor_labels[f]} tilt (β={b:.2f})")

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

    narrative = (
        f"This portfolio carries {mkt_desc}. "
    )
    if sig_tilts:
        narrative += "Statistically significant factor tilts include: " + "; ".join(sig_tilts) + ". "
    else:
        narrative += "No other factor tilts are statistically significant at the 5% level. "
    if style_desc_parts:
        narrative += "Style analysis shows a " + " and ".join(style_desc_parts) + ". "
    narrative += size_note

    st.info(f"*{narrative}*")
```

- [ ] **Step 3: Verify app starts without error**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python -c "import ast, sys; ast.parse(open('dashboard/app.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: tab5 section A — metric cards and auto-narrative"
```

---

### Task 4: Tab 5 — Section B (Investment Memo Expanders)

**Files:**
- Modify: `dashboard/app.py`

- [ ] **Step 1: Add Section B — three expanders**

Append inside the `with tab5:` block (after the narrative `st.info()` call) in `dashboard/app.py`:

```python
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
        for f in factors_display:
            b = reg_result["betas"][f]
            t = reg_result["t_stats"][f]
            p = reg_result["p_values"][f]
            sig = p < 0.05
            memo_rows.append({
                "Factor": factor_labels[f],
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

        # Radar chart (larger)
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

        # Ranked table
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
        # Stock concentration
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
            st.metric("HHI", f"{hhi:.4f}", hhi_label)
            st.metric("Effective N", f"{effective_n:.1f}")
            st.metric("Top 5 Holdings Weight", f"{top5_weight:.1f}%")

        with rc2:
            st.markdown("**Sector Concentration**")
            st.metric("Sector HHI", f"{sector_hhi:.4f}")
            for _, row in top2_sectors.iterrows():
                st.metric(row["sector"], f"{row['weight']*100:.1f}%")

        # Factor R² pie chart
        st.markdown("**Factor R² Breakdown**")
        port_excess_var = None
        try:
            factors_idx = iima_factors.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
            aligned_p, aligned_f = port_returns.align(factors_idx, join="inner")
            port_excess_series = aligned_p - aligned_f["rf"]
            port_var = port_excess_series.var()

            factor_stds = {
                f: aligned_f[f].std() for f in ["mkt_rf", "smb", "hml", "wml"]
            }
            factor_variances = {
                f: (reg_result["betas"][f] * factor_stds[f]) ** 2
                for f in ["mkt_rf", "smb", "hml", "wml"]
            }
            residual_share = max(0.0, 1 - reg_result["r_squared"])
            total_explained = sum(factor_variances.values())
            if port_var > 0 and total_explained > 0:
                pie_labels = [factor_labels[f] for f in ["mkt_rf", "smb", "hml", "wml"]] + ["Residual"]
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
```

- [ ] **Step 2: Syntax check**

```bash
python -c "import ast; ast.parse(open('dashboard/app.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: tab5 section B — factor tilts, style characteristics, risk profile expanders"
```

---

### Task 5: Tab 5 — Section C (4 Quantitative Charts)

**Files:**
- Modify: `dashboard/app.py`

- [ ] **Step 1: Add Section C — 4 charts**

Append inside the `with tab5:` block (after the risk profile expander) in `dashboard/app.py`:

```python
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
            fig_roll = go.Figure()
            roll_colors = {
                "mkt_rf": "#3498db", "smb": "#2ecc71",
                "hml": "#e67e22", "wml": "#9b59b6"
            }
            for f in ["mkt_rf", "smb", "hml", "wml"]:
                fig_roll.add_trace(go.Scatter(
                    x=valid_rolling.index,
                    y=valid_rolling[f],
                    name=factor_labels[f],
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
            "alpha": "#f39c12",
            "mkt_rf": "#3498db",
            "smb": "#2ecc71",
            "hml": "#e67e22",
            "wml": "#9b59b6",
            "residual": "#95a5a6",
        }
        attr_labels = {
            "alpha": "Alpha",
            "mkt_rf": "Market",
            "smb": "SMB",
            "hml": "HML",
            "wml": "WML",
            "residual": "Residual",
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
```

- [ ] **Step 2: Syntax check**

```bash
python -c "import ast; ast.parse(open('dashboard/app.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: Run all tests to confirm nothing broken**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass (14 regression + 10 scorer + integration/fetcher tests).

- [ ] **Step 4: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: tab5 section C — rolling betas, attribution, percentile, weight distribution charts"
```

- [ ] **Step 5: Push to GitHub**

```bash
git push origin main
```

Expected: Push succeeds. Streamlit Cloud auto-deploys.

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| 6 metric cards (Dominant Factor, Alpha, R², Top Style Tilt, HHI, Effective N) | Task 3 |
| Auto-generated narrative paragraph in st.info | Task 3 |
| Expander 1: Factor Tilts table with interpretations | Task 4 |
| Expander 2: Larger radar + ranked table with Nifty 500 percentile | Task 4 |
| Expander 3: Stock concentration, sector concentration, factor R² pie | Task 4 |
| Chart 1: Rolling factor betas with 12M/24M/36M selector | Task 5 |
| Chart 2: Factor return attribution stacked bar | Task 5 |
| Chart 3: Style score vs Nifty 500 percentile horizontal bar | Task 5 |
| Chart 4: Weight distribution bar + cumulative line | Task 5 |
| `rolling_carhart_betas()` in factors/regression.py | Task 1 |
| `factor_return_attribution()` in factors/regression.py | Task 1 |
| `compute_nifty500_percentile_scores()` in factors/scorer.py | Task 2 |

All requirements covered. No gaps found.

### Placeholder Scan

No TBD, TODO, or incomplete sections present.

### Type Consistency

- `rolling_carhart_betas` returns DataFrame with columns `mkt_rf, smb, hml, wml` — Task 5 accesses `valid_rolling[f]` for `f in ["mkt_rf", "smb", "hml", "wml"]` ✓
- `factor_return_attribution` returns DataFrame with columns `alpha, mkt_rf, smb, hml, wml, residual` — Task 5 iterates same list ✓
- `compute_nifty500_percentile_scores` returns Series indexed by dimension name — Task 4 calls `nifty_pct.get(d, 50.0)` ✓
- `nifty_pct` is defined in Expander 2 (Task 4) and reused in Chart 3 (Task 5) — both are inside `with tab5:` so scope is shared ✓
- `reg_result`, `port_returns`, `iima_factors`, `port_scores` all available from Tab 2/3 computation ✓
