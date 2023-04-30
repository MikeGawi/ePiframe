import os
from unittest.mock import patch
from modules.statsmanager import StatsManager
from tests.helpers.capturing import Capturing


def test_init():
    with patch.object(os, "system", mocked_system):
        with Capturing() as output:
            StatsManager(backend=MockBackend())

    assert output == [
        "rrdtool_bin_path create PATH/static/data/load.rrd "
        "--step 10 DS:load1:GAUGE:600:U:U DS:load5:GAUGE:600:U:U "
        "DS:load15:GAUGE:600:U:U RRA:AVERAGE:0.5:1:8640 RRA:AVERAGE:0.5:6:2880 "
        "RRA:AVERAGE:0.5:60:2016 RRA:AVERAGE:0.5:180:1488 RRA:AVERAGE:0.5:360:8784",
        "rrdtool_bin_path create PATH/static/data/mem.rrd --step 10 DS:total:GAUGE:600:U:U "
        "DS:used:GAUGE:600:U:U DS:free:GAUGE:600:U:U DS:available:GAUGE:600:U:U "
        "RRA:AVERAGE:0.5:1:8640 RRA:AVERAGE:0.5:6:2880 RRA:AVERAGE:0.5:60:2016 "
        "RRA:AVERAGE:0.5:180:1488 RRA:AVERAGE:0.5:360:8784",
        "rrdtool_bin_path create PATH/static/data/temp.rrd --step 10 "
        "DS:temp:GAUGE:600:U:U RRA:AVERAGE:0.5:1:8640 RRA:AVERAGE:0.5:6:2880 "
        "RRA:AVERAGE:0.5:60:2016 RRA:AVERAGE:0.5:180:1488 RRA:AVERAGE:0.5:360:8784",
    ]


def test_feed():
    with patch.object(os, "popen", mocked_system), patch.object(
        os, "system", mocked_system
    ), patch.object(os.path, "exists", mocked_exists):
        stats_manager = StatsManager(backend=MockBackend())
        with Capturing() as output:
            stats_manager.feed_stats()

    assert output == [
        'awk \'{print $1" " $2" "$3}\' /proc/loadavg 2> /dev/null',
        'rrdtool_bin_path update PATH/static/data/load.rrd N:awk:\'{print:$1":":$2":"$3}\':/proc/loadavg:2>:/dev/null',
        'free -m 2> /dev/null | awk \'FNR==2{print $2" "$3" "$4" "$7}\' 2> /dev/null',
        "rrdtool_bin_path update PATH/static/data/mem.rrd N:free:-m:2>:/dev/null:|:awk:'FNR==2{"
        'print:$2":"$3":"$4":"$7}\':2>:/dev/null',
        "/opt/vc/bin/vcgencmd measure_temp 2> /dev/null | awk -F \"[=']\" '{print $2}' 2> /dev/null",
        "rrdtool_bin_path update PATH/static/data/temp.rrd "
        "N:/opt/vc/bin/vcgencmd:measure_temp:2>:/dev/null:|:awk:-F:\"[=']\":'{print:$2}':2>:/dev/null",
    ]


def mocked_system(*args, **kwargs):
    print("".join(args) + "".join(kwargs))
    return MockRead("".join(args) + "".join(kwargs))


def mocked_exists(*args, **kwargs):
    return True


class MockRead:
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text


class MockConfig:
    @staticmethod
    def get(text):
        return text


class MockBackend:
    @staticmethod
    def get_path():
        return "PATH"

    @staticmethod
    def is_metric():
        return True

    @staticmethod
    def get_config():
        return MockConfig()
