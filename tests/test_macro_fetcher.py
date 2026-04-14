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
