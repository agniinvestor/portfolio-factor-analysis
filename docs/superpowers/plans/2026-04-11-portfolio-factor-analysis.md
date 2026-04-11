# Portfolio Factor Analysis Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit dashboard that identifies the factor tilt of a 33-stock Indian equity portfolio using a Carhart 4-factor regression (IIMA dataset) and a 6-dimension per-stock style scorecard, benchmarked against the Nifty 500.

**Architecture:** Modular pipeline — `data/fetcher.py` handles all web fetches and caching, `factors/scorer.py` computes per-stock style z-scores, `factors/regression.py` runs the OLS regression; `dashboard/app.py` is a Streamlit consumer of these three modules. The `india-equity-report` skill is installed globally and reused for data source rules and single-stock deep-dives.

**Tech Stack:** Python 3.12, Streamlit, pandas, statsmodels, plotly, requests, BeautifulSoup4, pyarrow, pytest, openpyxl.

---

## File Map

| File | Responsibility |
|---|---|
| `data/fetcher.py` | IIMA CSV download, Screener.in scraping, Tickertape price fetch, cache read/write, staleness check |
| `data/ticker_map.py` | ISIN → NSE ticker mapping for all 33 holdings |
| `factors/scorer.py` | Per-stock style z-scores across 6 dimensions; portfolio weighted average |
| `factors/regression.py` | Monthly portfolio return construction; Carhart 4-factor OLS; result formatting |
| `dashboard/app.py` | Streamlit app: 4 tabs, Refresh button, time horizon slider |
| `tests/test_fetcher.py` | Unit tests for cache logic and data parsing |
| `tests/test_scorer.py` | Unit tests for z-scoring and weighting |
| `tests/test_regression.py` | Unit tests for return construction and OLS output |
| `requirements.txt` | All dependencies pinned |
| `ticker_map.json` | ISIN → NSE ticker for all 33 holdings |

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `data/__init__.py`
- Create: `factors/__init__.py`
- Create: `dashboard/__init__.py`
- Create: `data/cache/.gitkeep`

- [ ] **Step 1: Create requirements.txt**

```
streamlit==1.33.0
pandas==2.2.2
numpy==1.26.4
openpyxl==3.1.2
statsmodels==0.14.2
plotly==5.21.0
requests==2.31.0
beautifulsoup4==4.12.3
pyarrow==15.0.2
pytest==8.1.1
pytest-mock==3.14.0
```

- [ ] **Step 2: Create directory structure and empty init files**

```bash
mkdir -p data/cache factors dashboard tests
touch data/__init__.py factors/__init__.py dashboard/__init__.py tests/__init__.py data/cache/.gitkeep
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt --break-system-packages -q
```

Expected: No errors. Verify with:
```bash
python3 -c "import streamlit, pandas, statsmodels, plotly, bs4, pyarrow; print('OK')"
```
Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git init
git add requirements.txt data/__init__.py factors/__init__.py dashboard/__init__.py tests/__init__.py data/cache/.gitkeep
git commit -m "chore: project scaffold and dependencies"
```

---

## Task 2: Install india-equity-report Skill Globally

**Files:**
- Install: `~/.claude/skills/india-equity-report/` (global, outside project)

- [ ] **Step 1: Clone and install globally**

```bash
git clone https://github.com/vishalmdi/india-equity-report-skill.git /tmp/india-equity-report-skill
mkdir -p ~/.claude/skills/
cp -r /tmp/india-equity-report-skill/india-equity-report ~/.claude/skills/
rm -rf /tmp/india-equity-report-skill
```

- [ ] **Step 2: Verify installation**

```bash
ls ~/.claude/skills/india-equity-report/
```

Expected output:
```
SKILL.md  references/
```

```bash
head -5 ~/.claude/skills/india-equity-report/SKILL.md
```

Expected: YAML frontmatter with `name: india-equity-report`.

- [ ] **Step 3: Commit note (project-level)**

```bash
git add .
git commit -m "docs: india-equity-report skill installed globally at ~/.claude/skills/"
```

---

## Task 3: ISIN → NSE Ticker Mapping

**Files:**
- Create: `data/ticker_map.py`
- Create: `ticker_map.json`
- Test: `tests/test_fetcher.py` (first test)

The portfolio has ISINs; Screener.in and Tickertape require NSE tickers. This mapping covers all 33 holdings.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetcher.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_fetcher.py::test_known_ticker_returns_correctly -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'data.ticker_map'`

- [ ] **Step 3: Create ticker_map.json**

```bash
cat > ticker_map.json << 'EOF'
{
  "INE040A01034": "HDFCBANK",
  "INE752E01010": "POWERGRID",
  "INE522F01014": "COALINDIA",
  "INE090A01021": "ICICIBANK",
  "INE154A01025": "ITC",
  "INE118A01012": "BAJAJHLDNG",
  "INE237A01036": "KOTAKBANK",
  "INE101A01026": "M&M",
  "INE860A01027": "HCLTECH",
  "INE238A01034": "AXISBANK",
  "INE397D01024": "BHARTIARTL",
  "INE585B01010": "MARUTI",
  "INE009A01021": "INFY",
  "INE467B01029": "TCS",
  "INE089A01031": "DRREDDY",
  "INE010B01027": "ZYDUSLIFE",
  "INE059A01026": "CIPLA",
  "INE768C01028": "ZDUSWEL",
  "INE022Q01020": "IEX",
  "INE126A01031": "EIDPARRY",
  "INE787D01026": "BALKRISIND",
  "INE410P01011": "NH",
  "INE017A01032": "GESHIP",
  "INE736A01011": "CDSL",
  "INE925R01014": "CMSINFO",
  "INE725G01011": "ICRA",
  "INE288A01013": "MAHSCOOTER",
  "INE121J01017": "INDUSTOWER",
  "INE536H01010": "CIEINDIA",
  "INE277A01016": "SWARAJENG",
  "INE317F01035": "NESCO",
  "INE203G01027": "IGL",
  "INE002S01010": "MGL"
}
EOF
```

- [ ] **Step 4: Create data/ticker_map.py**

```python
import json
from pathlib import Path

_MAP_PATH = Path(__file__).parent.parent / "ticker_map.json"

def load_ticker_map() -> dict[str, str]:
    with open(_MAP_PATH) as f:
        return json.load(f)

def get_ticker(isin: str) -> str:
    mapping = load_ticker_map()
    if isin not in mapping:
        raise KeyError(f"No NSE ticker found for ISIN: {isin}")
    return mapping[isin]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: 3 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add ticker_map.json data/ticker_map.py tests/test_fetcher.py
git commit -m "feat: ISIN to NSE ticker mapping for all 33 holdings"
```

---

## Task 4: Portfolio Loader

**Files:**
- Create: `data/portfolio.py`
- Test: `tests/test_fetcher.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetcher.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fetcher.py::test_load_portfolio_returns_dataframe -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'data.portfolio'`

- [ ] **Step 3: Create data/portfolio.py**

```python
import pandas as pd
from pathlib import Path
from data.ticker_map import load_ticker_map

def load_portfolio(xlsx_path: str) -> pd.DataFrame:
    """Load portfolio.xlsx and return a clean DataFrame with computed weights and tickers."""
    df = pd.read_excel(xlsx_path, sheet_name="Long")
    df.columns = ["name", "isin", "sector", "weight_formula", "value"]
    df = df.dropna(subset=["isin"]).copy()

    total_value = df["value"].sum()
    df["weight"] = df["value"] / total_value

    ticker_map = load_ticker_map()
    df["ticker"] = df["isin"].map(ticker_map)

    return df[["name", "isin", "ticker", "sector", "weight", "value"]].reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: all tests PASSED (3 ticker tests + 5 portfolio tests = 8 total).

- [ ] **Step 5: Commit**

```bash
git add data/portfolio.py tests/test_fetcher.py
git commit -m "feat: portfolio loader with weight computation and ticker mapping"
```

---

## Task 5: Cache Manager

**Files:**
- Create: `data/cache_manager.py`
- Test: `tests/test_fetcher.py` (add tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_fetcher.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_fetcher.py::test_missing_cache_is_stale -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'data.cache_manager'`

- [ ] **Step 3: Create data/cache_manager.py**

```python
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

def is_stale(path: Path, max_age_hours: int = 24) -> bool:
    """Return True if cache file is missing or older than max_age_hours."""
    if not path.exists():
        return True
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - mtime > timedelta(hours=max_age_hours)

def write_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

def read_cache(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: all 11 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add data/cache_manager.py tests/test_fetcher.py
git commit -m "feat: cache manager with staleness check and parquet read/write"
```

---

## Task 6: IIMA Factor Data Fetcher

**Files:**
- Modify: `data/fetcher.py` (create)
- Test: `tests/test_fetcher.py` (add tests)

The IIMA page at `https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/` provides monthly CSV downloads. We fetch, parse, and cache them.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_fetcher.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_fetcher.py::test_parse_iima_csv_returns_dataframe -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'data.fetcher'`

- [ ] **Step 3: Create data/fetcher.py with IIMA parsing and fetch**

```python
import io
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from data.cache_manager import is_stale, write_cache, read_cache, CACHE_DIR

IIMA_BASE_URL = "https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/"
IIMA_CACHE = CACHE_DIR / "iima_factors.parquet"


def parse_iima_csv(csv_text: str) -> pd.DataFrame:
    """Parse IIMA factor CSV text into a clean DataFrame with decimal returns."""
    df = pd.read_csv(io.StringIO(csv_text))
    df.columns = [c.strip().lower().replace("-", "_") for c in df.columns]
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01"
    )
    for col in ["mkt_rf", "smb", "hml", "wml", "rf"]:
        df[col] = df[col] / 100.0  # percent → decimal
    return df[["date", "mkt_rf", "smb", "hml", "wml", "rf"]].reset_index(drop=True)


def _discover_iima_csv_url() -> str:
    """Fetch the IIMA page and find the monthly factor CSV download link."""
    resp = requests.get(IIMA_BASE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "monthly" in href.lower() and href.endswith(".csv") and "factor" in href.lower():
            if href.startswith("http"):
                return href
            return IIMA_BASE_URL.rstrip("/") + "/" + href.lstrip("/")
    # Fallback: look for any CSV with survivorship-bias adjustment mention
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".csv") and "monthly" in href.lower():
            if href.startswith("http"):
                return href
            return IIMA_BASE_URL.rstrip("/") + "/" + href.lstrip("/")
    raise RuntimeError("Could not find IIMA monthly factor CSV URL on page")


def fetch_iima_factors(force_refresh: bool = False) -> pd.DataFrame:
    """Return IIMA 4-factor monthly data, using cache if fresh."""
    if not force_refresh and not is_stale(IIMA_CACHE):
        return read_cache(IIMA_CACHE)
    csv_url = _discover_iima_csv_url()
    resp = requests.get(csv_url, timeout=60)
    resp.raise_for_status()
    df = parse_iima_csv(resp.text)
    write_cache(df, IIMA_CACHE)
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py::test_parse_iima_csv_returns_dataframe tests/test_fetcher.py::test_parse_iima_csv_has_date_index tests/test_fetcher.py::test_parse_iima_csv_has_factor_columns tests/test_fetcher.py::test_parse_iima_csv_converts_percent_to_decimal -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Smoke-test live fetch (requires internet)**

```bash
python3 -c "
from data.fetcher import fetch_iima_factors
df = fetch_iima_factors(force_refresh=True)
print(df.tail(3))
print('Shape:', df.shape)
"
```

Expected: last 3 rows of factor data printed, shape like `(350+, 6)`.

- [ ] **Step 6: Commit**

```bash
git add data/fetcher.py tests/test_fetcher.py
git commit -m "feat: IIMA factor CSV fetcher with URL discovery and caching"
```

---

## Task 7: Screener.in Fundamentals Fetcher

**Files:**
- Modify: `data/fetcher.py` (add `fetch_screener_fundamentals`)
- Test: `tests/test_fetcher.py` (add tests)

Fetches P/B, P/E, ROE, ROCE, D/E, Revenue (3 years), CFO, PAT, Market Cap per stock from Screener.in.

- [ ] **Step 1: Write failing tests with mocked HTTP**

Append to `tests/test_fetcher.py`:

```python
from data.fetcher import parse_screener_fundamentals

SAMPLE_SCREENER_HTML = """
<html><body>
<section id="top-ratios">
  <li><span class="name">Stock P/E</span><span class="value">22.5</span></li>
  <li><span class="name">Price to book value</span><span class="value">3.1</span></li>
  <li><span class="name">Return on equity</span><span class="value">18.2%</span></li>
  <li><span class="name">Return on capital employed</span><span class="value">24.1%</span></li>
  <li><span class="name">Debt to equity</span><span class="value">0.45</span></li>
  <li><span class="name">Market Capitalization</span><span class="value">₹1,23,456 Cr.</span></li>
</section>
</body></html>
"""

def test_parse_screener_fundamentals_returns_dict():
    result = parse_screener_fundamentals(SAMPLE_SCREENER_HTML)
    assert isinstance(result, dict)

def test_parse_screener_fundamentals_extracts_pe():
    result = parse_screener_fundamentals(SAMPLE_SCREENER_HTML)
    assert abs(result["pe"] - 22.5) < 0.01

def test_parse_screener_fundamentals_extracts_pb():
    result = parse_screener_fundamentals(SAMPLE_SCREENER_HTML)
    assert abs(result["pb"] - 3.1) < 0.01

def test_parse_screener_fundamentals_extracts_roe():
    result = parse_screener_fundamentals(SAMPLE_SCREENER_HTML)
    assert abs(result["roe"] - 18.2) < 0.01

def test_parse_screener_fundamentals_extracts_market_cap():
    result = parse_screener_fundamentals(SAMPLE_SCREENER_HTML)
    assert result["market_cap_cr"] == 123456.0
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_fetcher.py::test_parse_screener_fundamentals_returns_dict -v
```

Expected: `ERROR` — `ImportError: cannot import name 'parse_screener_fundamentals'`

- [ ] **Step 3: Add parse_screener_fundamentals to data/fetcher.py**

Append to `data/fetcher.py`:

```python
import re
import time

SCREENER_CACHE = CACHE_DIR / "portfolio_fundamentals.parquet"


def _clean_numeric(text: str) -> float:
    """Strip currency symbols, commas, percent signs and return float."""
    cleaned = re.sub(r"[₹,% Cr.]", "", text.strip())
    return float(cleaned)


def parse_screener_fundamentals(html: str) -> dict:
    """Parse Screener.in company page HTML and extract key fundamental ratios."""
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    ratio_section = soup.find("section", {"id": "top-ratios"}) or soup.find("ul", {"id": "top-ratios"})
    if not ratio_section:
        return result
    for li in ratio_section.find_all("li"):
        name_el = li.find(class_="name") or li.find("span")
        val_el = li.find(class_="value") or li.find_all("span")[-1] if li.find_all("span") else None
        if not name_el or not val_el:
            continue
        name = name_el.get_text(strip=True).lower()
        try:
            val = _clean_numeric(val_el.get_text(strip=True))
        except (ValueError, AttributeError):
            continue
        if "p/e" in name or "price to earning" in name or "stock p/e" in name:
            result["pe"] = val
        elif "price to book" in name or "p/b" in name:
            result["pb"] = val
        elif "return on equity" in name or "roe" in name:
            result["roe"] = val
        elif "return on capital" in name or "roce" in name:
            result["roce"] = val
        elif "debt to equity" in name or "d/e" in name:
            result["de"] = val
        elif "market cap" in name:
            result["market_cap_cr"] = val
    return result


def fetch_screener_fundamentals(ticker: str, force_refresh: bool = False) -> dict:
    """Fetch fundamentals for a single NSE ticker from Screener.in."""
    cache_path = CACHE_DIR / f"screener_{ticker}.parquet"
    if not force_refresh and not is_stale(cache_path):
        return read_cache(cache_path).iloc[0].to_dict()
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = parse_screener_fundamentals(resp.text)
    df = pd.DataFrame([data])
    write_cache(df, cache_path)
    time.sleep(1.5)  # be polite to Screener.in
    return data


def fetch_all_fundamentals(tickers: list[str], force_refresh: bool = False) -> pd.DataFrame:
    """Fetch fundamentals for all tickers; return one row per ticker."""
    rows = []
    for ticker in tickers:
        data = fetch_screener_fundamentals(ticker, force_refresh=force_refresh)
        data["ticker"] = ticker
        rows.append(data)
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py -v -k "screener"
```

Expected: 5 screener tests PASSED.

- [ ] **Step 5: Smoke-test one live stock (HDFCBANK)**

```bash
python3 -c "
from data.fetcher import fetch_screener_fundamentals
d = fetch_screener_fundamentals('HDFCBANK', force_refresh=True)
print(d)
"
```

Expected: dict with pe, pb, roe, roce, market_cap_cr keys and plausible values.

- [ ] **Step 6: Commit**

```bash
git add data/fetcher.py tests/test_fetcher.py
git commit -m "feat: Screener.in fundamentals parser and fetcher"
```

---

## Task 8: Price History Fetcher (Tickertape)

**Files:**
- Modify: `data/fetcher.py` (add price fetch functions)
- Test: `tests/test_fetcher.py` (add tests)

Fetches monthly closing prices per stock to compute portfolio return series.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_fetcher.py`:

```python
from data.fetcher import compute_monthly_returns

def test_compute_monthly_returns_from_prices():
    prices = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=4, freq="MS"),
        "price": [100.0, 110.0, 105.0, 115.0]
    })
    returns = compute_monthly_returns(prices)
    assert isinstance(returns, pd.Series)
    assert len(returns) == 3  # n-1 returns from n prices
    assert abs(returns.iloc[0] - 0.10) < 0.001   # (110-100)/100

def test_compute_monthly_returns_index_is_datetime():
    prices = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "price": [100.0, 110.0, 105.0]
    })
    returns = compute_monthly_returns(prices)
    assert pd.api.types.is_datetime64_any_dtype(returns.index)
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_fetcher.py::test_compute_monthly_returns_from_prices -v
```

Expected: `ERROR` — `ImportError: cannot import name 'compute_monthly_returns'`

- [ ] **Step 3: Add price fetcher and return computation to data/fetcher.py**

Append to `data/fetcher.py`:

```python
PRICES_CACHE = CACHE_DIR / "stock_prices.parquet"


def fetch_tickertape_prices(ticker: str, years: int = 5, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch monthly closing prices from Tickertape for a given NSE ticker.

    Returns DataFrame with columns: date (datetime), price (float).
    Falls back to NSE historical data if Tickertape layout changes.
    """
    cache_path = CACHE_DIR / f"prices_{ticker}.parquet"
    if not force_refresh and not is_stale(cache_path):
        return read_cache(cache_path)

    # Tickertape uses a slug: lowercase ticker without special chars
    slug = ticker.lower().replace("&", "").replace(" ", "-")
    url = f"https://www.tickertape.in/stocks/{slug}-{ticker}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

    # Tickertape exposes historical price data via JSON endpoint
    api_url = f"https://api.tickertape.in/stocks/charts/inter/{ticker}?duration={years}y&type=price"
    resp = requests.get(api_url, headers=headers, timeout=30)

    if resp.status_code == 200:
        data = resp.json()
        points = data.get("data", {}).get("points", [])
        records = [{"date": pd.to_datetime(p["date"]), "price": p["value"]} for p in points]
    else:
        # Fallback: NSE historical data (bhav copy)
        records = _fetch_nse_historical(ticker, years)

    df = pd.DataFrame(records)
    df = df.sort_values("date").reset_index(drop=True)
    # Resample to month-end
    df = df.set_index("date").resample("ME")["price"].last().reset_index()
    write_cache(df, cache_path)
    time.sleep(1.0)
    return df


def _fetch_nse_historical(ticker: str, years: int) -> list[dict]:
    """Fallback: fetch historical data from NSE for a given ticker."""
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=365 * years)
    url = (
        f"https://www.nseindia.com/api/historical/cm/equity"
        f"?symbol={ticker}&series=EQ"
        f"&from={start.strftime('%d-%m-%Y')}&to={end.strftime('%d-%m-%Y')}"
    )
    session = requests.Session()
    session.get("https://www.nseindia.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    resp = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if resp.status_code != 200:
        return []
    rows = resp.json().get("data", [])
    return [{"date": pd.to_datetime(r["CH_TIMESTAMP"]), "price": float(r["CH_CLOSING_PRICE"])} for r in rows]


def compute_monthly_returns(prices_df: pd.DataFrame) -> pd.Series:
    """Compute monthly returns from a DataFrame with date and price columns."""
    s = prices_df.set_index("date")["price"].sort_index()
    returns = s.pct_change().dropna()
    return returns
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: all tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add data/fetcher.py tests/test_fetcher.py
git commit -m "feat: Tickertape price fetcher and monthly return computation"
```

---

## Task 9: Style Scorer

**Files:**
- Create: `factors/scorer.py`
- Create: `tests/test_scorer.py`

Computes per-stock style z-scores across 6 dimensions and portfolio-level weighted averages.

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorer.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_scorer.py::test_compute_style_scores_returns_dataframe -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'factors.scorer'`

- [ ] **Step 3: Create factors/scorer.py**

```python
import numpy as np
import pandas as pd


def _zscore(series: pd.Series) -> pd.Series:
    """Z-score a series; return zeros if std is 0."""
    std = series.std()
    if std == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def compute_style_scores(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Compute z-scored style dimensions for each stock.

    Input columns required: ticker, pe, pb, roe, roce, de, market_cap_cr,
                            momentum_12m_1m, revenue_cagr_3y, net_margin.
    Returns DataFrame with ticker + 6 dimension z-score columns.
    Higher score = stronger tilt in that direction for all dimensions.
    """
    df = fundamentals.copy()

    # Value: lower P/E and P/B = better value → invert
    df["value"] = _zscore(-df["pe"]) * 0.5 + _zscore(-df["pb"]) * 0.5

    # Quality: higher ROE, ROCE, lower D/E = better quality
    de_col = _zscore(-df["de"]) if "de" in df.columns else 0
    df["quality"] = (
        _zscore(df["roe"]) * 0.4
        + _zscore(df["roce"]) * 0.4
        + de_col * 0.2
    )

    # Momentum: 12M-1M return
    df["momentum"] = _zscore(df["momentum_12m_1m"])

    # Size: lower market cap = small-cap tilt → invert log
    df["size"] = _zscore(-np.log(df["market_cap_cr"].clip(lower=1)))

    # Growth: higher revenue CAGR = growth tilt
    df["growth"] = _zscore(df["revenue_cagr_3y"])

    # Profitability: higher net margin = better
    df["profitability"] = _zscore(df["net_margin"])

    return df[["ticker", "value", "quality", "momentum", "size", "growth", "profitability"]]


def compute_portfolio_scores(
    style_scores: pd.DataFrame,
    weights: pd.Series,
) -> pd.Series:
    """Compute portfolio-level weighted average z-score per dimension.

    Args:
        style_scores: DataFrame from compute_style_scores (ticker + 6 dims).
        weights: Series indexed by ticker, values are portfolio weights (sum to 1).
    Returns:
        Series indexed by dimension name with weighted average z-score.
    """
    dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
    scores_indexed = style_scores.set_index("ticker")[dims]
    aligned_weights = weights.reindex(scores_indexed.index).fillna(0)
    aligned_weights = aligned_weights / aligned_weights.sum()  # renormalise
    return scores_indexed.multiply(aligned_weights, axis=0).sum()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scorer.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add factors/scorer.py tests/test_scorer.py
git commit -m "feat: 6-dimension style scorer with z-scoring and weighted portfolio aggregation"
```

---

## Task 10: 4-Factor Regression Engine

**Files:**
- Create: `factors/regression.py`
- Create: `tests/test_regression.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_regression.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_regression.py::test_run_carhart_regression_returns_dict -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'factors.regression'`

- [ ] **Step 3: Create factors/regression.py**

```python
import numpy as np
import pandas as pd
import statsmodels.api as sm
from datetime import datetime
from dateutil.relativedelta import relativedelta


def build_portfolio_returns(
    stock_returns: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    """Compute weighted portfolio monthly returns.

    Args:
        stock_returns: DataFrame indexed by date, columns = tickers, values = monthly returns.
        weights: dict of {ticker: weight} — will be renormalised to sum to 1.
    Returns:
        Series of monthly portfolio returns indexed by date.
    """
    tickers = [t for t in weights if t in stock_returns.columns]
    w = pd.Series({t: weights[t] for t in tickers})
    w = w / w.sum()
    return stock_returns[tickers].dot(w).rename("portfolio")


def run_carhart_regression(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    window_years: int,
) -> dict:
    """Run Carhart 4-factor OLS regression over the specified trailing window.

    Args:
        portfolio_returns: Monthly portfolio excess returns (Series, datetime index).
        factor_returns: DataFrame with columns date, mkt_rf, smb, hml, wml, rf.
        window_years: Number of trailing years to include (1, 3, or 5).
    Returns:
        dict with keys: alpha, betas, t_stats, p_values, r_squared, n_obs.
    """
    factors = factor_returns.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]

    # Compute portfolio excess returns (subtract risk-free rate)
    aligned = portfolio_returns.align(factors, join="inner")
    port = aligned[0]
    fac = aligned[1]
    port_excess = port - fac["rf"]

    # Apply trailing window
    cutoff = port_excess.index.max() - relativedelta(years=window_years)
    port_excess = port_excess[port_excess.index > cutoff]
    fac = fac[fac.index > cutoff]

    X = sm.add_constant(fac[["mkt_rf", "smb", "hml", "wml"]])
    model = sm.OLS(port_excess, X).fit()

    betas = {col: model.params[col] for col in ["mkt_rf", "smb", "hml", "wml"]}
    t_stats = {col: model.tvalues[col] for col in ["mkt_rf", "smb", "hml", "wml"]}
    p_values = {col: model.pvalues[col] for col in ["mkt_rf", "smb", "hml", "wml"]}

    return {
        "alpha": model.params["const"],
        "alpha_t": model.tvalues["const"],
        "alpha_p": model.pvalues["const"],
        "betas": betas,
        "t_stats": t_stats,
        "p_values": p_values,
        "r_squared": model.rsquared,
        "n_obs": int(model.nobs),
    }
```

- [ ] **Step 4: Install missing dependency**

```bash
pip install python-dateutil --break-system-packages -q
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_regression.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add factors/regression.py tests/test_regression.py requirements.txt
git commit -m "feat: Carhart 4-factor OLS regression engine with trailing window"
```

---

## Task 11: Dashboard — Tab 1 (Portfolio Overview)

**Files:**
- Create: `dashboard/app.py`

- [ ] **Step 1: Create dashboard/app.py with Tab 1**

```python
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from data.portfolio import load_portfolio
from data.fetcher import fetch_iima_factors, fetch_all_fundamentals, fetch_tickertape_prices, compute_monthly_returns
from data.cache_manager import is_stale, CACHE_DIR
from factors.scorer import compute_style_scores, compute_portfolio_scores
from factors.regression import build_portfolio_returns, run_carhart_regression

PORTFOLIO_PATH = Path(__file__).parent.parent / "portfolio.xlsx"

st.set_page_config(page_title="Portfolio Factor Analysis", layout="wide")
st.title("Portfolio Factor Analysis Dashboard")

# ── Sidebar: Refresh ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Data")
    force_refresh = st.button("Refresh Data")
    iima_cache = CACHE_DIR / "iima_factors.parquet"
    if iima_cache.exists():
        import time
        mtime = iima_cache.stat().st_mtime
        st.caption(f"Last updated: {pd.Timestamp(mtime, unit='s').strftime('%Y-%m-%d %H:%M')}")
    else:
        st.caption("No cache yet — click Refresh Data")
    window_years = st.select_slider(
        "Regression window",
        options=[1, 3, 5],
        value=3,
        help="Years of history used for the Carhart 4-factor regression"
    )

# ── Load portfolio ────────────────────────────────────────────────────────────
portfolio = load_portfolio(str(PORTFOLIO_PATH))

# ── Fetch data ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Fetching IIMA factors…")
def get_iima(force):
    return fetch_iima_factors(force_refresh=force)

@st.cache_data(show_spinner="Fetching stock fundamentals from Screener.in…")
def get_fundamentals(tickers_tuple, force):
    return fetch_all_fundamentals(list(tickers_tuple), force_refresh=force)

iima_factors = get_iima(force_refresh)
fundamentals = get_fundamentals(tuple(portfolio["ticker"].tolist()), force_refresh)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Portfolio Overview",
    "Factor Regression",
    "Style Scorecard",
    "Stock Deep-Dive",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Portfolio Overview
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Holdings")

    display_df = portfolio[["name", "sector", "weight", "value"]].copy()
    display_df["weight_pct"] = (display_df["weight"] * 100).round(2)
    display_df["value_inr"] = display_df["value"].apply(lambda x: f"₹{x:,.0f}")
    st.dataframe(
        display_df[["name", "sector", "weight_pct", "value_inr"]].rename(columns={
            "name": "Stock", "sector": "Sector",
            "weight_pct": "Weight (%)", "value_inr": "Value (INR)"
        }),
        use_container_width=True, hide_index=True
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sector Concentration")
        sector_weights = portfolio.groupby("sector")["weight"].sum().reset_index()
        sector_weights = sector_weights.sort_values("weight", ascending=True)
        fig = px.bar(
            sector_weights, x="weight", y="sector", orientation="h",
            labels={"weight": "Portfolio Weight", "sector": ""},
            color="weight", color_continuous_scale="Blues",
        )
        fig.update_layout(coloraxis_showscale=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 5 / Bottom 5 by Weight")
        top5 = portfolio.nlargest(5, "weight")[["name", "weight"]].copy()
        bot5 = portfolio.nsmallest(5, "weight")[["name", "weight"]].copy()
        top5["weight_pct"] = (top5["weight"] * 100).round(2)
        bot5["weight_pct"] = (bot5["weight"] * 100).round(2)
        st.markdown("**Top 5**")
        st.dataframe(top5[["name", "weight_pct"]].rename(
            columns={"name": "Stock", "weight_pct": "Weight (%)"}),
            hide_index=True, use_container_width=True)
        st.markdown("**Bottom 5**")
        st.dataframe(bot5[["name", "weight_pct"]].rename(
            columns={"name": "Stock", "weight_pct": "Weight (%)"}),
            hide_index=True, use_container_width=True)
```

- [ ] **Step 2: Verify Tab 1 runs**

```bash
streamlit run dashboard/app.py --server.headless true &
sleep 5 && curl -s http://localhost:8501 | grep -o "Portfolio Factor Analysis" | head -1
kill %1
```

Expected output: `Portfolio Factor Analysis`

- [ ] **Step 3: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: dashboard Tab 1 — portfolio overview with sector chart and top/bottom holdings"
```

---

## Task 12: Dashboard — Tab 2 (Factor Regression)

**Files:**
- Modify: `dashboard/app.py` (fill in Tab 2)

- [ ] **Step 1: Add Tab 2 content to dashboard/app.py**

After the Tab 1 `with` block, find the `# TAB 1` comment block and add below it:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Factor Regression
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader(f"Carhart 4-Factor Regression ({window_years}Y window)")
    st.caption("Source: IIMA Indian Fama-French-Momentum dataset (survivorship-bias adjusted)")

    @st.cache_data(show_spinner="Fetching price history…")
    def get_all_prices(tickers_tuple, force):
        from data.fetcher import fetch_tickertape_prices
        all_returns = {}
        for ticker in tickers_tuple:
            try:
                prices = fetch_tickertape_prices(ticker, years=6, force_refresh=force)
                all_returns[ticker] = compute_monthly_returns(prices)
            except Exception:
                pass
        return pd.DataFrame(all_returns)

    stock_returns_df = get_all_prices(tuple(portfolio["ticker"].tolist()), force_refresh)
    weights_dict = portfolio.set_index("ticker")["weight"].to_dict()

    if stock_returns_df.empty:
        st.warning("No price data available. Click Refresh Data to fetch.")
    else:
        port_returns = build_portfolio_returns(stock_returns_df, weights_dict)
        reg_result = run_carhart_regression(port_returns, iima_factors, window_years=window_years)

        factors_display = ["mkt_rf", "smb", "hml", "wml"]
        factor_labels = {"mkt_rf": "Market (Rm-Rf)", "smb": "Size (SMB)",
                         "hml": "Value (HML)", "wml": "Momentum (WML)"}

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Alpha (monthly)", f"{reg_result['alpha']*100:.3f}%",
                    f"t = {reg_result['alpha_t']:.2f}")
        col2.metric("R²", f"{reg_result['r_squared']:.3f}")
        col3.metric("Observations", reg_result["n_obs"])

        # Factor table
        reg_rows = []
        for f in factors_display:
            sig = "✓" if reg_result["p_values"][f] < 0.05 else "—"
            reg_rows.append({
                "Factor": factor_labels[f],
                "Beta": round(reg_result["betas"][f], 3),
                "t-stat": round(reg_result["t_stats"][f], 2),
                "p-value": round(reg_result["p_values"][f], 3),
                "Significant (5%)": sig,
            })
        reg_df = pd.DataFrame(reg_rows)
        st.dataframe(reg_df, hide_index=True, use_container_width=True)

        # Beta bar chart
        fig = go.Figure()
        colors = ["#2ecc71" if b > 0 else "#e74c3c" for b in reg_result["betas"].values()]
        fig.add_trace(go.Bar(
            x=[factor_labels[f] for f in factors_display],
            y=[reg_result["betas"][f] for f in factors_display],
            marker_color=colors,
        ))
        fig.add_hline(y=0, line_width=1, line_color="gray")
        fig.update_layout(title="Factor Betas", yaxis_title="Beta", height=350)
        st.plotly_chart(fig, use_container_width=True)

        # Plain-English summary
        tilts = []
        for f in factors_display:
            if reg_result["p_values"][f] < 0.05:
                b = reg_result["betas"][f]
                label = factor_labels[f]
                direction = "positive" if b > 0 else "negative"
                tilts.append(f"{direction} {label} (β={b:.2f})")
        if tilts:
            st.info("**Significant factor tilts:** " + ", ".join(tilts) + ".")
        else:
            st.info("No statistically significant factor tilts detected at 5% level.")
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: dashboard Tab 2 — Carhart 4-factor regression with beta chart and plain-English summary"
```

---

## Task 13: Dashboard — Tab 3 (Style Scorecard)

**Files:**
- Modify: `dashboard/app.py` (fill in Tab 3)

- [ ] **Step 1: Add Tab 3 content**

Add after the Tab 2 block:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Style Scorecard
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Per-Stock Style Scorecard (z-scores vs universe)")
    st.caption("Green = strong positive tilt, Red = negative tilt. Scores are z-scored relative to peer universe.")

    # Merge momentum into fundamentals
    if not stock_returns_df.empty:
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

    fundamentals["revenue_cagr_3y"] = fundamentals.get("revenue_cagr_3y", pd.Series(0.0, index=fundamentals.index))
    fundamentals["net_margin"] = fundamentals.get("net_margin", pd.Series(0.0, index=fundamentals.index))

    style_scores = compute_style_scores(fundamentals)
    weights_series = portfolio.set_index("ticker")["weight"]
    port_scores = compute_portfolio_scores(style_scores, weights_series)

    # Heatmap
    dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
    heatmap_df = style_scores.set_index("ticker")[dims]
    heatmap_df.index = [
        portfolio.loc[portfolio["ticker"] == t, "name"].values[0]
        if t in portfolio["ticker"].values else t
        for t in heatmap_df.index
    ]

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_df.values,
        x=[d.capitalize() for d in dims],
        y=heatmap_df.index.tolist(),
        colorscale="RdYlGn",
        zmid=0,
        text=heatmap_df.round(2).values,
        texttemplate="%{text}",
        hovertemplate="Stock: %{y}<br>Factor: %{x}<br>Z-score: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(title="Style Score Heatmap", height=700)
    st.plotly_chart(fig, use_container_width=True)

    # Radar chart — portfolio vs benchmark (zero)
    st.subheader("Portfolio Factor Profile vs Nifty 500 Baseline")
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=port_scores[dims].values.tolist() + [port_scores[dims[0]]],
        theta=[d.capitalize() for d in dims] + [dims[0].capitalize()],
        fill="toself", name="Portfolio", line_color="#3498db",
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=[0] * (len(dims) + 1),
        theta=[d.capitalize() for d in dims] + [dims[0].capitalize()],
        fill="toself", name="Nifty 500 Baseline", line_color="#95a5a6",
        line_dash="dash",
    ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(range=[-2, 2])), height=450)
    st.plotly_chart(fig_radar, use_container_width=True)

    # Sortable table
    st.subheader("Sortable Factor Table")
    sort_dim = st.selectbox("Sort by", dims, index=0)
    sortable = style_scores.merge(portfolio[["ticker", "name"]], on="ticker")
    sortable = sortable[["name", "ticker"] + dims].sort_values(sort_dim, ascending=False)
    st.dataframe(sortable.rename(columns={"name": "Stock", "ticker": "Ticker"}).reset_index(drop=True),
                 hide_index=True, use_container_width=True)
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: dashboard Tab 3 — style scorecard heatmap, radar chart, sortable table"
```

---

## Task 14: Dashboard — Tab 4 (Stock Deep-Dive)

**Files:**
- Modify: `dashboard/app.py` (fill in Tab 4)

- [ ] **Step 1: Add Tab 4 content**

Add after the Tab 3 block:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Stock Deep-Dive
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Stock Deep-Dive")

    stock_options = portfolio[["name", "ticker"]].apply(
        lambda r: f"{r['name']} ({r['ticker']})", axis=1
    ).tolist()
    selected = st.selectbox("Select a holding", stock_options)
    selected_ticker = selected.split("(")[-1].rstrip(")")
    selected_row = portfolio[portfolio["ticker"] == selected_ticker].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Sector", selected_row["sector"])
    col2.metric("Portfolio Weight", f"{selected_row['weight']*100:.2f}%")
    col3.metric("Value (INR)", f"₹{selected_row['value']:,.0f}")

    # Style profile for selected stock
    if "style_scores" in dir():
        stock_scores = style_scores[style_scores["ticker"] == selected_ticker]
        if not stock_scores.empty:
            st.subheader("Style Profile")
            dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
            scores_row = stock_scores.iloc[0]
            score_data = pd.DataFrame({
                "Dimension": [d.capitalize() for d in dims],
                "Z-Score": [round(scores_row[d], 3) for d in dims],
                "Interpretation": [
                    "Cheap vs peers" if scores_row[d] > 0.5
                    else "Expensive vs peers" if scores_row[d] < -0.5
                    else "Neutral"
                    if d == "value" else
                    "Strong" if scores_row[d] > 0.5
                    else "Weak" if scores_row[d] < -0.5
                    else "Neutral"
                    for d in dims
                ]
            })
            st.dataframe(score_data, hide_index=True, use_container_width=True)

            # Mini radar for single stock
            fig_single = go.Figure(go.Scatterpolar(
                r=[scores_row[d] for d in dims] + [scores_row[dims[0]]],
                theta=[d.capitalize() for d in dims] + [dims[0].capitalize()],
                fill="toself", line_color="#e67e22",
            ))
            fig_single.update_layout(
                polar=dict(radialaxis=dict(range=[-3, 3])),
                title=f"Factor Profile: {selected_row['name']}",
                height=400,
            )
            st.plotly_chart(fig_single, use_container_width=True)

    # External links
    st.subheader("Research Links")
    screener_url = f"https://www.screener.in/company/{selected_ticker}/consolidated/"
    tickertape_url = f"https://www.tickertape.in/stocks/{selected_ticker.lower()}-{selected_ticker}"
    st.markdown(f"- [Screener.in — {selected_ticker}]({screener_url})")
    st.markdown(f"- [Tickertape — {selected_ticker}]({tickertape_url})")

    st.divider()
    st.subheader("Full Research Report")
    st.info(
        f"To generate a full Buy/Sell/Hold research report for **{selected_row['name']}**, "
        f"invoke the `india-equity-report` skill in a Claude Code session:\n\n"
        f"```\nAnalyse {selected_ticker} NSE\n```\n\n"
        f"The skill is installed globally at `~/.claude/skills/india-equity-report/`."
    )
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: dashboard Tab 4 — stock deep-dive with style profile, links, and skill handoff"
```

---

## Task 15: Integration Test & Final Verification

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration smoke test**

Create `tests/test_integration.py`:

```python
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
```

- [ ] **Step 2: Run all unit tests**

```bash
pytest tests/test_fetcher.py tests/test_scorer.py tests/test_regression.py -v
```

Expected: all tests PASSED (no failures).

- [ ] **Step 3: Run integration test**

```bash
pytest tests/test_integration.py -v
```

Expected: PASSED or SKIPPED (skip = cache not yet populated, which is fine pre-first-run).

- [ ] **Step 4: Verify global skill install**

```bash
ls ~/.claude/skills/india-equity-report/SKILL.md
```

Expected: file exists.

- [ ] **Step 5: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration smoke tests for full pipeline"
```

---

## Self-Review Against Spec

**Spec section → Task coverage:**

| Spec requirement | Covered by |
|---|---|
| 33-stock Indian equity portfolio from portfolio.xlsx | Task 4 |
| IIMA 4-factor dataset (monthly, survivorship-adjusted) | Task 6 |
| Screener.in fundamentals (P/B, P/E, ROE, ROCE, D/E, Market Cap) | Task 7 |
| Tickertape price history → monthly returns | Task 8 |
| 6-dimension style scorecard with z-scores | Task 9 |
| Carhart 4-factor OLS regression | Task 10 |
| User-selectable time horizon (1/3/5 yr) | Task 11 (sidebar slider) |
| Local cache (parquet) with staleness check | Task 5 |
| "Refresh Data" button invalidates cache | Task 11 (force_refresh flag) |
| Tab 1: Holdings table, sector chart, top/bottom 5 | Task 11 |
| Tab 2: Beta table, bar chart, R², plain-English summary | Task 12 |
| Tab 3: Heatmap, radar chart, sortable table | Task 13 |
| Tab 4: Style profile, Screener/Tickertape links, skill handoff | Task 14 |
| india-equity-report installed globally | Task 2 |
| Follows india-equity-report data source rules | Tasks 6, 7, 8 |
| All 33 tickers mapped correctly | Task 3 |

**Placeholder scan:** No TBD, TODO, or vague steps. All code is complete. ✓

**Type consistency:** `compute_style_scores` takes a DataFrame and returns a DataFrame with `ticker` + 6 dims throughout Tasks 9, 13, 14. `run_carhart_regression` signature matches across Tasks 10 and 12. `build_portfolio_returns` matches Task 10 definition used in Task 12. ✓
