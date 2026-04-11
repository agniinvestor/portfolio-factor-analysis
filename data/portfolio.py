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
