import logging
from contextlib import suppress
from datetime import date, datetime
from typing import Literal
from warnings import warn

import pandas as pd
import polars as pl
import pytz
from pandera.typing import DataFrame

from fbmc_quality.dataframe_schemas.schemas import JaoData, NetPosition
from fbmc_quality.enums.bidding_zones import BiddingZonesEnum as BiddingZonesEnum
from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries

ALTERNATIVE_NAMES = {
    "NO_NO2_NL->NO2": ["NL->NO2"],
    "NO_NO2_DE->NO2": ["DE->NO2"],
    "NO_NO2_DK1->NO2": ["DK1->NO2"],
}


BIDDING_ZONE_CNEC_MAP = {
    BiddingZonesEnum.NO1: [
        "NO2->NO1",
        "NO3->NO1",
        "NO5->NO1",
        "SE3->NO1",
    ],
    BiddingZonesEnum.NO2: [
        "NO_NO2_NL->NO2",
        "NO_NO2_DE->NO2",
        "NO_NO2_DK1->NO2",
        "NO5->NO2",
        "NO1->NO2",
    ],
    BiddingZonesEnum.NO3: [
        "NO1->NO3",
        "NO5->NO3",
        "NO4->NO3",
        "SE2->NO3",
    ],
    BiddingZonesEnum.NO4: [
        "SE1->NO4",
        "FI->NO4",
        "NO3->NO4",
        "SE2->NO4",
    ],
    BiddingZonesEnum.NO5: [
        "NO1->NO5",
        "NO3->NO5",
        "NO2->NO5",
    ],
    BiddingZonesEnum.NO2_SK: ["Border_CNEC_NO2-NO2_SK"],
    BiddingZonesEnum.NO2_NK: ["Border_CNEC_NO2-NO2_NK"],
    BiddingZonesEnum.NO2_ND: ["Border_CNEC_NO2-NO2_ND"],
    BiddingZonesEnum.DK1: [
        "Border_CNEC_DK1_DE-DK1",
        "Border_CNEC_DK1_KS-DK1",
        "Border_CNEC_DK1_SB-DK1",
        "Border_CNEC_DK1_CO-DK1",
        "Border_CNEC_DK1_SK-DK1",
    ],
    BiddingZonesEnum.DK2: ["Border_CNEC_DK2_SB-DK2", "Border_CNEC_DK2_KO-DK2", "Border_CNEC_SE4-DK2"],
    BiddingZonesEnum.DK1_CO: [
        "Border_CNEC_DK1-DK1_CO",
    ],
    BiddingZonesEnum.DK1_DE: [
        "Border_CNEC_DK1-DK1_DE",
    ],
    BiddingZonesEnum.DK1_KS: [
        "Border_CNEC_DK1-DK1_KS",
    ],
    BiddingZonesEnum.DK1_SB: [
        "Border_CNEC_DK1-DK1_SB",
    ],
    BiddingZonesEnum.DK1_SK: [
        "Border_CNEC_DK1-DK1_SK",
    ],
    BiddingZonesEnum.SE1: [
        "Border_CNEC_NO4-SE1",
        "Border_CNEC_SE2-SE1",
        "Border_CNEC_FI-SE1",
    ],
    BiddingZonesEnum.SE2: [
        "Border_CNEC_SE1-SE2",
        "Border_CNEC_SE3-SE2",
        "Border_CNEC_NO4-SE2",
        "Border_CNEC_NO3-SE2",
    ],
    BiddingZonesEnum.SE3: [
        "Border_CNEC_NO1-SE3",
        "Border_CNEC_SE3_KS-SE3",
        "Border_CNEC_SE3_FS-SE3",
        "Border_CNEC_SE3_SWL-SE3",
        "Border_CNEC_SE4-SE3",
        "Border_CNEC_SE2-SE3",
    ],
    BiddingZonesEnum.SE3_KS: ["Border_CNEC_SE3-SE3_KS"],
    BiddingZonesEnum.SE4: [
        "Border_CNEC_SE3-SE4",
        "Border_CNEC_SE4_BC-SE4",
        "Border_CNEC_SE4_SP-SE4",
        "Border_CNEC_SE4_NB-SE4",
        "Border_CNEC_SE4_SWL-SE4",
        "Border_CNEC_DK2-SE4",
    ],
    BiddingZonesEnum.SE4_SWL: [
        "Border_CNEC_SE4-SE4_SWL",
    ],
    BiddingZonesEnum.SE4_BC: [
        "Border_CNEC_SE4-SE4_BC",
    ],
    BiddingZonesEnum.SE4_SP: [
        "Border_CNEC_SE4-SE4_SP",
    ],
    BiddingZonesEnum.SE4_NB: [
        "Border_CNEC_SE4-SE4_NB",
    ],
    BiddingZonesEnum.FI: [
        "Border_CNEC_NO4-FI",
        "Border_CNEC_SE1-FI",
        "Border_CNEC_FI_FS-FI",
        "Border_CNEC_FI_EL-FI",
    ],
    BiddingZonesEnum.FI_EL: [
        "Border_CNEC_FI-FI_EL",
    ],
    BiddingZonesEnum.FI_FS: [
        "Border_CNEC_FI-FI_FS",
    ],
    BiddingZonesEnum.SE3_FS: [
        "Border_CNEC_SE3-SE3_FS",
    ],
    BiddingZonesEnum.SE3_KS: [
        "Border_CNEC_SE3-SE3_KS",
    ],
    BiddingZonesEnum.SE3_SWL: [
        "Border_CNEC_SE3-SE3_SWL",
    ],
}


def get_utc_delta(input_date: date | datetime) -> Literal[1, 2]:
    ref_datetime = datetime(input_date.year, input_date.month, input_date.day)
    delta = (
        pytz.timezone("Europe/Oslo").fromutc(ref_datetime) - ref_datetime.astimezone(pytz.timezone("Europe/Oslo"))
    ).total_seconds()
    hours = int(delta / (60 * 60))
    if hours not in (1, 2):
        raise ValueError(f"Unexpected delta {hours} between Oslo and UTC at {input_date} ")
    return hours


def get_cnec_id_from_name(cnecName: str, dataset: DataFrame[JaoData]) -> str:
    """Gets the CNEC-ID for a given cnec name. Returns the id(s) associated with this name
    at the 0th timestep of the dataset

    Args:
        cnecName (str): CNEC to find the correspondig ID for
        dataset (DataFrame[JaoData]): Dataset of CNEC information. See `make_data_array_from_datetime` for the schema

    Returns:
        np.ndarray | int: Possibly Id(s) of the cnecs that correspond to the
    """

    cnec_ids = None
    test_alternative = True

    time_obj = dataset.index.get_level_values(JaoData.time)[0]
    time_slice = dataset.xs(key=time_obj, level=JaoData.time)
    ds_where = time_slice[JaoData.cnecName].where(time_slice[JaoData.cnecName] == cnecName)
    cnec_ids = ds_where.dropna().index.get_level_values(JaoData.cnec_id)

    if len(cnec_ids) == 1:
        return cnec_ids.values[0]

    if cnecName in ALTERNATIVE_NAMES and test_alternative:
        test_alternative = False
        with suppress(ValueError):
            for alternative in ALTERNATIVE_NAMES[cnecName]:
                pot_id = get_cnec_id_from_name(alternative, dataset)
                return pot_id

    fallback_id = _get_cnec_id_from_polars_frame(cnecName, dataset)["cnec_id"].unique()
    if len(fallback_id) == 1:
        return fallback_id[0]

    raise ValueError(f"Ambigious or non-existent ID for {cnecName}, expected one but found {cnec_ids}")


def _get_cnec_id_from_polars_frame(cnecName: str, dataset: DataFrame[JaoData]) -> pd.DataFrame:
    logging.getLogger().info("Trying fallback method for finding CNEC ID")

    frame = pl.from_pandas(dataset, rechunk=False, include_index=True)
    selected_data = frame.filter(pl.col(JaoData.cnecName) == cnecName)
    return selected_data.select(pl.col(JaoData.cnec_id)).to_pandas()


def get_cross_border_cnec_ids(
    df: DataFrame[JaoData], bidding_zones: BiddingZonesEnum | list[BiddingZonesEnum] | None = None
) -> dict[BiddingZonesEnum, list[str]]:
    """From a dataset find the cnec ids (a coordinate in the DS) that correspond to the cross border flows.
    The mapping is maintained in BIDDING_ZONE_CNEC_MAP

    Args:
        ds (DataFrame[JaoData]): Dataset in which to find the cross border flows.
            Must have index cnec_id, and column cnecName
        bidding_zones (BiddingZonesEnum | list[BiddingZones] | None, optional):
            Bidding zones for which to find cross border cnecs. Defaults to None.

    Returns:
        dict[BiddingZonesEnum, list[str]]: mapping of bidding zone to cnec_id strings
    """
    if bidding_zones is None:
        bidding_zones = [bz for bz in BiddingZonesEnum]

    if isinstance(bidding_zones, BiddingZonesEnum):
        bidding_zones = [bidding_zones]

    bz_to_cnec_id_map = {bz: [] for bz in bidding_zones}

    for bidding_zone in bidding_zones:
        cnec_mrids = []
        try:
            cnec_names = BIDDING_ZONE_CNEC_MAP[bidding_zone]
            for cnec_name in cnec_names:
                mrid = get_cnec_id_from_name(cnec_name, df)
                cnec_mrids.append(mrid)
        except (ValueError, KeyError):
            continue
        bz_to_cnec_id_map[bidding_zone] = cnec_mrids

    return bz_to_cnec_id_map


def compute_basecase_net_pos(
    start: date,
    end: date,
    bidding_zones: BiddingZonesEnum | list[BiddingZonesEnum] | None = None,
    filter_non_conforming_hours: bool = False,
) -> DataFrame[NetPosition] | None:
    """Computes the net-positions in a period from `start` to `end` from data in `dataset`,
      for the given `bidding_zones`

    Args:
        dataset (DataFrame[JaoData]): Data used to compute the net positions.
        start (date | None, optional): Date to start filter the computation on.
        end (date | None, optional): Date to end filter the computation on.
        bidding_zones (BiddingZonesEnum | list[BiddingZones] | None, optional):
            Bidding zones to compute the net position for.
            Defaults to None, which will compute for ALL bidding zones.

    Returns DataFrame[JaoData]:
    """

    check_for_zero_zum = False
    if bidding_zones is None:
        bidding_zones = [bz for bz in BiddingZonesEnum]
        check_for_zero_zum = True
    elif filter_non_conforming_hours is True:
        raise RuntimeError("Cannot supply subset of bidding_zones and `filter_non_conforming_hours=True`")

    if isinstance(bidding_zones, BiddingZonesEnum):
        bidding_zones = [bidding_zones]

    dataset = fetch_jao_dataframe_timeseries(start, end)
    if dataset is None:
        raise RuntimeError(f"No date in interval {start} to {end}")

    all_cnec_mrids = get_cross_border_cnec_ids(dataset, bidding_zones)
    inner_dataset = dataset.dropna(subset=[JaoData.fref], how="all", axis=0)
    np_frames = []

    for bidding_zone in bidding_zones:
        cnec_mrids = all_cnec_mrids[bidding_zone]
        selected_data = inner_dataset[inner_dataset.index.get_level_values(JaoData.cnec_id).isin(cnec_mrids)]

        nps = selected_data[JaoData.fref].groupby(level=JaoData.time).sum()
        np_frames.append(nps.to_frame(bidding_zone.value))

    retval = -1 * pd.concat(np_frames, axis=1)
    if check_for_zero_zum:
        filter_list = is_elements_equal_to_target(retval.sum(1), threshold=5)
        if filter_non_conforming_hours:
            retval = retval.where(~filter_list)
    return retval


def is_elements_equal_to_target(
    array: "pd.Series[pd.Float64Dtype | pd.Int64Dtype]", target: int | float = 0, threshold: float = 1e-6
) -> "pd.Series[bool]":
    diff_arr = (array - target).abs() < threshold

    if diff_arr.sum() > 0:
        warn(
            (
                f"Conservation rule broken, expected array to equal {target}"
                f"everywhere, but {diff_arr.sum()} did not match the threshold"
            ),
            UserWarning,
        )

    return diff_arr
