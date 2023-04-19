class MockedBackendManager:

    pid = True
    metric = True
    interval = 5
    max_interval = 5
    cmd = None
    interval_mult_enabled = True

    def refresh(self):
        print("refresh")

    def get_token(self):
        print("get_token")
        return "token"

    def get_chat_id(self):
        print("get_chat_id")
        return "1,2,3"

    def update_time(self):
        print("update_time")

    def get_current_file(self):
        print("get_current_file")
        return "tests/assets/waveshare.bmp"

    @classmethod
    def set_pid(cls, response: bool):
        cls.pid = response

    def pid_file_exists(self):
        print("pid_file_exists")
        return self.pid

    def get_original_file(self):
        print("get_original_file")
        return "tests/assets/waveshare.bmp"

    def fire_event(self):
        print("fire_event")

    def get_next_time(self):
        print("get_next_time")
        return "next_time"

    @classmethod
    def set_metric(cls, response: bool):
        cls.metric = response

    def is_metric(self):
        print("is_metric")
        return self.metric

    @classmethod
    def set_cmd(cls, response):
        cls.cmd = response

    def start_system_command(self, cmd):
        print("start_system_command")
        print(cmd)
        return self.cmd

    def reboot(self):
        print("reboot")

    def get_download_file(self):
        print("get_download_file")
        return "test_upload_file"

    def download_file(self, path):
        print(f"download_file {path}")
        return path

    def refresh_frame(self):
        print("refresh_frame")

    def save_interval(self, interval):
        print("save_interval")
        print(interval)

    @classmethod
    def set_interval(cls, response: int):
        cls.interval = response

    def get_interval(self):
        print("get_interval")
        return self.interval

    @classmethod
    def set_max_interval(cls, response: int):
        cls.max_interval = response

    def get_max_interval(self):
        print("get_max_interval")
        return self.max_interval

    @classmethod
    def set_interval_mult_enabled(cls, response: bool):
        cls.interval_mult_enabled = response

    def is_interval_mult_enabled(self) -> bool:
        print("is_interval_mult_enabled")
        return self.interval_mult_enabled
