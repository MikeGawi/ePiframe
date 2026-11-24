import pytest

from epiframe.core.console import ask_yes, read_secret
from tests.helpers.console import Console


@pytest.mark.parametrize(
    ("answers", "default", "expected"),
    [
        (["y"], False, True),
        ([" YES "], False, True),
        (["n"], True, False),
        (["no"], True, False),
        ([""], True, True),
        ([""], False, False),
        (["maybe", "y"], False, True),
    ],
)
def test_ask_yes(answers: list[str], default: bool, expected: bool) -> None:
    console = Console(*answers)

    assert ask_yes(console.ask, "Sure?", default) is expected
    assert console.prompts[0] == ("Sure? [Y/n] " if default else "Sure? [y/N] ")
    assert len(console.prompts) == len(answers)


@pytest.mark.parametrize(("terminal", "reader"), [(True, "getpass"), (False, "input")])
def test_read_secret(
    monkeypatch: pytest.MonkeyPatch, terminal: bool, reader: str
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: terminal)
    monkeypatch.setattr("getpass.getpass", lambda _: "getpass")
    monkeypatch.setattr("builtins.input", lambda _: "input")

    assert read_secret("Password: ") == reader
