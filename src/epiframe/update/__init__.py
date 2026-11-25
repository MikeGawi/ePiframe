"""One photo update (``epiframe``): the photo index is brought up to date with the
sources, the next photo is picked, fetched, converted and shown.

:mod:`.flow` runs it, :mod:`.sources` syncs the index, :mod:`.fetch` gets the
photo file, :mod:`.pipeline` converts and shows it, :mod:`.commands` holds the
commands working on single files and :mod:`.lock` the PID file of a running update.
"""


class UpdateError(Exception):
    """The update stopped; the message says why (logged without a traceback)."""
