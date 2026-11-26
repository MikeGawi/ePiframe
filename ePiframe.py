#!/usr/bin/env python3
"""The ``epiframe`` command (``epiframe.cli``), see ``./ePiframe.py --help``."""

import sys

# a clear message for an older system Python (keep in sync with requires-python)
if sys.version_info < (3, 11):  # noqa: UP036
    sys.exit("ePiframe needs Python 3.11 or newer!")

from epiframe.cli import main

if __name__ == "__main__":
    sys.exit(main())
