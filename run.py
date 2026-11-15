"""Start BandwidthGuard from the source tree:  python run.py

This tiny launcher is also the entry point that PyInstaller bundles into the .exe.
"""
import os
import sys

# Make the "src" folder importable when running directly from a git checkout.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from bandwidthguard.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
