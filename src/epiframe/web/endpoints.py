"""The REST API of ePiframe (``/api/...``); the WebUI pages use it too."""

from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any

from flask import Response, current_app, jsonify, send_file
from werkzeug.datastructures import FileStorage

from epiframe.core.media_types import EXTENSION_TO_TYPE, EXTENSIONS
from epiframe.service.frame import Frame
from epiframe.stats.charts import Chart, StatsQuery, chart_data, metric_names
from epiframe.stats.store import MetricsStore
from epiframe.version import VERSION
from epiframe.web.api import DONE, ApiError, Done, api, doc
from epiframe.web.context import context
from epiframe.web.extensions import Route
from epiframe.web.openapi import document
from epiframe.web.status import Status, read_status

BAD_REQUEST = HTTPStatus.BAD_REQUEST
NOT_FOUND = HTTPStatus.NOT_FOUND
OFF_ON = ("0", "1")

# ------------------------------------------------------------------------ photos


@dataclass(frozen=True)
class ImageQuery:
    thumb: bool = field(default=False, metadata=doc("The thumbnail of the photo"))
    original: bool = field(
        default=False, metadata=doc("The original photo instead of the displayed one")
    )


def image_file(frame: Frame, query: ImageQuery) -> Path | None:
    if query.original and not query.thumb:
        return frame.original_file()
    prefix = "thumb_" if query.thumb else ""
    name = "photo_download_name" if query.original else "photo_convert_filename"
    return frame.file(prefix + name)


@api(
    "Photo",
    description="The displayed photo (default) or the original one.",
    query=ImageQuery,
    media_type="image/*",
    errors=(NOT_FOUND,),
)
def get_image(query: ImageQuery) -> Response:
    path = image_file(context().frame, query)
    if path is None:
        raise ApiError("No photo!", NOT_FOUND)
    mimetype = EXTENSION_TO_TYPE.get(path.suffix[1:].lower())
    # Flask would take a relative path from its root path, not from the cwd
    return send_file(path.absolute(), mimetype=mimetype)


@dataclass(frozen=True)
class UploadForm:
    file: FileStorage = field(metadata=doc("The photo"))


def save_upload(frame: Frame, file: FileStorage) -> None:
    """Show the uploaded photo ``file`` now (the timer starts again)."""
    extension = Path(file.filename or "").suffix[1:].lower()
    if extension not in EXTENSIONS:
        raise ApiError(f"Unknown file type {file.filename!r}!")
    file.save(frame.download_file(extension))
    frame.redisplay()


@api(
    "Upload photo",
    description="Converts and displays the photo; the next change is a full"
    " interval later.",
    form=UploadForm,
    response=Done,
    errors=(BAD_REQUEST,),
)
def upload_photo(form: UploadForm) -> Done:
    save_upload(context().frame, form.file)
    return DONE


# ------------------------------------------------------------------------ status


@api("Status", description="Status of the frame and the system.", response=Status)
def get_status() -> Status:
    return read_status(context().frame)


@api(
    "Statistics",
    description="Chart data of the metrics gathered by the service (`show_stats`)."
    " Samples every 10 seconds are kept for a day, averages for 10 minutes for a"
    " week, for hours for a month and for days for a year.",
    query=StatsQuery,
    response=Chart,
    errors=(BAD_REQUEST,),
)
def get_stats(query: StatsQuery) -> Chart:
    try:
        names = metric_names(query.metrics)
    except ValueError as error:
        raise ApiError(str(error)) from None
    frame = context().frame
    series = MetricsStore(frame.stats_file).series(query.period, names)
    return chart_data(series, query.period, frame.metric)


def log_text(frame: Frame) -> str:
    path = Path(frame.config.get("log_files"))
    return path.read_text(errors="replace") if path.is_file() else ""


@api("Log", description="The log of the current day.", media_type="text/plain")
def get_log() -> Response:
    return Response(log_text(context().frame), mimetype="text/plain")


# ----------------------------------------------------------------------- control


@dataclass(frozen=True)
class ActionPath:
    action: str = field(
        metadata=doc(
            "next (photo), restart (the service), reboot, poweroff or an action"
            " of a plugin"
        )
    )


def run_action(name: str) -> None:
    found = context().actions.get(name)
    if found is None:
        raise ApiError(f"Unknown action {name!r}!")
    found.run()


@api(
    "Action",
    description="Runs the action at once, **without confirmation**.",
    path=ActionPath,
    response=Done,
    errors=(BAD_REQUEST,),
)
def action(path: ActionPath) -> Done:
    run_action(path.action)
    return DONE


@dataclass(frozen=True)
class PowerState:
    state: str = field(metadata=doc("1: on, 0: off or unknown"))


@api(
    "Display power state",
    description="Power of an HDMI display.",
    response=PowerState,
)
def display_power_state() -> PowerState:
    return PowerState(OFF_ON[bool(context().frame.hdmi.state())])


@dataclass(frozen=True)
class PowerPath:
    power: bool = field(metadata=doc("on/1/true or off/0/false"))


@api(
    "Display power",
    description="Turns an HDMI display on or off.",
    path=PowerPath,
    response=Done,
    errors=(BAD_REQUEST,),
)
def display_power(path: PowerPath) -> Done:
    context().frame.hdmi.set(path.power)
    return DONE


# ------------------------------------------------------------------ the document


@api("OpenAPI document", description="This document.", media_type="application/json")
def openapi() -> Any:
    return jsonify(document(current_app, VERSION))


ROUTES = (
    Route("/api/get_image", get_image),
    Route("/api/get_status", get_status),
    Route("/api/get_stats", get_stats),
    Route("/api/get_log", get_log),
    Route("/api/upload_photo", upload_photo, ("POST",)),
    Route("/api/action=<action>", action),
    Route("/api/display_power=", display_power_state),
    Route("/api/display_power=<power>", display_power),
    Route("/api/openapi.json", openapi),
)
