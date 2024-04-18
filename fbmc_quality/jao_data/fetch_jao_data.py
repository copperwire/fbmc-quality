import asyncio
import hashlib
import logging
import uuid
import warnings
from datetime import datetime, timedelta
from typing import Hashable, Iterable, TypeVar

import aiohttp
import duckdb
import pandas as pd
from pandera.typing import DataFrame
from pytz import AmbiguousTimeError
from sqlalchemy import Engine, create_engine

from fbmc_quality.dataframe_schemas.cache_db import DB_PATH
from fbmc_quality.dataframe_schemas.cache_db.cache_db_functions import store_df_in_table
from fbmc_quality.dataframe_schemas.schemas import JaoData
from fbmc_quality.datetime_handlers.handle_timezones import convert_date_to_utc_pandas
from fbmc_quality.exceptions.fbmc_exceptions import JAOLookupException, WrongTimezoneException

warnings.filterwarnings(
    "ignore",
    message=".*Unverified",
)

timedata = TypeVar("timedata", pd.Timestamp, datetime)


def create_uuid_from_string(val: str) -> str:
    hex_string = hashlib.md5(val.encode("UTF-8"), usedforsecurity=False).hexdigest()
    return str(uuid.UUID(hex=hex_string))


async def get_ptdfs(date: timedata, session: aiohttp.ClientSession) -> pd.DataFrame:
    """get PTDFs from JAO, query by datetime

    Args:
        date (datetime): date to query the JAO by

    Returns:
        Dict[str, object]: HTTP payload from the API request
    """
    session.verify = False

    date_str = date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_date_str = (date + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    url = 'https://test-publicationtool.jao.eu/nordic/api/data/finalComputation'
    headers = {
   "Accept":"application/json, text/plain, */*",
  "Accept-Encoding":"gzip, deflate, br, zstd",
  "Accept-Language":"nb-NO,nb;q=0.9,no;q=0.8,nn;q=0.7,en-US;q=0.6,en;q=0.5",
  "Origin":"https://test-publicationtool.jao.eu",
  "Referer":"https://test-publicationtool.jao.eu/nordic/flowbasedDomain",
  "Sec-Fetch-Dest":"empty",
  "Sec-Fetch-Mode":"cors",
  "Sec-Fetch-Site":"same-origin",
  "X-Requested-With":"XMLHttpRequest",
}

    data = {
        "FromUtc": date_str,
        "ToUtc": to_date_str,
        "Filter": '{}',
        "Skip": '0',
        "Take": '0',
    }

    async with session.get(url=url, data=data, headers=headers) as response:
        json = await response.json()
        if json['totalRowsWithFilter'] == 0:
            raise JAOLookupException(f'No data for {date_str} to {to_date_str}')
        else:
            total_num_data = json['totalRowsWithFilter'] 
    
    df = pd.DataFrame()  # type: ignore
    args = []

    for i in range(0, total_num_data, 100):
        args.append({
            'FromUtc': date_str,
            'ToUtc': to_date_str,
            'Filter': '{}',
            'Skip': i,
            'Take': 100
        })

    for arg in args:
        async with session.get(url=url, data=arg, headers=headers) as response:
            json = await response.json()
            df = pd.concat([df, pd.DataFrame(json['data'])])
    return df


async def _fetch_jao_dataframe_from_datetime(
    date: timedata, engine: Engine, session: aiohttp.ClientSession | None = None
) -> DataFrame[JaoData]:
    """Fetches a dataframe representation of JAO data"""

    if session is None:
        async with aiohttp.ClientSession() as new_session:
            df = await get_ptdfs(date, new_session)
    else:
        df = await get_ptdfs(date, session)

    df = df.loc[df[JaoData.cnecName].notnull(), :]
    df[JaoData.cnec_id] = df.apply(
        lambda row: create_uuid_from_string(row[JaoData.cnecName] + row[JaoData.contName]), axis=1
    )
    df[JaoData.time] = pd.to_datetime(df[JaoData.dateTimeUtc])
    col = df.columns.to_list()

    for i, col_name in enumerate(col):
        col[i] = col_name.replace("ptdf_", "")
    df.columns = col

    df["ROW_KEY"] = df[JaoData.cnec_id] + "_" + df[JaoData.time].astype(str)
    df = df.drop_duplicates(["ROW_KEY"])
    df = df.drop(["SE3_SWL", "SE4_SWL"], axis=1)

    store_df_in_table("JAO", df, engine)
    df = df.set_index([JaoData.cnec_id, JaoData.time]).drop("ROW_KEY", axis=1)
    df_validated: DataFrame[JaoData] = JaoData.validate(df)  # type: ignore
    return df_validated


async def _fetch_jao_dataframe_timeseries(time_points: list[datetime]) -> DataFrame[JaoData] | None:
    logging.getLogger().info(f"Fetching JAO data from {len(time_points)} hours")

    all_results: list[DataFrame[JaoData]] = []
    engine = create_engine("duckdb:///" + str(DB_PATH))

    async with aiohttp.ClientSession() as session:
        for time_point in time_points:
            results = await _fetch_jao_dataframe_from_datetime(time_point, engine, session)
            all_results.append(results)

    engine.dispose()
    if all_results:
        return_frame = pd.concat(all_results)
        return return_frame  # type: ignore
    else:
        return None


def try_jao_cache_before_async(
    from_time: timedata, to_time: timedata
) -> tuple[DataFrame[JaoData] | None, list[datetime]]:
    if not isinstance(from_time, datetime):
        dt_from_time = datetime(from_time.year, from_time.month, from_time.day)
    else:
        dt_from_time = from_time

    if not isinstance(to_time, datetime):
        dt_to_time = datetime(to_time.year, to_time.month, to_time.day)
    else:
        dt_to_time = to_time

    for dt in [dt_from_time, dt_to_time]:
        if dt.tzname() != "UTC":
            raise WrongTimezoneException(f"Expected UTC timestamps, but got {dt.tzname()}")

    loop_time = dt_from_time
    time_range: list[datetime] = []
    while loop_time < (dt_to_time):
        time_range.append(loop_time)
        loop_time += pd.Timedelta(hours=1)

    connection = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        cached_data = (
            connection.sql(
                (
                    "SELECT * FROM JAO WHERE time BETWEEN"
                    f" TIMESTAMPTZ '{from_time.isoformat()}'"
                    f"AND TIMESTAMPTZ '{(to_time + pd.Timedelta(1, unit='minutes')).isoformat()}'"
                )
            )
            .df()
            .drop("ROW_KEY", axis=1)
        )
    except duckdb.CatalogException:
        return None, time_range
    connection.close()

    if cached_data.empty:
        return None, time_range
    else:
        cached_data = formatting_cache_to_retval(cached_data)
        unique_hours: Iterable[datetime] = cached_data.index.get_level_values(JaoData.time).unique().to_pydatetime()
        subset_time = [loop_time for loop_time in time_range if loop_time not in unique_hours]

        return cached_data, subset_time


def formatting_cache_to_retval(cached_data: pd.DataFrame) -> pd.DataFrame:
    try:
        cached_data[JaoData.time] = cached_data[JaoData.time].astype(pd.DatetimeTZDtype("ns", "UTC"))
    except AmbiguousTimeError:
        cached_data = correct_for_dst(cached_data)
    cached_data[JaoData.cnec_id] = cached_data[JaoData.cnec_id].astype(pd.StringDtype())
    cached_data[JaoData.dateTimeUtc] = cached_data[JaoData.dateTimeUtc].astype(pd.DatetimeTZDtype("ns", "UTC"))
    cached_data[JaoData.contingencies] = cached_data[JaoData.contingencies].astype(pd.StringDtype())
    cached_data = cached_data.set_index([JaoData.cnec_id, JaoData.time])
    cached_data = cached_data.sort_index(level=JaoData.time)
    return cached_data


def correct_for_dst(frame: pd.DataFrame):
    new_time_for_cnec: dict[Hashable, pd.Series] = {}
    for cnec_id, subframe in frame.groupby(JaoData.cnec_id):
        new_time_for_cnec[cnec_id] = subframe[JaoData.time].astype(pd.DatetimeTZDtype("ns", "UTC"))

    for cnec_id, data in new_time_for_cnec.items():
        frame.loc[frame[JaoData.cnec_id] == cnec_id, JaoData.time] = data

    frame[JaoData.time] = frame[JaoData.time].astype(pd.DatetimeTZDtype("ns", "UTC"))
    return frame


def fetch_jao_dataframe_timeseries(from_time: timedata, to_time: timedata) -> DataFrame[JaoData] | None:
    """Reads JAO data from the API and returns the corresponding frame.
    Pulls data from cache in the `write_path`

    Args:
        from_time (timedata): from when to pull data
        to_time (timedata): to when to pull data
        write_path (Path | None, optional): Path to use for data caching. Defaults to None,
            and uses `~/.linearisation_error`.

    Raises:
        FileError: If `write_path` does not exist

    Returns:
        DataFrame[JaoData] | None: pandas Dataframe with JAO date,
            returns `None` if no data is found in API or cache
    """
    logger = logging.getLogger()

    from_time_pd = convert_date_to_utc_pandas(from_time)
    to_time_pd = convert_date_to_utc_pandas(to_time)

    all_results = None
    cached_results, timestamps_not_in_cache = try_jao_cache_before_async(from_time_pd, to_time_pd)

    if len(timestamps_not_in_cache) > 0:
        logger.info(f"JAO: Hit cache - but need extra data from {len(timestamps_not_in_cache)}")
        try:
            all_results = asyncio.run(_fetch_jao_dataframe_timeseries(timestamps_not_in_cache))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            all_results = asyncio.run_coroutine_threadsafe(
                _fetch_jao_dataframe_timeseries(timestamps_not_in_cache), loop
            ).result()
    elif cached_results is not None:
        logger.info("JAO: Full Cache Hit")
        return cached_results

    if cached_results is not None and all_results is not None:
        return_frame = pd.concat([cached_results, all_results]).sort_index()
        return return_frame  # type: ignore
    elif all_results is not None:
        return all_results.sort_index()  # type: ignore


"""
'id': id of entry in JAO database

'dateTimeUtc': UTC timestamp

'tso': Sending TSO (if any)

'cnecName': name of CNEC

'cnecType': type of CNEC (BRANCH, ALLOCATION_CONSTRAINT)

'cneName': name of CNE

'cneType': type of CNE  (CNE, PTC, [blank for Allocation constraints])

'cneStatus': CNE status (OK, OUT)

'cneEic': EIC of CNE (if any)

'direction': N/A

'hubFrom': sending end bidding zone

'hubTo': receiving end bidding zone

'substationFrom': sending end substation

'substationTo': receiving end substation

'elementType': N/A

'fmaxType': N/A

'contTso': N/A

'contName': name of contingency

'contStatus': status of contingency (N or N-k)

'contSubstationFrom': contingency element sending end substation

'contSubstationTo': contingency element receiving end substation

'imaxMethod': PATL – permanent limit or TATL – temporary limit

'contingencies': N/A

'number': N/A

'branchName': N/A

'branchEic': N/A

'hubFrom': N/A

'hubTo': N/A

'substationFrom': N/A

'substationTo': N/A

'elementType': N/A

'presolved': if true: CNEC is limiting the domain (i.e. non-redundant constraint),
    if false: CNEC is not limiting the domain (i.e. redundant constraint)

'significant': True

'ram': remaining available margin of CNEC

'imax': current limit provided for CNEC

'u': voltage, at which Fmax was calculated

'fmax': Highest permissible flow of active power on CNEC

'frm': Flow reliability margin

'frefInit': N/A

'fnrao': Remedial action contribution to RAM

'fref': flow on CNEC at base case net position

'fcore': N/A

'fall': F0 – flow on CNEC in case of zero net positions in all bidding zones

'fuaf': N/A

'amr': Adjustment for negative RAM (zero if RAM is positive)

'aac': Already allocated capacity

'ltaMargin': N/A

'cva': N/A

'iva': individual value adjustment

'ftotalLtn': N/A

'fltn': N/A

'ptdf_DK1': zone-slack PTDF towards DK1

'ptdf_DK1_CO': zone-slack PTDF towards DK1_CO

'ptdf_DK1_DE': zone-slack PTDF towards DK1_DE

'ptdf_DK1_KS': zone-slack PTDF towards DK1_KS

'ptdf_DK1_SK': zone-slack PTDF towards DK1_SK

'ptdf_DK1_ST': zone-slack PTDF towards DK1_ST

'ptdf_DK2': zone-slack PTDF towards DK2

'ptdf_DK2_KO': zone-slack PTDF towards DK2_KO

'ptdf_DK2_ST': zone-slack PTDF towards DK2_ST

'ptdf_FI': zone-slack PTDF towards FI

'ptdf_FI_EL': zone-slack PTDF towards FI_EL

'ptdf_FI_FS': zone-slack PTDF towards FI_FS

'ptdf_NO1': zone-slack PTDF towards NO1

'ptdf_NO2': zone-slack PTDF towards NO2

'ptdf_NO2_ND': zone-slack PTDF towards NO2_ND

'ptdf_NO2_SK': zone-slack PTDF towards NO2_SK

'ptdf_NO2_NK': zone-slack PTDF towards NO2_NK

'ptdf_NO3': zone-slack PTDF towards NO3

'ptdf_NO4': zone-slack PTDF towards NO4

'ptdf_NO5': zone-slack PTDF towards NO5

'ptdf_SE1': zone-slack PTDF towards SE1

'ptdf_SE2': zone-slack PTDF towards SE2

'ptdf_SE3': zone-slack PTDF towards SE3

'ptdf_SE3_FS': zone-slack PTDF towards SE3_FS

'ptdf_SE3_KS': zone-slack PTDF towards SE3_KS

'ptdf_SE3_SWL': zone-slack PTDF towards SE3_SWL

'ptdf_SE4': zone-slack PTDF towards SE4

'ptdf_SE4_BC': zone-slack PTDF towards SE4_BC

'ptdf_SE4_NB': zone-slack PTDF towards SE4_NB

'ptdf_SE4_SP': zone-slack PTDF towards SE4_SP

'ptdf_SE4_SWL': zone-slack PTDF towards SE4_SWL
"""
