"""
Integration smoke test: runs the full pipeline end-to-end with cached data.
Requires: cache populated (run dashboard once or call refresh first).
Skip if cache is missing (CI-safe).
"""
import pytest
import pandas as pd
from pathlib import Path
from data.cache_manager import CACHE_DIR, is_stale
from data.portfolio import load_portfolio
from data.fetcher import fetch_iima_factors
from factors.scorer import compute_style_scores, compute_portfolio_scores
from factors.regression import run_carhart_regression

PORTFOLIO_PATH = Path(__file__).parent.parent / "portfolio.xlsx"

@pytest.fixture(scope="module")
def portfolio():
    return load_portfolio(str(PORTFOLIO_PATH))

@pytest.fixture(scope="module")
def iima_factors():
    cache = CACHE_DIR / "iima_factors.parquet"
    if is_stale(cache):
        pytest.skip("IIMA cache not populated; run dashboard first")
    return fetch_iima_factors(force_refresh=False)

def test_portfolio_loads_correctly(portfolio):
    assert len(portfolio) == 33
    assert abs(portfolio["weight"].sum() - 1.0) < 0.001

def test_iima_factors_have_all_columns(iima_factors):
    for col in ["date", "mkt_rf", "smb", "hml", "wml", "rf"]:
        assert col in iima_factors.columns

def test_iima_factors_sufficient_history(iima_factors):
    # At least 5 years of monthly data = 60 rows
    assert len(iima_factors) >= 60

def test_style_scorer_runs_on_minimal_data(portfolio):
    # Minimal fundamentals with required columns
    fundamentals = pd.DataFrame({
        "ticker": portfolio["ticker"].tolist(),
        "pe": [20.0] * 33,
        "pb": [2.0] * 33,
        "roe": [15.0] * 33,
        "roce": [18.0] * 33,
        "de": [0.5] * 33,
        "market_cap_cr": [10000.0] * 33,
        "momentum_12m_1m": [0.1] * 33,
        "revenue_cagr_3y": [0.1] * 33,
        "net_margin": [0.15] * 33,
    })
    scores = compute_style_scores(fundamentals)
    assert len(scores) == 33
    weights = portfolio.set_index("ticker")["weight"]
    port_scores = compute_portfolio_scores(scores, weights)
    assert len(port_scores) == 6
