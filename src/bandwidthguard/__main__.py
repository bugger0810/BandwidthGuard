"""Allows ``python -m bandwidthguard``."""
import sys

from .app import main

sys.exit(main())
