import numpy as np
import pandas as pd
import statsmodels.api as sm
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
        dict with keys: alpha, alpha_t, alpha_p, betas, t_stats, p_values, r_squared, n_obs.
    """
    factors = factor_returns.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]

    # Align portfolio returns with factor dates
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
