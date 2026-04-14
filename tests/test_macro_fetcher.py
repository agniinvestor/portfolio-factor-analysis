"""Tests for data.macro_fetcher pure helpers and lookup tables."""
import pytest
import pandas as pd

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


class TestFetchRatesSignal:
    def test_rising_when_yield_up(self, monkeypatch):
        """Yield today > yield 3 months ago -> rising."""
        idx = pd.date_range("2026-01-01", periods=90, freq="B")
        series = pd.Series(range(90), index=idx, dtype="float64")  # strictly increasing
        df = pd.DataFrame({"Close": series})

        class FakeTicker:
            def __init__(self, ticker): self.ticker = ticker
            def history(self, period="6mo", interval="1d"):
                return df

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_rates_signal("US", "^TNX") == "rising"

    def test_falling_when_yield_down(self, monkeypatch):
        idx = pd.date_range("2026-01-01", periods=90, freq="B")
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

    def test_too_few_points_returns_unknown(self, monkeypatch):
        idx = pd.date_range("2026-01-01", periods=15, freq="B")
        df = pd.DataFrame({"Close": pd.Series(range(15), index=idx, dtype="float64")})
        class FakeTicker:
            def __init__(self, ticker): pass
            def history(self, **_): return df
        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_rates_signal("US", "^TNX") == "unknown"


class TestFetchGrowthSignal:
    def test_us_expanding_when_pmi_above_50_and_rising(self, monkeypatch):
        # Descending order (FRED sort_order=desc): latest first
        payload = {
            "observations": [
                {"date": "2026-03-01", "value": "54.2"},
                {"date": "2026-02-01", "value": "53.0"},
                {"date": "2026-01-01", "value": "52.1"},
            ]
        }

        class FakeResp:
            status_code = 200
            def json(self): return payload
            def raise_for_status(self): pass

        monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
        assert mf._fetch_growth_signal("US", "FAKE_KEY") == "expanding"

    def test_us_contracting_when_pmi_below_50(self, monkeypatch):
        payload = {
            "observations": [
                {"date": "2026-03-01", "value": "48.0"},
                {"date": "2026-02-01", "value": "49.0"},
                {"date": "2026-01-01", "value": "49.5"},
            ]
        }

        class FakeResp:
            status_code = 200
            def json(self): return payload
            def raise_for_status(self): pass

        monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
        assert mf._fetch_growth_signal("US", "FAKE_KEY") == "contracting"

    def test_us_no_api_key_returns_unknown(self):
        assert mf._fetch_growth_signal("US", None) == "unknown"

    def test_india_uses_equity_proxy_positive(self, monkeypatch):
        idx = pd.date_range("2026-01-01", periods=90, freq="B")
        series = pd.Series(range(100, 190), index=idx, dtype="float64")
        df = pd.DataFrame({"Close": series})

        class FakeTicker:
            def __init__(self, t): pass
            def history(self, period="6mo", interval="1d"):
                return df

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_growth_signal("India", None) == "expanding"

    def test_japan_equity_proxy_negative(self, monkeypatch):
        idx = pd.date_range("2026-01-01", periods=90, freq="B")
        series = pd.Series(range(200, 110, -1), index=idx, dtype="float64")
        df = pd.DataFrame({"Close": series})

        class FakeTicker:
            def __init__(self, t): pass
            def history(self, period="6mo", interval="1d"):
                return df

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_growth_signal("Japan", None) == "contracting"

    def test_europe_exception_returns_unknown(self, monkeypatch):
        class FakeTicker:
            def __init__(self, t): pass
            def history(self, period="6mo", interval="1d"):
                raise RuntimeError("boom")

        monkeypatch.setattr(mf, "yf", type("YF", (), {"Ticker": FakeTicker}))
        assert mf._fetch_growth_signal("Europe", None) == "unknown"


class TestFetchInflationSignal:
    def _cpi_payload(self, values_desc):
        """Build a FRED-style response with 18 monthly CPI levels, latest first."""
        obs = [
            {"date": f"2026-{12 - i:02d}-01", "value": str(v)}
            for i, v in enumerate(values_desc)
        ]
        return {"observations": obs}

    def test_rising_when_recent_3m_yoy_gt_prior_3m_yoy(self, monkeypatch):
        # 18 months, latest first. recent YoY = avg(0:3)/avg(12:15) - 1 must exceed
        # prior YoY = avg(3:6)/avg(15:18) - 1. Use accelerating CPI in the recent window.
        values = [
            140, 138, 136,       # recent 3m (avg 138)
            128, 127, 126,       # 3-6 months ago (avg 127)
            125, 124, 123,       # 6-9
            122, 121, 120,       # 9-12
            119, 118, 117,       # 12-15 (avg 118) — recent YoY ≈ 138/118 - 1 ≈ 0.169
            116, 115, 114,       # 15-18 (avg 115) — prior YoY ≈ 127/115 - 1 ≈ 0.104
        ]
        payload = self._cpi_payload(values)

        class FakeResp:
            status_code = 200
            def json(self): return payload
            def raise_for_status(self): pass

        monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
        assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "rising"

    def test_falling_when_recent_3m_yoy_lt_prior_3m_yoy(self, monkeypatch):
        # Decelerating CPI
        values = [
            120.1, 120.0, 119.9,  # recent 3m
            119.8, 119.7, 119.6,
            119.5, 119.4, 119.3,
            119.2, 119.1, 119.0,
            117.0, 116.0, 115.0,  # 12-15 months ago
            113.0, 112.0, 111.0,  # 15-18 months ago (big jump earlier -> prior YoY higher)
        ]
        payload = self._cpi_payload(values)

        class FakeResp:
            status_code = 200
            def json(self): return payload
            def raise_for_status(self): pass

        monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
        assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "falling"

    def test_no_api_key_returns_unknown(self):
        assert mf._fetch_inflation_signal("US", "CPIAUCSL", None) == "unknown"

    def test_http_error_returns_unknown(self, monkeypatch):
        class FakeResp:
            status_code = 500
            def json(self): return {}
            def raise_for_status(self): raise RuntimeError("500")

        monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
        assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "unknown"

    def test_insufficient_observations_returns_unknown(self, monkeypatch):
        payload = {"observations": [{"date": "2026-03-01", "value": "130"}]}

        class FakeResp:
            status_code = 200
            def json(self): return payload
            def raise_for_status(self): pass

        monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp())
        assert mf._fetch_inflation_signal("US", "CPIAUCSL", "FAKE_KEY") == "unknown"
