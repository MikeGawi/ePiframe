import datetime
from itertools import cycle, islice
from typing import List


class TimerManager:

    __DATE_MASK = "%H:%M"
    __NO_TIME_MARK = "-"
    __DELIMITER = ","

    def __init__(self, start_times: List[str], end_times: List[str]):
        self.__start_times = start_times
        self.__end_times = end_times

    def should_i_work_now(self) -> bool:
        now = datetime.datetime.now()

        day_of_week = now.weekday()
        yesterday = (datetime.datetime.now() - datetime.timedelta(1)).weekday() - 1
        start_tab = self.__start_times[day_of_week].strip()
        end_tab = self.__end_times[day_of_week].strip()

        return self.__get_value(day_of_week, end_tab, now, start_tab, yesterday)

    def __get_value(
        self,
        day_of_week: int,
        end_tab: str,
        now: datetime,
        start_tab: str,
        yesterday: int,
    ) -> bool:
        for execute in [
            self.__check_no_time_mark,
            self.__check_yesterday,
            self.__check_day_of_week,
            self.__check_now,
        ]:
            value = execute.__call__(now, start_tab, end_tab, day_of_week, yesterday)
            if value is not None:
                break

        return value or False

    def __check_no_time_mark(
        self,
        now: datetime,
        start_tab: str,
        end_tab: str,
        day_of_week: int,
        yesterday: int,
    ) -> bool:
        return False if start_tab == self.__NO_TIME_MARK else None

    def __check_yesterday(
        self,
        now: datetime,
        start_tab: str,
        end_tab: str,
        day_of_week: int,
        yesterday: int,
    ) -> bool:
        return (
            True
            if (
                now.time() < self.get_time_from_string(start_tab).time()
                and self.__end_times[yesterday].strip() == self.__NO_TIME_MARK
            )
            else None
        )

    def __check_day_of_week(
        self,
        now: datetime,
        start_tab: str,
        end_tab: str,
        day_of_week: int,
        yesterday: int,
    ) -> bool:
        return (
            (
                self.get_time_from_string(start_tab).time()
                < now.time()
                < self.get_time_from_string(end_tab).time()
            )
            if (
                now.time() > self.get_time_from_string(start_tab).time()
                and not self.__end_times[day_of_week].strip() == self.__NO_TIME_MARK
            )
            else None
        )

    def __check_now(
        self,
        now: datetime,
        start_tab: str,
        end_tab: str,
        day_of_week: int,
        yesterday: int,
    ) -> bool:
        return (
            True
            if (
                now.time() > self.get_time_from_string(start_tab).time()
                and self.__end_times[day_of_week].strip() == self.__NO_TIME_MARK
            )
            else None
        )

    def when_i_work_next(self) -> datetime:
        now = datetime.datetime.now()
        day_of_week = now.weekday()

        return_value = datetime.datetime.now(
            datetime.datetime.now().astimezone().tzinfo
        )
        now_tab = islice(cycle(self.__start_times), day_of_week, None)

        if (
            self.__end_times[day_of_week].strip() == self.__NO_TIME_MARK
            or now.time()
            > self.get_time_from_string(self.__end_times[day_of_week].strip()).time()
        ):
            return_value += datetime.timedelta(1)

        while True:
            value = next(now_tab)
            if value == self.__NO_TIME_MARK:
                return_value += datetime.timedelta(1)
            else:
                return_value = return_value.replace(
                    hour=self.get_time_from_string(value).hour,
                    minute=self.get_time_from_string(value).minute,
                    second=0,
                )
                break

        return return_value

    @classmethod
    def get_time_from_string(cls, time: str) -> datetime:
        return datetime.datetime.strptime(time, cls.__DATE_MASK)

    @classmethod
    def verify(cls, times: List[str]):
        times1 = times[0].split(cls.__DELIMITER)
        times2 = times[1].split(cls.__DELIMITER)

        for index in range(len(times1)):
            cls.__verify_times(index, times1, times2)

    @classmethod
    def __verify_times(cls, index, times1, times2):
        if not times1[index].strip() == cls.__NO_TIME_MARK:
            cls.get_time_from_string(times1[index].strip())
        if not times2[index].strip() == cls.__NO_TIME_MARK:
            cls.get_time_from_string(times2[index].strip())
        cls.__verify_indices(index, times1, times2)

    @classmethod
    def __verify_indices(cls, index, times1, times2):
        if (
            not times2[index].strip() == cls.__NO_TIME_MARK
            and not times1[index].strip() == cls.__NO_TIME_MARK
        ):
            if cls.get_time_from_string(
                times1[index].strip()
            ) > cls.get_time_from_string(times2[index].strip()):
                raise Exception(
                    "Configuration start_times times are older than stop_times!"
                )
