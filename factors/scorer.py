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
    Missing optional columns (pb, de, revenue_cagr_3y, net_margin) default to 0.
    Returns DataFrame with ticker + 6 dimension z-score columns.
    Higher score = stronger tilt in that direction for all dimensions.
    """
    df = fundamentals.copy()

    # Fill missing columns with 0 before z-scoring
    for col in ["pb", "de", "revenue_cagr_3y", "net_margin", "momentum_12m_1m"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in ["pe", "pb", "roe", "roce", "market_cap_cr"]:
        if col not in df.columns:
            df[col] = 1.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(df[col].median() if col in df.columns else 1.0)

    # Value: lower P/E and P/B = better value → invert
    df["value"] = _zscore(-df["pe"]) * 0.5 + _zscore(-df["pb"]) * 0.5

    # Quality: higher ROE, ROCE, lower D/E = better quality
    de_col = _zscore(-df["de"])
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


def compute_nifty500_percentile_scores(
    port_scores: pd.Series,
    nifty500_snapshot_path: str,
) -> pd.Series:
    """Rank portfolio style scores vs Nifty 500 universe distribution.

    Loads the Nifty 500 snapshot, computes style z-scores for that universe,
    then finds where each portfolio dimension score falls in the resulting
    cross-sectional distribution (0 = bottom, 100 = top).

    Args:
        port_scores: Series of weighted portfolio z-scores (from compute_portfolio_scores),
                     indexed by dimension name.
        nifty500_snapshot_path: Path to CSV with Nifty 500 fundamentals.
    Returns:
        Series indexed by dimension with percentile ranks 0–100.
    """
    dims = ["value", "quality", "momentum", "size", "growth", "profitability"]
    try:
        nifty_df = pd.read_csv(nifty500_snapshot_path)
    except Exception:
        return pd.Series(50.0, index=dims)

    for col in ["momentum_12m_1m", "net_margin", "revenue_cagr_3y"]:
        if col not in nifty_df.columns:
            nifty_df[col] = 0.0

    nifty_scores = compute_style_scores(nifty_df)
    nifty_indexed = nifty_scores.set_index("ticker")[dims]

    percentiles = {}
    for dim in dims:
        universe = nifty_indexed[dim].dropna().values
        if len(universe) == 0:
            percentiles[dim] = 50.0
            continue
        score = port_scores.get(dim, 0.0)
        pct = float(np.mean(universe < score) * 100)
        percentiles[dim] = round(pct, 1)

    return pd.Series(percentiles)
