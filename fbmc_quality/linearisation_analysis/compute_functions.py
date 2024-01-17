from typing import Literal, Union

import pandas as pd
import numpy as np
from pandera.typing import DataFrame

from fbmc_quality.dataframe_schemas import CnecData, JaoData, NetPosition
from fbmc_quality.entsoe_data.fetch_entsoe_data import resample_to_hour_and_replace


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
    expected_flow.index.rename("time", inplace=True)
    expected_flow = resample_to_hour_and_replace(expected_flow)
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
    max_flow: "pd.Series[pd.Float64Dtype]" = cnec_data[JaoData.maxFlow]
    if max_flow.shape == linear_flow.shape:
        linear_flow = np.minimum(max_flow.to_numpy(), linear_flow.to_numpy())
    else:
        lin_flow_arr = linear_flow.to_numpy()
        max_flow_arr = np.ones_like(lin_flow_arr)
        max_flow_arr[:] = max_flow.mean()
        linear_flow = np.minimum(max_flow_arr, lin_flow_arr)
    rel_error = target_flow - linear_flow
    return rel_error


def compute_cnec_vulnerability_to_err(
    cnec_data: DataFrame[CnecData],
    target_net_positions: DataFrame[NetPosition],
    target_flow: "pd.Series[pd.Float64Dtype]",
    alt_fmax: Union["pd.Series[pd.Float64Dtype]", None] = None,
    relative_or_absolute: Literal["relative", "absolute"] = "relative",
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
    fmax = cnec_data[JaoData.fmax] if alt_fmax is None else alt_fmax
    linearisation_error = compute_linearisation_error(cnec_data, target_net_positions, target_flow)
    ram_obs = fmax - target_flow
    ram_bc = fmax - cnec_data[JaoData.fref]

    # flows = np.vstack([target_flow, compute_linearised_flow(cnec_data, target_net_positions)]).T
    vulnerability_score = linearisation_error / (fmax - target_flow)
    basecase_relative_margin = (ram_obs / ram_bc).abs()

    return_frame = pd.DataFrame(
        {
            "vulnerability_score": vulnerability_score,
            "basecase_relative_margin": basecase_relative_margin,
        }
    )
    return return_frame
