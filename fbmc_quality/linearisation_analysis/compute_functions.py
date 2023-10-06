import pandas as pd
from pandera.typing import DataFrame

from fbmc_quality.dataframe_schemas import CnecData, JaoData, NetPosition


def compute_linearised_flow(
    cnec_data: DataFrame[CnecData], target_net_positions: DataFrame[NetPosition]
) -> "pd.Series[pd.Float64Dtype]":
    """Computes the FBMC linearised flow given a set of target net positions, zonal PTDFS and the y-axis offset

    Args:
        cnec_data (DataFrame[CnecData]): Zonal PTDFs and y axis offset
        target_net_positions (DataFrame[NetPosition]): Net positions to use as targets for computing the flow

    Returns:
        pd.Series[pd.Float64Dtype]: linearlised flow
    """
    expected_flow = (cnec_data * target_net_positions).dropna(axis=1, how="all").sum(axis=1) + cnec_data[JaoData.fall]
    return expected_flow


def compute_linearisation_error(
    cnec_data: DataFrame[CnecData],
    target_net_positions: DataFrame[NetPosition],
    target_flow: "pd.Series[pd.Float64Dtype]",
) -> "pd.Series[pd.Float64Dtype]":
    """Computes the linearisation error as a relative error, with `target_flow - linear_flow` as  the return value

    Args:
        cnec_data (DataFrame[CnecData]): Zonal PTDFs and y axis offset
        target_net_positions (DataFrame[NetPosition]): net positions to use for the linearisation
        target_flow (pd.Series[pd.Float64Dtype]): observed flow at the given net positions

    Returns:
        pd.Series[pd.Float64Dtype]: linearisation error
    """
    linear_flow = compute_linearised_flow(cnec_data, target_net_positions)
    rel_error = target_flow - linear_flow
    return rel_error


def compute_weghted_loading(
    cnec_data: DataFrame[CnecData],
    target_net_positions: DataFrame[NetPosition],
    target_flow: "pd.Series[pd.Float64Dtype]",
) -> pd.DataFrame:
    r"""returns the mean value of the vulnerability score, and mean basecase relative margin

    vulnerability is the fraction of linearisation-error to the margin in MW in the target situation:
        `v = linearisation-error/(f_max - target-flow)`

    basecase relative margin is the

    Args:
        cnec_data (DataFrame[CnecData]): zonal ptdfs and y axis offset
        target_net_positions (DataFrame[NetPosition]): target net positions to linearise from
        target_flow (pd.Series[pd.Float64Dtype]): target for computing linearisation error

    Returns:
        pd.DataFrame: frame with vulnerability score, basecase_relative_margin
    """
    linearisation_error = compute_linearisation_error(cnec_data, target_net_positions, target_flow).abs()
    ram_obs = cnec_data[JaoData.fmax] - target_flow
    ram_bc = cnec_data[JaoData.fmax] - cnec_data[JaoData.fref]
    vulnerability_score = (linearisation_error / ram_obs).abs()
    basecase_relative_margin = (ram_obs / ram_bc).abs()
    
    return_frame = pd.DataFrame(
        {
            "vulnerability_score": vulnerability_score,
            "basecase_relative_margin": basecase_relative_margin,
        }
    )
    return return_frame
