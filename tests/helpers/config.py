class Config:
    settings = {
        "interval_mult_file": "time.test",
        "start_times": "5:30,5:30,5:30,5:30,5:30,5:30,5:30",
        "stop_times": "23:30,23:30,23:30,23:30,23:30,23:30,23:30",
        "log_files": "log.test",
        "pid_file": "pid.test",
        "display_type": "SPI",
        "control_display_power": "1",
        "photo_convert_path": "tests/assets/",
        "photo_convert_filename": "waveshare.bmp",
        "photo_download_name": "waveshare",
        "chat_id": "chats",
        "allow_triggers": "1",
        "interval_mult": "1",
        "interval_max_mult": "6",
        "units": "metric",
        "token": "token",
        "slide_interval": "600",
        "use_telebot": "1",
        "use_web": "1",
        "web_host": "0.0.0.0",
        "web_port": "80",
        "show_stats": "1",
        "dark_theme": "1",
    }

    def __init__(self, arg1, arg2):
        pass

    def get(self, name: str) -> str:
        return self.settings.get(name)

    def getint(self, name: str) -> int:
        return int(self.settings.get(name))

    @classmethod
    def set(cls, name: str, value: str):
        cls.settings[name] = value
