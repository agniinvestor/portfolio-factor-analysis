# GUI Polish — Design Spec

**Goal:** Elevate the dashboard from a developer tool to a client-ready screen-share presentation by applying a light minimal theme, reordering tabs to match the client conversation flow, adding a sidebar portfolio summary panel, and replacing `st.info()` narrative blocks with styled callout cards.

**Audience:** External clients — dashboard is screen-shared, not self-served.

**Constraint:** No new dependencies. All changes use stock Streamlit primitives and a `config.toml` theme file.

---

## 1. Theme — `.streamlit/config.toml`

Create/update `.streamlit/config.toml` with:

```toml
[theme]
base                = "light"
backgroundColor     = "#FFFFFF"
secondaryBackgroundColor = "#F7F9FC"
textColor           = "#1C2B3A"
primaryColor        = "#1A3A5C"
font                = "sans serif"
```

- `backgroundColor` — pure white canvas; removes the default grey
- `secondaryBackgroundColor` — very light grey for sidebar, expanders, metric cards
- `textColor` — near-black for readable body text
- `primaryColor` — deep navy for buttons, active tab indicator, links
- `font` — clean sans-serif (Streamlit default)

---

## 2. Tab Order and Labels

Reorder and rename all six tabs in `dashboard/app.py`:

| Position | Old name | New name |
|---|---|---|
| 1 | Macro Regime | Macro Regime |
| 2 | Portfolio Profile | Portfolio Summary |
| 3 | Portfolio Overview | Holdings |
| 4 | Factor Regression | Factor Analysis |
| 5 | Style Scorecard | Style Scorecard |
| 6 | Stock Deep-Dive | Stock Deep-Dive |

**Implementation note:** The tab variables (`tab1`…`tab6`) are positional — all code inside each `with tabN:` block moves with its tab. The data that Tab 4 (Factor Analysis) and Tab 2 (Portfolio Summary) share (`reg_result`, `port_scores`, `port_returns`) must be computed before either tab block renders. Currently these are computed inside Tab 2 and Tab 5 respectively. They must be lifted to a shared computation block before the tab blocks.

---

## 3. Sidebar "Portfolio at a Glance" Panel

Replace the current sparse sidebar (refresh button + slider only) with a mini-scorecard above the controls.

**Always-visible rows** (computed from `portfolio.xlsx`, no external data needed):
- Total Value — `₹{portfolio['value'].sum():,.0f}`
- Holdings — `{len(portfolio)} stocks`
- Top Sector — name + weight percentage of the largest sector by weight

**Conditionally visible rows** (shown only when IIMA data + regression result are available):
- Effective N — `{effective_n:.1f}`
- Alpha (monthly) — `{reg_result['alpha']*100:+.3f}%`

When IIMA data is not yet loaded, show a single `st.caption("Factor data loading…")` in place of the conditional rows.

**Layout:** Use `st.metric()` for each row — consistent with the rest of the dashboard. Divider line (`st.divider()`) separates the scorecard from the existing controls.

**Sequencing:** The sidebar scorecard block must reference `reg_result` and `effective_n`. Since these are computed inside the tab blocks, the sidebar must either (a) use `st.session_state` to store computed values, or (b) compute them in a shared block before the tabs. Option (b) is simpler — lift the shared computation block.

---

## 4. Styled Callout Boxes

Replace `st.info(text)` narrative calls with a reusable helper `_callout(text)` defined at the top of `app.py`:

```python
def _callout(text: str) -> None:
    st.markdown(
        f"""<div style="
            border-left: 4px solid #1A3A5C;
            background: #F7F9FC;
            padding: 12px 16px;
            border-radius: 0 6px 6px 0;
            font-size: 15px;
            line-height: 1.6;
            margin: 8px 0;
        ">{text}</div>""",
        unsafe_allow_html=True,
    )
```

**Applied to:**
- Tab 4 (Factor Analysis, formerly Tab 2): the significant factor tilts summary sentence
- Tab 2 (Portfolio Summary, formerly Tab 5): the executive narrative paragraph

**Not changed:** `st.warning()`, `st.error()`, `st.success()` — these are genuine status messages and should remain as-is.

**Note:** The narrative text currently uses `**bold**` markdown. Inside an HTML div, markdown is not rendered — bold must be expressed as `<b>text</b>` HTML tags. The narrative generation code must be updated accordingly.

---

## 5. Shared Computation Block

To support both the sidebar panel and the reordered tabs, a shared computation block is needed before the tab declarations. This block computes:

- `stock_returns_df` — fetched via `get_all_prices()` (currently inside Tab 2, moved here)
- `port_returns` — portfolio monthly returns (from prices + weights)
- `reg_result` — Carhart regression result dict
- `hhi` — sum of squared weights
- `effective_n` — 1 / hhi
- `port_scores` — portfolio-level style scores (requires style_scores from Tab 3 scorer — compute here too)

These are only computed when the prerequisite data is available (`not iima_factors.empty` and `not stock_returns_df.empty`). If unavailable, these variables are set to `None` and each tab guards against `None` with its existing empty-state message.

---

## Files Modified

| File | Change |
|---|---|
| `.streamlit/config.toml` | Create/update with light theme |
| `dashboard/app.py` | Tab reorder, sidebar panel, `_callout()` helper, shared computation block |

No new files beyond `config.toml`. No new dependencies.

---

## Out of Scope

- Chart colour palette unification (Option C — deferred)
- Metric card CSS injection (Option C — deferred)
- Table column config styling (Option C — deferred)
- Macro Regime card HTML redesign (Option C — deferred)
