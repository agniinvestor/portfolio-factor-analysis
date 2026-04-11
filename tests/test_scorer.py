import pytest
import numpy as np
import pandas as pd
from factors.scorer import compute_style_scores, compute_portfolio_scores

SAMPLE_FUNDAMENTALS = pd.DataFrame({
    "ticker": ["A", "B", "C"],
    "pe":     [10.0, 20.0, 30.0],
    "pb":     [1.0,  2.0,  3.0],
    "roe":    [20.0, 15.0, 10.0],
    "roce":   [25.0, 18.0, 12.0],
    "de":     [0.1,  0.5,  1.2],
    "market_cap_cr": [10000.0, 5000.0, 1000.0],
    "momentum_12m_1m": [0.20, 0.05, -0.10],
    "revenue_cagr_3y": [0.15, 0.10, 0.05],
    "net_margin":      [0.20, 0.15, 0.08],
})

def test_compute_style_scores_returns_dataframe():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    assert isinstance(scores, pd.DataFrame)

def test_compute_style_scores_has_6_dimension_columns():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    for dim in ["value", "quality", "momentum", "size", "growth", "profitability"]:
        assert dim in scores.columns, f"Missing dimension: {dim}"

def test_compute_style_scores_z_scores_mean_near_zero():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    for dim in ["value", "quality", "momentum", "size", "growth", "profitability"]:
        assert abs(scores[dim].mean()) < 1e-10, f"Mean not zero for {dim}"

def test_compute_portfolio_scores_returns_series():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    weights = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    port_scores = compute_portfolio_scores(scores, weights)
    assert isinstance(port_scores, pd.Series)

def test_compute_portfolio_scores_has_correct_dimensions():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    weights = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    port_scores = compute_portfolio_scores(scores, weights)
    for dim in ["value", "quality", "momentum", "size", "growth", "profitability"]:
        assert dim in port_scores.index

def test_higher_roe_gives_higher_quality_score():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    scores_indexed = scores.set_index("ticker")
    # Stock A has highest ROE (20%), should have highest quality score
    assert scores_indexed.loc["A", "quality"] > scores_indexed.loc["C", "quality"]

def test_lower_pe_gives_higher_value_score():
    scores = compute_style_scores(SAMPLE_FUNDAMENTALS)
    scores_indexed = scores.set_index("ticker")
    # Stock A has lowest P/E (10), should have highest value score
    assert scores_indexed.loc["A", "value"] > scores_indexed.loc["C", "value"]
