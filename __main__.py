"""Allows `python "Nifty Pricing Mirror"` from the parent directory.

For the typical use case run `python -m nifty_pricing_mirror.cli` from inside
this directory instead.
"""

from nifty_pricing_mirror.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
