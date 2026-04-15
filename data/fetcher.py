import io
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from data.cache_manager import is_stale, write_cache, read_cache, CACHE_DIR

IIMA_BASE_URL = "https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/"
IIMA_CACHE = CACHE_DIR / "iima_factors.parquet"
_IIMA_SNAPSHOT_PATH = Path(__file__).parent / "iima_factors_snapshot.csv"


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


def _parse_iima_live_csv(csv_text: str) -> pd.DataFrame:
    """Parse the actual IIMA CSV format (Date col in YYYY-MM, MF for market factor)."""
    df = pd.read_csv(io.StringIO(csv_text))
    df.columns = [c.strip() for c in df.columns]
    # Normalize date: YYYY-MM -> YYYY-MM-01
    df["date"] = pd.to_datetime(df["Date"].astype(str) + "-01", format="%Y-%m-%d")
    # Map MF -> mkt_rf; drop rows where market factor is NA
    df = df.rename(columns={"MF": "mkt_rf", "SMB": "smb", "HML": "hml", "WML": "wml", "RF": "rf"})
    df = df.dropna(subset=["mkt_rf", "smb", "hml", "wml", "rf"])
    for col in ["mkt_rf", "smb", "hml", "wml", "rf"]:
        df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0  # percent → decimal
    return df[["date", "mkt_rf", "smb", "hml", "wml", "rf"]].reset_index(drop=True)


def _discover_iima_csv_url() -> str:
    """Fetch the IIMA page and find the monthly factor CSV download link."""
    resp = requests.get(IIMA_BASE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Prefer survivorship-bias-adjusted monthly four-factor file
    for link in soup.find_all("a", href=True):
        href = link["href"]
        href_lower = href.lower()
        if (href.endswith(".csv") and "monthly" in href_lower
                and "fourfactor" in href_lower.replace("_", "").replace("-", "")
                and "survivorship" in href_lower):
            if href.startswith("http"):
                return href
            return IIMA_BASE_URL.rstrip("/") + "/" + href.lstrip("./")
    # Fallback: any monthly four-factor CSV
    for link in soup.find_all("a", href=True):
        href = link["href"]
        href_lower = href.lower()
        if (href.endswith(".csv") and "monthly" in href_lower
                and "fourfactor" in href_lower.replace("_", "").replace("-", "")):
            if href.startswith("http"):
                return href
            return IIMA_BASE_URL.rstrip("/") + "/" + href.lstrip("./")
    # Last resort: any monthly CSV
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".csv") and "monthly" in href.lower():
            if href.startswith("http"):
                return href
            return IIMA_BASE_URL.rstrip("/") + "/" + href.lstrip("./")
    raise RuntimeError("Could not find IIMA monthly factor CSV URL on page")


def _load_iima_snapshot() -> pd.DataFrame:
    """Load the committed IIMA snapshot CSV, or return empty DataFrame."""
    if _IIMA_SNAPSHOT_PATH.exists():
        df = pd.read_csv(_IIMA_SNAPSHOT_PATH, parse_dates=["date"])
        return df
    return pd.DataFrame()


def fetch_iima_factors(force_refresh: bool = False) -> pd.DataFrame:
    """Return IIMA 4-factor monthly data, using cache if fresh.

    Falls back to data/iima_factors_snapshot.csv when the IIMA site is unreachable.
    """
    if not force_refresh and not is_stale(IIMA_CACHE):
        return read_cache(IIMA_CACHE)
    try:
        csv_url = _discover_iima_csv_url()
        resp = requests.get(csv_url, timeout=60)
        resp.raise_for_status()
        df = _parse_iima_live_csv(resp.text)
        write_cache(df, IIMA_CACHE)
        return df
    except Exception:
        snapshot = _load_iima_snapshot()
        if not snapshot.empty:
            return snapshot
        return pd.DataFrame()


import re
import time

SCREENER_CACHE = CACHE_DIR / "portfolio_fundamentals.parquet"


def _clean_numeric(text: str) -> float:
    """Strip currency symbols, commas, percent signs and return float."""
    cleaned = re.sub(r"[₹,%\s]|Cr\.", "", text.strip())
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
    """Fetch fundamentals for a single NSE ticker from Screener.in.

    Returns an empty dict if Screener.in is unreachable or blocks the request.
    """
    cache_path = CACHE_DIR / f"screener_{ticker}.parquet"
    if not force_refresh and not is_stale(cache_path):
        return read_cache(cache_path).iloc[0].to_dict()
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = parse_screener_fundamentals(resp.text)
    except Exception:
        data = {}
    data["ticker"] = ticker
    if data:
        try:
            write_cache(pd.DataFrame([data]), cache_path)
        except Exception:
            pass
    time.sleep(1.5)  # be polite to Screener.in
    return data


_SNAPSHOT_PATH = Path(__file__).parent.parent / "data" / "screener_snapshot.csv"


def _load_snapshot() -> pd.DataFrame:
    """Load the committed Screener.in snapshot CSV, or return empty DataFrame."""
    if _SNAPSHOT_PATH.exists():
        return pd.read_csv(_SNAPSHOT_PATH)
    return pd.DataFrame()


def fetch_all_fundamentals(tickers: list[str], force_refresh: bool = False) -> pd.DataFrame:
    """Fetch fundamentals for all tickers; return one row per ticker.

    Falls back to the committed screener_snapshot.csv when Screener.in is unreachable.
    """
    snapshot = _load_snapshot()

    rows = []
    for ticker in tickers:
        data = fetch_screener_fundamentals(ticker, force_refresh=force_refresh)
        # If live fetch returned nothing, try the snapshot
        if not any(k != "ticker" for k in data):
            if not snapshot.empty and ticker in snapshot["ticker"].values:
                snap_row = snapshot[snapshot["ticker"] == ticker].iloc[0].to_dict()
                snap_row["ticker"] = ticker
                data = snap_row
        data["ticker"] = ticker
        rows.append(data)
    return pd.DataFrame(rows)


PRICES_CACHE = CACHE_DIR / "stock_prices.parquet"
_PRICE_SNAPSHOT_PATH = Path(__file__).parent.parent / "data" / "price_returns_snapshot.csv"


def _load_price_snapshot() -> pd.DataFrame:
    """Load committed monthly-returns snapshot; index = datetime, columns = tickers."""
    if _PRICE_SNAPSHOT_PATH.exists():
        df = pd.read_csv(_PRICE_SNAPSHOT_PATH, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    return pd.DataFrame()


def fetch_tickertape_prices(ticker: str, years: int = 5, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch monthly closing prices for a given NSE ticker via yfinance.

    Returns DataFrame with columns: date (datetime), price (float).
    """
    cache_path = CACHE_DIR / f"prices_{ticker}.parquet"
    if not force_refresh and not is_stale(cache_path):
        return read_cache(cache_path)

    try:
        import yfinance as yf
        raw = yf.download(
            f"{ticker}.NS", period=f"{years}y", interval="1mo",
            auto_adjust=True, progress=False
        )["Close"]
        if raw.empty:
            raise ValueError("empty")
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        df = raw.reset_index()
        df.columns = ["date", "price"]
        df = df.dropna()
        write_cache(df, cache_path)
        return df
    except Exception:
        return pd.DataFrame(columns=["date", "price"])


def fetch_all_prices(tickers: list[str], years: int = 6, force_refresh: bool = False) -> pd.DataFrame:
    """Return a DataFrame of monthly returns indexed by date, columns = tickers.

    Tries yfinance first; falls back to the committed price_returns_snapshot.csv.
    """
    try:
        import yfinance as yf
        yf_tickers = [f"{t}.NS" for t in tickers]
        raw = yf.download(yf_tickers, period=f"{years}y", interval="1mo",
                          auto_adjust=True, progress=False)["Close"]
        raw.columns = [c.replace(".NS", "") for c in raw.columns]
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        returns = raw.pct_change().dropna(how="all")
        if not returns.empty:
            return returns
    except Exception:
        pass

    # Fallback: committed snapshot
    return _load_price_snapshot()


def compute_monthly_returns(prices_df: pd.DataFrame) -> pd.Series:
    """Compute monthly returns from a DataFrame with date and price columns."""
    s = prices_df.set_index("date")["price"].sort_index()
    returns = s.pct_change().dropna()
    return returns
