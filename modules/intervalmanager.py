import os


class IntervalManager:

    __path = None

    def __init__(self, path: str):
        self.__path = path

    def read(self) -> int:
        interval = -1

        if os.path.exists(self.__path):
            with open(self.__path, "r") as file_lines:
                lines = file_lines.readlines()
                interval = str(lines[0]).rstrip()
                file_lines.close()
        return int(interval)

    def save(self, interval: int):
        if interval <= 1:
            self.remove()
        else:
            with open(self.__path, "w") as file_data:
                file_data.write(str(interval))
                file_data.close()

    def remove(self):
        if os.path.exists(self.__path):
            os.remove(self.__path)

    def save_interval(self, interval: str, hot_word: str, max_value: int):
        if hot_word.lower() in interval.lower():
            interval_value = interval.lower().replace(hot_word.lower(), "").strip()
            try:
                self.save(max_value) if int(interval_value) > max_value else self.save(
                    int(interval_value)
                )
            except Exception:
                pass
