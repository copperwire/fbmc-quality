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
    cnec_id: Index[pd.StringDtype] = pa.Field(coerce=True)  #: Index value
    time: Index[Annotated[pd.DatetimeTZDtype, "ns", "utc"]]  #: Index value


class JaoBase(pa.DataFrameModel):
    id: Series[pd.Int64Dtype]  #: JAO field value
    dateTimeUtc: Series[Annotated[pd.DatetimeTZDtype, "ns", "utc"]] = pa.Field(coerce=True)  #: JAO field value
    tso: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    cnecName: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    cnecType: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    cneName: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    cneType: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    cneStatus: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    cneEic: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    direction: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    hubFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    hubTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    substationFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    substationTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    elementType: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    fmaxType: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contTso: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contName: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contStatus: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contSubstationFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contSubstationTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    imaxMethod: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    contingencies: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    presolved: Series[pd.BooleanDtype] = pa.Field(coerce=True)  #: JAO field value
    significant: Series[pd.BooleanDtype] = pa.Field(coerce=True)  #: JAO field value
    ram: Series[float]  #: JAO field value
    minFlow: Series[float]  #: JAO field value
    maxFlow: Series[float]  #: JAO field value
    u: Series[float]  #: JAO field value
    imax: Series[float]  #: JAO field value
    fmax: Series[float]  #: JAO field value
    frm: Series[float]  #: JAO field value
    frefInit: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value
    fnrao: Series[float]  #: JAO field value
    fref: Series[float]  #: JAO field value
    fcore: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value
    fall: Series[float]  #: JAO field value
    fuaf: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value
    amr: Series[float]  #: JAO field value
    aac: Series[float]  #: JAO field value
    ltaMargin: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value
    cva: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value
    iva: Series[float]  #: JAO field value
    ftotalLtn: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value
    fltn: Series[float] = pa.Field(nullable=True, coerce=True)  #: JAO field value


class BiddingZones(pa.DataFrameModel):
    DK1: Optional[Series[float]] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_CO: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_DE: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_KS: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_SK: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_ST: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK2: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK2_KO: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK2_ST: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    FI: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    FI_EL: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    FI_FS: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO1: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO2: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO2_ND: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO2_SK: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO2_NK: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO3: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO4: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    NO5: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE1: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE2: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE3: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE3_FS: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE3_KS: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE3_SWL: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_BC: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_NB: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_SP: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_SWL: Series[float] = pa.Field(nullable=True)  #: value of bidding zone


class JaoData(JaoBase, BiddingZones, CnecMultiindex):
    """Schema describing the flow based market clearing data coming from JAO."""

    ...


class CnecData(JaoBase, BiddingZones):
    """Schema describing the flow based market clearing data coming from JAO.
    For a single CNEC

    """

    time: Index[Annotated[pd.DatetimeTZDtype, "ns", "utc"]]  #: time index


class NetPosition(BiddingZones):
    """Schema describing net positions of a set of areas"""

    time: Index[Annotated[pd.DatetimeTZDtype, "ns", "utc"]]  #: time index
