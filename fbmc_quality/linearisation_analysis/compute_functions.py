import pandas as pd
from dataframe_schemas.schemas import CnecData, JaoData, NetPosition
from pandera.typing import DataFrame


def compute_linearised_flow(
    cnec_data: DataFrame[CnecData], target_net_positions: DataFrame[NetPosition]
) -> "pd.Series[pd.Float64Dtype]":
    expected_flow = (cnec_data * target_net_positions).dropna(axis=1, how="all").sum(axis=1) + cnec_data[JaoData.fall]
    return expected_flow


def compute_linearisation_error(
    cnec_data: DataFrame[CnecData],
    target_net_positions: DataFrame[NetPosition],
    target_flow: "pd.Series[pd.Float64Dtype]",
) -> "pd.Series[pd.Float64Dtype]":
    linear_flow = compute_linearised_flow(cnec_data, target_net_positions)
    rel_error = target_flow - linear_flow
    return rel_error


def compute_weghted_loading(
    cnec_data: DataFrame[CnecData],
    target_net_positions: DataFrame[NetPosition],
    target_flow: "pd.Series[pd.Float64Dtype]",
):
    linearisation_error = compute_linearisation_error(cnec_data, target_net_positions, target_flow).abs()
    ram_obs = cnec_data[JaoData.fmax] - target_flow
    ram_bc = cnec_data[JaoData.fmax] - cnec_data[JaoData.fref]
    vulnerability_score = (linearisation_error / ram_obs).abs().mean()
    basecase_relative_margin = (ram_obs / ram_bc).abs().mean()
    return vulnerability_score, basecase_relative_margin
