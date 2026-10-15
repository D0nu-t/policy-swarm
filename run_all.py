#!/usr/bin/env python3
"""Command-line entry point for PolicySwarm. See ``policyswarm/cli.py`` for usage."""

import sys

from policyswarm.cli import main

if __name__ == "__main__":
    sys.exit(main())
