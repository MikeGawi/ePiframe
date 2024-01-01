import os
import requests
import re


class Connection:
    @staticmethod
    def check_internet(url: str, timeout: int) -> str:
        return_value = None

        try:
            requests.get(url, timeout=timeout)
        except requests.ConnectionError as exception:
            return_value = str(exception)

        return return_value

    @staticmethod
    def download_file(
        url: str, destination_folder: str, file_name: str, code: int, timeout: int
    ) -> int:
        session = requests.Session()
        response = session.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        if response.status_code == code:
            filename = os.path.join(destination_folder, file_name)

            with open(filename, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
                file.close()

        return response.status_code

    @staticmethod
    def is_ip(ip: str):
        if not re.match(
            r"^((\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.){3}(\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])$",
            ip,
        ):
            raise Exception("Not a valid IP address!")
