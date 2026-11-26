#!/usr/bin/env python3
"""The ePiframe service: ``epiframe service`` (``epiframe.cli``), see ``--help``."""

import sys

from epiframe.cli import main

if __name__ == "__main__":
    sys.exit(main(["service", *sys.argv[1:]]))
