from datetime import datetime
from pathlib import Path
from pandas.testing import assert_series_equal, assert_index_equal, assert_frame_equal
import os



def test_jao_data(tmp_path):
    
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")
    from fbmc_quality.jao_data.fetch_jao_data import try_jao_cache_before_async
    from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries
    from fbmc_quality.dataframe_schemas.schemas import JaoData

    from_time = datetime(2023, 4, 1, 0)
    to_time = datetime(2023, 4, 1, 4)

    data = fetch_jao_dataframe_timeseries(from_time, to_time)
    cached_data, time_buckets = try_jao_cache_before_async(from_time, to_time)

    assert data is not None
    assert cached_data is not None
    assert time_buckets == []

    data = data.sort_values(['cnec_id', 'time'], axis=0)
    cached_data = cached_data.sort_values(['cnec_id', 'time'], axis=0)
    assert_index_equal(data.index, cached_data.index)
    for column in data.columns:
        if column == JaoData.contingencies:
            continue
        assert_series_equal(data[column], cached_data[column], check_index_type=False, check_dtype=False)


def test_entsoe_data(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")
    
    from fbmc_quality.entsoe_data.fetch_entsoe_data import fetch_observed_entsoe_data_for_cnec, _get_cross_border_flow_from_api
    from fbmc_quality.enums.bidding_zones import BiddingZonesEnum

    from_time = datetime(2023, 4, 1, 0)
    to_time = datetime(2023, 4, 1, 4)

    flow = fetch_observed_entsoe_data_for_cnec(BiddingZonesEnum.NO1, BiddingZonesEnum.NO2, from_time, to_time)
    os.environ["ENTSOE_API_KEY"] = ""
    cached_flow = fetch_observed_entsoe_data_for_cnec(BiddingZonesEnum.NO1, BiddingZonesEnum.NO2, from_time, to_time)
    assert_frame_equal(flow, cached_flow)
