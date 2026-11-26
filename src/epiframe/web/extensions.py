"""What the WebUI can be extended with (by ePiframe itself and by plugins).

Plain data, no Flask: the plugin base class refers to these types.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Route:
    """A REST API endpoint: ``rule`` under ``/api/`` served by ``view``.

    The view must be declared with :func:`epiframe.web.api.api` (login,
    validation and the OpenAPI document come from it); others are refused.
    """

    rule: str  # Flask rule, e.g. "/api/get_text/<text>"
    view: Callable[..., Any]
    methods: Sequence[str] = ("GET",)


@dataclass(frozen=True)
class Action:
    """A WebUI tool button, also run by ``/api/action=<id>``."""

    id: str
    label: str
    run: Callable[[], object]
    icon: str  # Bootstrap icon classes, e.g. "bi bi-lightbulb"
    button: bool = True  # shown on the Tools page


@dataclass(frozen=True)
class MenuEntry:
    """A WebUI menu entry."""

    name: str
    url: str
    id: str
    icon: str
