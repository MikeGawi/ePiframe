#!/usr/bin/env python3
"""The ePiframe service, see ``epiframe.service.daemon`` (``--help``)."""

import sys

from epiframe.service.daemon import main

if __name__ == "__main__":
    sys.exit(main())
