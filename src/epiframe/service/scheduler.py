"""When the service changes the photo.

:class:`PhotoScheduler` runs in its own thread of the service: every slide
interval (times the display time multiplier of the photo) it starts a photo
change within the working hours; out of them it turns the HDMI screen off and
checks again every :data:`IDLE_CHECK` seconds. Photo change requests
(:class:`~epiframe.service.frame.Trigger`) from the WebUI, the bot or the API
come from other threads; they only wake the scheduler, so the photo changes are
always run by its thread, one at a time (1.x ran them in the caller's thread).
A request that comes while a photo change runs waits for it and runs right
after it (1.x stopped the running one; several requests count as one).
"""

import threading
from collections.abc import Callable, Sequence

from epiframe.core.logs import get_logger
from epiframe.service.frame import Frame, Trigger, timestamp_text

INITIAL_DELAY = 10  # seconds after the start until the first photo change
IDLE_CHECK = 60  # seconds between the checks out of the working hours
SLEEP_NOTICE_EVERY = 10  # "Off hours" is logged once every 10 checks

PREFIX = "--------ePiframe Service: "
TRIGGERED = PREFIX + "Activity triggered"
STARTING = PREFIX + "Starting ePiframe script"
SLEEPING = PREFIX + "Off hours - sleeping"
MULTIPLIED = PREFIX + "Interval multiplication for current photo"
NEXT = PREFIX + "Next update scheduled at {}"
NO_NEXT = PREFIX + "No next update scheduled (start_times has no start time)"

log = get_logger("service")

StartRefresh = Callable[[Sequence[str]], object]


class PhotoScheduler:
    """Changes the photo of ``frame`` with ``start_refresh(arguments)``.

    Without ``scheduled`` (the service runs only the WebUI or the bot) only
    the triggers change the photo.
    """

    def __init__(
        self, frame: Frame, start_refresh: StartRefresh, *, scheduled: bool = True
    ) -> None:
        self.frame = frame
        self.start_refresh = start_refresh
        self.scheduled = scheduled
        self._wake = threading.Condition()
        self._trigger: Trigger | None = None
        self._stopped = False
        self._sleep_checks = 0

    # ----------------------------------------------------- from other threads

    def trigger(self, trigger: Trigger) -> None:
        """Change the photo now (the frame's ``on_trigger``)."""
        log.info(TRIGGERED)
        with self._wake:
            self._trigger = trigger
            self._wake.notify()

    def stop(self) -> None:
        with self._wake:
            self._stopped = True
            self._wake.notify()

    # ------------------------------------------------------ scheduler thread

    def run(self) -> None:
        """Wait for the next photo change or a trigger until :meth:`stop`."""
        delay: float | None = INITIAL_DELAY
        while True:
            stopped, trigger = self.wait(delay if self.scheduled else None)
            if stopped:
                return
            delay = self.safe_task(trigger)

    def wait(self, timeout: float | None) -> tuple[bool, Trigger | None]:
        """Wait ``timeout`` seconds (``None``: no limit) for a trigger or the stop."""
        with self._wake:
            self._wake.wait_for(
                lambda: self._stopped or self._trigger is not None, timeout
            )
            trigger, self._trigger = self._trigger, None
            return self._stopped, trigger

    def safe_task(self, trigger: Trigger | None = None) -> float:
        try:
            return self.task(trigger)
        except Exception as error:  # e.g. the configuration got broken
            log.error(f"Error changing the photo: {error}")
            return IDLE_CHECK

    def task(self, trigger: Trigger | None = None) -> float:
        """Change the photo if it is time to; return the seconds until the next
        check."""
        self.frame.refresh()
        changed = True
        if trigger is not None or not self.multiplied():
            changed = self.change(trigger)
        self.frame.schedule_next()
        if not changed:
            return IDLE_CHECK
        when = self.frame.next_update
        log.info(NEXT.format(timestamp_text(when)) if when else NO_NEXT)
        return self.frame.slide_interval

    def multiplied(self) -> bool:
        """Whether the photo stays for one more interval (hot word multiplier)."""
        if not self.frame.interval_enabled:
            return False
        remaining = self.frame.multiplier.read()
        if remaining > 0:
            self.frame.multiplier.save(remaining - 1)
            log.info(MULTIPLIED)
            return True
        self.frame.multiplier.remove()
        return False

    def allowed(self, trigger: Trigger | None) -> bool:
        """Within the working hours; off them only a trigger, if allowed."""
        if self.frame.working():
            return True
        return trigger is not None and self.frame.triggers_enabled

    def change(self, trigger: Trigger | None) -> bool:
        """Start the photo change within the working hours (or for a trigger, if
        allowed off hours); return whether it was started."""
        if self.allowed(trigger):
            self._sleep_checks = 0
            log.info(STARTING)
            self.frame.power_display(True)
            self.start_refresh((trigger or Trigger.NEXT_PHOTO).arguments)
            return True
        self.frame.power_display(False)
        if self._sleep_checks == 0:
            log.info(SLEEPING)
        self._sleep_checks = (self._sleep_checks + 1) % SLEEP_NOTICE_EVERY
        return False
