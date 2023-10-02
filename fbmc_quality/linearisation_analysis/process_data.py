import re
from datetime import date

import numpy as np
from pandera.typing import DataFrame

#from bdl_data.fetch_bdl_data import get_bdl_data_for_cnec
from fbmc_quality.entsoe_data.fetch_entsoe_data import get_net_position_from_crossborder_flows, get_observed_entsoe_data_for_cnec
from fbmc_quality.enums.bidding_zones import BiddingZonesEnum
from fbmc_quality.jao_data.analyse_jao_data import compute_basecase_net_pos, get_cnec_id_from_name
from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries
from fbmc_quality.linearisation_analysis.compute_functions import compute_linearised_flow
from fbmc_quality.linearisation_analysis.dataclasses import CnecDataAndNPS, JaoDataAndNPS, PlotData
from fbmc_quality.dataframe_schemas import JaoData, NetPosition, BiddingZones



def make_train_and_targets(cnec_data: CnecDataAndNPS) -> PlotData:
    expected_observed_flow = compute_linearised_flow(cnec_data.cnecData, cnec_data.observedNPs).to_frame("flow")
    # expected_observed_flow = cnec_ds['fref']
    unweighted_delta_net_pos = cnec_data.observedNPs - cnec_data.basecaseNPs

    x, y = (
        transform_delta_np_and_ptdfs_to_numpy(unweighted_delta_net_pos, cnec_data.cnecData),
        (cnec_data.observed_flow - expected_observed_flow).to_numpy(),
    )

    np.nan_to_num(x, copy=False, nan=0)
    return PlotData(expected_observed_flow, unweighted_delta_net_pos, x, y)


def transform_delta_np_and_ptdfs_to_numpy(
    unweighted_delta_np: DataFrame[NetPosition], cnec_ds: DataFrame[JaoData]
) -> np.ndarray:
    """takes net position and ptdf data array and concatenates them to a numpy array.
    Will replace NaN with 0 in the PTDF matrix

    Args:
        unweighted_delta_np (DataFrame[NetPosition]): Dataframe net_positions
        cnec_ds (DataFrame[JaoData]): Dataframe with ptdfs

    Returns:
        np.ndarray: Array with dimensions (time, bidding_zones x 2)
    """

    cols = BiddingZones.to_schema().columns
    weighted_ptdfs = unweighted_delta_np * cnec_ds
    renamed_ptdf_ds = (
        weighted_ptdfs.rename({col: col + "_ptdf" for col in cnec_ds.columns}, axis=1)
        .loc[:, [col + "_ptdf" for col in cols.keys()]]
        .fillna(0)
    )

    renamed_unweighted_delta_np = unweighted_delta_np.rename(
        {col: col + "_np_delta" for col in unweighted_delta_np.columns}, axis=1
    )

    merged_data = renamed_unweighted_delta_np.merge(renamed_ptdf_ds, left_index=True, right_index=True)
    return merged_data.to_numpy()


def load_jao_data_basecase_nps_and_observed_nps(start: date, end: date) -> JaoDataAndNPS:
    jao_data = fetch_jao_dataframe_timeseries(start, end)
    observed_nps = get_net_position_from_crossborder_flows(start, end)
    basecase_nps = compute_basecase_net_pos(start, end)
    if observed_nps is None:
        raise ValueError(f"No observed data for {start} {end}")
    if basecase_nps is None:
        raise ValueError(f"No entose data for {start} {end}")
    if jao_data is None:
        raise ValueError(f"No jao data for {start} {end}")

    return JaoDataAndNPS(jao_data, basecase_nps, observed_nps)


def load_data_for_cnec(cnecName: str, jao_and_entsoe_data: JaoDataAndNPS) -> CnecDataAndNPS | None:
    cnec_id = get_cnec_id_from_name(cnecName, jao_and_entsoe_data.jaoData)
    cnec_ds = jao_and_entsoe_data.jaoData.xs(cnec_id, level=JaoData.cnec_id)

    end = jao_and_entsoe_data.jaoData.index.get_level_values(JaoData.time).max().to_pydatetime()
    start = jao_and_entsoe_data.jaoData.index.get_level_values(JaoData.time).min().to_pydatetime()

    if re.search(r"\d{5}_\d{2}", cnecName) is not None:
        observed_flow = get_bdl_data_for_cnec(start, end, cnecName)
    else:
        bidding_zone, to_zone = get_from_to_bz_from_name(cnecName)
        if bidding_zone is None or to_zone is None:
            raise ValueError(f"No from/to zone found for {cnecName}")

        observed_flow = get_observed_entsoe_data_for_cnec(bidding_zone, to_zone, start, end)

    if observed_flow is None or observed_flow.empty or cnec_ds.empty:
        return None

    index_alignment = (
        cnec_ds.index.get_level_values(JaoData.time)
        .intersection(observed_flow.index)
        .intersection(jao_and_entsoe_data.observedNPs.index)
        .intersection(jao_and_entsoe_data.basecaseNPs.index)
    )
    cnec_ds = cnec_ds.loc[index_alignment, :]
    observed_flow = observed_flow.loc[index_alignment, :]
    jao_and_entsoe_data = JaoDataAndNPS(
        jao_and_entsoe_data.jaoData,
        jao_and_entsoe_data.basecaseNPs.loc[index_alignment, :],  # type: ignore
        jao_and_entsoe_data.observedNPs.loc[index_alignment, :],  # type: ignore
    )

    return CnecDataAndNPS(
        cnec_id, cnecName, cnec_ds, jao_and_entsoe_data.basecaseNPs, jao_and_entsoe_data.observedNPs, observed_flow
    )


def get_from_to_bz_from_name(cnecName: str):
    for bz_from in BiddingZonesEnum:
        for bz_to in BiddingZonesEnum:
            if bz_from == bz_to:
                continue

            match = re.search(rf"{bz_from.value}.+{bz_to}", cnecName)
            if match is not None:
                return bz_from, bz_to

    return (None, None)
