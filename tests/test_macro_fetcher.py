"""Tests for data.macro_fetcher pure helpers and lookup tables."""
import pytest

from data import macro_fetcher as mf


class TestRegimeMap:
    def test_all_8_combinations_present(self):
        assert len(mf.REGIME_MAP) == 8

    def test_goldilocks(self):
        label, color = mf.REGIME_MAP[("falling", "expanding", "falling")]
        assert label == "Goldilocks"
        assert color == "#27ae60"

    def test_stagflation(self):
        label, _ = mf.REGIME_MAP[("rising", "contracting", "rising")]
        assert label == "Stagflation"

    @pytest.mark.parametrize("key,expected_label", [
        (("rising",  "expanding",   "rising"),   "Overheating"),
        (("falling", "contracting", "falling"),  "Deflation / Bust"),
        (("rising",  "expanding",   "falling"),  "Recovery / Tightening"),
        (("falling", "contracting", "rising"),   "Stagflation-Lite"),
        (("rising",  "contracting", "falling"),  "Recession / Tightening"),
        (("falling", "expanding",   "rising"),   "Reflation"),
    ])
    def test_all_regime_labels(self, key, expected_label):
        label, _ = mf.REGIME_MAP[key]
        assert label == expected_label


class TestFactorMatrix:
    def test_all_regimes_covered(self):
        expected = {
            "Goldilocks", "Overheating", "Stagflation", "Deflation / Bust",
            "Recovery / Tightening", "Stagflation-Lite",
            "Recession / Tightening", "Reflation",
        }
        assert set(mf.FACTOR_MATRIX.keys()) == expected

    def test_every_regime_has_7_factors(self):
        factors = {"Mkt Beta", "Size", "Value", "Momentum", "Quality", "Low Vol", "Growth"}
        for regime, row in mf.FACTOR_MATRIX.items():
            assert set(row.keys()) == factors, regime

    def test_symbols_valid(self):
        for regime, row in mf.FACTOR_MATRIX.items():
            for factor, sym in row.items():
                assert sym in {"●", "○", "✕"}, (regime, factor, sym)


class TestDetermineRegime:
    def test_known_triple(self):
        label, color = mf._determine_regime("falling", "expanding", "falling")
        assert label == "Goldilocks"
        assert color == "#27ae60"

    def test_unknown_returns_unknown(self):
        label, color = mf._determine_regime("unknown", "expanding", "falling")
        assert label == "Unknown"
        assert color == "#7f8c8d"

    def test_all_three_unknown(self):
        label, color = mf._determine_regime("unknown", "unknown", "unknown")
        assert label == "Unknown"
        assert color == "#7f8c8d"


class TestFactorRecommendations:
    def test_goldilocks_favored(self):
        favored, avoided = mf._get_factor_recommendations("Goldilocks")
        assert "Mkt Beta" in favored
        assert "Growth" in favored
        assert "Low Vol" in avoided

    def test_unknown_regime_returns_empty(self):
        favored, avoided = mf._get_factor_recommendations("Unknown")
        assert favored == []
        assert avoided == []

    def test_stagflation(self):
        favored, avoided = mf._get_factor_recommendations("Stagflation")
        assert "Quality" in favored
        assert "Low Vol" in favored
        assert "Mkt Beta" in avoided

    def test_goldilocks_neutral_not_in_favored_or_avoided(self):
        favored, avoided = mf._get_factor_recommendations("Goldilocks")
        # Value is ○ (Neutral) in Goldilocks — must not appear in either list
        assert "Value" not in favored
        assert "Value" not in avoided


class TestSignalArrow:
    def test_rising(self):
        assert mf._signal_arrow("rising") == "↑"

    def test_expanding(self):
        assert mf._signal_arrow("expanding") == "↑"

    def test_falling(self):
        assert mf._signal_arrow("falling") == "↓"

    def test_contracting(self):
        assert mf._signal_arrow("contracting") == "↓"

    def test_unknown(self):
        assert mf._signal_arrow("unknown") == "?"

    def test_arbitrary_string_returns_question_mark(self):
        assert mf._signal_arrow("anything_else") == "?"


import pandas as pd


class TestFetchRatesSignal:
    def test_rising_when_yield_up(self, monkeypatch):
        """Yield today > yield 3 months ago -> rising."""
        idx = pd.date_range("2026-01-01", periods=90, freq="D")
        series = pd.Series(range(90), index=idx, dtype="float64")  # strictly increasing
        df = pd.DataFrame({"Close": series})

        class FakeTicker:
            def __init__(self, ticker): self.ticker = ticker
            def history(self, period="6mo", interval="1d"):
                return df

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_rates_signal("US", "^TNX") == "rising"

    def test_falling_when_yield_down(self, monkeypatch):
        idx = pd.date_range("2026-01-01", periods=90, freq="D")
        series = pd.Series(range(90, 0, -1), index=idx, dtype="float64")
        df = pd.DataFrame({"Close": series})

        class FakeTicker:
            def __init__(self, ticker): pass
            def history(self, period="6mo", interval="1d"):
                return df

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_rates_signal("US", "^TNX") == "falling"

    def test_empty_returns_unknown(self, monkeypatch):
        class FakeTicker:
            def __init__(self, ticker): pass
            def history(self, period="6mo", interval="1d"):
                return pd.DataFrame()

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_rates_signal("US", "^TNX") == "unknown"

    def test_exception_returns_unknown(self, monkeypatch):
        class FakeTicker:
            def __init__(self, ticker): pass
            def history(self, period="6mo", interval="1d"):
                raise RuntimeError("network down")

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_rates_signal("US", "^TNX") == "unknown"
