"""GUI package.

The Tk-dependent application is imported lazily so that non-GUI helpers
(e.g. protocol preview logic) remain importable on headless systems
without Tk installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import StudioApp, run

__all__ = ["StudioApp", "run"]


def __getattr__(name: str) -> object:
    if name in __all__:
        from .main import StudioApp, run

        return {"StudioApp": StudioApp, "run": run}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
