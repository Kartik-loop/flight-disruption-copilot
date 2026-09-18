"""
Flight Disruption Copilot — top-level package.

This is the root of the copilot package. It exists to make Python treat
the `copilot/` directory as a package, so we can do imports like:

    from copilot.schemas.flight import FlightDisruption
    from copilot.rules.eu261 import evaluate_eu261

LEARN: In Python, a directory needs an __init__.py file (even an empty one)
to be importable as a package. We keep this file minimal — just a version
string — and put real logic in sub-modules.
"""

__version__ = "0.1.0"
