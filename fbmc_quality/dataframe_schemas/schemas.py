from typing import Annotated, Optional

import pandas as pd
import pandera as pa
import pydantic
from pandera.typing import Index, Series


class Contingency(pydantic.BaseModel):
    number: int
    branchname: str
    branchEic: str
    hubFrom: str
    hubTo: str
    substationFrom: str
    substationTo: str
    elementType: str


class Contingencies(pydantic.BaseModel):  # the datamodel describing the contingencies field in JaoBaseFrame
    contingencies: list[Contingency]


class CnecMultiindex(pa.DataFrameModel):
    cnec_id: Index[pd.StringDtype] = pa.Field(coerce=True)
    time: Index[Annotated[pd.DatetimeTZDtype, "ns", "utc"]]


class JaoBase(pa.DataFrameModel):
    id: Series[pd.Int64Dtype]
    dateTimeUtc: Series[Annotated[pd.DatetimeTZDtype, "ns", "utc"]] = pa.Field(coerce=True)
    tso: Series[pd.StringDtype] = pa.Field(coerce=True)
    cnecName: Series[pd.StringDtype] = pa.Field(coerce=True)
    cnecType: Series[pd.StringDtype] = pa.Field(coerce=True)
    cneName: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    cneType: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    cneStatus: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    cneEic: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    direction: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    hubFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    hubTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    substationFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    substationTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    elementType: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    fmaxType: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    contTso: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    contName: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    contStatus: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    contSubstationFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    contSubstationTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)
    imaxMethod: Series[pd.StringDtype] = pa.Field(coerce=True)
    contingencies: Series[pd.StringDtype] = pa.Field(coerce=True)
    presolved: Series[pd.BooleanDtype] = pa.Field(coerce=True)
    significant: Series[pd.BooleanDtype] = pa.Field(coerce=True)
    ram: Series[float]
    minFlow: Series[float]
    maxFlow: Series[float]
    u: Series[float]
    imax: Series[float]
    fmax: Series[float]
    frm: Series[float]
    frefInit: Series[float] = pa.Field(nullable=True, coerce=True)
    fnrao: Series[float]
    fref: Series[float]
    fcore: Series[float] = pa.Field(nullable=True, coerce=True)
    fall: Series[float]
    fuaf: Series[float] = pa.Field(nullable=True, coerce=True)
    amr: Series[float]
    aac: Series[float]
    ltaMargin: Series[float] = pa.Field(nullable=True, coerce=True)
    cva: Series[float] = pa.Field(nullable=True, coerce=True)
    iva: Series[float]
    ftotalLtn: Series[float] = pa.Field(nullable=True, coerce=True)
    fltn: Series[float] = pa.Field(nullable=True, coerce=True)


class BiddingZones(pa.DataFrameModel):
    DK1: Optional[Series[float]] = pa.Field(nullable=True)
    DK1_CO: Series[float] = pa.Field(nullable=True)
    DK1_DE: Series[float] = pa.Field(nullable=True)
    DK1_KS: Series[float] = pa.Field(nullable=True)
    DK1_SK: Series[float] = pa.Field(nullable=True)
    DK1_ST: Series[float] = pa.Field(nullable=True)
    DK2: Series[float] = pa.Field(nullable=True)
    DK2_KO: Series[float] = pa.Field(nullable=True)
    DK2_ST: Series[float] = pa.Field(nullable=True)
    FI: Series[float] = pa.Field(nullable=True)
    FI_EL: Series[float] = pa.Field(nullable=True)
    FI_FS: Series[float] = pa.Field(nullable=True)
    NO1: Series[float] = pa.Field(nullable=True)
    NO2: Series[float] = pa.Field(nullable=True)
    NO2_ND: Series[float] = pa.Field(nullable=True)
    NO2_SK: Series[float] = pa.Field(nullable=True)
    NO2_NK: Series[float] = pa.Field(nullable=True)
    NO3: Series[float] = pa.Field(nullable=True)
    NO4: Series[float] = pa.Field(nullable=True)
    NO5: Series[float] = pa.Field(nullable=True)
    SE1: Series[float] = pa.Field(nullable=True)
    SE2: Series[float] = pa.Field(nullable=True)
    SE3: Series[float] = pa.Field(nullable=True)
    SE3_FS: Series[float] = pa.Field(nullable=True)
    SE3_KS: Series[float] = pa.Field(nullable=True)
    SE3_SWL: Series[float] = pa.Field(nullable=True)
    SE4: Series[float] = pa.Field(nullable=True)
    SE4_BC: Series[float] = pa.Field(nullable=True)
    SE4_NB: Series[float] = pa.Field(nullable=True)
    SE4_SP: Series[float] = pa.Field(nullable=True)
    SE4_SWL: Series[float] = pa.Field(nullable=True)


class JaoData(JaoBase, BiddingZones, CnecMultiindex):
    ...


class CnecData(JaoBase, BiddingZones):
    time: Index[Annotated[pd.DatetimeTZDtype, "ns", "utc"]]


class NetPosition(BiddingZones):
    time: Index[Annotated[pd.DatetimeTZDtype, "ns", "utc"]]
