from typing import NamedTuple

import numpy as np
import pandas as pd
from fbmc_quality.dataframe_schemas import CnecData, JaoData, NetPosition
from pandera.typing import DataFrame


class JaoDataAndNPS(NamedTuple):
    jaoData: DataFrame[JaoData]
    basecaseNPs: DataFrame[NetPosition]
    observedNPs: DataFrame[NetPosition]


class CnecDataAndNPS(NamedTuple):
    cnec_id: str
    cnec_name: str
    cnecData: DataFrame[CnecData]
    basecaseNPs: DataFrame[NetPosition]
    observedNPs: DataFrame[NetPosition]
    observed_flow: pd.DataFrame


class PlotData(NamedTuple):
    expected_observed_flow: pd.Series
    unweighted_delta_net_pos: DataFrame[NetPosition]
    x: np.ndarray
    y: np.ndarray
