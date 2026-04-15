# GUI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate the dashboard to a client-ready screen-share tool by applying a light minimal theme, reordering tabs to match the client conversation flow, adding a sidebar portfolio summary panel, and replacing `st.info()` narrative blocks with styled callout cards.

**Architecture:** Four independent changes to `dashboard/app.py` plus a new `config.toml`. A shared computation block is extracted before the tab declarations so both the sidebar panel and reordered tabs can access `reg_result`, `port_scores`, `hhi`, and `effective_n`. The tab variable names are changed from positional (`tab1`–`tab6`) to semantic (`tab_macro`, `tab_profile`, etc.) to make the reordering explicit.

**Tech Stack:** Python 3.11, Streamlit (stock primitives only — no new packages), Plotly.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `.streamlit/config.toml` | Create | Light theme colours and font |
| `dashboard/app.py` | Modify | Shared computation block, sidebar panel, tab reorder, callout helper |

---

### Task 1: Create `.streamlit/config.toml` with light theme

**Files:**
- Create: `.streamlit/config.toml`

- [ ] **Step 1: Write the config file**

```toml
[theme]
base                     = "light"
backgroundColor          = "#FFFFFF"
secondaryBackgroundColor = "#F7F9FC"
textColor                = "#1C2B3A"
primaryColor             = "#1A3A5C"
font                     = "sans serif"
```

- [ ] **Step 2: Verify Streamlit picks it up**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python3 -c "import toml; cfg = toml.load('.streamlit/config.toml'); print(cfg['theme']['primaryColor'])"
```

Expected output: `#1A3A5C`

If `toml` is not installed, verify by reading the file directly:

```bash
cat .streamlit/config.toml
```

Expected: file content matches what was written.

- [ ] **Step 3: Commit**

```bash
git add .streamlit/config.toml
git commit -m "feat: add light minimal theme to config.toml"
```

---

### Task 2: Extract shared computation block in `dashboard/app.py`

**Files:**
- Modify: `dashboard/app.py`

**Context:** Currently `get_all_prices`, `stock_returns_df`, `port_returns`, `reg_result` are computed inside `with tab2:` (Factor Regression). `style_scores`, `port_scores` are computed inside `with tab3:`. `hhi`, `effective_n` are computed inside `with tab5:`. The sidebar needs `reg_result` and `effective_n`, and tab reordering needs all of these available before any tab block runs.

- [ ] **Step 1: Remove computation from inside `with tab2:` block**

Find and remove these lines from inside the `with tab2:` block (they appear after `if iima_factors.empty: ... else:`):

```python
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
```

Replace the entire `if iima_factors.empty: ... else:` guard in tab2 with just:

```python
    if iima_factors.empty or reg_result is None:
        st.info("IIMA factor data is currently unavailable (source unreachable). This tab will populate once the data source is back online.")
    else:
        if stock_returns_df.empty:
            st.warning("No price data available. Click Refresh Data to fetch.")
        else:
```

Keep everything from `factors_display = ...` onwards inside the `else:` block unchanged.

- [ ] **Step 2: Remove computation from inside `with tab3:` block**

Find and remove these lines from the top of the `with tab3:` block:

```python
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
```

These will now live in the shared block (added in Step 4).

- [ ] **Step 3: Remove computation from inside `with tab5:` block**

Find and remove these lines from the top of the `with tab5:` else-block:

```python
        # HHI and Effective N
        hhi = (portfolio["weight"] ** 2).sum()
        effective_n = 1 / hhi if hhi > 0 else len(portfolio)
```

Also update the guard at the top of `with tab5:` from:

```python
    if iima_factors.empty or "reg_result" not in dir() or "port_scores" not in dir():
```

to:

```python
    if iima_factors.empty or reg_result is None:
```

- [ ] **Step 4: Insert shared computation block before the `st.tabs()` call**

Find the line:

```python
# ── Tabs ──────────────────────────────────────────────────────────────────────
```

Insert the following block IMMEDIATELY BEFORE that line:

```python
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

```

- [ ] **Step 5: Fix the `with tab3:` reference to `style_scores` in dir() guard**

In the old tab4 (Stock Deep-Dive), find:

```python
    if "style_scores" in dir():
```

Replace with:

```python
    if not stock_returns_df.empty:
```

- [ ] **Step 6: Fix the `with tab5:` reference to `nifty_pct` that was computed inside tab5**

`nifty_pct` is computed inside `with st.expander("Style Characteristics"):` in tab5 and referenced later in `with st.expander("Risk Profile"):` section — check that `nifty_pct` is still in scope (it is, since it's inside the same outer `if reg_result is not None:` block). No change needed here.

- [ ] **Step 7: Verify app imports without error**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python3 -c "import dashboard.app" 2>&1 | grep -i error
```

Expected: No output (no errors). Streamlit runtime warnings about browser are fine.

- [ ] **Step 8: Run tests**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add dashboard/app.py
git commit -m "refactor: lift shared computation block before tabs"
```

---

### Task 3: Add sidebar "Portfolio at a Glance" panel

**Files:**
- Modify: `dashboard/app.py`

**Context:** The shared computation block (Task 2) now makes `reg_result`, `hhi`, `effective_n` available before the tabs. A second `with st.sidebar:` block appended after the shared computation block will render below the existing controls.

- [ ] **Step 1: Add the sidebar panel block**

Find the line:

```python
# ── Shared computation (sidebar + multiple tabs) ──────────────────────────────
```

Insert the following block IMMEDIATELY AFTER the shared computation block ends (after `port_scores = compute_portfolio_scores(style_scores, weights_series)`) and BEFORE the `# ── Tabs ──` line:

```python
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

```

- [ ] **Step 2: Verify app imports without error**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python3 -c "import dashboard.app" 2>&1 | grep -i error
```

Expected: No output.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: add Portfolio at a Glance sidebar panel"
```

---

### Task 4: Reorder and rename tabs

**Files:**
- Modify: `dashboard/app.py`

**Context:** Current order: Portfolio Overview, Factor Regression, Style Scorecard, Stock Deep-Dive, Portfolio Profile, Macro Regime. New order: Macro Regime, Portfolio Summary, Holdings, Factor Analysis, Style Scorecard, Stock Deep-Dive.

- [ ] **Step 1: Replace the `st.tabs()` call and variable names**

Find:

```python
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Portfolio Overview",
    "Factor Regression",
    "Style Scorecard",
    "Stock Deep-Dive",
    "Portfolio Profile",
    "Macro Regime",
])
```

Replace with:

```python
tab_macro, tab_profile, tab_holdings, tab_factor, tab_style, tab_deepdive = st.tabs([
    "Macro Regime",
    "Portfolio Summary",
    "Holdings",
    "Factor Analysis",
    "Style Scorecard",
    "Stock Deep-Dive",
])
```

- [ ] **Step 2: Rename the `with tabN:` block headers**

Make the following six replacements throughout the file (each block header comment + `with` line):

| Old | New |
|---|---|
| `# TAB 1 — Portfolio Overview` | `# TAB: Holdings` |
| `with tab1:` | `with tab_holdings:` |
| `# TAB 2 — Factor Regression` | `# TAB: Factor Analysis` |
| `with tab2:` | `with tab_factor:` |
| `# TAB 3 — Style Scorecard` | `# TAB: Style Scorecard` |
| `with tab3:` | `with tab_style:` |
| `# TAB 4 — Stock Deep-Dive` | `# TAB: Stock Deep-Dive` |
| `with tab4:` | `with tab_deepdive:` |
| `# TAB 5 — Portfolio Profile` | `# TAB: Portfolio Summary` |
| `with tab5:` | `with tab_profile:` |
| `# TAB 6 — Macro Regime` | `# TAB: Macro Regime` |
| `with tab6:` | `with tab_macro:` |

- [ ] **Step 3: Reorder the `with tab_x:` blocks in the file**

Currently the blocks appear in this order in the file: tab_holdings, tab_factor, tab_style, tab_deepdive, tab_profile, tab_macro.

Reorder them to: tab_macro, tab_profile, tab_holdings, tab_factor, tab_style, tab_deepdive.

Move the entire `# TAB: Macro Regime` block (from its comment line to the last line `tab_macro_regime.render(signals, force_refresh=macro_refresh)`) to appear first among the tab blocks.

Move the entire `# TAB: Portfolio Summary` block (from its comment line to the closing of the `with tab_profile:` block at the `st.plotly_chart(fig_weights...)` line) to appear second.

The remaining four blocks stay in their relative order: Holdings, Factor Analysis, Style Scorecard, Stock Deep-Dive.

- [ ] **Step 4: Update the subheader inside Portfolio Summary tab**

Find inside `with tab_profile:`:

```python
    st.subheader("Portfolio Profile")
```

Replace with:

```python
    st.subheader("Portfolio Summary")
```

- [ ] **Step 5: Verify app imports without error**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python3 -c "import dashboard.app" 2>&1 | grep -i error
```

Expected: No output.

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: reorder tabs to client-facing flow (Macro Regime first)"
```

---

### Task 5: Add `_callout()` helper and replace `st.info()` narrative blocks

**Files:**
- Modify: `dashboard/app.py`

**Context:** Two `st.info()` calls carry auto-generated narrative text that should render as styled insight cards rather than system alerts. The `narrative` string uses `**bold**` markdown syntax, which must be converted to `<b>bold</b>` HTML before passing to the HTML div.

- [ ] **Step 1: Add `_callout()` helper function**

Find the line:

```python
PORTFOLIO_PATH = Path(__file__).parent.parent / "portfolio.xlsx"
```

Add immediately after it:

```python

def _callout(text: str) -> None:
    """Render a styled insight card with a navy left border."""
    st.markdown(
        f'<div style="border-left:4px solid #1A3A5C;background:#F7F9FC;'
        f'padding:12px 16px;border-radius:0 6px 6px 0;font-size:15px;'
        f'line-height:1.6;margin:8px 0;">{text}</div>',
        unsafe_allow_html=True,
    )

```

- [ ] **Step 2: Replace `st.info()` in Factor Analysis tab**

Inside `with tab_factor:`, find:

```python
            if tilts:
                st.info("**Significant factor tilts:** " + ", ".join(tilts) + ".")
            else:
                st.info("No statistically significant factor tilts detected at 5% level.")
```

Replace with:

```python
            if tilts:
                _callout("<b>Significant factor tilts:</b> " + ", ".join(tilts) + ".")
            else:
                _callout("No statistically significant factor tilts detected at 5% level.")
```

- [ ] **Step 3: Replace `st.info()` in Portfolio Summary tab**

Inside `with tab_profile:`, find:

```python
        st.info(f"*{narrative}*")
```

The `narrative` string contains `**bold**` markdown markers from `mkt_desc` and `size_note`. First, add `import re` to the imports block at the top of `app.py` (after the existing stdlib imports if not already present). Then replace the `st.info` call with:

```python
        narrative_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', narrative)
        _callout(narrative_html)
```

- [ ] **Step 4: Verify app imports without error**

```bash
cd /home/ubuntu/claude_projects/portfolio_factor_analysis
python3 -c "import dashboard.app" 2>&1 | grep -i error
```

Expected: No output.

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 6: Commit and push**

```bash
git add dashboard/app.py
git commit -m "feat: add _callout() helper and replace st.info() narrative blocks"
git push
```
