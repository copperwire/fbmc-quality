import logging
from contextlib import suppress
from datetime import date
from warnings import warn

import pandas as pd
import polars as pl
from pandera.typing import DataFrame

from fbmc_quality.dataframe_schemas.schemas import JaoData, NetPosition
from fbmc_quality.enums.bidding_zones import BiddingZonesEnum as BiddingZonesEnum
from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries

ALTERNATIVE_NAMES = {
    "NO_NO2_NL->NO2": ["NL->NO2"],
    "NO_NO2_DE->NO2": ["DE->NO2"],
    "NO_NO2_DK1->NO2": ["DK1->NO2"],
}


BIDDING_ZONE_CNEC_MAP: dict[BiddingZonesEnum, list[tuple[str, BiddingZonesEnum]]] = {
    BiddingZonesEnum.NO1: [
        ("NO2->NO1", BiddingZonesEnum.NO2),
        ("NO3->NO1", BiddingZonesEnum.NO3),
        ("NO5->NO1", BiddingZonesEnum.NO5),
        ("SE3->NO1", BiddingZonesEnum.SE3),
    ],
    BiddingZonesEnum.NO2: [
        ("NO_NO2_NL->NO2", BiddingZonesEnum.NO2_ND),
        ("NO_NO2_DE->NO2", BiddingZonesEnum.NO2_NK),
        ("NO_NO2_DK1->NO2", BiddingZonesEnum.NO2_SK),
        ("NO5->NO2", BiddingZonesEnum.NO5),
        ("NO1->NO2", BiddingZonesEnum.NO1),
    ],
    BiddingZonesEnum.NO3: [
        ("NO1->NO3", BiddingZonesEnum.NO1),
        ("NO5->NO3", BiddingZonesEnum.NO5),
        ("NO4->NO3", BiddingZonesEnum.NO4),
        ("SE2->NO3", BiddingZonesEnum.SE2),
    ],
    BiddingZonesEnum.NO4: [
        ("SE1->NO4", BiddingZonesEnum.SE1),
        ("FI->NO4", BiddingZonesEnum.FI),
        ("NO3->NO4", BiddingZonesEnum.NO3),
        ("SE2->NO4", BiddingZonesEnum.SE2),
    ],
    BiddingZonesEnum.NO5: [
        ("NO1->NO5", BiddingZonesEnum.NO1),
        ("NO3->NO5", BiddingZonesEnum.NO3),
        ("NO2->NO5", BiddingZonesEnum.NO2),
    ],
    BiddingZonesEnum.NO2_SK: [("Border_CNEC_NO2-NO2_SK", BiddingZonesEnum.NO2)],
    BiddingZonesEnum.NO2_NK: [("Border_CNEC_NO2-NO2_NK", BiddingZonesEnum.NO2)],
    BiddingZonesEnum.NO2_ND: [("Border_CNEC_NO2-NO2_ND", BiddingZonesEnum.NO2)],
    BiddingZonesEnum.DK1: [
        ("Border_CNEC_DK1_DE-DK1", BiddingZonesEnum.DK1_DE),
        ("Border_CNEC_DK1_KS-DK1", BiddingZonesEnum.DK1_KS),
        ("Border_CNEC_DK1_SB-DK1", BiddingZonesEnum.DK1_SB),
        ("Border_CNEC_DK1_CO-DK1", BiddingZonesEnum.DK1_CO),
        ("Border_CNEC_DK1_SK-DK1", BiddingZonesEnum.DK1_SK),
    ],
    BiddingZonesEnum.DK2: [
        ("Border_CNEC_DK2_SB-DK2", BiddingZonesEnum.DK2_SB),
        ("Border_CNEC_DK2_KO-DK2", BiddingZonesEnum.DK2_KO),
        ("Border_CNEC_SE4-DK2", BiddingZonesEnum.SE4),
    ],
    BiddingZonesEnum.DK1_CO: [
        ("Border_CNEC_DK1-DK1_CO", BiddingZonesEnum.DK1),
    ],
    BiddingZonesEnum.DK1_DE: [
        ("Border_CNEC_DK1-DK1_DE", BiddingZonesEnum.DK1),
    ],
    BiddingZonesEnum.DK1_KS: [
        ("Border_CNEC_DK1-DK1_KS", BiddingZonesEnum.DK1),
    ],
    BiddingZonesEnum.DK1_SB: [
        ("Border_CNEC_DK1-DK1_SB", BiddingZonesEnum.DK1),
    ],
    BiddingZonesEnum.DK1_SK: [
        ("Border_CNEC_DK1-DK1_SK", BiddingZonesEnum.DK1),
    ],
    BiddingZonesEnum.SE1: [
        ("Border_CNEC_NO4-SE1", BiddingZonesEnum.NO4),
        ("Border_CNEC_SE2-SE1", BiddingZonesEnum.SE2),
        ("Border_CNEC_FI-SE1", BiddingZonesEnum.FI),
    ],
    BiddingZonesEnum.SE2: [
        ("Border_CNEC_SE1-SE2", BiddingZonesEnum.SE1),
        ("Border_CNEC_SE3-SE2", BiddingZonesEnum.SE3),
        ("Border_CNEC_NO4-SE2", BiddingZonesEnum.NO4),
        ("Border_CNEC_NO3-SE2", BiddingZonesEnum.NO3),
    ],
    BiddingZonesEnum.SE3: [
        ("Border_CNEC_NO1-SE3", BiddingZonesEnum.NO1),
        ("Border_CNEC_SE3_KS-SE3", BiddingZonesEnum.SE3_KS),
        ("Border_CNEC_SE3_FS-SE3", BiddingZonesEnum.SE3_FS),
        ("Border_CNEC_SE3_SWL-SE3", BiddingZonesEnum.SE3_SWL),
        ("Border_CNEC_SE4-SE3", BiddingZonesEnum.SE4),
        ("Border_CNEC_SE2-SE3", BiddingZonesEnum.SE2),
    ],
    BiddingZonesEnum.SE3_KS: [("Border_CNEC_SE3-SE3_KS", BiddingZonesEnum.SE3)],
    BiddingZonesEnum.SE4: [
        ("Border_CNEC_SE3-SE4", BiddingZonesEnum.SE3),
        ("Border_CNEC_SE4_BC-SE4", BiddingZonesEnum.SE4_BC),
        ("Border_CNEC_SE4_SP-SE4", BiddingZonesEnum.SE4_SP),
        ("Border_CNEC_SE4_NB-SE4", BiddingZonesEnum.SE4_NB),
        ("Border_CNEC_SE4_SWL-SE4", BiddingZonesEnum.SE4_SWL),
        ("Border_CNEC_DK2-SE4", BiddingZonesEnum.DK2),
    ],
    BiddingZonesEnum.SE4_SWL: [
        ("Border_CNEC_SE4-SE4_SWL", BiddingZonesEnum.SE4),
    ],
    BiddingZonesEnum.SE4_BC: [
        ("Border_CNEC_SE4-SE4_BC", BiddingZonesEnum.SE4),
    ],
    BiddingZonesEnum.SE4_SP: [
        ("Border_CNEC_SE4-SE4_SP", BiddingZonesEnum.SE4),
    ],
    BiddingZonesEnum.SE4_NB: [
        ("Border_CNEC_SE4-SE4_NB", BiddingZonesEnum.SE4),
    ],
    BiddingZonesEnum.FI: [
        ("Border_CNEC_NO4-FI", BiddingZonesEnum.NO4),
        ("Border_CNEC_SE1-FI", BiddingZonesEnum.SE1),
        ("Border_CNEC_FI_FS-FI", BiddingZonesEnum.FI_FS),
        ("Border_CNEC_FI_EL-FI", BiddingZonesEnum.FI_EL),
    ],
    BiddingZonesEnum.FI_EL: [
        ("Border_CNEC_FI-FI_EL", BiddingZonesEnum.FI),
    ],
    BiddingZonesEnum.FI_FS: [
        ("Border_CNEC_FI-FI_FS", BiddingZonesEnum.FI),
    ],
    BiddingZonesEnum.SE3_FS: [
        ("Border_CNEC_SE3-SE3_FS", BiddingZonesEnum.SE3),
    ],
    BiddingZonesEnum.SE3_KS: [
        ("Border_CNEC_SE3-SE3_KS", BiddingZonesEnum.SE3),
    ],
    BiddingZonesEnum.SE3_SWL: [
        ("Border_CNEC_SE3-SE3_SWL", BiddingZonesEnum.SE3),
    ],
}


def get_cnec_id_from_name(
    cnecName: str, dataset: DataFrame[JaoData], alternative_names: dict[str, list[str]] = ALTERNATIVE_NAMES
) -> str:
    """Gets the CNEC-ID for a given cnec name. Returns the id(s) associated with this name
    at the 0th timestep of the dataset

    Args:
        cnecName (str): CNEC to find the correspondig ID for
        dataset (DataFrame[JaoData]): Dataset of CNEC information. See `make_data_array_from_datetime` for the schema
        alternative_names (dict[str, list[str]]): mapping of names that may have changed

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

    if cnecName in alternative_names and test_alternative:
        test_alternative = False
        with suppress(ValueError):
            for alternative in alternative_names[cnecName]:
                pot_id = get_cnec_id_from_name(alternative, dataset, alternative_names)
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
    df: DataFrame[JaoData],
    bidding_zones: BiddingZonesEnum | list[BiddingZonesEnum] | None = None,
    bidding_zone_cnec_map: dict[BiddingZonesEnum, list[tuple[str, BiddingZonesEnum]]] = BIDDING_ZONE_CNEC_MAP,
) -> dict[BiddingZonesEnum, list[str]]:
    """From a dataset find the cnec ids (a coordinate in the DS) that correspond to the cross border flows.
    The mapping is maintained in BIDDING_ZONE_CNEC_MAP

    Args:
        ds (DataFrame[JaoData]): Dataset in which to find the cross border flows.
            Must have index cnec_id, and column cnecName
        bidding_zones (BiddingZonesEnum | list[BiddingZones] | None, optional):
            Bidding zones for which to find cross border cnecs. Defaults to None.
        bidding_zone_cnec_map (dict[BiddingZonesEnum, list[str]]):
            Mapping from bidding zone to cnec names, i.e.
            >>> bidding_zone_cnec_map = {
            >>> BiddingZonesEnum.NO1: [
            >>>     "NO2->NO1",
            >>>     "NO3->NO1",
            >>>     "NO5->NO1",
            >>>     "SE3->NO1",
            >>> ],
            >>> ...
            >>> }

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
            cnec_names = bidding_zone_cnec_map[bidding_zone]
            for cnec_name_and_bz in cnec_names:
                mrid = get_cnec_id_from_name(cnec_name_and_bz[0], df)
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
