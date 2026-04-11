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
