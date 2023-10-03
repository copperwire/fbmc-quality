import asyncio
import hashlib
import logging
import uuid
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import gettempdir
from typing import TypeVar

import aiohttp
import pandas as pd
import psutil
from click import FileError
from joblib import Parallel, delayed
from pandera.typing import DataFrame

from fbmc_quality.dataframe_schemas.schemas import JaoData

warnings.filterwarnings(
    "ignore",
    message=".*Unverified",
)

timedata = TypeVar("timedata", date, datetime)


def create_uuid_from_string(val: str) -> str:
    hex_string = hashlib.md5(val.encode("UTF-8"), usedforsecurity=False).hexdigest()
    return str(uuid.UUID(hex=hex_string))


async def get_ptdfs(date: timedata, session: aiohttp.ClientSession) -> dict[str, object]:
    """get PTDFs from JAO, query by datetime

    Args:
        date (datetime): date to query the JAO by

    Returns:
        Dict[str, object]: HTTP payload from the API request
    """
    session.verify = False
    date_str = date.strftime("%Y-%m-%dT%H")

    url = f"https://test-publicationtool.jao.eu/nordic/api/nordic/finalComputation/index?date={date_str}%3A00%3A00.000Z&search=&skip=0"  # noqa

    async with session.get(url=url) as response:
        return await response.json()


async def _fetch_jao_dataframe_from_datetime(
    date: timedata, write_path: None | Path = None, session: aiohttp.ClientSession | None = None
) -> DataFrame[JaoData]:
    """Fetches a dataframe representation of JAO data"""

    if session is None:
        async with aiohttp.ClientSession() as new_session:
            data_from_jao = await get_ptdfs(date, new_session)
    else:
        data_from_jao = await get_ptdfs(date, session)

    file_path = (
        write_path / f'jao_{date.strftime("%Y%m%dT%H")}.arrow'
        if write_path is not None
        else Path(gettempdir()) / f'jao_{date.strftime("%Y%m%dT%H")}.arrow'
    )
    if file_path.exists():
        return pd.read_feather(file_path)  # type: ignore

    df = pd.DataFrame(data_from_jao["data"])  # type: ignore
    df = df.loc[df[JaoData.cnecName].notnull(), :]
    df[JaoData.cnec_id] = df.apply(
        lambda row: create_uuid_from_string(row[JaoData.cnecName] + row[JaoData.contName]), axis=1
    )
    df[JaoData.time] = pd.to_datetime(df[JaoData.dateTimeUtc])
    col = df.columns.to_list()

    for i, col_name in enumerate(col):
        col[i] = col_name.replace("ptdf_", "")
    df.columns = col
    df = df.set_index([JaoData.cnec_id, JaoData.time])
    df_validated: DataFrame[JaoData] = JaoData.validate(df)  # type: ignore

    df_validated.to_feather(file_path)
    return df_validated


async def _fetch_jao_dataframe_timeseries(
    from_time: timedata, to_time: timedata, write_path: Path | None = None
) -> DataFrame[JaoData] | None:
    logging.getLogger().info(f"Fetching JAO data from {from_time} to {to_time}")
    if isinstance(from_time, date):
        dt_from_time = datetime(from_time.year, from_time.month, from_time.day)
    else:
        dt_from_time = from_time

    if isinstance(to_time, date):
        dt_to_time = datetime(to_time.year, to_time.month, to_time.day)
    else:
        dt_to_time = to_time

    current_time = dt_from_time
    all_results: list[DataFrame[JaoData]] = []

    async with aiohttp.ClientSession() as session:
        while current_time < dt_to_time:
            results = await _fetch_jao_dataframe_from_datetime(current_time, write_path, session)
            all_results.append(results)
            current_time += timedelta(hours=1)

    if all_results:
        return_frame = pd.concat(all_results)
        return return_frame  # type: ignore
    else:
        return None


def create_default_folder(default_folder_path: Path):
    try:
        default_folder_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise FileError(f"Error creating default folder: {e}") from e


def try_jao_cache_before_async(
    from_time: timedata, to_time: timedata, write_path: Path
) -> tuple[DataFrame[JaoData] | None, datetime]:
    if isinstance(from_time, date):
        dt_from_time = datetime(from_time.year, from_time.month, from_time.day)
    else:
        dt_from_time = from_time

    if isinstance(to_time, date):
        dt_to_time = datetime(to_time.year, to_time.month, to_time.day)
    else:
        dt_to_time = to_time

    current_time: datetime = dt_from_time
    all_paths = []

    while current_time < dt_to_time:
        file_path = write_path / f'jao_{current_time.strftime("%Y%m%dT%H")}.arrow'
        if file_path.exists():
            all_paths.append(file_path)
        else:
            break

        current_time += timedelta(hours=1)

    if all_paths:
        cores = psutil.cpu_count()
        context = Parallel(cores, backend="loky")
        return pd.concat(context(delayed(pd.read_feather)(path) for path in all_paths)), current_time  # type: ignore
    else:
        return None, current_time  # type: ignore


def fetch_jao_dataframe_timeseries(
    from_time: timedata, to_time: timedata, write_path: Path | None = None
) -> DataFrame[JaoData] | None:
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
    if write_path is None:
        default_folder_path = Path.home() / Path(".flowbased_data/jao")
        create_default_folder(default_folder_path)
        write_path = default_folder_path
    elif not write_path.exists():
        raise FileError(f"No directory at {write_path}")

    all_results = None
    cached_results, new_start = try_jao_cache_before_async(from_time, to_time, write_path)

    if isinstance(to_time, date):
        dt_to_time = datetime(to_time.year, to_time.month, to_time.day)

    if new_start != dt_to_time:
        try:
            all_results = asyncio.run(_fetch_jao_dataframe_timeseries(new_start, dt_to_time, write_path))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            all_results = asyncio.run_coroutine_threadsafe(
                _fetch_jao_dataframe_timeseries(new_start, dt_to_time, write_path), loop
            ).result()
    elif cached_results is not None:
        return cached_results

    if cached_results is not None and all_results is not None:
        return_frame = pd.concat([cached_results, all_results]).sort_index()
        return return_frame  # type: ignore


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
