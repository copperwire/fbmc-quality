import os
from pathlib import Path

from pandas.testing import assert_series_equal
from pytz import timezone


def test_entsoe_conservation(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")

    from contextlib import suppress
    from datetime import datetime

    import pandas as pd

    from fbmc_quality.entsoe_data import fetch_entsoe_data_from_bidding_zones, fetch_net_position_from_crossborder_flows
    from fbmc_quality.enums.bidding_zones import BIDDING_ZONE_CNEC_MAP, BiddingZonesEnum
    from fbmc_quality.exceptions.fbmc_exceptions import ENTSOELookupException

    test_period = (datetime(2023, 10, 1, tzinfo=timezone("utc")), datetime(2023, 10, 2, tzinfo=timezone("utc")))
    start = test_period[0]
    end = test_period[1]

    net_positions = fetch_net_position_from_crossborder_flows(start, end)
    assert net_positions is not None

    for zone in net_positions.columns:
        zone = BiddingZonesEnum(zone)
        flows = pd.DataFrame()

        with suppress(KeyError, ENTSOELookupException):
            for other in BIDDING_ZONE_CNEC_MAP[zone]:
                zone_to_other_flow = fetch_entsoe_data_from_bidding_zones(start, end, zone, other[1]).rename(
                    {"flow": other[0]}, axis=1
                )
                flows = flows.merge(zone_to_other_flow, left_index=True, right_index=True, how="outer")

        if flows.empty:
            continue

        compared_np = flows.sum(axis=1).rename(zone.value)
        assert_series_equal(compared_np, net_positions[zone.value])


def test_ptdf_conservation(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")

    from datetime import datetime

    import pandas as pd

    from fbmc_quality.entsoe_data import fetch_net_position_from_crossborder_flows
    from fbmc_quality.enums.bidding_zones import BIDDING_ZONE_CNEC_MAP, BiddingZonesEnum
    from fbmc_quality.jao_data.analyse_jao_data import compute_basecase_net_pos
    from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries
    from fbmc_quality.linearisation_analysis.compute_functions import compute_linearised_flow
    from fbmc_quality.linearisation_analysis.dataclasses import JaoDataAndNPS
    from fbmc_quality.linearisation_analysis.process_data import load_data_for_corridor_cnec

    test_period = (datetime(2023, 10, 1, 21, tzinfo=timezone("UTC")), datetime(2023, 10, 2, 0, tzinfo=timezone("UTC")))
    start = test_period[0]
    end = test_period[1]

    net_positions = fetch_net_position_from_crossborder_flows(start, end)
    jao_data = fetch_jao_dataframe_timeseries(start, end)
    basecase_nps = compute_basecase_net_pos(start, end)

    assert net_positions is not None
    assert jao_data is not None
    assert basecase_nps is not None

    jaodata_and_nps = JaoDataAndNPS(jao_data, basecase_nps, net_positions)

    for zone in net_positions.columns:
        if zone not in [
            # BiddingZonesEnum.NO1,
            BiddingZonesEnum.NO2,
            BiddingZonesEnum.NO3,
            BiddingZonesEnum.NO4,
            BiddingZonesEnum.NO5,
            BiddingZonesEnum.SE1,
            BiddingZonesEnum.SE2,
            BiddingZonesEnum.SE3,
            BiddingZonesEnum.SE4,
        ]:
            continue
        zone = BiddingZonesEnum(zone)
        flows = pd.DataFrame()

        # with suppress(KeyError, ENTSOELookupException):
        for other in BIDDING_ZONE_CNEC_MAP[zone]:
            cnec_data = load_data_for_corridor_cnec(other[0], jaodata_and_nps)
            if cnec_data is None:
                continue
            flow = compute_linearised_flow(cnec_data.cnecData, jaodata_and_nps.observedNPs).rename(cnec_data.cnec_name)
            flows = flows.merge(flow, left_index=True, right_index=True, how="outer")

        recomputed_np = -1 * flows.sum(axis=1).rename(zone.value)
        assert_series_equal(recomputed_np, net_positions.loc[:, zone.value], atol=2)
