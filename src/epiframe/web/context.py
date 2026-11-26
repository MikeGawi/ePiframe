"""What the views of a WebUI app work with (kept in ``app.extensions``)."""

from dataclasses import dataclass, field
from typing import cast

from flask import Flask, current_app

from epiframe.service.frame import Frame
from epiframe.users.store import Users
from epiframe.web.extensions import Action, MenuEntry

EXTENSION = "epiframe"


@dataclass
class WebContext:
    frame: Frame
    users: Users
    actions: dict[str, Action] = field(default_factory=dict)
    menu: list[MenuEntry] = field(default_factory=list)

    def install(self, app: Flask) -> None:
        app.extensions[EXTENSION] = self


def context() -> WebContext:
    """The context of the app serving the current request."""
    return cast(WebContext, current_app.extensions[EXTENSION])
