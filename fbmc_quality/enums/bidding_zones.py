from enum import Enum


class AltBiddingZonesEnum(str, Enum):
    NO_NO2_NL = "NO_NO2_NL"
    NO_NO2_DE = "NO_NO2_DE"
    NO_NO2_DK1 = "NO_NO2_DK1"


class BiddingZonesEnum(str, Enum):
    DK1 = "DK1"
    DK1_SB = "DK1_SB"
    DK1_CO = "DK1_CO"
    DK1_DE = "DK1_DE"
    DK1_KS = "DK1_KS"
    DK1_SK = "DK1_SK"
    DK1_ST = "DK1_ST"
    DK2_SB = "DK2_SB"
    DK2_KO = "DK2_KO"
    DK2_ST = "DK2_ST"
    DK2 = "DK2"
    FI = "FI"
    FI_EL = "FI_EL"
    FI_FS = "FI_FS"
    NO1 = "NO1"
    NO2 = "NO2"
    NO2_ND = "NO2_ND"
    NO2_SK = "NO2_SK"
    NO2_NK = "NO2_NK"
    NO3 = "NO3"
    NO4 = "NO4"
    NO5 = "NO5"
    SE1 = "SE1"
    SE2 = "SE2"
    SE3 = "SE3"
    SE3_FS = "SE3_FS"
    SE3_KS = "SE3_KS"
    # SE3_SWL = "SE3_SWL"
    SE4 = "SE4"
    SE4_BC = "SE4_BC"
    SE4_NB = "SE4_NB"
    SE4_SP = "SE4_SP"
    # SE4_SWL = "SE4_SWL"


ALT_NAME_MAP = {
    AltBiddingZonesEnum.NO_NO2_DE: BiddingZonesEnum.NO2_NK,
    AltBiddingZonesEnum.NO_NO2_NL: BiddingZonesEnum.NO2_ND,
    AltBiddingZonesEnum.NO_NO2_DK1: BiddingZonesEnum.NO2_SK,
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
    BiddingZonesEnum.DK2_ST: [
        ("Border_CNEC_DK2-DK2_ST", BiddingZonesEnum.DK2),
    ],
    BiddingZonesEnum.DK1_ST: [
        ("Border_CNEC_DK1-DK1_ST", BiddingZonesEnum.DK1),
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
        # ("Border_CNEC_SE3_SWL-SE3", BiddingZonesEnum.SE3_SWL),
        ("Border_CNEC_SE4-SE3", BiddingZonesEnum.SE4),
        ("Border_CNEC_SE2-SE3", BiddingZonesEnum.SE2),
    ],
    BiddingZonesEnum.SE3_KS: [("Border_CNEC_SE3-SE3_KS", BiddingZonesEnum.SE3)],
    BiddingZonesEnum.SE4: [
        ("Border_CNEC_SE3-SE4", BiddingZonesEnum.SE3),
        ("Border_CNEC_SE4_BC-SE4", BiddingZonesEnum.SE4_BC),
        ("Border_CNEC_SE4_SP-SE4", BiddingZonesEnum.SE4_SP),
        ("Border_CNEC_SE4_NB-SE4", BiddingZonesEnum.SE4_NB),
        # ("Border_CNEC_SE4_SWL-SE4", BiddingZonesEnum.SE4_SWL),
        ("Border_CNEC_DK2-SE4", BiddingZonesEnum.DK2),
    ],
    # BiddingZonesEnum.SE4_SWL: [
    #     ("Border_CNEC_SE4-SE4_SWL", BiddingZonesEnum.SE4),
    # ],
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
    # BiddingZonesEnum.SE3_SWL: [
    #     ("Border_CNEC_SE3-SE3_SWL", BiddingZonesEnum.SE3),
    # ],
}
