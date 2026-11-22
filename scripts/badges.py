#!/usr/bin/env python3
"""Generate all README badges (SVG) from real tool output.

Usage (CI runs it after the test job, see .github/workflows/ci.yml)::

    uv run pytest --cov --cov-report=xml --junitxml=junit.xml
    uv run python scripts/badges.py --junit junit.xml --coverage coverage.xml

Badges: tests (JUnit XML), coverage (coverage.xml), cc (worst radon rank), ruff, mypy,
python (requires-python), license and version (pyproject.toml).
"""

import argparse
import subprocess
import tomllib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from genbadge import Badge
from genbadge.utils_coverage import get_color as coverage_color
from genbadge.utils_coverage import get_coverage_stats
from genbadge.utils_junit import get_color as tests_color
from genbadge.utils_junit import get_test_stats
from radon.complexity import cc_rank, cc_visit

from epiframe.version import display_version

ROOT = Path(__file__).resolve().parent.parent

# Python code checked for cyclomatic complexity (same scope as the xenon gate).
CC_PATHS = (
    "src",
    "scripts",
    "ePiframe.py",
    "ePiframe_service.py",
    "misc",
    "modules",
    "tools",
)
CC_COLORS = {
    "A": "brightgreen",
    "B": "green",
    "C": "yellowgreen",
    "D": "yellow",
    "E": "orange",
    "F": "red",
}
INFO_COLOR = "blue"

Runner = Callable[[Sequence[str]], int]


@dataclass(frozen=True)
class Project:
    version: str
    requires_python: str
    license: str


def run(command: Sequence[str]) -> int:
    """Run a command in the repository root and return its exit code."""
    # commands are fixed lists defined in this script, never user input
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)  # noqa: S603
    return result.returncode


def read_project(pyproject: Path) -> Project:
    data = tomllib.loads(pyproject.read_text())["project"]
    return Project(
        version=data["version"],
        requires_python=data["requires-python"],
        license=data["license"],
    )


def python_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        files.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return files


def worst_cc_rank(files: Iterable[Path]) -> str:
    """Return the worst radon rank (A-F) of all functions, methods and classes."""
    complexities = [
        block.complexity for file in files for block in cc_visit(file.read_text())
    ]
    return str(cc_rank(max(complexities, default=1)))


def status_badge(name: str, command: Sequence[str], runner: Runner) -> Badge:
    passed = runner(command) == 0
    return Badge(
        left_txt=name,
        right_txt="passing" if passed else "failing",
        color="brightgreen" if passed else "red",
    )


def tests_badge(junit_xml: Path) -> Badge:
    stats = get_test_stats(str(junit_xml))
    return Badge(
        left_txt="tests",
        right_txt=f"{stats.success}/{stats.total_with_skipped}",
        color=tests_color(stats),
    )


def coverage_badge(coverage_xml: Path) -> Badge:
    stats = get_coverage_stats(str(coverage_xml))
    return Badge(
        left_txt="coverage",
        right_txt=f"{stats.total_coverage:.0f}%",
        color=coverage_color(stats),
    )


def cc_badge(files: Iterable[Path]) -> Badge:
    rank = worst_cc_rank(files)
    return Badge(left_txt="cc", right_txt=rank, color=CC_COLORS[rank])


def project_badges(project: Project) -> dict[str, Badge]:
    python = project.requires_python.removeprefix(">=")
    return {
        "version": Badge("version", display_version(project.version), INFO_COLOR),
        "python": Badge("python", f"{python}+", INFO_COLOR),
        "license": Badge("license", project.license, INFO_COLOR),
    }


def build_badges(args: argparse.Namespace, runner: Runner) -> dict[str, Badge]:
    badges = project_badges(read_project(ROOT / "pyproject.toml"))
    badges["tests"] = tests_badge(args.junit)
    badges["coverage"] = coverage_badge(args.coverage)
    badges["cc"] = cc_badge(python_files(ROOT / path for path in CC_PATHS))
    badges["ruff"] = status_badge("ruff", ["ruff", "check", "."], runner)
    badges["mypy"] = status_badge("mypy", ["mypy"], runner)
    return badges


def write_badges(badges: dict[str, Badge], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, badge in badges.items():
        badge.write_to(str(out / f"{name}.svg"), use_shields=False)
        print(f"{name}: {badge.right_txt}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--junit", type=Path, default=Path("junit.xml"))
    parser.add_argument("--coverage", type=Path, default=Path("coverage.xml"))
    parser.add_argument("--out", type=Path, default=Path("badges"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, runner: Runner = run) -> None:
    args = parse_args(argv)
    write_badges(build_badges(args, runner), args.out)


if __name__ == "__main__":  # pragma: no cover
    main()
