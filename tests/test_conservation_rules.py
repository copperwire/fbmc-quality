from pandas.testing import assert_series_equal
import os
from pathlib import Path


def test_entsoe_conservation(tmp_path):
    # HACK: to override the setting of the DB_PATH this has to be inserted into env before the imports
    os.environ["DB_PATH"] = str(Path(tmp_path) / "test_data.duckdb")
    
    from contextlib import suppress
    from datetime import datetime

    import pandas as pd

    from fbmc_quality.entsoe_data import fetch_entsoe_data_from_bidding_zones, fetch_net_position_from_crossborder_flows
    from fbmc_quality.enums.bidding_zones import BiddingZonesEnum
    from fbmc_quality.exceptions.fbmc_exceptions import ENTSOELookupException
    from fbmc_quality.jao_data.analyse_jao_data import BIDDING_ZONE_CNEC_MAP


    test_period = (datetime(2023, 10, 1), datetime(2023, 10, 2))
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
