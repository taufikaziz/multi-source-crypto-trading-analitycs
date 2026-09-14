import numpy as np
import pandas as pd


def build_market_metrics(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build Gold-layer market metrics from a Silver market snapshot.
    """

    df = dataframe.copy()

    # ---------------------------------
    # 24-HOUR PRICE CHANGE
    # ---------------------------------

    df["price_change_24h"] = (
        df["last_price"]
        - df["price_24h_ago"]
    )

    df["price_change_24h_pct"] = np.where(
        df["price_24h_ago"] > 0,
        (
            df["price_change_24h"]
            / df["price_24h_ago"]
        )
        * 100,
        np.nan,
    )

    # ---------------------------------
    # 7-DAY PRICE CHANGE
    # ---------------------------------

    df["price_change_7d"] = (
        df["last_price"]
        - df["price_7d_ago"]
    )

    df["price_change_7d_pct"] = np.where(
        df["price_7d_ago"] > 0,
        (
            df["price_change_7d"]
            / df["price_7d_ago"]
        )
        * 100,
        np.nan,
    )

    # ---------------------------------
    # BUY / SELL SPREAD
    # ---------------------------------

    df["spread"] = (
        df["sell_price"]
        - df["buy_price"]
    )

    df["spread_pct"] = np.where(
        df["buy_price"] > 0,
        (
            df["spread"]
            / df["buy_price"]
        )
        * 100,
        np.nan,
    )

    # ---------------------------------
    # VOLUME RANK
    # ---------------------------------

    df["volume_rank"] = (
        df["volume_idr"]
        .rank(
            ascending=False,
            method="dense",
        )
        .astype("Int64")
    )

    return df