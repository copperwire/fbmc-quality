from typing import NamedTuple

import numpy as np
import pandas as pd
from pandera.typing import DataFrame

from fbmc_quality.dataframe_schemas import CnecData, JaoData, NetPosition


class JaoDataAndNPS(NamedTuple):
    """Dataclass conaining pandas Dataframes of data from JAO and observed and basecase Net Positions"""

    jaoData: DataFrame[JaoData]
    basecaseNPs: DataFrame[NetPosition]
    observedNPs: DataFrame[NetPosition]


class CnecDataAndNPS(NamedTuple):
    """Dataclass conaining pandas Dataframes of data from JAO and observed and basecase Net Positions,
    as well as observed flow.
    For a single CNEC.
    """

    cnec_id: str
    cnec_name: str
    cnecData: DataFrame[CnecData]
    basecaseNPs: DataFrame[NetPosition]
    observedNPs: DataFrame[NetPosition]
    observed_flow: pd.DataFrame


class PlotData(NamedTuple):
    """Simple container used for plotting when investigating the difference
    between basecase Net Positions and an observed state.

    """

    expected_observed_flow: pd.Series
    unweighted_delta_net_pos: DataFrame[NetPosition]
    x: np.ndarray
    y: np.ndarray
