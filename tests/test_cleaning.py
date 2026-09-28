import pandas as pd

from indusense.features.cleaning import clean_sensor_data


def test_clean_sensor_data_imputes_by_machine():
    df = pd.DataFrame(
        {
            "machine": ["MACH-01", "MACH-01", "MACH-02", "MACH-02"],
            "temperature": [10.0, None, 30.0, None],
            "pressure_bar": [100.0, 102.0, 200.0, None],
        }
    )
    out = clean_sensor_data(df)
    assert out.loc[1, "temperature"] == 10.0
    assert out.loc[3, "temperature"] == 30.0
