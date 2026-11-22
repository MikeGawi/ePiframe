from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import badges

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="0" failures="1" skipped="0" tests="3">
<testcase classname="t" name="a"/><testcase classname="t" name="b"/>
<testcase classname="t" name="c"><failure message="boom">boom</failure></testcase>
</testsuite></testsuites>
"""
COVERAGE = """<?xml version="1.0" ?>
<coverage version="7.6" line-rate="1" branch-rate="1"
 lines-covered="10" lines-valid="10" branches-covered="4" branches-valid="4"
 complexity="0"><packages/></coverage>
"""
SIMPLE = "def f(x):\n    return x\n"
COMPLEX = "def g(x):\n" + "".join(
    f"    if x == {i}:\n        return {i}\n" for i in range(12)
)


def passing(command: Sequence[str]) -> int:
    return 0


def failing(command: Sequence[str]) -> int:
    return 1


@pytest.fixture
def reports(tmp_path: Path) -> tuple[Path, Path]:
    junit, coverage = tmp_path / "junit.xml", tmp_path / "coverage.xml"
    junit.write_text(JUNIT)
    coverage.write_text(COVERAGE)
    return junit, coverage


def test_read_project() -> None:
    project = badges.read_project(badges.ROOT / "pyproject.toml")
    assert project.requires_python == ">=3.11"
    assert project.license == "GPL-3.0-only"
    assert project.version


def test_project_badges() -> None:
    result = badges.project_badges(badges.Project("2.0.0a1", ">=3.11", "GPL-3.0-only"))
    assert {name: badge.right_txt for name, badge in result.items()} == {
        "version": "v2.0.0-alpha.1",
        "python": "3.11+",
        "license": "GPL-3.0-only",
    }


def test_python_files(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "b.py").write_text(SIMPLE)
    (tmp_path / "pkg" / "a.py").write_text(SIMPLE)
    (tmp_path / "pkg" / "data.txt").write_text("")
    (tmp_path / "main.py").write_text(SIMPLE)
    files = badges.python_files([tmp_path / "pkg", tmp_path / "main.py"])
    assert files == [
        tmp_path / "pkg" / "a.py",
        tmp_path / "pkg" / "b.py",
        tmp_path / "main.py",
    ]


@pytest.mark.parametrize(
    ("sources", "rank", "color"),
    [
        ([], "A", "brightgreen"),
        ([SIMPLE], "A", "brightgreen"),
        ([SIMPLE, COMPLEX], "C", "yellowgreen"),
    ],
)
def test_cc_badge(tmp_path: Path, sources: list[str], rank: str, color: str) -> None:
    files = []
    for number, source in enumerate(sources):
        file = tmp_path / f"m{number}.py"
        file.write_text(source)
        files.append(file)
    badge = badges.cc_badge(files)
    assert (badge.right_txt, badge.color) == (rank, color)


@pytest.mark.parametrize(
    ("runner", "text", "color"),
    [(passing, "passing", "brightgreen"), (failing, "failing", "red")],
)
def test_status_badge(runner: badges.Runner, text: str, color: str) -> None:
    badge = badges.status_badge("ruff", ["ruff"], runner)
    assert (badge.left_txt, badge.right_txt, badge.color) == ("ruff", text, color)


def test_tests_and_coverage_badges(reports: tuple[Path, Path]) -> None:
    junit, coverage = reports
    assert badges.tests_badge(junit).right_txt == "2/3"
    assert badges.coverage_badge(coverage).right_txt == "100%"


def test_main_writes_all_badges(
    tmp_path: Path, reports: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    junit, coverage = reports
    out = tmp_path / "out"
    badges.main(
        ["--junit", str(junit), "--coverage", str(coverage), "--out", str(out)], passing
    )

    expected = {
        "version",
        "python",
        "license",
        "tests",
        "coverage",
        "cc",
        "ruff",
        "mypy",
    }
    assert {file.stem for file in out.glob("*.svg")} == expected
    assert "tests: 2/3" in capsys.readouterr().out


def test_parse_args_defaults() -> None:
    args = badges.parse_args([])
    assert (args.junit, args.coverage, args.out) == (
        Path("junit.xml"),
        Path("coverage.xml"),
        Path("badges"),
    )


def test_run() -> None:
    assert badges.run(["true"]) == 0
    assert badges.run(["false"]) == 1
