import pytest
from data.ticker_map import get_ticker, load_ticker_map

def test_known_ticker_returns_correctly():
    assert get_ticker("INE040A01034") == "HDFCBANK"

def test_unknown_isin_raises():
    with pytest.raises(KeyError):
        get_ticker("INVALID_ISIN")

def test_all_33_holdings_mapped():
    mapping = load_ticker_map()
    portfolio_isins = [
        "INE040A01034", "INE752E01010", "INE522F01014", "INE090A01021",
        "INE154A01025", "INE118A01012", "INE237A01036", "INE101A01026",
        "INE860A01027", "INE238A01034", "INE397D01024", "INE585B01010",
        "INE009A01021", "INE467B01029", "INE089A01031", "INE010B01027",
        "INE059A01026", "INE768C01028", "INE022Q01020", "INE126A01031",
        "INE787D01026", "INE410P01011", "INE017A01032", "INE736A01011",
        "INE925R01014", "INE725G01011", "INE288A01013", "INE121J01017",
        "INE536H01010", "INE277A01016", "INE317F01035", "INE203G01027",
        "INE002S01010",
    ]
    for isin in portfolio_isins:
        assert isin in mapping, f"Missing ticker for ISIN {isin}"

import pandas as pd
from data.portfolio import load_portfolio

def test_load_portfolio_returns_dataframe():
    df = load_portfolio("portfolio.xlsx")
    assert isinstance(df, pd.DataFrame)

def test_load_portfolio_has_required_columns():
    df = load_portfolio("portfolio.xlsx")
    assert set(["name", "isin", "sector", "weight", "value"]).issubset(df.columns)

def test_load_portfolio_weights_sum_to_one():
    df = load_portfolio("portfolio.xlsx")
    assert abs(df["weight"].sum() - 1.0) < 0.001

def test_load_portfolio_has_33_rows():
    df = load_portfolio("portfolio.xlsx")
    assert len(df) == 33

def test_load_portfolio_adds_ticker_column():
    df = load_portfolio("portfolio.xlsx")
    assert "ticker" in df.columns
    assert df["ticker"].notna().all()

import time
from pathlib import Path
from data.cache_manager import is_stale, write_cache, read_cache

def test_missing_cache_is_stale(tmp_path):
    assert is_stale(tmp_path / "nonexistent.parquet") is True

def test_fresh_cache_is_not_stale(tmp_path):
    p = tmp_path / "test.parquet"
    df = pd.DataFrame({"a": [1, 2]})
    write_cache(df, p)
    assert is_stale(p, max_age_hours=24) is False

def test_write_and_read_roundtrip(tmp_path):
    p = tmp_path / "test.parquet"
    df = pd.DataFrame({"x": [1.0, 2.0], "y": ["a", "b"]})
    write_cache(df, p)
    result = read_cache(p)
    pd.testing.assert_frame_equal(result, df)

from unittest.mock import patch, MagicMock
from data.fetcher import parse_iima_csv

SAMPLE_IIMA_CSV = """year,month,Mkt-RF,SMB,HML,WML,RF
2023,1,2.5,-0.3,1.1,0.8,0.5
2023,2,-1.2,0.4,-0.6,1.2,0.5
2023,3,3.1,0.1,0.9,-0.5,0.5
"""

def test_parse_iima_csv_returns_dataframe():
    df = parse_iima_csv(SAMPLE_IIMA_CSV)
    assert isinstance(df, pd.DataFrame)

def test_parse_iima_csv_has_date_index():
    df = parse_iima_csv(SAMPLE_IIMA_CSV)
    assert "date" in df.columns
    assert df["date"].dtype == "datetime64[ns]"

def test_parse_iima_csv_has_factor_columns():
    df = parse_iima_csv(SAMPLE_IIMA_CSV)
    for col in ["mkt_rf", "smb", "hml", "wml", "rf"]:
        assert col in df.columns, f"Missing column: {col}"

def test_parse_iima_csv_converts_percent_to_decimal():
    df = parse_iima_csv(SAMPLE_IIMA_CSV)
    # Values in CSV are percentages (e.g. 2.5 means 2.5%), stored as decimals (0.025)
    assert abs(df.iloc[0]["mkt_rf"] - 0.025) < 1e-6
