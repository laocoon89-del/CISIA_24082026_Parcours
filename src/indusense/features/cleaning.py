from __future__ import annotations

import pandas as pd


def clean_sensor_data(
    df: pd.DataFrame,
    sensor_cols: tuple[str, ...] = ("temperature", "pressure_bar"),
) -> pd.DataFrame:
    """Drop duplicate rows and impute missing sensor values with the per-machine median."""
    df = df.drop_duplicates().copy()
    for col in sensor_cols:
        df[col] = df.groupby("machine")[col].transform(lambda s: s.fillna(s.median()))
    return df
