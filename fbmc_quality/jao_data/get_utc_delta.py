from datetime import date, datetime
from typing import Literal

import pytz


def get_utc_delta(input_date: date | datetime) -> Literal[1, 2]:
    ref_datetime = datetime(input_date.year, input_date.month, input_date.day)
    delta = (
        pytz.timezone("Europe/Oslo").fromutc(ref_datetime) - ref_datetime.astimezone(pytz.timezone("Europe/Oslo"))
    ).total_seconds()
    hours = int(delta / (60 * 60))
    if hours not in (1, 2):
        raise ValueError(f"Unexpected delta {hours} between Oslo and UTC at {input_date} ")
    return hours
