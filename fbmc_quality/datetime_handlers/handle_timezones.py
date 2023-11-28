from datetime import date, datetime
from typing import Literal

import pandas as pd
import pytz

from fbmc_quality.exceptions.fbmc_exceptions import NaiveTimestampException


def get_utc_delta(input_date: date | datetime) -> Literal[1, 2]:
    ref_datetime = datetime(input_date.year, input_date.month, input_date.day)
    delta = (
        pytz.timezone("Europe/Oslo").fromutc(ref_datetime) - ref_datetime.astimezone(pytz.timezone("Europe/Oslo"))
    ).total_seconds()
    hours = int(delta / (60 * 60))
    if hours not in (1, 2):
        raise ValueError(f"Unexpected delta {hours} between Oslo and UTC at {input_date} ")
    return hours


def convert_date_to_utc_pandas(date_obj: pd.Timestamp | datetime) -> pd.Timestamp:
    if hasattr(date_obj, "tzinfo") and date_obj.tzinfo is None:
        raise NaiveTimestampException("tzinfo is None - please supply a tz-aware timestamp")
    elif not hasattr(date_obj, "tzinfo"):
        raise NaiveTimestampException(
            "object does not have a tzinfo attribute. Please use an API that does expose timezones"
        )

    return pd.Timestamp(date_obj).tz_convert("UTC")
