import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal, assert_index_equal, assert_series_equal
from pytz import timezone
from sqlalchemy import create_engine


def test_jao_data(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")
    from fbmc_quality.dataframe_schemas.schemas import JaoData
    from fbmc_quality.datetime_handlers.handle_timezones import convert_date_to_utc_pandas
    from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries, try_jao_cache_before_async

    from_time = datetime(2023, 4, 2, 22, tzinfo=timezone("utc"))
    to_time = datetime(2023, 4, 3, 2, tzinfo=timezone("utc"))

    data = fetch_jao_dataframe_timeseries(from_time, to_time)
    from_time_pd = convert_date_to_utc_pandas(from_time)
    to_time_pd = convert_date_to_utc_pandas(to_time)
    cached_data, time_buckets = try_jao_cache_before_async(from_time_pd, to_time_pd)

    assert data is not None
    assert cached_data is not None
    assert time_buckets == []

    data = data.sort_values(["cnec_id", "time"], axis=0)
    cached_data = cached_data.sort_values(["cnec_id", "time"], axis=0)
    assert_index_equal(data.index, cached_data.index)
    for column in data.columns:
        if column == JaoData.contingencies:
            continue
        assert_series_equal(data[column], cached_data[column], check_index_type=False, check_dtype=False)


def test_entsoe_data(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")

    from fbmc_quality.dataframe_schemas.cache_db import DB_PATH
    from fbmc_quality.entsoe_data.fetch_entsoe_data import (
        _get_cross_border_flow_from_api,
        convert_date_to_utc_pandas,
        fetch_entsoe_data_from_bidding_zones,
        lookup_entsoe_areas_from_bz,
        query_and_cache_data,
        resample_to_hour_and_replace,
    )
    from fbmc_quality.enums.bidding_zones import BIDDING_ZONE_CNEC_MAP
    from fbmc_quality.exceptions.fbmc_exceptions import ENTSOELookupException

    from_time = datetime(2023, 4, 1, 0, tzinfo=timezone("utc"))
    to_time = datetime(2023, 4, 1, 4, tzinfo=timezone("utc"))

    api_key = os.getenv("ENTSOE_API_KEY")
    assert api_key is not None

    for from_zone, to_zones_and_cnec in BIDDING_ZONE_CNEC_MAP.items():
        for _, to_zone in to_zones_and_cnec:
            try:
                from_area, to_area = lookup_entsoe_areas_from_bz(from_zone, to_zone)
            except ENTSOELookupException:
                continue

            oneway_flow = _get_cross_border_flow_from_api(
                convert_date_to_utc_pandas(from_time), convert_date_to_utc_pandas(to_time), from_area, to_area
            )
            otherway_flow = _get_cross_border_flow_from_api(
                convert_date_to_utc_pandas(from_time), convert_date_to_utc_pandas(to_time), to_area, from_area
            )

            engine = create_engine("duckdb:///" + str(DB_PATH))
            query_and_cache_data(
                convert_date_to_utc_pandas(from_time), convert_date_to_utc_pandas(to_time), from_area, to_area, engine
            )
            flow = resample_to_hour_and_replace((oneway_flow - otherway_flow).to_frame("flow"))
            flow.index.rename("time", True)
            engine.dispose()

            os.environ["ENTSOE_API_KEY"] = ""
            cached_flow = fetch_entsoe_data_from_bidding_zones(from_time, to_time, from_zone, to_zone)
            assert_frame_equal(flow, cached_flow)
            os.environ["ENTSOE_API_KEY"] = api_key


def test_entsoe_expected_date_range(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")

    from fbmc_quality.entsoe_data.fetch_entsoe_data import fetch_net_position_from_crossborder_flows

    from_time = datetime(2023, 3, 31, 22, tzinfo=timezone("utc"))
    to_time = datetime(2023, 4, 1, 4, tzinfo=timezone("utc"))
    expected_range = pd.date_range(from_time, to_time, freq="H", inclusive="left").rename("time")

    nps = fetch_net_position_from_crossborder_flows(from_time, to_time)

    assert nps is not None
    assert_index_equal(expected_range, nps.index)


def test_jao_expected_date_range(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")
    from fbmc_quality.jao_data.analyse_jao_data import compute_basecase_net_pos
    from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries

    from_time = datetime(2023, 4, 2, 22, tzinfo=timezone("utc"))
    to_time = datetime(2023, 4, 3, 2, tzinfo=timezone("utc"))
    expected_range = pd.date_range(from_time, to_time, freq="H", inclusive="left").rename("time")

    data = fetch_jao_dataframe_timeseries(from_time, to_time)
    assert data is not None
    assert_index_equal(expected_range, data.index.unique("time"))

    nps = compute_basecase_net_pos(from_time, to_time)
    assert nps is not None
    assert_index_equal(expected_range, nps.index)
