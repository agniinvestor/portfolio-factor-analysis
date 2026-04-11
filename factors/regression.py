import numpy as np
import pandas as pd
import statsmodels.api as sm
from dateutil.relativedelta import relativedelta
from statsmodels.regression.rolling import RollingOLS


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


def rolling_carhart_betas(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    window_months: int = 24,
) -> pd.DataFrame:
    """Compute rolling Carhart 4-factor betas.

    Args:
        portfolio_returns: Monthly portfolio returns (Series, datetime index).
        factor_returns: DataFrame with columns date, mkt_rf, smb, hml, wml, rf.
        window_months: Rolling window size in months.
    Returns:
        DataFrame indexed by date with columns mkt_rf, smb, hml, wml.
        Rows before the window fills are NaN.
    """
    factors = factor_returns.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
    aligned_port, aligned_fac = portfolio_returns.align(factors, join="inner")
    port_excess = aligned_port - aligned_fac["rf"]

    X = sm.add_constant(aligned_fac[["mkt_rf", "smb", "hml", "wml"]])
    rols = RollingOLS(port_excess, X, window=window_months).fit()

    betas = rols.params[["mkt_rf", "smb", "hml", "wml"]].copy()
    betas.index = port_excess.index
    return betas


def factor_return_attribution(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    reg_result: dict,
) -> pd.DataFrame:
    """Decompose monthly portfolio excess returns into factor contributions.

    For each month: alpha + Σ(beta_i * factor_i) + residual = port_excess.

    Args:
        portfolio_returns: Monthly portfolio returns (Series, datetime index).
        factor_returns: DataFrame with columns date, mkt_rf, smb, hml, wml, rf.
        reg_result: Dict returned by run_carhart_regression.
    Returns:
        DataFrame indexed by date with columns alpha, mkt_rf, smb, hml, wml, residual.
    """
    factors = factor_returns.set_index("date")[["mkt_rf", "smb", "hml", "wml", "rf"]]
    aligned_port, aligned_fac = portfolio_returns.align(factors, join="inner")
    port_excess = aligned_port - aligned_fac["rf"]

    result = pd.DataFrame(index=port_excess.index)
    result["alpha"] = reg_result["alpha"]

    factor_cols = ["mkt_rf", "smb", "hml", "wml"]
    for f in factor_cols:
        result[f] = reg_result["betas"][f] * aligned_fac[f]

    explained = result["alpha"] + result[factor_cols].sum(axis=1)
    result["residual"] = port_excess - explained
    return result
