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
