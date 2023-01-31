from misc.telebotcmd import TelebotCmd


def test_all_commands():
    assert (
        TelebotCmd.ALL
        == "/start-/help-/ping-/echo #-/status-/reboot-/when-/next-/current-/original-/longer #"
    )


def test_desc():
    assert TelebotCmd.DESC == {
        "start": "Show help",
        "help": "Show help",
        "ping": "Ping frame",
        "echo": "Say # text",
        "status": "Show frame status",
        "reboot": "Reboot frame",
        "when": "Show next update time",
        "next": "Trigger frame update",
        "current": "Show current photo",
        "original": "Show current original photo",
        "longer": "Display current photo # times longer",
    }


def test_descriptions():
    assert TelebotCmd.DESCRIPTIONS == "\n".join(
        "_{}_ - {}".format(key, value) for key, value in TelebotCmd.DESC.items()
    )
