import logging
import os
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator, Iterable, Sequence

import duckdb
import numpy as np
import pandas as pd
import psutil
from entsoe import Area, EntsoePandasClient
from joblib import Parallel, delayed
from pandera.typing import DataFrame
from requests import Session
from sqlalchemy import Engine, create_engine

from fbmc_quality.dataframe_schemas.cache_db.cache_db_functions import store_df_in_table
from fbmc_quality.dataframe_schemas.schemas import Base, NetPosition
from fbmc_quality.enums.bidding_zones import BiddingZonesEnum
from fbmc_quality.jao_data.analyse_jao_data import is_elements_equal_to_target
from fbmc_quality.jao_data.get_utc_delta import get_utc_delta

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
    # BiddingZones.DK1: Area.DK_1,
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
    # Area.DK_1: [Area.NO_2, Area.DK_2, Area.SE_3, Area.DE_LU],
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
}


BIDDINGZONE_CROSS_BORDER_NP_MAP: dict[BiddingZonesEnum, list[BiddingZonesEnum]] = {
    BiddingZonesEnum.NO1: [
        BiddingZonesEnum.NO2,
        BiddingZonesEnum.NO3,
        BiddingZonesEnum.NO5,
        BiddingZonesEnum.SE3,
    ],
    BiddingZonesEnum.NO2: [
        BiddingZonesEnum.NO2_ND,
        BiddingZonesEnum.NO2_NK,
        BiddingZonesEnum.DK1,
        BiddingZonesEnum.NO5,
        BiddingZonesEnum.NO1,
    ],
    BiddingZonesEnum.NO3: [
        BiddingZonesEnum.NO1,
        BiddingZonesEnum.NO5,
        BiddingZonesEnum.NO4,
        BiddingZonesEnum.SE2,
    ],
    BiddingZonesEnum.NO4: [
        BiddingZonesEnum.SE1,
        BiddingZonesEnum.FI,
        BiddingZonesEnum.NO3,
        BiddingZonesEnum.SE2,
    ],
    BiddingZonesEnum.NO5: [BiddingZonesEnum.NO1, BiddingZonesEnum.NO3, BiddingZonesEnum.NO2],
    BiddingZonesEnum.SE1: [BiddingZonesEnum.NO4, BiddingZonesEnum.SE2, BiddingZonesEnum.FI],
    BiddingZonesEnum.SE2: [
        BiddingZonesEnum.SE1,
        BiddingZonesEnum.SE3,
        BiddingZonesEnum.NO3,
        BiddingZonesEnum.NO4,
    ],
    BiddingZonesEnum.SE3: [
        BiddingZonesEnum.NO1,
        BiddingZonesEnum.DK1,
        BiddingZonesEnum.FI,
        BiddingZonesEnum.SE4,
        BiddingZonesEnum.SE2,
    ],
    BiddingZonesEnum.SE4: [
        BiddingZonesEnum.SE3,
        BiddingZonesEnum.SE4_SP,
        BiddingZonesEnum.SE4_NB,
        BiddingZonesEnum.SE4_BC,
        BiddingZonesEnum.DK2,
    ],
    BiddingZonesEnum.FI: [
        BiddingZonesEnum.NO4,
        BiddingZonesEnum.SE1,
        BiddingZonesEnum.SE3,
        BiddingZonesEnum.FI_EL,
    ],
}


def convert_date_to_utc_pandas(date_obj: date | datetime) -> pd.Timestamp:
    if isinstance(date_obj, pd.Timestamp):
        return date_obj
    if hasattr(date_obj, "tzinfo") and date_obj.tzinfo is not None:
        return pd.Timestamp(date_obj)
        
    return pd.Timestamp(date_obj, tz="Europe/Oslo").tz_convert('UTC')


def get_entsoe_client(session: Session | None = None) -> EntsoePandasClient:
    api_key = os.getenv("ENTSOE_API_KEY")
    if api_key is None:
        raise EnvironmentError("No environment variable named ENTSOE_API_KEY")

    return EntsoePandasClient(api_key, session=session)


def get_np_data_from_cache(
    start: pd.Timestamp, end: pd.Timestamp, write_path: Path
) -> tuple[DataFrame[NetPosition], pd.Timestamp] | tuple[None, pd.Timestamp]:
    current_time = start
    all_paths = []

    while current_time < end:
        file_path = write_path / f'net_positions_{current_time.strftime("%Y%m%dT%H")}.arrow'
        if file_path.exists():
            all_paths.append(file_path)
        else:
            break
        current_time += timedelta(hours=1)

    if all_paths:
        cores = psutil.cpu_count()
        frames: Generator[pd.DataFrame, None, None] = Parallel(cores, backend="loky", return_as="generator")(
            delayed(pd.read_feather)(path) for path in all_paths
        )
        return pd.concat(frames), current_time
    else:
        return None, current_time  # type: ignore


def cache_np_data(frame: pd.DataFrame, write_path: Path) -> None:
    for hour, sub_frame in frame.iterrows():
        sub_frame.to_frame().T.to_feather(write_path / f'net_positions_{hour.strftime("%Y%m%dT%H")}.arrow')


def fetch_net_position_from_crossborder_flows(
    start: date,
    end: date,
    bidding_zones: list[BiddingZonesEnum] | BiddingZonesEnum | None = None,
    filter_non_conforming_hours: bool = False,
) -> DataFrame[NetPosition] | None:
    """Computes the net-positions in a period from `start` to `end` from data from ENTSOE Transparency,
      for the given `bidding_zones`

    Args:
        start (date | None, optional): Date to start filter the computation on.
        end (date | None, optional): Date to end filter the computation on.
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

    retval = _get_net_position_from_crossborder_flows(start_pd, end_pd)
    retval = pd.concat(retval, axis=1)

    if check_for_zero_zum:
        filter_list = is_elements_equal_to_target(retval.sum(axis=1), threshold=1)
        if filter_non_conforming_hours:
            retval = retval.where(~filter_list)
    return retval  # type: ignore


def _get_net_position_from_crossborder_flows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    bidding_zones: list[BiddingZonesEnum] | BiddingZonesEnum | None = None,
) -> list[DataFrame[NetPosition]]:
    if bidding_zones is None:
        bidding_zones = [bz for bz in BiddingZonesEnum]

    df_list = []

    for bidding_zone in bidding_zones:
        if bidding_zone in ENSTOE_BIDDING_ZONE_MAP:
            area_from = ENSTOE_BIDDING_ZONE_MAP[bidding_zone]
            exchange_areas = ENTSOE_CROSS_BORDER_NP_MAP[area_from]
        elif bidding_zone in ENTSOE_HVDC_ZONE_MAP:
            area_from = ENTSOE_HVDC_ZONE_MAP[bidding_zone][0]
            exchange_areas: list[Area] = [ENTSOE_HVDC_ZONE_MAP[bidding_zone][1]]
        else:
            continue

        data: list[pd.Series] = []
        other_direction_data: list[pd.Series] = []

        for area_to in exchange_areas:
            series_onedir = _get_cross_border_flow(start, end, area_from, area_to)
            data.append(series_onedir)
            series_otherdir = _get_cross_border_flow(start, end, area_to, area_from)
            other_direction_data.append(series_otherdir)

        resampled_data = []
        for series in data:
            if series.index.freqstr != "H":
                resampled_data.append(series.resample("H", label="left").mean())

        resampled_other_direction_data = []
        for series in other_direction_data:
            if series.index.freqstr != "H":
                resampled_other_direction_data.append(series.resample("H", label="left").mean())

        left_data = pd.concat(resampled_data, axis=1).sum(axis=1).tz_convert("UTC")
        right_data = pd.concat(resampled_other_direction_data, axis=1).sum(axis=1).tz_convert("UTC")

        _df_bz = left_data - right_data
        _df_bz.name = bidding_zone.value
        df_list.append(_df_bz)  # , bidding_zone)

    return df_list


def _get_cross_border_flow(
    start: pd.Timestamp, end: pd.Timestamp, area_from: Area, area_to: Area, _recursive: bool = False
) -> pd.Series:
    default_folder_path = Path.home() / Path(".flowbased_data")
    db_path = default_folder_path / "linearisation_analysis.duckdb"

    connection = duckdb.connect(str(db_path), read_only=False)

    cached_data = None
    with suppress(duckdb.CatalogException):
        cached_data = connection.sql(
            (
                "SELECT * FROM ENTSOE WHERE time BETWEEN"
                f"'{start + timedelta(hours=get_utc_delta(start))}' AND '{end + timedelta(hours=get_utc_delta(start))}'"
                f"AND area_from='{area_from.value}' AND area_to='{area_to.value}'"
            )
        ).df()
    connection.close()

    engine = create_engine("duckdb:///" + str(db_path))
    Base.metadata.create_all(engine)

    if cached_data is not None and not cached_data.empty:
        cached_data["time"] = cached_data["time"].dt.tz_localize("Europe/Oslo").dt.tz_convert("UTC")
        cached_retval = cached_data.set_index("time")["flow"]
        unique_timestamps: Sequence[datetime] = np.sort(cached_data["time"].unique().to_pydatetime())
        hours = (end - start).total_seconds() // (60 * 60)
        quarters = (end - start).total_seconds() // (60 * 15)

        if len(unique_timestamps) == hours or len(unique_timestamps) == quarters:
            return cached_retval

    data = _get_cross_border_flow_from_api(start, end, area_from, area_to)
    cache_flow_data(engine, data, area_from, area_to)
    if _recursive:
        raise RuntimeError("Recurse calls did not yield all data from ENTSOE - report this error to the maintainer")
    return _get_cross_border_flow(start, end, area_from, area_to, _recursive=True)


def cache_flow_data(engine: Engine, data: pd.Series, area_from: Area, area_to: Area):
    frame = pd.DataFrame({"flow": data})
    frame["area_from"] = area_from.value
    frame["area_to"] = area_to.value
    frame = frame.rename_axis("time").reset_index()
    frame["time"] = frame["time"].dt.tz_convert("UTC")
    frame["ROW_KEY"] = frame["area_from"] + "_" + frame["area_to"] + "_" + frame["time"].astype(str)
    store_df_in_table("ENTSOE", frame, engine)


def _get_cross_border_flow_from_api(
    start: pd.Timestamp, end: pd.Timestamp, area_from: Area, area_to: Area
) -> pd.Series:
    logging.getLogger().info(f"Fetching ENTSOE data from {start} to {end} for {area_from} to {area_to}")

    client = get_entsoe_client()
    crossborder_flow = client.query_crossborder_flows(
        country_code_from=area_from,
        country_code_to=area_to,
        start=start,
        end=end,
    )

    return crossborder_flow


def get_cross_border_flow(start: date, end: date, area_from: Area, area_to: Area) -> pd.Series:
    """Gets the cross border flow from in a date-range for an interchange from/to an Area.
    `**NOTE**` the flows are all > 0, meaning you need to retrieve both directions to get expected data

    Args:
        start (date): stat of the retrieval range
        end (date): end of the retrieval range
        area_from (Area): from area
        area_to (Area): to area

    Returns:
        pd.Series: series of cross border flow
    """
    start_pd = convert_date_to_utc_pandas(start)
    end_pd = convert_date_to_utc_pandas(end)

    return _get_cross_border_flow(start_pd, end_pd, area_from, area_to)


def fetch_observed_entsoe_data_for_cnec(
    from_area: BiddingZonesEnum,
    to_area: BiddingZonesEnum,
    start_date: date,
    end_date: date,
) -> DataFrame:
    """Calculates the flow on a border CNEC between two areas for a time period

    Args:
        from_area (BiddingZonesEnum): Start biddingzone - flow from this area has a positive sign
        to_area (BiddingZonesEnum): End biddingzone - flow to this area has positive sign
        start_date (date): start date to pull data from
        end_date (date): enddate to pull data to

    Raises:
        ValueError: Mapping error if `ENTSOE_BIDDING_ZONE_MAP` does not contain the from/to zone.

    Returns:
        DataFrame: Frame with  time as index and one column `flow`
    """
    if from_area in ENSTOE_BIDDING_ZONE_MAP:
        enstoe_from_area = ENSTOE_BIDDING_ZONE_MAP[from_area]
    elif from_area in ENTSOE_HVDC_ZONE_MAP:
        enstoe_from_area = ENTSOE_HVDC_ZONE_MAP[from_area][0]
    else:
        raise ValueError(f"No mapping for {from_area}")

    if to_area in ENSTOE_BIDDING_ZONE_MAP:
        entsoe_to_area = ENSTOE_BIDDING_ZONE_MAP[to_area]
    elif to_area in ENTSOE_HVDC_ZONE_MAP:
        entsoe_to_area = ENTSOE_HVDC_ZONE_MAP[to_area][1]
        if entsoe_to_area == enstoe_from_area:
            entsoe_to_area = ENTSOE_HVDC_ZONE_MAP[to_area][0]
    else:
        raise ValueError(f"No mapping for {to_area}")

    df0 = get_cross_border_flow(start_date, end_date, enstoe_from_area, entsoe_to_area)
    df1 = get_cross_border_flow(start_date, end_date, entsoe_to_area, enstoe_from_area)

    df = df0 - df1

    return df.to_frame("flow")
