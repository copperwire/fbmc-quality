from typing import Annotated, Optional

import pandas as pd
import pandera as pa
import pydantic
from pandera.typing import Index, Series
from sqlalchemy import Boolean, Column, Float, Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CorridorFlowModel(Base):
    __tablename__ = "ENTSOE"

    time = Column(TIMESTAMP(timezone=True))  #: Index value
    ROW_KEY = Column(String, primary_key=True)
    area_from = Column(String)
    area_to = Column(String)
    flow = Column(Float)


class JaoModel(Base):  # type: ignore
    __tablename__ = "JAO"

    # id = Column(Integer, Sequence("fakemodel_id_sequence"), primary_key=True)
    # name = Column(String)
    cnec_id = Column(String)  #: Index value
    time = Column(TIMESTAMP(timezone=True))  #: Index value
    ROW_KEY = Column(String, primary_key=True)
    id = Column(Integer)  #: JAO field value
    dateTimeUtc = Column(TIMESTAMP(timezone=True))  #: JAO field value
    tso = Column(String)  #: JAO field value
    mrId = Column(String)  #: JAO field value
    biddingZoneFrom = Column(String)
    biddingZoneTo = Column(String)
    cnecName = Column(String)  #: JAO field value
    cnecType = Column(String)  #: JAO field value
    cneName = Column(String)  #: JAO field value
    cneType = Column(String)  #: JAO field value
    cneStatus = Column(String)  #: JAO field value
    cneEic = Column(String)  #: JAO field value
    direction = Column(String)  #: JAO field value
    hubFrom = Column(String)  #: JAO field value
    hubTo = Column(String)  #: JAO field value
    substationFrom = Column(String)  #: JAO field value
    substationTo = Column(String)  #: JAO field value
    elementType = Column(String)  #: JAO field value
    fmaxType = Column(String)  #: JAO field value
    contTso = Column(String)  #: JAO field value
    contName = Column(String)  #: JAO field value
    contStatus = Column(String)  #: JAO field value
    contSubstationFrom = Column(String)  #: JAO field value
    contSubstationTo = Column(String)  #: JAO field value
    contEic = Column(String)
    imaxMethod = Column(String)  #: JAO field value
    contingencies = Column(String)  #: JAO field value
    nonRedundant = Column(Boolean)  #: JAO field value
    significant = Column(Boolean)  #: JAO field value
    ram = Column(Float)  #: JAO field value
    minFlow = Column(Float)  #: JAO field value
    maxFlow = Column(Float)  #: JAO field value
    u = Column(Float)  #: JAO field value
    imax = Column(Float)  #: JAO field value
    fmax = Column(Float)  #: JAO field value
    frm = Column(Float)  #: JAO field value
    frefInit = Column(Float)  #: JAO field value
    fnrao = Column(Float)  #: JAO field value
    fref = Column(Float)  #: JAO field value
    fcore = Column(Float)  #: JAO field value
    fall = Column(Float)  #: JAO field value
    fuaf = Column(Float)  #: JAO field value
    amr = Column(Float)  #: JAO field value
    aac = Column(Float)  #: JAO field value
    ltaMargin = Column(Float)  #: JAO field value
    cva = Column(Float)  #: JAO field value
    iva = Column(Float)  #: JAO field value
    ftotalLtn = Column(Float)  #: JAO field value
    fltn = Column(Float)  #: JAO field value
    DK1 = Column(Float)  #: value of bidding zone
    DK1_CO = Column(Float)  #: value of bidding zone
    DK1_DE = Column(Float)  #: value of bidding zone
    DK1_KS = Column(Float)  #: value of bidding zone
    DK1_SK = Column(Float)  #: value of bidding zone
    DK1_SB = Column(Float)  #: value of bidding zone
    DK2 = Column(Float)  #: value of bidding zone
    DK2_KO = Column(Float)  #: value of bidding zone
    DK2_SB = Column(Float)  #: value of bidding zone
    FI = Column(Float)  #: value of bidding zone
    FI_EL = Column(Float)  #: value of bidding zone
    FI_FS = Column(Float)  #: value of bidding zone
    NO1 = Column(Float)  #: value of bidding zone
    NO2 = Column(Float)  #: value of bidding zone
    NO2_ND = Column(Float)  #: value of bidding zone
    NO2_SK = Column(Float)  #: value of bidding zone
    NO2_NK = Column(Float)  #: value of bidding zone
    NO3 = Column(Float)  #: value of bidding zone
    NO4 = Column(Float)  #: value of bidding zone
    NO5 = Column(Float)  #: value of bidding zone
    SE1 = Column(Float)  #: value of bidding zone
    SE2 = Column(Float)  #: value of bidding zone
    SE3 = Column(Float)  #: value of bidding zone
    SE3_FS = Column(Float)  #: value of bidding zone
    SE3_KS = Column(Float)  #: value of bidding zone
    # SE3_SWL = Column(Float)  #: see SWL for SE4
    SE4 = Column(Float)  #: value of bidding zone
    SE4_BC = Column(Float)  #: value of bidding zone
    SE4_NB = Column(Float)  #: value of bidding zone
    SE4_SP = Column(Float)  #: value of bidding zone
    # SE4_SWL = Column(Float)  #: Not represented since we dont have the HVDC flow


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
    substationFrom: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    substationTo: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contName: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    contStatus: Series[pd.StringDtype] = pa.Field(coerce=True, nullable=True)  #: JAO field value
    imaxMethod: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    contingencies: Series[pd.StringDtype] = pa.Field(coerce=True)  #: JAO field value
    nonRedundant: Series[pd.BooleanDtype] = pa.Field(coerce=True)  #: JAO field value
    significant: Series[pd.BooleanDtype] = pa.Field(coerce=True)  #: JAO field value
    ram: Series[float]  #: JAO field value
    minFlow: Series[float]  #: JAO field value
    maxFlow: Series[float]  #: JAO field value
    u: Series[float]  #: JAO field value
    imax: Series[float]  #: JAO field value
    fmax: Series[float]  #: JAO field value
    frm: Series[float]  #: JAO field value
    fnrao: Series[float]  #: JAO field value
    fref: Series[float]  #: JAO field value
    fall: Series[float]  #: JAO field value
    amr: Series[float]  #: JAO field value
    aac: Series[float]  #: JAO field value
    iva: Series[float]  #: JAO field value


class BiddingZones(pa.DataFrameModel):
    DK1: Optional[Series[float]] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_CO: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_DE: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_KS: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK1_SK: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK2: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    DK2_KO: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
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
    # SE3_SWL: Series[float] = pa.Field(nullable=True)  #: see other SWL refs
    SE4: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_BC: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_NB: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    SE4_SP: Series[float] = pa.Field(nullable=True)  #: value of bidding zone
    # SE4_SWL: Series[float] = pa.Field(nullable=True)  #: see other SWL refs


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
