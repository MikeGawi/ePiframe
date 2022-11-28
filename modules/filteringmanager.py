from typing import List
import pandas as pd
import dateutil
from dateutil.parser import parser
from datetime import datetime


class FilteringManager:
    __DATE_MASK = "%Y-%m-%d %H:%M:%S"
    __DATE_MASK_OLD = "%Y.%m.%d %H:%M:%S"

    __SORTING_VALUES = ["none", "asc", "desc"]

    __ERROR_SORTING_VALUE_TEXT = "Configuration sorting should be one of {}"

    @classmethod
    def filter_by_from_date(cls, photos, date: str, header: str):
        start_date_time = datetime.strptime(date, cls.__DATE_MASK)
        time_filter = photos.apply(
            lambda row: dateutil.parser.isoparse(row[header]).replace(tzinfo=None)
            > start_date_time,
            axis=1,
        )
        return photos[time_filter]

    @classmethod
    def filter_by_to_date(cls, photos, date: str, header: str):
        start_date_time = datetime.strptime(date, cls.__DATE_MASK)
        time_filter = photos.apply(
            lambda row: dateutil.parser.isoparse(row[header]).replace(tzinfo=None)
            < start_date_time,
            axis=1,
        )
        return photos[time_filter]

    @classmethod
    def filter_by_number(cls, photos, number: int):
        return_value = photos

        if number > 0:
            return_value = photos.head(number)

        return return_value

    @classmethod
    def sort(cls, photos, header: str, column, type_name: str):
        return_value = photos

        if not type_name == cls.__SORTING_VALUES[0]:
            photos[header] = pd.to_datetime(column)
            if type_name == cls.__SORTING_VALUES[-1]:
                return_value = photos.sort_values(by=header, ascending=False)
            else:
                return_value = photos.sort_values(by=header, ascending=True)

        return return_value

    @classmethod
    def convert(cls, date):
        result = date
        try:
            datetime.strptime(date, cls.__DATE_MASK_OLD)
            result = date.replace(".", "-")
        except Exception:
            pass

        return result

    @classmethod
    def verify(cls, date):
        datetime.strptime(date, cls.__DATE_MASK)

    @classmethod
    def verify_times(cls, dates):
        date1 = dates[0]
        date2 = dates[1]
        if date1 and date2:
            if datetime.strptime(date1, cls.__DATE_MASK) > datetime.strptime(
                date2, cls.__DATE_MASK
            ):
                raise Exception(
                    "Configuration photos_from time is older than photos_to!"
                )

    @classmethod
    def verify_sorting(cls, value: str):
        if value not in [key.lower() for key in cls.__SORTING_VALUES]:
            raise Exception(
                cls.__ERROR_SORTING_VALUE_TEXT.format(
                    [key.lower() for key in cls.__SORTING_VALUES]
                )
            )

    @classmethod
    def get_sorting(cls) -> List[str]:
        return [key.lower() for key in cls.__SORTING_VALUES]

    # legacy
    @classmethod
    def get_descending(cls, value) -> str:
        return cls.__SORTING_VALUES[-1] if bool(int(value)) else cls.__SORTING_VALUES[0]
