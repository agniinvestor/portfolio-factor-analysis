import numpy as np
import pandas as pd
import pytest
from factors.regression import build_portfolio_returns, run_carhart_regression

# Synthetic data: 36 months
np.random.seed(42)
N = 36
DATES = pd.date_range("2023-01-01", periods=N, freq="ME")
FACTORS = pd.DataFrame({
    "date":   DATES,
    "mkt_rf": np.random.normal(0.008, 0.04, N),
    "smb":    np.random.normal(0.001, 0.02, N),
    "hml":    np.random.normal(0.002, 0.02, N),
    "wml":    np.random.normal(0.003, 0.03, N),
    "rf":     np.full(N, 0.005),
})

# Portfolio returns: ~0.6 * mkt_rf + noise (true beta = 0.6)
PORT_RETURNS = pd.Series(
    0.6 * FACTORS["mkt_rf"].values + np.random.normal(0, 0.01, N),
    index=DATES,
    name="portfolio"
)

def test_run_carhart_regression_returns_dict():
    result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    assert isinstance(result, dict)

def test_regression_result_has_required_keys():
    result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    for key in ["alpha", "betas", "t_stats", "p_values", "r_squared", "n_obs"]:
        assert key in result, f"Missing key: {key}"

def test_regression_betas_keys():
    result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    for factor in ["mkt_rf", "smb", "hml", "wml"]:
        assert factor in result["betas"]

def test_regression_recovers_market_beta_approximately():
    result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    mkt_beta = result["betas"]["mkt_rf"]
    assert 0.3 < mkt_beta < 0.9, f"Market beta {mkt_beta} not close to true 0.6"

def test_regression_r_squared_between_0_and_1():
    result = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    assert 0.0 <= result["r_squared"] <= 1.0

def test_regression_window_1yr_uses_fewer_observations():
    r3 = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=3)
    r1 = run_carhart_regression(PORT_RETURNS, FACTORS, window_years=1)
    assert r1["n_obs"] < r3["n_obs"]

def test_build_portfolio_returns_weighted_correctly():
    stock_returns = pd.DataFrame({
        "A": [0.10, 0.20],
        "B": [0.30, 0.40],
    }, index=pd.date_range("2023-01-01", periods=2, freq="ME"))
    weights = {"A": 0.6, "B": 0.4}
    result = build_portfolio_returns(stock_returns, weights)
    assert abs(result.iloc[0] - (0.6 * 0.10 + 0.4 * 0.30)) < 1e-9
