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


def fetch_iima_factors(force_refresh: bool = False) -> pd.DataFrame:
    """Return IIMA 4-factor monthly data, using cache if fresh."""
    if not force_refresh and not is_stale(IIMA_CACHE):
        return read_cache(IIMA_CACHE)
    csv_url = _discover_iima_csv_url()
    resp = requests.get(csv_url, timeout=60)
    resp.raise_for_status()
    df = _parse_iima_live_csv(resp.text)
    write_cache(df, IIMA_CACHE)
    return df


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


def fetch_all_fundamentals(tickers: list[str], force_refresh: bool = False) -> pd.DataFrame:
    """Fetch fundamentals for all tickers; return one row per ticker.

    Stocks where Screener.in fetch fails will have NaN for fundamental columns.
    """
    rows = []
    for ticker in tickers:
        data = fetch_screener_fundamentals(ticker, force_refresh=force_refresh)
        data["ticker"] = ticker
        rows.append(data)
    return pd.DataFrame(rows)


PRICES_CACHE = CACHE_DIR / "stock_prices.parquet"


def fetch_tickertape_prices(ticker: str, years: int = 5, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch monthly closing prices from Tickertape for a given NSE ticker.

    Returns DataFrame with columns: date (datetime), price (float).
    Falls back to NSE historical data if Tickertape layout changes.
    """
    cache_path = CACHE_DIR / f"prices_{ticker}.parquet"
    if not force_refresh and not is_stale(cache_path):
        return read_cache(cache_path)

    # Tickertape exposes historical price data via JSON endpoint
    api_url = f"https://api.tickertape.in/stocks/charts/inter/{ticker}?duration={years}y&type=price"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
    resp = requests.get(api_url, headers=headers, timeout=30)

    if resp.status_code == 200:
        data = resp.json()
        points = data.get("data", {}).get("points", [])
        records = [{"date": pd.to_datetime(p["date"]), "price": p["value"]} for p in points]
    else:
        # Fallback: NSE historical data
        records = _fetch_nse_historical(ticker, years)

    df = pd.DataFrame(records)
    if df.empty:
        return df
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
