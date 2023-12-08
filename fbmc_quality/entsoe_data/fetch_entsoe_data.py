import logging
import os
import re
from contextlib import suppress
from datetime import datetime
from typing import Sequence, TypeVar

import duckdb
import Levenshtein
import numpy as np
import pandas as pd
from entsoe import Area, EntsoePandasClient
from pandera.typing import DataFrame
from requests import Session
from sqlalchemy import Engine, create_engine

from fbmc_quality.dataframe_schemas.cache_db import DB_PATH
from fbmc_quality.dataframe_schemas.cache_db.cache_db_functions import store_df_in_table
from fbmc_quality.dataframe_schemas.schemas import NetPosition
from fbmc_quality.datetime_handlers.handle_timezones import convert_date_to_utc_pandas
from fbmc_quality.enums.bidding_zones import ALT_NAME_MAP, BIDDING_ZONE_CNEC_MAP, AltBiddingZonesEnum, BiddingZonesEnum
from fbmc_quality.exceptions.fbmc_exceptions import ENTSOELookupException
from fbmc_quality.jao_data.analyse_jao_data import is_elements_equal_to_target

pandasDtypes = TypeVar("pandasDtypes", pd.DataFrame, pd.Series)

ENSTOE_BIDDING_ZONE_MAP: dict[BiddingZonesEnum, Area] = {
    BiddingZonesEnum.NO1: Area.NO_1,
    BiddingZonesEnum.NO2: Area.NO_2,
    BiddingZonesEnum.NO3: Area.NO_3,
    BiddingZonesEnum.NO4: Area.NO_4,
    BiddingZonesEnum.NO5: Area.NO_5,
    BiddingZonesEnum.SE1: Area.SE_1,
    BiddingZonesEnum.SE2: Area.SE_2,
    BiddingZonesEnum.SE3: Area.SE_3,
    BiddingZonesEnum.SE4: Area.SE_4,
    BiddingZonesEnum.FI: Area.FI,
    BiddingZonesEnum.DK2: Area.DK_2,
    BiddingZonesEnum.DK1: Area.DK_1,
}

ENTSOE_CROSS_BORDER_NP_MAP: dict[Area, list[Area]] = {
    Area.NO_1: [Area.NO_2, Area.NO_3, Area.NO_5, Area.SE_3],
    Area.NO_2: [Area.NL, Area.DE_LU, Area.DK_1, Area.NO_5, Area.NO_1],
    Area.NO_3: [Area.NO_1, Area.NO_5, Area.NO_4, Area.SE_2],
    Area.NO_4: [Area.SE_1, Area.FI, Area.NO_3, Area.SE_2],
    Area.NO_5: [Area.NO_1, Area.NO_3, Area.NO_2],
    Area.SE_1: [Area.NO_4, Area.SE_2, Area.FI],
    Area.SE_2: [Area.SE_1, Area.SE_3, Area.NO_3, Area.NO_4],
    Area.SE_3: [Area.NO_1, Area.DK_1, Area.FI, Area.SE_4, Area.SE_2],
    Area.SE_4: [Area.SE_3, Area.PL, Area.LT, Area.DE_LU, Area.DK_2],
    Area.FI: [Area.NO_4, Area.SE_1, Area.SE_3, Area.EE],
    Area.DK_2: [Area.SE_4, Area.DK_1, Area.DE_LU],
    Area.DK_1: [Area.NO_2, Area.DK_2, Area.SE_3, Area.DE_LU],
}

ENTSOE_HVDC_ZONE_MAP: dict[BiddingZonesEnum, tuple[Area, Area]] = {
    BiddingZonesEnum.NO2_SK: (Area.DK_1, Area.NO_2),
    BiddingZonesEnum.NO2_ND: (Area.NL, Area.NO_2),
    BiddingZonesEnum.NO2_NK: (Area.DE_LU, Area.NO_2),
    BiddingZonesEnum.SE3_FS: (Area.FI, Area.SE_3),
    BiddingZonesEnum.SE3_KS: (Area.DK_1, Area.SE_3),
    BiddingZonesEnum.SE4_SP: (Area.PL, Area.SE_4),
    BiddingZonesEnum.SE4_NB: (Area.LT, Area.SE_4),
    BiddingZonesEnum.SE4_BC: (Area.DE_LU, Area.SE_4),
    BiddingZonesEnum.FI_FS: (Area.SE_3, Area.FI),
    BiddingZonesEnum.FI_EL: (Area.EE, Area.FI),
    BiddingZonesEnum.DK2_SB: (Area.DK_1, Area.DK_2),
    BiddingZonesEnum.DK2_KO: (Area.DE_LU, Area.DK_2),
    BiddingZonesEnum.DK1_SB: (Area.DK_2, Area.DK_1),
    BiddingZonesEnum.DK1_CO: (Area.NL, Area.DK_1),
    BiddingZonesEnum.DK1_DE: (Area.DE_LU, Area.DK_1),
    BiddingZonesEnum.DK1_KS: (Area.SE_3, Area.DK_1),
    BiddingZonesEnum.DK1_SK: (Area.NO_2, Area.DK_1),
    BiddingZonesEnum.DK1_ST: (Area.DK_2, Area.DK_1),
    BiddingZonesEnum.DK2_ST: (Area.DK_1, Area.DK_2),
}


def get_from_to_bz_from_name(cnecName: str) -> tuple[BiddingZonesEnum, BiddingZonesEnum] | tuple[None, None]:
    bz1, bz2 = regex_get_from_to_bz_from_name(cnecName)
    if bz1 is None or bz2 is None:
        return substring_get_from_to_bz_from_name(cnecName)
    else:
        return bz1, bz2


def substring_get_from_to_bz_from_name(cnecName: str) -> tuple[BiddingZonesEnum, BiddingZonesEnum] | tuple[None, None]:
    all_bidding_zones = [bz for bz in BiddingZonesEnum] + [bz for bz in AltBiddingZonesEnum]

    for bz_from in all_bidding_zones:
        for bz_to in all_bidding_zones:
            if bz_from == bz_to:
                continue

            if bz_from.value in cnecName and bz_to.value in cnecName:
                dist1 = Levenshtein.distance(f"{bz_from.value} {bz_to.value}", cnecName)
                dist2 = Levenshtein.distance(f"{bz_to.value} {bz_from.value}", cnecName)
                if dist1 < dist2:
                    return (
                        BiddingZonesEnum(bz_from) if bz_from not in AltBiddingZonesEnum else ALT_NAME_MAP[bz_from],
                        BiddingZonesEnum(bz_to) if bz_to not in AltBiddingZonesEnum else ALT_NAME_MAP[bz_to],
                    )
                else:
                    return (
                        BiddingZonesEnum(bz_to) if bz_to not in AltBiddingZonesEnum else ALT_NAME_MAP[bz_to],
                        BiddingZonesEnum(bz_from) if bz_from not in AltBiddingZonesEnum else ALT_NAME_MAP[bz_from],
                    )
    return (None, None)


def regex_get_from_to_bz_from_name(cnecName: str) -> tuple[BiddingZonesEnum, BiddingZonesEnum] | tuple[None, None]:
    all_bidding_zones = [bz for bz in BiddingZonesEnum] + [bz for bz in AltBiddingZonesEnum]
    for bz_from in all_bidding_zones:
        for bz_to in all_bidding_zones:
            if bz_from == bz_to:
                continue

            match = re.search(rf"{bz_from.value}.+{bz_to.value}", cnecName)
            if match is not None:
                return (
                    BiddingZonesEnum(bz_from) if bz_from not in AltBiddingZonesEnum else ALT_NAME_MAP[bz_from],
                    BiddingZonesEnum(bz_to) if bz_to not in AltBiddingZonesEnum else ALT_NAME_MAP[bz_to],
                )
    return (None, None)


def get_entsoe_client(session: Session | None = None) -> EntsoePandasClient:
    api_key = os.getenv("ENTSOE_API_KEY")
    if api_key is None:
        raise EnvironmentError("No environment variable named ENTSOE_API_KEY")

    return EntsoePandasClient(api_key, session=session)


def fetch_net_position_from_crossborder_flows(
    start: datetime | pd.Timestamp,
    end: datetime | pd.Timestamp,
    bidding_zones: list[BiddingZonesEnum] | BiddingZonesEnum | None = None,
    filter_non_conforming_hours: bool = False,
) -> DataFrame[NetPosition] | None:
    """Computes the net-positions in a period from `start` to `end` from data from ENTSOE Transparency,
      for the given `bidding_zones`

    Args:
        start (datetime | pd.Timestamp): Datetime to start filter the computation on.
        end (datetime | pd.Timestamp): Datetime to end filter the computation on.
        bidding_zones (BiddingZones | list[BiddingZones] | None, optional):
            Bidding zones to compute the net position for.
            Defaults to None, which will compute for ALL bidding zones.

    Returns DataFrame[NetPosition]:
    """

    check_for_zero_zum = False
    if bidding_zones is None:
        bidding_zones = [bz for bz in BiddingZonesEnum]
        check_for_zero_zum = True
    elif filter_non_conforming_hours is True:
        raise RuntimeError("Cannot supply subset of bidding_zones and `filter_non_conforming_hours=True`")

    start_pd = convert_date_to_utc_pandas(start)
    end_pd = convert_date_to_utc_pandas(end)

    retval = _get_net_position_from_crossborder_flows(start_pd, end_pd, bidding_zones)

    if check_for_zero_zum:
        filter_list = is_elements_equal_to_target(retval.sum(axis=1), threshold=1)
        if filter_non_conforming_hours:
            retval = retval.where(~filter_list)
    return retval  # type: ignore


def _get_net_position_from_crossborder_flows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    bidding_zones: list[BiddingZonesEnum] | BiddingZonesEnum | None = None,
) -> DataFrame[NetPosition]:
    if bidding_zones is None:
        bidding_zones = [bz for bz in BiddingZonesEnum]
    elif isinstance(bidding_zones, BiddingZonesEnum):
        bidding_zones = [bidding_zones]

    df_list = []
    for bidding_zone in bidding_zones:
        data: list[pd.DataFrame] = []
        with suppress(KeyError, ENTSOELookupException):
            for bidding_zone_to in BIDDING_ZONE_CNEC_MAP[bidding_zone]:
                data.append(fetch_entsoe_data_from_bidding_zones(start, end, bidding_zone, bidding_zone_to[1]))

        if data:
            corridor_flows = pd.concat(data, axis=1)
            df_list.append(corridor_flows.sum(axis=1).rename(bidding_zone.value))

    return pd.concat(df_list, axis=1)  # type: ignore


def resample_to_hour_and_replace(data: pandasDtypes) -> pandasDtypes:
    if data.index.freqstr != "H":  # type: ignore
        data = data.resample("H", label="left").mean()
    return data


def _get_cross_border_flow(
    start: pd.Timestamp, end: pd.Timestamp, area_from: Area, area_to: Area, _recurse: bool = True
) -> "pd.Series[float]":
    connection = duckdb.connect(str(DB_PATH), read_only=False)
    cached_data = None
    with suppress(duckdb.CatalogException):
        cached_data = connection.sql(
            (
                "SELECT * FROM ENTSOE WHERE time BETWEEN "
                f"TIMESTAMPTZ '{start.isoformat()}' AND TIMESTAMPTZ '{end.isoformat()}'"
                f"AND area_from='{area_from.value}' AND area_to='{area_to.value}'"
            )
        ).df()
    connection.close()

    if cached_data is not None and not cached_data.empty:
        cached_retval = cast_cache_to_correct_types(cached_data)
        cached_retval = cached_retval[(start <= cached_retval.index) & (cached_retval.index < end)]
        unique_timestamps: Sequence[datetime] = np.sort(cached_retval.index.unique().to_pydatetime())  # type: ignore
        hours = (end - start).total_seconds() // (60 * 60)
        quarters = (end - start).total_seconds() // (60 * 15)

        if len(unique_timestamps) == hours or len(unique_timestamps) == quarters:
            return cached_retval

    engine = create_engine("duckdb:///" + str(DB_PATH))
    query_and_cache_data(start, end, area_from, area_to, engine)

    if not _recurse:
        raise RuntimeError("Recurse calls did not yield all data from ENTSOE - report this error to the maintainer")
    return _get_cross_border_flow(start, end, area_from, area_to, _recurse=False)


def cast_cache_to_correct_types(cached_data: pd.DataFrame) -> "pd.Series[float]":
    cached_data["time"] = cached_data["time"].astype(pd.DatetimeTZDtype("ns", "UTC"))
    cached_data["flow"] = cached_data["flow"].astype(pd.Float64Dtype())
    cached_retval = cached_data.set_index("time")["flow"]
    cached_retval.index.rename("time", True)
    with suppress(ValueError):
        cached_retval.index.freq = pd.infer_freq(cached_retval.index)  # type: ignore
    return cached_retval


def query_and_cache_data(start: pd.Timestamp, end: pd.Timestamp, area_from: Area, area_to: Area, engine: Engine):
    data = _get_cross_border_flow_from_api(start, end, area_from, area_to)
    other_data = _get_cross_border_flow_from_api(start, end, area_to, area_from)

    data = resample_to_hour_and_replace(data)
    other_data = resample_to_hour_and_replace(other_data)

    cache_flow_data(engine, data - other_data, area_from, area_to)
    cache_flow_data(engine, other_data - data, area_to, area_from)


def cache_flow_data(engine: Engine, data: pd.Series, area_from: Area, area_to: Area):
    frame = pd.DataFrame({"flow": data})
    frame["area_from"] = area_from.value
    frame["area_to"] = area_to.value
    frame = frame.rename_axis("time").reset_index()
    frame["ROW_KEY"] = frame["area_from"] + "_" + frame["area_to"] + "_" + frame["time"].astype(str)
    store_df_in_table("ENTSOE", frame, engine)


def _get_cross_border_flow_from_api(
    start: pd.Timestamp, end: pd.Timestamp, area_from: Area, area_to: Area
) -> "pd.Series[float]":
    logging.getLogger().info(f"Fetching ENTSOE data from {start} to {end} for {area_from} to {area_to}")

    client = get_entsoe_client()
    crossborder_flow = client.query_crossborder_flows(
        country_code_from=area_from,
        country_code_to=area_to,
        start=start,
        end=end,
    )
    crossborder_flow.index = crossborder_flow.index.tz_convert("UTC")  # type: ignore
    crossborder_flow = crossborder_flow.astype(pd.Float64Dtype())

    return crossborder_flow


def get_cross_border_flow(
    start: datetime | pd.Timestamp, end: datetime | pd.Timestamp, area_from: Area, area_to: Area
) -> pd.Series:
    """Gets the cross border flow from in a date-range for an interchange from/to an Area.
    Timestamps are converted to UTC before querying the API. Returned time-data is in UTC.

    Args:
        start (date): start of the retrieval range, in local time
        end (date): end of the retrieval range, in local time
        area_from (Area): from area
        area_to (Area): to area

    Returns:
        pd.Series: series of cross border flow
    """
    start_pd = convert_date_to_utc_pandas(start)
    end_pd = convert_date_to_utc_pandas(end)

    return _get_cross_border_flow(start_pd, end_pd, area_from, area_to)


def fetch_entsoe_data_from_bidding_zones(
    start_date: datetime | pd.Timestamp,
    end_date: datetime | pd.Timestamp,
    from_area: BiddingZonesEnum,
    to_area: BiddingZonesEnum,
) -> pd.DataFrame:
    """Calculates the flow on a border CNEC between two areas for a time period

    Args:
        from_area (BiddingZonesEnum): Start biddingzone - flow from this area has a positive sign
        to_area (BiddingZonesEnum): End biddingzone - flow to this area has positive sign
        start_date (date): start date to pull data from
        end_date (date): enddate to pull data to

    Raises:
        ENTSOELookupException: Mapping error if `ENTSOE_BIDDING_ZONE_MAP` does not contain the from/to zone.

    Returns:
        DataFrame: Frame with  time as index and one column `flow`
    """

    enstoe_from_area, entsoe_to_area = lookup_entsoe_areas_from_bz(from_area, to_area)
    cross_border_flow = get_cross_border_flow(start_date, end_date, enstoe_from_area, entsoe_to_area)

    return_frame = cross_border_flow.to_frame("flow")
    return_frame = return_frame.sort_index()
    return return_frame


def fetch_entsoe_data_from_cnecname(
    start_date: datetime | pd.Timestamp,
    end_date: datetime | pd.Timestamp,
    cnecName: str,
) -> pd.DataFrame:
    """Calculates the flow on a border CNEC between two areas for a time period
    Wrapper around fetch_entsoe_data_from_bidding_zones

    Args:
        start_date (date): start date to pull data from
        end_date (date): enddate to pull data to
        cnecName (str): name of cnec to pull data for

    Raises:
        ENTSOELookupException: Mapping error if `ENTSOE_BIDDING_ZONE_MAP` does not contain the from/to zone.

    Returns:
        DataFrame: Frame with  time as index and one column `flow`
    """

    bidding_zone, to_zone = get_from_to_bz_from_name(cnecName)
    if bidding_zone is None or to_zone is None:
        raise ENTSOELookupException(f"No from/to zone found for {cnecName}")

    return fetch_entsoe_data_from_bidding_zones(start_date, end_date, bidding_zone, to_zone)


def lookup_entsoe_areas_from_bz(from_area: BiddingZonesEnum, to_area: BiddingZonesEnum) -> tuple[Area, Area]:
    if from_area in ENSTOE_BIDDING_ZONE_MAP:
        enstoe_from_area = ENSTOE_BIDDING_ZONE_MAP[from_area]
    elif from_area in ENTSOE_HVDC_ZONE_MAP:
        enstoe_from_area = ENTSOE_HVDC_ZONE_MAP[from_area][0]
    else:
        raise ENTSOELookupException(f"No mapping for {from_area}")

    if to_area in ENSTOE_BIDDING_ZONE_MAP:
        entsoe_to_area = ENSTOE_BIDDING_ZONE_MAP[to_area]
    elif to_area in ENTSOE_HVDC_ZONE_MAP:
        entsoe_to_area = ENTSOE_HVDC_ZONE_MAP[to_area][1]
        if entsoe_to_area == enstoe_from_area:
            entsoe_to_area = ENTSOE_HVDC_ZONE_MAP[to_area][0]
    else:
        raise ENTSOELookupException(f"No mapping for {to_area}")
    return enstoe_from_area, entsoe_to_area
